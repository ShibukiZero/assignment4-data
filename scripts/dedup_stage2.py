from __future__ import annotations

import argparse
import glob
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

from xopen import xopen

from cs336_data.deduplication import hash_line, minhash_deduplication


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Chapter 4 stage-2 dedup pipeline over the kept-doc JSONL "
            "outputs from stage 1. This script first removes corpus-global "
            "duplicate lines from each kept document, then applies MinHash "
            "fuzzy deduplication at the document level."
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
    return parser.parse_args()


def text_preview(text: str, review_chars: int) -> str:
    compact = " ".join(text.split())
    return compact[:review_chars]


def stable_doc_id(source_path: Path, line_index: int, record_id: str) -> str:
    payload = f"{source_path}:{line_index}:{record_id}".encode("utf-8")
    return hashlib.sha1(payload).hexdigest()


def sharded_text_path(root: Path, doc_id: str) -> Path:
    shard = doc_id[:2]
    return root / shard / f"{doc_id}.txt"


def stage1_documents(input_paths: list[Path]) -> Iterable[tuple[Path, int, dict]]:
    for input_path in input_paths:
        with xopen(input_path, "rt") as handle:
            for line_index, line in enumerate(handle):
                yield input_path, line_index, json.loads(line)


def document_lines(text: str) -> list[str]:
    lines = text.splitlines(keepends=True)
    if not lines and text:
        return [text]
    return lines


def count_line_hashes_in_stage1_docs(input_paths: list[Path]) -> Counter[bytes]:
    counts: Counter[bytes] = Counter()
    for _source_path, _line_index, payload in stage1_documents(input_paths):
        for line in document_lines(payload["text"]):
            counts[hash_line(line)] += 1
    return counts


def exact_dedup_text(text: str, line_hash_counts: Counter[bytes]) -> tuple[str, int, int]:
    original_lines = document_lines(text)
    kept_lines = [line for line in original_lines if line_hash_counts[hash_line(line)] == 1]
    return "".join(kept_lines), len(original_lines), len(kept_lines)


def ensure_output_layout(output_dir: Path) -> dict[str, Path]:
    layout = {
        "deduped_docs": output_dir / "deduped_docs",
        "review_logs": output_dir / "review_logs",
        "summaries": output_dir / "summaries",
        "work_exact_texts": output_dir / "_work" / "exact_texts",
        "work_minhash_texts": output_dir / "_work" / "minhash_survivors",
        "work_manifest": output_dir / "_work" / "exact_manifest.jsonl",
    }
    for key, path in layout.items():
        if key == "work_manifest":
            path.parent.mkdir(parents=True, exist_ok=True)
            continue
        path.mkdir(parents=True, exist_ok=True)
    return layout


def append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with xopen(path, "at") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


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


def main() -> None:
    args = parse_args()

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

    line_hash_counts = count_line_hashes_in_stage1_docs(input_paths)

    exact_doc_paths: list[Path] = []
    manifest_path = layout["work_manifest"]
    with xopen(manifest_path, "wt") as manifest_handle:
        for source_path, line_index, payload in stage1_documents(input_paths):
            source_name = source_path.name
            aggregate["docs_seen"] += 1
            source_counts[source_name]["docs_seen"] += 1

            doc_id = stable_doc_id(source_path, line_index, payload["record_id"])
            exact_text, original_line_count, kept_line_count = exact_dedup_text(
                payload["text"], line_hash_counts
            )
            line_instances_removed = original_line_count - kept_line_count
            aggregate["exact_line_instances_removed"] += line_instances_removed
            source_counts[source_name]["exact_line_instances_removed"] += line_instances_removed

            manifest_entry = {
                "doc_id": doc_id,
                "source_name": source_name,
                "source_stage1_kept_docs_path": str(source_path),
                "line_index": line_index,
                "payload": payload,
                "original_line_count": original_line_count,
                "exact_line_count": kept_line_count,
                "exact_line_instances_removed": line_instances_removed,
            }

            if not exact_text.strip():
                aggregate["decision_exact_line_dedup_empty"] += 1
                source_counts[source_name]["decision_exact_line_dedup_empty"] += 1

                review_payload = {
                    **payload,
                    "decision": "drop",
                    "drop_reason": "exact_line_dedup_empty",
                    "original_line_count": original_line_count,
                    "exact_line_count": kept_line_count,
                    "exact_line_instances_removed": line_instances_removed,
                    "text_preview": text_preview(payload["text"], args.review_chars),
                }
                append_jsonl(output_dir / "review_logs" / source_name, review_payload)
                continue

            exact_text_path = sharded_text_path(layout["work_exact_texts"], doc_id)
            exact_text_path.parent.mkdir(parents=True, exist_ok=True)
            exact_text_path.write_text(exact_text, encoding="utf-8")

            manifest_entry["exact_text_path"] = str(exact_text_path)
            manifest_handle.write(json.dumps(manifest_entry, ensure_ascii=False) + "\n")
            exact_doc_paths.append(exact_text_path)

            aggregate["docs_after_exact_line_dedup"] += 1
            source_counts[source_name]["docs_after_exact_line_dedup"] += 1

    survivor_names: set[str] = set()
    if exact_doc_paths:
        minhash_deduplication(
            input_files=exact_doc_paths,
            num_hashes=args.num_hashes,
            num_bands=args.num_bands,
            ngrams=args.ngrams,
            jaccard_threshold=args.jaccard_threshold,
            output_directory=layout["work_minhash_texts"],
        )
        survivor_names = {
            path.name for path in layout["work_minhash_texts"].glob("*.txt")
        }

    with xopen(manifest_path, "rt") as manifest_handle:
        for line in manifest_handle:
            entry = json.loads(line)
            payload = entry["payload"]
            source_name = entry["source_name"]
            exact_text_path = Path(entry["exact_text_path"])
            exact_text = exact_text_path.read_text(encoding="utf-8")

            if exact_text_path.name in survivor_names:
                kept_payload = dict(payload)
                kept_payload["text"] = exact_text
                kept_payload["text_preview"] = text_preview(exact_text, args.review_chars)
                kept_payload["dedup"] = {
                    "exact_line_instances_removed": entry["exact_line_instances_removed"],
                    "original_line_count": entry["original_line_count"],
                    "exact_line_count": entry["exact_line_count"],
                    "minhash_survivor": True,
                }
                append_jsonl(output_dir / "deduped_docs" / source_name, kept_payload)
                aggregate["decision_keep"] += 1
                source_counts[source_name]["decision_keep"] += 1
            else:
                review_payload = {
                    **payload,
                    "decision": "drop",
                    "drop_reason": "minhash_duplicate",
                    "original_line_count": entry["original_line_count"],
                    "exact_line_count": entry["exact_line_count"],
                    "exact_line_instances_removed": entry["exact_line_instances_removed"],
                    "text_preview": text_preview(exact_text, args.review_chars),
                }
                append_jsonl(output_dir / "review_logs" / source_name, review_payload)
                aggregate["decision_minhash_duplicate"] += 1
                source_counts[source_name]["decision_minhash_duplicate"] += 1

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
        "aggregate_counts": dict(aggregate),
        "per_file_summary_paths": summary_paths,
    }
    (output_dir / "aggregate_summary.json").write_text(
        json.dumps(aggregate_summary, indent=2, ensure_ascii=False) + "\n"
    )


if __name__ == "__main__":
    main()
