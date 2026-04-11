from __future__ import annotations

import argparse
import concurrent.futures
import glob
import hashlib
import json
import shutil
from collections import Counter, defaultdict
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
_DUPLICATE_LINE_HASHES: set[bytes] = set()
_FUZZY_REMOVED_GLOBAL_DOC_INDICES: set[int] = set()


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
        required=True,
        help="Glob pattern for stage-1 kept-doc JSONL files.",
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
        "--keep-work",
        action="store_true",
        help="Keep stage-2 temporary work files after they have been consumed.",
    )
    parser.add_argument(
        "--delete-input-after-write",
        action="store_true",
        help=(
            "Delete each input stage-1 kept-doc file after its final stage-2 outputs "
            "have been written. This is intended for disk-constrained full-pipeline runs."
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
    duplicate_line_hashes: set[bytes],
    fuzzy_removed_global_doc_indices: set[int] | None = None,
) -> None:
    global _DUPLICATE_LINE_HASHES, _FUZZY_REMOVED_GLOBAL_DOC_INDICES
    _DUPLICATE_LINE_HASHES = duplicate_line_hashes
    _FUZZY_REMOVED_GLOBAL_DOC_INDICES = fuzzy_removed_global_doc_indices or set()


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


def count_line_hashes_for_stage1_file(
    input_path: str,
) -> tuple[str, dict[str, int], Counter[bytes]]:
    input_path_obj = Path(input_path)
    source_name = input_path_obj.name
    counts = Counter()
    line_hash_counts: Counter[bytes] = Counter()

    with xopen(input_path_obj, "rt") as handle:
        for line in handle:
            payload = json.loads(line)
            counts["docs_seen"] += 1
            for doc_line in document_lines(payload["text"]):
                line_hash_counts[hash_line(doc_line)] += 1
                counts["line_instances_seen"] += 1

    return source_name, dict(counts), line_hash_counts


def exact_line_dedup_text(text: str) -> tuple[str, int, int, int]:
    original_lines = document_lines(text)
    kept_lines = [
        doc_line
        for doc_line in original_lines
        if hash_line(doc_line) not in _DUPLICATE_LINE_HASHES
    ]
    exact_text = "".join(kept_lines)
    return exact_text, len(original_lines), len(kept_lines), len(original_lines) - len(kept_lines)


def count_exact_line_dedup_for_stage1_file(input_path: str) -> tuple[str, dict[str, int]]:
    input_path_obj = Path(input_path)
    source_name = input_path_obj.name
    counts = Counter()

    with xopen(input_path_obj, "rt") as source:
        for line in source:
            payload = json.loads(line)
            exact_text, _original_line_count, _exact_line_count, line_instances_removed = (
                exact_line_dedup_text(payload["text"])
            )
            counts["exact_line_instances_removed"] += line_instances_removed

            if not exact_text.strip():
                counts["decision_exact_line_dedup_empty"] += 1
            else:
                counts["docs_after_exact_line_dedup"] += 1

    return source_name, dict(counts)


def preprocess_stage1_file_to_chunks(
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
                exact_text, _original_line_count, _exact_line_count, _line_instances_removed = (
                    exact_line_dedup_text(payload["text"])
                )

                if not exact_text.strip():
                    continue

                if chunk_handle is None:
                    current_chunk_path, chunk_handle = open_chunk()

                normalized_text = normalize_document_for_deduplication(exact_text)
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


def write_final_outputs_for_stage1_file(
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
            exact_text, original_line_count, exact_line_count, line_instances_removed = (
                exact_line_dedup_text(payload["text"])
            )

            if not exact_text.strip():
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
                continue

            global_doc_index = global_doc_offset + local_doc_index
            local_doc_index += 1

            if global_doc_index in _FUZZY_REMOVED_GLOBAL_DOC_INDICES:
                counts["decision_minhash_duplicate"] += 1
                review_payload = {
                    **payload,
                    "decision": "drop",
                    "drop_reason": "minhash_duplicate",
                    "original_line_count": original_line_count,
                    "exact_line_count": exact_line_count,
                    "exact_line_instances_removed": line_instances_removed,
                    "text_preview": text_preview(exact_text, review_chars),
                }
                review_sink.write(json.dumps(review_payload, ensure_ascii=False) + "\n")
                continue

            kept_payload = dict(payload)
            kept_payload["text"] = exact_text
            kept_payload["text_preview"] = text_preview(exact_text, review_chars)
            kept_payload["dedup"] = {
                "exact_line_instances_removed": line_instances_removed,
                "original_line_count": original_line_count,
                "exact_line_count": exact_line_count,
                "minhash_survivor": True,
            }
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
        "preprocessed_chunks": output_dir / "_work" / "preprocessed_chunks",
    }
    for path in layout.values():
        path.mkdir(parents=True, exist_ok=True)
    return layout


def main() -> None:
    args = parse_args()
    total_start = time.time()

    if args.num_hashes <= 0 or args.num_bands <= 0 or args.ngrams <= 0:
        raise ValueError("num_hashes, num_bands, and ngrams must be positive.")
    if args.num_hashes % args.num_bands != 0:
        raise ValueError("num_hashes must be evenly divisible by num_bands.")
    if args.phase3_chunk_docs <= 0:
        raise ValueError("phase3_chunk_docs must be positive.")

    input_paths = sorted(Path(path) for path in glob.glob(args.input_glob))
    if not input_paths:
        raise FileNotFoundError(
            f"No stage-1 kept-doc files matched input glob: {args.input_glob}"
        )

    output_dir = Path(args.output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(
            f"Output directory must be empty for a clean stage-2 run: {output_dir}"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    layout = ensure_output_layout(output_dir)

    aggregate = Counter()
    source_counts: dict[str, Counter] = defaultdict(Counter)
    worker_count = min(args.workers, len(input_paths))
    phase_elapsed_seconds: dict[str, float] = {}

    # Phase 1: parallel global line-hash counting for exact line deduplication.
    phase_start = time.time()
    line_hash_counts: Counter[bytes] = Counter()
    with concurrent.futures.ProcessPoolExecutor(max_workers=worker_count) as executor:
        futures = [
            executor.submit(count_line_hashes_for_stage1_file, str(input_path))
            for input_path in input_paths
        ]
        for future in concurrent.futures.as_completed(futures):
            source_name, counts, local_counter = future.result()
            aggregate.update(counts)
            source_counts[source_name].update(counts)
            line_hash_counts.update(local_counter)
    phase_elapsed_seconds["phase_1_line_hash_counting"] = time.time() - phase_start

    duplicate_line_hashes = {
        line_hash for line_hash, count in line_hash_counts.items() if count > 1
    }
    del line_hash_counts

    # Phase 2: exact line deduplication planning. This computes per-file survivor
    # counts first so phase 3 can assign stable global_doc_index offsets while
    # still processing files in parallel.
    phase_start = time.time()
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=worker_count,
        initializer=init_exact_worker,
        initargs=(duplicate_line_hashes,),
    ) as executor:
        futures = [
            executor.submit(count_exact_line_dedup_for_stage1_file, str(input_path))
            for input_path in input_paths
        ]
        for future in concurrent.futures.as_completed(futures):
            source_name, counts = future.result()
            aggregate.update(counts)
            source_counts[source_name].update(counts)

    global_doc_offsets: dict[str, int] = {}
    next_global_doc_index = 0
    for input_path in input_paths:
        source_name = input_path.name
        global_doc_offsets[source_name] = next_global_doc_index
        next_global_doc_index += source_counts[source_name]["docs_after_exact_line_dedup"]
    phase_elapsed_seconds["phase_2_exact_line_dedup"] = time.time() - phase_start

    # Phase 3: directly preprocess exact-surviving docs into compact compressed
    # chunks. This avoids materializing exact_stage and exact_chunks copies.
    phase_start = time.time()
    preprocessed_chunk_paths: list[Path] = []
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=worker_count,
        initializer=init_exact_worker,
        initargs=(duplicate_line_hashes,),
    ) as executor:
        futures = [
            executor.submit(
                preprocess_stage1_file_to_chunks,
                str(input_path),
                str(layout["preprocessed_chunks"]),
                global_doc_offsets[input_path.name],
                args.ngrams,
                args.num_hashes,
                args.phase3_chunk_docs,
            )
            for input_path in input_paths
        ]
        for future in concurrent.futures.as_completed(futures):
            source_name, chunk_paths, counts = future.result()
            preprocessed_chunk_paths.extend(Path(path) for path in chunk_paths)
            aggregate.update(counts)
            source_counts[source_name].update(counts)
    phase_elapsed_seconds["phase_3_signature_preprocessing"] = time.time() - phase_start

    # Phase 4: build the same global MinHash candidate space as Chapter 3.
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

    # Phase 5: parallel confirmation of candidate pairs with true Jaccard.
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

    # Phase 6: final write-back with the original metadata restored. Re-reading
    # stage-1 inputs avoids keeping a full exact_stage payload copy on disk.
    phase_start = time.time()
    input_files_deleted = 0
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=worker_count,
        initializer=init_exact_worker,
        initargs=(duplicate_line_hashes, fuzzy_removed_global_doc_indices),
    ) as executor:
        futures = [
            executor.submit(
                write_final_outputs_for_stage1_file,
                str(input_path),
                str(output_dir),
                global_doc_offsets[input_path.name],
                args.review_chars,
                args.delete_input_after_write,
            )
            for input_path in input_paths
        ]
        for future in concurrent.futures.as_completed(futures):
            source_name, counts, input_deleted = future.result()
            aggregate.update(counts)
            source_counts[source_name].update(counts)
            if input_deleted:
                input_files_deleted += 1
    phase_elapsed_seconds["phase_6_write_back"] = time.time() - phase_start

    if not args.keep_work and layout["work"].exists():
        shutil.rmtree(layout["work"])

    summary_paths = write_per_source_summaries(
        input_paths=input_paths,
        output_dir=output_dir,
        source_counts=source_counts,
    )

    aggregate_summary = {
        "input_glob": args.input_glob,
        "num_input_files": len(input_paths),
        "num_hashes": args.num_hashes,
        "num_bands": args.num_bands,
        "ngrams": args.ngrams,
        "jaccard_threshold": args.jaccard_threshold,
        "review_chars": args.review_chars,
        "workers": worker_count,
        "phase3_chunk_docs": args.phase3_chunk_docs,
        "keep_work": args.keep_work,
        "delete_input_after_write": args.delete_input_after_write,
        "total_elapsed_seconds": time.time() - total_start,
        "phase_elapsed_seconds": phase_elapsed_seconds,
        "cleanup": {
            "preprocessed_chunks_deleted_after_phase_4": preprocessed_chunks_deleted,
            "input_files_deleted_after_phase_6": input_files_deleted,
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
