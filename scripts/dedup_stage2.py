from __future__ import annotations

import argparse
import concurrent.futures
import glob
import hashlib
import json
import mmap
import shutil
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path
import time

from xopen import xopen

from cs336_data.deduplication import (
    MAX_HASH_VALUE,
    candidate_duplicate_pairs,
    document_word_ngrams,
    find_root,
    hash_line,
    jaccard_similarity,
    normalize_document_for_deduplication,
    union_sets,
)


_SIMILARITY_NORMALIZED_TEXTS: list[str] = []
_SIMILARITY_NGRAMS = 5
_SIMILARITY_THRESHOLD = 0.8
_DUPLICATE_LINE_HASH_INDEX: DuplicateLineHashIndex | None = None
_FUZZY_REMOVED_GLOBAL_DOC_INDICES: set[int] = set()
LINE_HASH_BYTES = 16
SHARD_WRITE_HANDLE_CACHE_SIZE = 64


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Chapter 4 stage-2 dedup pipeline over stage-1 kept-doc "
            "JSONL files while preserving the Chapter 3 dedup semantics: "
            "exact line deduplication followed by MinHash fuzzy deduplication."
        )
    )
    parser.add_argument(
        "--input-glob",
        help=(
            "Glob pattern for stage-1 kept-doc JSONL files. Required unless "
            "--resume-from-exact-docs is used."
        ),
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory where deduped docs, review logs, and summaries will be written.",
    )
    parser.add_argument(
        "--num-hashes",
        type=int,
        default=100,
        help="Number of MinHash functions for stage-2 fuzzy deduplication.",
    )
    parser.add_argument(
        "--num-bands",
        type=int,
        default=10,
        help="Number of LSH bands for stage-2 fuzzy deduplication.",
    )
    parser.add_argument(
        "--ngrams",
        type=int,
        default=5,
        help="Word n-gram size for MinHash deduplication.",
    )
    parser.add_argument(
        "--jaccard-threshold",
        type=float,
        default=0.8,
        help="Jaccard threshold for declaring fuzzy duplicates.",
    )
    parser.add_argument(
        "--review-chars",
        type=int,
        default=500,
        help="Number of characters to keep in stage-2 review previews.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Number of worker processes for parallelizable stage-2 phases.",
    )
    parser.add_argument(
        "--phase3-chunk-docs",
        type=int,
        default=1000,
        help="Number of exact-stage documents per phase-3 preprocessing task.",
    )
    parser.add_argument(
        "--exact-hash-buckets",
        type=int,
        default=256,
        help=(
            "Number of disk buckets for the exact-line duplicate-hash index. "
            "More buckets reduce per-bucket memory during index construction."
        ),
    )
    parser.add_argument(
        "--exact-bucket-workers",
        type=int,
        default=8,
        help="Number of workers used to build duplicate line-hash bucket files.",
    )
    parser.add_argument(
        "--exact-bucket-cache-size",
        type=int,
        default=256,
        help=(
            "Maximum duplicate-hash bucket mmaps kept open per worker while "
            "checking exact-line dedup membership."
        ),
    )
    parser.add_argument(
        "--keep-work",
        action="store_true",
        help="Keep stage-2 temporary work files after they have been consumed.",
    )
    parser.add_argument(
        "--delete-input-after-write",
        action="store_true",
        help=(
            "Delete each input stage-1 kept-doc file after its exact-deduplicated "
            "stage-2 checkpoint has been written. This is intended for disk-constrained "
            "full-pipeline runs."
        ),
    )
    parser.add_argument(
        "--resume-from-exact-docs",
        action="store_true",
        help=(
            "Resume from an existing phase-2 exact-deduplicated checkpoint in "
            "OUTPUT_DIR/_work/exact_docs. This reruns phases 3-6 and is intended "
            "for failures before phase 6 started."
        ),
    )
    return parser.parse_args()


def text_preview(text: str, review_chars: int) -> str:
    compact = " ".join(text.split())
    return compact[:review_chars]


def document_lines(text: str) -> list[str]:
    lines = text.splitlines(keepends=True)
    if not lines and text:
        return [text]
    return lines


def append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with xopen(path, "at") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def chunked_pairs(
    pairs: list[tuple[int, int]],
    chunk_size: int,
) -> list[list[tuple[int, int]]]:
    return [pairs[index : index + chunk_size] for index in range(0, len(pairs), chunk_size)]


def log_progress(message: str) -> None:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[dedup_stage2] {timestamp} {message}", flush=True)


def chunked_paths(paths: list[Path], num_chunks: int) -> list[list[Path]]:
    chunk_size = max(1, (len(paths) + num_chunks - 1) // num_chunks)
    return [paths[index : index + chunk_size] for index in range(0, len(paths), chunk_size)]


def line_hash_bucket_id(line_hash: bytes, num_buckets: int) -> int:
    return int.from_bytes(line_hash[:4], byteorder="big", signed=False) % num_buckets


def duplicate_hash_bucket_path(bucket_dir: Path, bucket_id: int) -> Path:
    return bucket_dir / f"bucket_{bucket_id:04d}.bin"


def sorted_hash_bucket_contains(bucket_mmap: mmap.mmap, line_hash: bytes) -> bool:
    record_count = len(bucket_mmap) // LINE_HASH_BYTES
    left = 0
    right = record_count

    while left < right:
        middle = (left + right) // 2
        start = middle * LINE_HASH_BYTES
        middle_hash = bucket_mmap[start : start + LINE_HASH_BYTES]
        if middle_hash < line_hash:
            left = middle + 1
        else:
            right = middle

    if left >= record_count:
        return False
    start = left * LINE_HASH_BYTES
    return bucket_mmap[start : start + LINE_HASH_BYTES] == line_hash


class DuplicateLineHashIndex:
    def __init__(self, bucket_dir: str, num_buckets: int, cache_size: int) -> None:
        self.bucket_dir = Path(bucket_dir)
        self.num_buckets = num_buckets
        self.cache_size = max(1, cache_size)
        self._cache: OrderedDict[int, tuple[object, mmap.mmap]] = OrderedDict()
        self._missing_buckets: set[int] = set()

    def contains(self, line_hash: bytes) -> bool:
        bucket_id = line_hash_bucket_id(line_hash, self.num_buckets)
        if bucket_id in self._missing_buckets:
            return False

        handle_and_mmap = self._cache.get(bucket_id)
        if handle_and_mmap is None:
            bucket_path = duplicate_hash_bucket_path(self.bucket_dir, bucket_id)
            if not bucket_path.exists() or bucket_path.stat().st_size == 0:
                self._missing_buckets.add(bucket_id)
                return False

            handle = bucket_path.open("rb")
            bucket_mmap = mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ)
            handle_and_mmap = (handle, bucket_mmap)
            self._cache[bucket_id] = handle_and_mmap

            while len(self._cache) > self.cache_size:
                _old_bucket_id, (old_handle, old_mmap) = self._cache.popitem(last=False)
                old_mmap.close()
                old_handle.close()
        else:
            self._cache.move_to_end(bucket_id)

        return sorted_hash_bucket_contains(handle_and_mmap[1], line_hash)


def init_similarity_worker(
    normalized_texts: list[str],
    ngrams: int,
    jaccard_threshold: float,
) -> None:
    global _SIMILARITY_NORMALIZED_TEXTS, _SIMILARITY_NGRAMS, _SIMILARITY_THRESHOLD
    _SIMILARITY_NORMALIZED_TEXTS = normalized_texts
    _SIMILARITY_NGRAMS = ngrams
    _SIMILARITY_THRESHOLD = jaccard_threshold


def init_exact_worker(
    duplicate_line_hash_bucket_dir: str,
    exact_hash_buckets: int,
    exact_bucket_cache_size: int,
    fuzzy_removed_global_doc_indices: set[int] | None = None,
) -> None:
    global _DUPLICATE_LINE_HASH_INDEX, _FUZZY_REMOVED_GLOBAL_DOC_INDICES
    _DUPLICATE_LINE_HASH_INDEX = DuplicateLineHashIndex(
        duplicate_line_hash_bucket_dir,
        exact_hash_buckets,
        exact_bucket_cache_size,
    )
    _FUZZY_REMOVED_GLOBAL_DOC_INDICES = fuzzy_removed_global_doc_indices or set()


def init_fuzzy_write_worker(fuzzy_removed_global_doc_indices: set[int]) -> None:
    global _FUZZY_REMOVED_GLOBAL_DOC_INDICES
    _FUZZY_REMOVED_GLOBAL_DOC_INDICES = fuzzy_removed_global_doc_indices


def similar_pairs_in_chunk(pair_chunk: list[tuple[int, int]]) -> list[tuple[int, int]]:
    ngram_cache: dict[int, set[tuple[str, ...]]] = {}

    def cached_ngrams(index: int) -> set[tuple[str, ...]]:
        if index not in ngram_cache:
            ngram_cache[index] = document_word_ngrams(
                _SIMILARITY_NORMALIZED_TEXTS[index],
                _SIMILARITY_NGRAMS,
            )
        return ngram_cache[index]

    confirmed_pairs: list[tuple[int, int]] = []
    for left, right in pair_chunk:
        similarity = jaccard_similarity(cached_ngrams(left), cached_ngrams(right))
        if similarity >= _SIMILARITY_THRESHOLD:
            confirmed_pairs.append((left, right))
    return confirmed_pairs


def normalized_text_ngram_payloads(normalized_text: str, ngrams: int) -> list[bytes]:
    """Return the exact n-gram payload strings used by Chapter 3 MinHashing."""

    words = normalized_text.split()
    if not words:
        return []

    if len(words) < ngrams:
        return [" ".join(words).encode("utf-8")]

    # Chapter 3 hashes a set of word n-gram tuples. Using a set of joined
    # strings is equivalent here because normalized tokens cannot contain
    # whitespace.
    return [
        ngram_text.encode("utf-8")
        for ngram_text in {
            " ".join(words[index : index + ngrams])
            for index in range(len(words) - ngrams + 1)
        }
    ]


def compute_minhash_signature_from_payloads(
    ngram_payloads: list[bytes],
    seed_prefixes: list[bytes],
) -> tuple[int, ...]:
    """Compute the same signature as Chapter 3 with less repeated string work."""

    if not ngram_payloads:
        return tuple(MAX_HASH_VALUE for _ in seed_prefixes)

    signature: list[int] = []
    for seed_prefix in seed_prefixes:
        min_hash = min(
            int.from_bytes(
                hashlib.blake2b(seed_prefix + ngram_payload, digest_size=8).digest(),
                byteorder="big",
                signed=False,
            )
            for ngram_payload in ngram_payloads
        )
        signature.append(min_hash)
    return tuple(signature)


def write_line_hash_bucket_shard(
    input_paths: list[str],
    shard_id: int,
    shard_root_dir: str,
    exact_hash_buckets: int,
) -> tuple[str, dict[str, dict[str, int]]]:
    shard_dir = Path(shard_root_dir) / f"shard_{shard_id:04d}"
    shard_dir.mkdir(parents=True, exist_ok=True)
    handles: OrderedDict[int, object] = OrderedDict()
    source_counts: dict[str, dict[str, int]] = {}

    def bucket_handle(bucket_id: int) -> object:
        handle = handles.get(bucket_id)
        if handle is None:
            bucket_path = duplicate_hash_bucket_path(shard_dir, bucket_id)
            handle = bucket_path.open("ab")
            handles[bucket_id] = handle
            while len(handles) > SHARD_WRITE_HANDLE_CACHE_SIZE:
                _old_bucket_id, old_handle = handles.popitem(last=False)
                old_handle.close()
        else:
            handles.move_to_end(bucket_id)
        return handle

    try:
        for input_path in input_paths:
            input_path_obj = Path(input_path)
            source_name = input_path_obj.name
            counts = Counter()

            with xopen(input_path_obj, "rt") as handle:
                for line in handle:
                    payload = json.loads(line)
                    counts["docs_seen"] += 1
                    for doc_line in document_lines(payload["text"]):
                        line_hash = hash_line(doc_line)
                        bucket_id = line_hash_bucket_id(line_hash, exact_hash_buckets)
                        bucket_handle(bucket_id).write(line_hash)
                        counts["line_instances_seen"] += 1

            source_counts[source_name] = dict(counts)
    finally:
        for handle in handles.values():
            handle.close()

    return str(shard_dir), source_counts


def build_duplicate_line_hash_bucket(
    bucket_id: int,
    shard_dirs: list[str],
    duplicate_bucket_dir: str,
    delete_shards_after_read: bool,
) -> tuple[int, int, int]:
    line_hash_counts: Counter[bytes] = Counter()
    raw_line_hash_instances = 0

    for shard_dir in shard_dirs:
        shard_bucket_path = duplicate_hash_bucket_path(Path(shard_dir), bucket_id)
        if not shard_bucket_path.exists():
            continue

        with shard_bucket_path.open("rb") as handle:
            while chunk := handle.read(LINE_HASH_BYTES * 65536):
                if len(chunk) % LINE_HASH_BYTES != 0:
                    raise ValueError(f"Corrupt line-hash bucket: {shard_bucket_path}")
                raw_line_hash_instances += len(chunk) // LINE_HASH_BYTES
                line_hash_counts.update(
                    chunk[index : index + LINE_HASH_BYTES]
                    for index in range(0, len(chunk), LINE_HASH_BYTES)
                )

        if delete_shards_after_read:
            shard_bucket_path.unlink()

    duplicate_hashes = sorted(
        line_hash for line_hash, count in line_hash_counts.items() if count > 1
    )
    duplicate_bucket_path = duplicate_hash_bucket_path(Path(duplicate_bucket_dir), bucket_id)
    duplicate_bucket_path.parent.mkdir(parents=True, exist_ok=True)
    if duplicate_hashes:
        with duplicate_bucket_path.open("wb") as handle:
            handle.writelines(duplicate_hashes)

    return bucket_id, raw_line_hash_instances, len(duplicate_hashes)


def duplicate_line_hash_exists(line_hash: bytes) -> bool:
    if _DUPLICATE_LINE_HASH_INDEX is None:
        raise RuntimeError("Duplicate line-hash index has not been initialized.")
    return _DUPLICATE_LINE_HASH_INDEX.contains(line_hash)


def exact_line_dedup_text(text: str) -> tuple[str, int, int, int]:
    original_lines = document_lines(text)
    kept_lines = [
        doc_line
        for doc_line in original_lines
        if not duplicate_line_hash_exists(hash_line(doc_line))
    ]
    exact_text = "".join(kept_lines)
    return exact_text, len(original_lines), len(kept_lines), len(original_lines) - len(kept_lines)


def materialize_exact_stage_for_stage1_file(
    input_path: str,
    exact_doc_dir: str,
    review_log_dir: str,
    review_chars: int,
    delete_input_after_write: bool,
) -> tuple[str, dict[str, int], bool, str]:
    input_path_obj = Path(input_path)
    source_name = input_path_obj.name
    exact_doc_path = Path(exact_doc_dir) / source_name
    review_path = Path(review_log_dir) / source_name
    exact_doc_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.parent.mkdir(parents=True, exist_ok=True)
    counts = Counter()

    with (
        xopen(input_path_obj, "rt") as source,
        xopen(exact_doc_path, "wt") as exact_sink,
        xopen(review_path, "at") as review_sink,
    ):
        for line in source:
            payload = json.loads(line)
            exact_text, original_line_count, exact_line_count, line_instances_removed = (
                exact_line_dedup_text(payload["text"])
            )
            counts["exact_line_instances_removed"] += line_instances_removed

            if not exact_text.strip():
                counts["decision_exact_line_dedup_empty"] += 1
                review_payload = {
                    **payload,
                    "decision": "drop",
                    "drop_reason": "exact_line_dedup_empty",
                    "original_line_count": original_line_count,
                    "exact_line_count": exact_line_count,
                    "exact_line_instances_removed": line_instances_removed,
                    "text_preview": text_preview(payload["text"], review_chars),
                }
                review_sink.write(json.dumps(review_payload, ensure_ascii=False) + "\n")
            else:
                exact_payload = dict(payload)
                exact_payload["text"] = exact_text
                exact_payload["text_preview"] = text_preview(exact_text, review_chars)
                exact_payload["dedup"] = {
                    "exact_line_instances_removed": line_instances_removed,
                    "original_line_count": original_line_count,
                    "exact_line_count": exact_line_count,
                }
                exact_sink.write(json.dumps(exact_payload, ensure_ascii=False) + "\n")
                counts["docs_after_exact_line_dedup"] += 1

    input_deleted = False
    if delete_input_after_write:
        input_path_obj.unlink()
        input_deleted = True

    return source_name, dict(counts), input_deleted, str(exact_doc_path)


def preprocess_exact_stage_file_to_chunks(
    input_path: str,
    preprocessed_chunk_dir: str,
    global_doc_offset: int,
    ngrams: int,
    num_hashes: int,
    chunk_docs: int,
) -> tuple[str, list[str], dict[str, int]]:
    input_path_obj = Path(input_path)
    preprocessed_chunk_dir_obj = Path(preprocessed_chunk_dir)
    source_name = input_path_obj.name
    counts = Counter()
    seed_prefixes = [f"{seed}\x1f".encode("utf-8") for seed in range(num_hashes)]
    chunk_paths: list[str] = []
    chunk_index = 0
    docs_in_chunk = 0
    local_doc_index = 0
    chunk_handle = None

    def open_chunk() -> tuple[Path, object]:
        chunk_path = preprocessed_chunk_dir_obj / f"{source_name}.chunk_{chunk_index:05d}.jsonl.gz"
        return chunk_path, xopen(chunk_path, "wt")

    try:
        with xopen(input_path_obj, "rt") as source:
            current_chunk_path: Path | None = None
            for line in source:
                payload = json.loads(line)

                if chunk_handle is None:
                    current_chunk_path, chunk_handle = open_chunk()

                normalized_text = normalize_document_for_deduplication(payload["text"])
                ngram_payloads = normalized_text_ngram_payloads(normalized_text, ngrams)
                signature = list(
                    compute_minhash_signature_from_payloads(ngram_payloads, seed_prefixes)
                )

                chunk_handle.write(
                    json.dumps(
                        {
                            "global_doc_index": global_doc_offset + local_doc_index,
                            "normalized_text": normalized_text,
                            "signature": signature,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )

                local_doc_index += 1
                docs_in_chunk += 1
                counts["docs_preprocessed"] += 1

                if docs_in_chunk >= chunk_docs:
                    chunk_handle.close()
                    chunk_paths.append(str(current_chunk_path))
                    chunk_index += 1
                    docs_in_chunk = 0
                    chunk_handle = None

            if chunk_handle is not None:
                chunk_handle.close()
                chunk_paths.append(str(current_chunk_path))
    finally:
        if chunk_handle is not None and not chunk_handle.closed:
            chunk_handle.close()

    return source_name, chunk_paths, dict(counts)


def write_final_outputs_for_exact_stage_file(
    input_path: str,
    output_dir: str,
    global_doc_offset: int,
    review_chars: int,
    delete_input_after_write: bool,
) -> tuple[str, dict[str, int], bool]:
    input_path_obj = Path(input_path)
    output_dir_obj = Path(output_dir)
    source_name = input_path_obj.name
    counts = Counter()
    local_doc_index = 0
    deduped_path = output_dir_obj / "deduped_docs" / source_name
    review_path = output_dir_obj / "review_logs" / source_name
    deduped_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.parent.mkdir(parents=True, exist_ok=True)

    with (
        xopen(input_path_obj, "rt") as handle,
        xopen(deduped_path, "at") as deduped_sink,
        xopen(review_path, "at") as review_sink,
    ):
        for line in handle:
            payload = json.loads(line)
            global_doc_index = global_doc_offset + local_doc_index
            local_doc_index += 1

            if global_doc_index in _FUZZY_REMOVED_GLOBAL_DOC_INDICES:
                counts["decision_minhash_duplicate"] += 1
                exact_dedup = payload.get("dedup", {})
                review_payload = {
                    **payload,
                    "decision": "drop",
                    "drop_reason": "minhash_duplicate",
                    "original_line_count": exact_dedup.get("original_line_count"),
                    "exact_line_count": exact_dedup.get("exact_line_count"),
                    "exact_line_instances_removed": exact_dedup.get(
                        "exact_line_instances_removed"
                    ),
                    "text_preview": text_preview(payload["text"], review_chars),
                }
                review_payload.pop("dedup", None)
                review_sink.write(json.dumps(review_payload, ensure_ascii=False) + "\n")
                continue

            kept_payload = dict(payload)
            kept_payload["text_preview"] = text_preview(payload["text"], review_chars)
            kept_payload["dedup"] = dict(payload.get("dedup", {}))
            kept_payload["dedup"]["minhash_survivor"] = True
            deduped_sink.write(json.dumps(kept_payload, ensure_ascii=False) + "\n")
            counts["decision_keep"] += 1

    input_deleted = False
    if delete_input_after_write:
        input_path_obj.unlink()
        input_deleted = True

    return source_name, dict(counts), input_deleted


def source_output_paths(output_dir: Path, source_name: str) -> tuple[Path, Path, Path]:
    summary_name = f"{source_name.removesuffix('.jsonl')}.json"
    return (
        output_dir / "deduped_docs" / source_name,
        output_dir / "review_logs" / source_name,
        output_dir / "summaries" / summary_name,
    )


def write_per_source_summaries(
    *,
    input_paths: list[Path],
    output_dir: Path,
    source_counts: dict[str, Counter],
) -> list[str]:
    summary_paths: list[str] = []
    for input_path in input_paths:
        source_name = input_path.name
        deduped_path, review_path, summary_path = source_output_paths(output_dir, source_name)
        deduped_path.touch(exist_ok=True)
        review_path.touch(exist_ok=True)

        summary = {
            "source_stage1_kept_docs_path": str(input_path),
            "deduped_docs_path": str(deduped_path),
            "review_log_path": str(review_path),
            "counts": dict(source_counts[source_name]),
        }
        summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
        summary_paths.append(str(summary_path))
    return summary_paths


def ensure_output_layout(output_dir: Path) -> dict[str, Path]:
    layout = {
        "deduped_docs": output_dir / "deduped_docs",
        "review_logs": output_dir / "review_logs",
        "summaries": output_dir / "summaries",
        "work": output_dir / "_work",
        "exact_docs": output_dir / "_work" / "exact_docs",
        "line_hash_shards": output_dir / "_work" / "line_hash_shards",
        "duplicate_line_hashes": output_dir / "_work" / "duplicate_line_hashes",
        "preprocessed_chunks": output_dir / "_work" / "preprocessed_chunks",
    }
    for path in layout.values():
        path.mkdir(parents=True, exist_ok=True)
    return layout


def exact_stage_manifest_path(output_dir: Path) -> Path:
    return output_dir / "_work" / "exact_stage_manifest.json"


def write_exact_stage_manifest(
    *,
    output_dir: Path,
    input_glob: str | None,
    input_paths: list[Path],
    exact_doc_paths: list[Path],
    global_doc_offsets: dict[str, int],
    source_counts: dict[str, Counter],
    aggregate: Counter,
    phase_elapsed_seconds: dict[str, float],
    raw_line_hash_instances_indexed: int,
    duplicate_line_hash_count: int,
    exact_bucket_workers: int,
    args: argparse.Namespace,
    stage1_input_files_deleted: int,
) -> None:
    manifest = {
        "input_glob": input_glob,
        "input_paths": [str(path) for path in input_paths],
        "exact_doc_paths": [str(path) for path in exact_doc_paths],
        "global_doc_offsets": global_doc_offsets,
        "source_counts": {
            source_name: dict(counts) for source_name, counts in source_counts.items()
        },
        "aggregate_counts": dict(aggregate),
        "phase_elapsed_seconds": dict(phase_elapsed_seconds),
        "exact_line_index": {
            "raw_line_hash_instances_indexed": raw_line_hash_instances_indexed,
            "duplicate_line_hashes": duplicate_line_hash_count,
        },
        "exact_hash_buckets": args.exact_hash_buckets,
        "exact_bucket_workers": exact_bucket_workers,
        "exact_bucket_cache_size": args.exact_bucket_cache_size,
        "stage1_input_files_deleted_after_phase_2": stage1_input_files_deleted,
    }
    manifest_path = exact_stage_manifest_path(output_dir)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


def load_exact_stage_manifest(
    output_dir: Path,
) -> tuple[
    str | None,
    list[Path],
    list[Path],
    dict[str, int],
    defaultdict[str, Counter],
    Counter,
    dict[str, float],
    int,
    int,
    int,
    int,
]:
    manifest_path = exact_stage_manifest_path(output_dir)
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing exact-stage manifest: {manifest_path}")

    manifest = json.loads(manifest_path.read_text())
    input_paths = [Path(path) for path in manifest["input_paths"]]
    exact_doc_paths = [Path(path) for path in manifest["exact_doc_paths"]]
    missing_exact_docs = [str(path) for path in exact_doc_paths if not path.exists()]
    if missing_exact_docs:
        raise FileNotFoundError(
            "Cannot resume because exact checkpoint files are missing: "
            + ", ".join(missing_exact_docs[:10])
        )

    source_counts: defaultdict[str, Counter] = defaultdict(Counter)
    for source_name, counts in manifest["source_counts"].items():
        source_counts[source_name].update(counts)

    exact_line_index = manifest.get("exact_line_index", {})
    return (
        manifest.get("input_glob"),
        input_paths,
        exact_doc_paths,
        {source_name: int(offset) for source_name, offset in manifest["global_doc_offsets"].items()},
        source_counts,
        Counter(manifest["aggregate_counts"]),
        dict(manifest.get("phase_elapsed_seconds", {})),
        int(exact_line_index.get("raw_line_hash_instances_indexed", 0)),
        int(exact_line_index.get("duplicate_line_hashes", 0)),
        int(manifest.get("exact_bucket_workers", 0)),
        int(manifest.get("stage1_input_files_deleted_after_phase_2", 0)),
    )


def prepare_resume_from_exact_docs(layout: dict[str, Path]) -> None:
    if any(layout["deduped_docs"].glob("*.jsonl")):
        raise RuntimeError(
            "Refusing to resume because deduped_docs already contains outputs. "
            "This lightweight resume mode only supports failures before phase 6 started."
        )

    for key in ("preprocessed_chunks", "summaries"):
        if layout[key].exists():
            shutil.rmtree(layout[key])
        layout[key].mkdir(parents=True, exist_ok=True)


def main() -> None:
    args = parse_args()
    total_start = time.time()

    if args.num_hashes <= 0 or args.num_bands <= 0 or args.ngrams <= 0:
        raise ValueError("num_hashes, num_bands, and ngrams must be positive.")
    if args.num_hashes % args.num_bands != 0:
        raise ValueError("num_hashes must be evenly divisible by num_bands.")
    if args.phase3_chunk_docs <= 0:
        raise ValueError("phase3_chunk_docs must be positive.")
    if args.exact_hash_buckets <= 0:
        raise ValueError("exact_hash_buckets must be positive.")
    if args.exact_bucket_workers <= 0:
        raise ValueError("exact_bucket_workers must be positive.")
    if args.exact_bucket_cache_size <= 0:
        raise ValueError("exact_bucket_cache_size must be positive.")

    output_dir = Path(args.output_dir)
    if output_dir.exists() and any(output_dir.iterdir()) and not args.resume_from_exact_docs:
        raise FileExistsError(
            f"Output directory must be empty for a clean stage-2 run: {output_dir}"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    layout = ensure_output_layout(output_dir)

    if args.resume_from_exact_docs:
        (
            input_glob,
            input_paths,
            exact_doc_paths,
            global_doc_offsets,
            source_counts,
            aggregate,
            phase_elapsed_seconds,
            raw_line_hash_instances_indexed,
            duplicate_line_hash_count,
            exact_bucket_workers,
            stage1_input_files_deleted,
        ) = load_exact_stage_manifest(output_dir)
        prepare_resume_from_exact_docs(layout)
        worker_count = min(args.workers, len(exact_doc_paths))
        log_progress(
            "resuming stage 2 from exact checkpoint with "
            f"{len(exact_doc_paths)} exact-doc files and {worker_count} workers"
        )
    else:
        if not args.input_glob:
            raise ValueError("--input-glob is required unless --resume-from-exact-docs is used.")
        input_glob = args.input_glob
        input_paths = sorted(Path(path) for path in glob.glob(args.input_glob))
        if not input_paths:
            raise FileNotFoundError(
                f"No stage-1 kept-doc files matched input glob: {args.input_glob}"
            )

        aggregate = Counter()
        source_counts = defaultdict(Counter)
        worker_count = min(args.workers, len(input_paths))
        phase_elapsed_seconds = {}
        log_progress(
            f"starting stage 2 with {len(input_paths)} input files, "
            f"{worker_count} document workers, {args.exact_hash_buckets} exact-hash buckets"
        )

        # Phase 1a: stream line hashes to disk buckets. Returning one giant Counter
        # per worker does not scale to the full 5000-WET run.
        log_progress("phase 1a start: writing exact-line hash bucket shards")
        phase_start = time.time()
        shard_dirs: list[str] = []
        input_path_chunks = chunked_paths(input_paths, worker_count)
        with concurrent.futures.ProcessPoolExecutor(max_workers=worker_count) as executor:
            futures = [
                executor.submit(
                    write_line_hash_bucket_shard,
                    [str(input_path) for input_path in input_path_chunk],
                    shard_id,
                    str(layout["line_hash_shards"]),
                    args.exact_hash_buckets,
                )
                for shard_id, input_path_chunk in enumerate(input_path_chunks)
            ]
            for future in concurrent.futures.as_completed(futures):
                shard_dir, shard_source_counts = future.result()
                shard_dirs.append(shard_dir)
                for source_name, counts in shard_source_counts.items():
                    aggregate.update(counts)
                    source_counts[source_name].update(counts)
        phase_elapsed_seconds["phase_1a_line_hash_bucket_sharding"] = (
            time.time() - phase_start
        )
        log_progress(
            "phase 1a complete: "
            f"{aggregate['line_instances_seen']} line instances bucketed in "
            f"{phase_elapsed_seconds['phase_1a_line_hash_bucket_sharding']:.3f}s"
        )

        # Phase 1b: build the exact duplicate-hash index one bucket at a time so the
        # peak Counter size is bounded by a bucket, not by the full corpus.
        log_progress("phase 1b start: building duplicate line-hash bucket index")
        phase_start = time.time()
        exact_bucket_workers = min(args.exact_bucket_workers, args.exact_hash_buckets)
        duplicate_line_hash_count = 0
        raw_line_hash_instances_indexed = 0
        with concurrent.futures.ProcessPoolExecutor(max_workers=exact_bucket_workers) as executor:
            futures = [
                executor.submit(
                    build_duplicate_line_hash_bucket,
                    bucket_id,
                    shard_dirs,
                    str(layout["duplicate_line_hashes"]),
                    not args.keep_work,
                )
                for bucket_id in range(args.exact_hash_buckets)
            ]
            for future in concurrent.futures.as_completed(futures):
                _bucket_id, bucket_instances, bucket_duplicate_hashes = future.result()
                raw_line_hash_instances_indexed += bucket_instances
                duplicate_line_hash_count += bucket_duplicate_hashes

        if not args.keep_work and layout["line_hash_shards"].exists():
            shutil.rmtree(layout["line_hash_shards"])
        phase_elapsed_seconds["phase_1b_duplicate_line_hash_index"] = (
            time.time() - phase_start
        )
        log_progress(
            "phase 1b complete: "
            f"{raw_line_hash_instances_indexed} line-hash instances indexed, "
            f"{duplicate_line_hash_count} duplicate hashes retained in "
            f"{phase_elapsed_seconds['phase_1b_duplicate_line_hash_index']:.3f}s"
        )

        # Phase 2: materialize the globally exact-deduplicated checkpoint. After
        # this finishes, downstream phases no longer need the large stage-1 inputs.
        log_progress("phase 2 start: materializing exact-line dedup checkpoint")
        phase_start = time.time()
        stage1_input_files_deleted = 0
        exact_doc_path_by_source: dict[str, Path] = {}
        with concurrent.futures.ProcessPoolExecutor(
            max_workers=worker_count,
            initializer=init_exact_worker,
            initargs=(
                str(layout["duplicate_line_hashes"]),
                args.exact_hash_buckets,
                args.exact_bucket_cache_size,
            ),
        ) as executor:
            futures = [
                executor.submit(
                    materialize_exact_stage_for_stage1_file,
                    str(input_path),
                    str(layout["exact_docs"]),
                    str(layout["review_logs"]),
                    args.review_chars,
                    args.delete_input_after_write,
                )
                for input_path in input_paths
            ]
            for future in concurrent.futures.as_completed(futures):
                source_name, counts, input_deleted, exact_doc_path = future.result()
                aggregate.update(counts)
                source_counts[source_name].update(counts)
                exact_doc_path_by_source[source_name] = Path(exact_doc_path)
                if input_deleted:
                    stage1_input_files_deleted += 1

        global_doc_offsets = {}
        next_global_doc_index = 0
        for input_path in input_paths:
            source_name = input_path.name
            global_doc_offsets[source_name] = next_global_doc_index
            next_global_doc_index += source_counts[source_name]["docs_after_exact_line_dedup"]
        exact_doc_paths = [exact_doc_path_by_source[input_path.name] for input_path in input_paths]
        phase_elapsed_seconds["phase_2_exact_line_dedup"] = time.time() - phase_start
        log_progress(
            "phase 2 complete: "
            f"{aggregate['docs_after_exact_line_dedup']} docs survive exact-line dedup, "
            f"{stage1_input_files_deleted} stage-1 files deleted in "
            f"{phase_elapsed_seconds['phase_2_exact_line_dedup']:.3f}s"
        )
        write_exact_stage_manifest(
            output_dir=output_dir,
            input_glob=input_glob,
            input_paths=input_paths,
            exact_doc_paths=exact_doc_paths,
            global_doc_offsets=global_doc_offsets,
            source_counts=source_counts,
            aggregate=aggregate,
            phase_elapsed_seconds=phase_elapsed_seconds,
            raw_line_hash_instances_indexed=raw_line_hash_instances_indexed,
            duplicate_line_hash_count=duplicate_line_hash_count,
            exact_bucket_workers=exact_bucket_workers,
            args=args,
            stage1_input_files_deleted=stage1_input_files_deleted,
        )
        log_progress(f"exact checkpoint manifest written: {exact_stage_manifest_path(output_dir)}")

    # Phase 3: preprocess the exact-deduplicated checkpoint into compact
    # compressed chunks for global MinHash/LSH.
    log_progress("phase 3 start: preprocessing MinHash signatures")
    phase_start = time.time()
    preprocessed_chunk_paths: list[Path] = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=worker_count) as executor:
        futures = [
            executor.submit(
                preprocess_exact_stage_file_to_chunks,
                str(input_path),
                str(layout["preprocessed_chunks"]),
                global_doc_offsets[input_path.name],
                args.ngrams,
                args.num_hashes,
                args.phase3_chunk_docs,
            )
            for input_path in exact_doc_paths
        ]
        for future in concurrent.futures.as_completed(futures):
            source_name, chunk_paths, counts = future.result()
            preprocessed_chunk_paths.extend(Path(path) for path in chunk_paths)
            aggregate.update(counts)
            source_counts[source_name].update(counts)
    phase_elapsed_seconds["phase_3_signature_preprocessing"] = time.time() - phase_start
    log_progress(
        "phase 3 complete: "
        f"{aggregate['docs_preprocessed']} docs preprocessed into "
        f"{len(preprocessed_chunk_paths)} chunks in "
        f"{phase_elapsed_seconds['phase_3_signature_preprocessing']:.3f}s"
    )

    # Phase 4: build the same global MinHash candidate space as Chapter 3.
    log_progress("phase 4 start: building MinHash LSH candidate pairs")
    phase_start = time.time()
    fuzzy_global_doc_indices: list[int] = []
    fuzzy_signatures: list[tuple[int, ...]] = []
    preprocessed_signature_entries: list[tuple[int, tuple[int, ...]]] = []
    preprocessed_chunks_deleted = 0
    for preprocessed_chunk_path in preprocessed_chunk_paths:
        with xopen(preprocessed_chunk_path, "rt") as handle:
            for line in handle:
                entry = json.loads(line)
                preprocessed_signature_entries.append(
                    (entry["global_doc_index"], tuple(entry["signature"]))
                )

    preprocessed_signature_entries.sort(key=lambda entry: entry[0])
    for global_doc_index, signature in preprocessed_signature_entries:
        fuzzy_global_doc_indices.append(global_doc_index)
        fuzzy_signatures.append(signature)
    preprocessed_signature_entries.clear()

    candidate_pairs = candidate_duplicate_pairs(fuzzy_signatures, args.num_bands)
    aggregate["minhash_candidate_pairs"] = len(candidate_pairs)

    fuzzy_normalized_texts = [""] * len(fuzzy_signatures)
    if candidate_pairs:
        candidate_local_indices = {
            local_index for pair in candidate_pairs for local_index in pair
        }
        candidate_global_doc_indices = {
            fuzzy_global_doc_indices[local_index] for local_index in candidate_local_indices
        }
        local_index_by_global_doc_index = {
            global_doc_index: local_index
            for local_index, global_doc_index in enumerate(fuzzy_global_doc_indices)
            if global_doc_index in candidate_global_doc_indices
        }

        for preprocessed_chunk_path in preprocessed_chunk_paths:
            with xopen(preprocessed_chunk_path, "rt") as handle:
                for line in handle:
                    entry = json.loads(line)
                    global_doc_index = entry["global_doc_index"]
                    if global_doc_index in candidate_global_doc_indices:
                        fuzzy_normalized_texts[
                            local_index_by_global_doc_index[global_doc_index]
                        ] = entry["normalized_text"]

    if not args.keep_work:
        for preprocessed_chunk_path in preprocessed_chunk_paths:
            if preprocessed_chunk_path.exists():
                preprocessed_chunk_path.unlink()
                preprocessed_chunks_deleted += 1
    phase_elapsed_seconds["phase_4_candidate_generation"] = time.time() - phase_start
    log_progress(
        "phase 4 complete: "
        f"{aggregate['minhash_candidate_pairs']} candidate pairs generated in "
        f"{phase_elapsed_seconds['phase_4_candidate_generation']:.3f}s"
    )

    # Phase 5: parallel confirmation of candidate pairs with true Jaccard.
    log_progress("phase 5 start: confirming candidate pairs")
    phase_start = time.time()
    confirmed_duplicate_pairs: list[tuple[int, int]] = []
    if candidate_pairs:
        pair_list = sorted(candidate_pairs)
        similarity_workers = min(worker_count, len(pair_list))

        if similarity_workers <= 1:
            init_similarity_worker(
                fuzzy_normalized_texts,
                args.ngrams,
                args.jaccard_threshold,
            )
            confirmed_duplicate_pairs = similar_pairs_in_chunk(pair_list)
        else:
            chunk_size = max(1000, len(pair_list) // (similarity_workers * 8) or 1)
            pair_chunks = chunked_pairs(pair_list, chunk_size)
            with concurrent.futures.ProcessPoolExecutor(
                max_workers=similarity_workers,
                initializer=init_similarity_worker,
                initargs=(
                    fuzzy_normalized_texts,
                    args.ngrams,
                    args.jaccard_threshold,
                ),
            ) as executor:
                futures = [
                    executor.submit(similar_pairs_in_chunk, pair_chunk)
                    for pair_chunk in pair_chunks
                ]
                for future in concurrent.futures.as_completed(futures):
                    confirmed_duplicate_pairs.extend(future.result())

    aggregate["minhash_confirmed_duplicate_pairs"] = len(confirmed_duplicate_pairs)

    parents = list(range(len(fuzzy_signatures)))
    for left, right in confirmed_duplicate_pairs:
        union_sets(parents, left, right)

    survivor_by_root: dict[int, int] = {}
    for local_index in range(len(fuzzy_signatures)):
        root = find_root(parents, local_index)
        survivor_by_root[root] = min(survivor_by_root.get(root, local_index), local_index)
    fuzzy_survivor_local_indices = set(survivor_by_root.values())
    fuzzy_removed_global_doc_indices = {
        fuzzy_global_doc_indices[local_index]
        for local_index in range(len(fuzzy_signatures))
        if local_index not in fuzzy_survivor_local_indices
    }
    phase_elapsed_seconds["phase_5_candidate_confirmation"] = time.time() - phase_start
    log_progress(
        "phase 5 complete: "
        f"{aggregate['minhash_confirmed_duplicate_pairs']} duplicate pairs confirmed in "
        f"{phase_elapsed_seconds['phase_5_candidate_confirmation']:.3f}s"
    )

    # Phase 6: final write-back from the exact-deduplicated checkpoint.
    log_progress("phase 6 start: writing final deduped docs")
    phase_start = time.time()
    exact_doc_files_deleted = 0
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=worker_count,
        initializer=init_fuzzy_write_worker,
        initargs=(fuzzy_removed_global_doc_indices,),
    ) as executor:
        futures = [
            executor.submit(
                write_final_outputs_for_exact_stage_file,
                str(input_path),
                str(output_dir),
                global_doc_offsets[input_path.name],
                args.review_chars,
                not args.keep_work,
            )
            for input_path in exact_doc_paths
        ]
        for future in concurrent.futures.as_completed(futures):
            source_name, counts, input_deleted = future.result()
            aggregate.update(counts)
            source_counts[source_name].update(counts)
            if input_deleted:
                exact_doc_files_deleted += 1
    phase_elapsed_seconds["phase_6_write_back"] = time.time() - phase_start
    log_progress(
        "phase 6 complete: "
        f"{aggregate['decision_keep']} docs kept, "
        f"{exact_doc_files_deleted} exact checkpoint files deleted in "
        f"{phase_elapsed_seconds['phase_6_write_back']:.3f}s"
    )

    if not args.keep_work and layout["work"].exists():
        shutil.rmtree(layout["work"])
        log_progress("temporary work directory removed")

    summary_paths = write_per_source_summaries(
        input_paths=input_paths,
        output_dir=output_dir,
        source_counts=source_counts,
    )

    aggregate_summary = {
        "input_glob": input_glob,
        "num_input_files": len(input_paths),
        "resumed_from_exact_docs": args.resume_from_exact_docs,
        "num_hashes": args.num_hashes,
        "num_bands": args.num_bands,
        "ngrams": args.ngrams,
        "jaccard_threshold": args.jaccard_threshold,
        "review_chars": args.review_chars,
        "workers": worker_count,
        "phase3_chunk_docs": args.phase3_chunk_docs,
        "exact_hash_buckets": args.exact_hash_buckets,
        "exact_bucket_workers": exact_bucket_workers,
        "exact_bucket_cache_size": args.exact_bucket_cache_size,
        "keep_work": args.keep_work,
        "delete_input_after_write": args.delete_input_after_write,
        "total_elapsed_seconds": time.time() - total_start,
        "phase_elapsed_seconds": phase_elapsed_seconds,
        "exact_line_index": {
            "raw_line_hash_instances_indexed": raw_line_hash_instances_indexed,
            "duplicate_line_hashes": duplicate_line_hash_count,
        },
        "cleanup": {
            "preprocessed_chunks_deleted_after_phase_4": preprocessed_chunks_deleted,
            "stage1_input_files_deleted_after_phase_2": stage1_input_files_deleted,
            "exact_doc_files_deleted_after_phase_6": exact_doc_files_deleted,
            "work_dir_removed_after_phase_6": not args.keep_work,
        },
        "aggregate_counts": dict(aggregate),
        "per_file_summary_paths": summary_paths,
    }
    (output_dir / "aggregate_summary.json").write_text(
        json.dumps(aggregate_summary, indent=2, ensure_ascii=False) + "\n"
    )


if __name__ == "__main__":
    main()
