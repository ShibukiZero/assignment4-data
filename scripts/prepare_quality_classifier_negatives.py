from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from fastwarc.warc import ArchiveIterator, WarcRecordType

from cs336_data.html_text import extract_text_from_html_bytes
from cs336_data.langid import identify_language
from cs336_data.quality import passes_gopher_quality_filters


DEFAULT_WARC_PATH = Path("data/raw/cc_samples/example.warc.gz")
DEFAULT_DATA_OUTPUT_DIR = Path("data/quality_classifier/negatives")
DEFAULT_LOG_OUTPUT_DIR = Path("runs/quality_classifier_negative_texts")
DEFAULT_OUTPUT_DOCS_PATH = DEFAULT_DATA_OUTPUT_DIR / "candidate_negative_docs.jsonl"
DEFAULT_OUTPUT_SUMMARY_PATH = DEFAULT_LOG_OUTPUT_DIR / "summary.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare candidate negative documents for the quality classifier by "
            "sampling extracted text from Common Crawl WARC files and applying "
            "lightweight eligibility checks."
        )
    )
    parser.add_argument(
        "warc_paths",
        nargs="*",
        type=Path,
        help=(
            "Paths to input .warc or .warc.gz files. If omitted, defaults to the prepared "
            "Common Crawl sample file."
        ),
    )
    parser.add_argument(
        "--num-docs",
        type=int,
        default=5000,
        help="Final number of candidate negative documents to write.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Random seed for reproducible sampling.",
    )
    parser.add_argument(
        "--min-text-chars",
        type=int,
        default=200,
        help="Minimum extracted-text length required for a document to be eligible.",
    )
    parser.add_argument(
        "--required-language",
        type=str,
        default="en",
        help="Keep only documents whose top language-ID label matches this value.",
    )
    parser.add_argument(
        "--min-language-score",
        type=float,
        default=0.4,
        help="Minimum language-ID confidence required for eligible documents.",
    )
    parser.add_argument(
        "--output-docs-path",
        type=Path,
        default=DEFAULT_OUTPUT_DOCS_PATH,
        help=(
            "Path to the output JSONL file containing candidate negative documents. "
            "This should usually point to a data directory rather than a review-log directory."
        ),
    )
    parser.add_argument(
        "--output-summary-path",
        type=Path,
        default=DEFAULT_OUTPUT_SUMMARY_PATH,
        help="Path to the JSON summary describing the sampling and filtering process.",
    )
    return parser.parse_args()


def iter_response_records(warc_paths: list[Path]):
    for warc_path in warc_paths:
        if not warc_path.exists():
            raise FileNotFoundError(f"WARC path does not exist: {warc_path}")

        with warc_path.open("rb") as f:
            for record_index, record in enumerate(ArchiveIterator(f), start=1):
                if record.record_type != WarcRecordType.response:
                    continue

                uri = record.headers.get("WARC-Target-URI")
                html_bytes = record.reader.read()
                yield warc_path, record_index, uri, html_bytes


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")


def reservoir_sample_negative_documents(
    warc_paths: list[Path],
    *,
    num_docs: int,
    seed: int,
    min_text_chars: int,
    required_language: str,
    min_language_score: float,
) -> tuple[list[dict[str, object]], dict[str, int]]:
    rng = random.Random(seed)
    reservoir: list[dict[str, object]] = []

    stats = {
        "num_response_records": 0,
        "num_extraction_failures": 0,
        "num_empty_or_short_text": 0,
        "num_language_filtered_out": 0,
        "num_eligible_documents": 0,
        "num_eligible_passing_gopher_filter": 0,
        "num_eligible_failing_gopher_filter": 0,
    }

    for warc_path, record_index, uri, html_bytes in iter_response_records(warc_paths):
        stats["num_response_records"] += 1

        try:
            extracted_text = extract_text_from_html_bytes(html_bytes)
        except Exception:
            stats["num_extraction_failures"] += 1
            continue

        if len(extracted_text.strip()) < min_text_chars:
            stats["num_empty_or_short_text"] += 1
            continue

        language_label, language_score = identify_language(extracted_text)
        if language_label != required_language or language_score < min_language_score:
            stats["num_language_filtered_out"] += 1
            continue

        stats["num_eligible_documents"] += 1

        passes_gopher_filter = passes_gopher_quality_filters(extracted_text)
        if passes_gopher_filter:
            stats["num_eligible_passing_gopher_filter"] += 1
        else:
            stats["num_eligible_failing_gopher_filter"] += 1

        doc = {
            "source_warc_path": str(warc_path),
            "record_index": record_index,
            "target_uri": uri,
            "language_label": language_label,
            "language_score": language_score,
            "passes_gopher_filter": passes_gopher_filter,
            "extracted_text": extracted_text,
        }

        if len(reservoir) < num_docs:
            reservoir.append(doc)
            continue

        draw = rng.randint(1, stats["num_eligible_documents"])
        if draw <= num_docs:
            reservoir[draw - 1] = doc

    return reservoir, stats


def main() -> None:
    args = parse_args()

    warc_paths = args.warc_paths or [DEFAULT_WARC_PATH]
    num_docs: int = args.num_docs
    seed: int = args.seed
    min_text_chars: int = args.min_text_chars
    required_language: str = args.required_language
    min_language_score: float = args.min_language_score
    output_docs_path: Path = args.output_docs_path
    output_summary_path: Path = args.output_summary_path

    if num_docs <= 0:
        raise ValueError("--num-docs must be positive.")
    if min_text_chars <= 0:
        raise ValueError("--min-text-chars must be positive.")
    if not 0.0 <= min_language_score <= 1.0:
        raise ValueError("--min-language-score must lie in [0, 1].")

    sampled_docs, stats = reservoir_sample_negative_documents(
        warc_paths=warc_paths,
        num_docs=num_docs,
        seed=seed,
        min_text_chars=min_text_chars,
        required_language=required_language,
        min_language_score=min_language_score,
    )

    if not sampled_docs:
        raise RuntimeError("No eligible negative documents survived sampling.")

    sampled_docs.sort(key=lambda doc: (str(doc["source_warc_path"]), int(doc["record_index"])))
    write_jsonl(output_docs_path, sampled_docs)
    output_docs_size_bytes = output_docs_path.stat().st_size

    num_eligible = stats["num_eligible_documents"]
    summary = {
        "warc_paths": [str(path) for path in warc_paths],
        "required_language": required_language,
        "min_language_score": min_language_score,
        "num_docs_requested": num_docs,
        "num_docs_returned": len(sampled_docs),
        "output_docs_path": str(output_docs_path),
        "output_docs_size_bytes": output_docs_size_bytes,
        "seed": seed,
        "min_text_chars": min_text_chars,
        **stats,
        "fractions": {
            "language_filtered_fraction": stats["num_language_filtered_out"] / stats["num_response_records"]
            if stats["num_response_records"]
            else 0.0,
            "eligible_fraction": num_eligible / stats["num_response_records"]
            if stats["num_response_records"]
            else 0.0,
            "eligible_passing_gopher_fraction": stats["num_eligible_passing_gopher_filter"] / num_eligible
            if num_eligible
            else 0.0,
        },
        "sample_preview": [
            {
                "target_uri": doc["target_uri"],
                "language_label": doc["language_label"],
                "language_score": doc["language_score"],
                "passes_gopher_filter": doc["passes_gopher_filter"],
                "text_preview": doc["extracted_text"][:200],
            }
            for doc in sampled_docs[:5]
        ],
    }

    output_summary_path.parent.mkdir(parents=True, exist_ok=True)
    output_summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print(f"Wrote {output_docs_path}")
    print(f"Wrote {output_summary_path}")
    print(
        "Sampling stats: "
        f"{stats['num_response_records']} response records, "
        f"{stats['num_eligible_documents']} eligible negatives, "
        f"{len(sampled_docs)} sampled outputs"
    )
    print(
        "Eligibility checks: "
        f"{stats['num_extraction_failures']} extraction failures, "
        f"{stats['num_empty_or_short_text']} too-short texts, "
        f"{stats['num_language_filtered_out']} language-filtered documents"
    )


if __name__ == "__main__":
    main()
