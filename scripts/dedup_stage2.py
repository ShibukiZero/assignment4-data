from __future__ import annotations

import argparse
import concurrent.futures
import glob
import json
from collections import Counter, defaultdict
from pathlib import Path
import time

from xopen import xopen

from cs336_data.deduplication import (
    candidate_duplicate_pairs,
    compute_minhash_signature,
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


def preprocess_exact_stage_file(
    exact_stage_path: str,
    preprocessed_path: str,
    ngrams: int,
    num_hashes: int,
) -> tuple[str, dict[str, int]]:
    exact_stage_path_obj = Path(exact_stage_path)
    preprocessed_path_obj = Path(preprocessed_path)
    source_name = exact_stage_path_obj.name
    counts = Counter()

    with xopen(exact_stage_path_obj, "rt") as source, xopen(preprocessed_path_obj, "wt") as sink:
        for line in source:
            entry = json.loads(line)
            exact_text = entry["exact_text"]
            normalized_text = normalize_document_for_deduplication(exact_text)
            ngram_set = document_word_ngrams(normalized_text, ngrams)
            signature = list(compute_minhash_signature(ngram_set, num_hashes))

            sink.write(
                json.dumps(
                    {
                        "global_doc_index": entry["global_doc_index"],
                        "normalized_text": normalized_text,
                        "signature": signature,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            counts["docs_preprocessed"] += 1

    return source_name, dict(counts)


def source_output_paths(output_dir: Path, source_name: str) -> tuple[Path, Path, Path]:
    return (
        output_dir / "deduped_docs" / source_name,
        output_dir / "review_logs" / source_name,
        output_dir / "summaries" / f"{source_name}.json",
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
        "exact_stage": output_dir / "_work" / "exact_stage",
        "preprocessed_stage": output_dir / "_work" / "preprocessed_stage",
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

    # Phase 2: exact line deduplication, preserving the global input order used
    # by Chapter 3 before MinHash survivor selection.
    phase_start = time.time()
    next_global_doc_index = 0
    exact_stage_paths: list[Path] = []
    for input_path in input_paths:
        source_name = input_path.name
        exact_stage_path = layout["exact_stage"] / source_name
        exact_stage_paths.append(exact_stage_path)

        with xopen(input_path, "rt") as source, xopen(exact_stage_path, "wt") as sink:
            for line in source:
                payload = json.loads(line)
                original_lines = document_lines(payload["text"])
                kept_lines = [
                    doc_line
                    for doc_line in original_lines
                    if line_hash_counts[hash_line(doc_line)] == 1
                ]
                exact_text = "".join(kept_lines)
                line_instances_removed = len(original_lines) - len(kept_lines)

                aggregate["exact_line_instances_removed"] += line_instances_removed
                source_counts[source_name]["exact_line_instances_removed"] += line_instances_removed

                if not exact_text.strip():
                    aggregate["decision_exact_line_dedup_empty"] += 1
                    source_counts[source_name]["decision_exact_line_dedup_empty"] += 1
                    review_payload = {
                        **payload,
                        "decision": "drop",
                        "drop_reason": "exact_line_dedup_empty",
                        "original_line_count": len(original_lines),
                        "exact_line_count": len(kept_lines),
                        "exact_line_instances_removed": line_instances_removed,
                        "text_preview": text_preview(payload["text"], args.review_chars),
                    }
                    append_jsonl(layout["review_logs"] / source_name, review_payload)
                    continue

                sink.write(
                    json.dumps(
                        {
                            "global_doc_index": next_global_doc_index,
                            "source_name": source_name,
                            "payload": payload,
                            "exact_text": exact_text,
                            "original_line_count": len(original_lines),
                            "exact_line_count": len(kept_lines),
                            "exact_line_instances_removed": line_instances_removed,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                aggregate["docs_after_exact_line_dedup"] += 1
                source_counts[source_name]["docs_after_exact_line_dedup"] += 1
                next_global_doc_index += 1
    phase_elapsed_seconds["phase_2_exact_line_dedup"] = time.time() - phase_start

    # Phase 3: parallel normalization + signature computation on exact-surviving docs.
    phase_start = time.time()
    preprocessed_stage_paths = [
        layout["preprocessed_stage"] / path.name for path in exact_stage_paths
    ]
    with concurrent.futures.ProcessPoolExecutor(max_workers=worker_count) as executor:
        futures = [
            executor.submit(
                preprocess_exact_stage_file,
                str(exact_stage_path),
                str(preprocessed_stage_path),
                args.ngrams,
                args.num_hashes,
            )
            for exact_stage_path, preprocessed_stage_path in zip(
                exact_stage_paths,
                preprocessed_stage_paths,
                strict=True,
            )
        ]
        for future in concurrent.futures.as_completed(futures):
            source_name, counts = future.result()
            aggregate.update(counts)
            source_counts[source_name].update(counts)
    phase_elapsed_seconds["phase_3_signature_preprocessing"] = time.time() - phase_start

    # Phase 4: build the same global MinHash candidate space as Chapter 3.
    phase_start = time.time()
    fuzzy_global_doc_indices: list[int] = []
    fuzzy_signatures: list[tuple[int, ...]] = []
    fuzzy_normalized_texts: list[str] = []
    for preprocessed_stage_path in preprocessed_stage_paths:
        with xopen(preprocessed_stage_path, "rt") as handle:
            for line in handle:
                entry = json.loads(line)
                fuzzy_global_doc_indices.append(entry["global_doc_index"])
                fuzzy_signatures.append(tuple(entry["signature"]))
                fuzzy_normalized_texts.append(entry["normalized_text"])

    candidate_pairs = candidate_duplicate_pairs(fuzzy_signatures, args.num_bands)
    aggregate["minhash_candidate_pairs"] = len(candidate_pairs)
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

    # Phase 6: final write-back with the original metadata restored.
    phase_start = time.time()
    for exact_stage_path in exact_stage_paths:
        source_name = exact_stage_path.name
        with xopen(exact_stage_path, "rt") as handle:
            for line in handle:
                entry = json.loads(line)
                payload = entry["payload"]
                global_doc_index = entry["global_doc_index"]

                if global_doc_index in fuzzy_removed_global_doc_indices:
                    aggregate["decision_minhash_duplicate"] += 1
                    source_counts[source_name]["decision_minhash_duplicate"] += 1
                    review_payload = {
                        **payload,
                        "decision": "drop",
                        "drop_reason": "minhash_duplicate",
                        "original_line_count": entry["original_line_count"],
                        "exact_line_count": entry["exact_line_count"],
                        "exact_line_instances_removed": entry["exact_line_instances_removed"],
                        "text_preview": text_preview(entry["exact_text"], args.review_chars),
                    }
                    append_jsonl(layout["review_logs"] / source_name, review_payload)
                    continue

                kept_payload = dict(payload)
                kept_payload["text"] = entry["exact_text"]
                kept_payload["text_preview"] = text_preview(entry["exact_text"], args.review_chars)
                kept_payload["dedup"] = {
                    "exact_line_instances_removed": entry["exact_line_instances_removed"],
                    "original_line_count": entry["original_line_count"],
                    "exact_line_count": entry["exact_line_count"],
                    "minhash_survivor": True,
                }
                append_jsonl(layout["deduped_docs"] / source_name, kept_payload)
                aggregate["decision_keep"] += 1
                source_counts[source_name]["decision_keep"] += 1
    phase_elapsed_seconds["phase_6_write_back"] = time.time() - phase_start

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
        "total_elapsed_seconds": time.time() - total_start,
        "phase_elapsed_seconds": phase_elapsed_seconds,
        "aggregate_counts": dict(aggregate),
        "per_file_summary_paths": summary_paths,
    }
    (output_dir / "aggregate_summary.json").write_text(
        json.dumps(aggregate_summary, indent=2, ensure_ascii=False) + "\n"
    )


if __name__ == "__main__":
    main()
