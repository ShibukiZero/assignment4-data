from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from fastwarc.warc import ArchiveIterator, WarcRecordType

from cs336_data.html_text import extract_text_from_html_bytes
from cs336_data.quality import (
    MAX_ELLIPSIS_LINE_FRACTION,
    MAX_MEAN_WORD_LENGTH,
    MAX_WORDS,
    MIN_ALPHABETIC_WORD_FRACTION,
    MIN_MEAN_WORD_LENGTH,
    MIN_WORDS,
    extract_word_like_tokens,
    fraction_of_lines_ending_with_ellipsis,
    fraction_of_words_with_alphabetic_character,
    mean_word_length,
    passes_gopher_quality_filters,
)


DEFAULT_WARC_PATH = Path("data/raw/cc_samples/example.warc.gz")
DEFAULT_OUTPUT_DIR = Path("runs/gopher_quality_audit")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Randomly sample extracted documents from one or more WARC files and "
            "write Gopher-rule filter outputs for manual quality auditing."
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
        "--num-samples",
        type=int,
        default=20,
        help="Number of random non-empty extracted documents to sample.",
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
        default=1,
        help="Minimum extracted-text length required for a document to be eligible.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where the sample and prediction files will be written.",
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


def compute_quality_diagnostics(text: str) -> dict[str, object]:
    words = extract_word_like_tokens(text)
    word_count = len(words)
    average_word_length = mean_word_length(words)
    ellipsis_line_fraction = fraction_of_lines_ending_with_ellipsis(text)
    alphabetic_word_fraction = fraction_of_words_with_alphabetic_character(words)
    passes = passes_gopher_quality_filters(text)

    return {
        "passes_gopher_filter": passes,
        "word_count": word_count,
        "mean_word_length": average_word_length,
        "ellipsis_line_fraction": ellipsis_line_fraction,
        "alphabetic_word_fraction": alphabetic_word_fraction,
        "rule_thresholds": {
            "min_words": MIN_WORDS,
            "max_words": MAX_WORDS,
            "min_mean_word_length": MIN_MEAN_WORD_LENGTH,
            "max_mean_word_length": MAX_MEAN_WORD_LENGTH,
            "max_ellipsis_line_fraction": MAX_ELLIPSIS_LINE_FRACTION,
            "min_alphabetic_word_fraction": MIN_ALPHABETIC_WORD_FRACTION,
        },
        "failed_rules": {
            "word_count_too_small": word_count < MIN_WORDS,
            "word_count_too_large": word_count > MAX_WORDS,
            "mean_word_length_too_small": average_word_length < MIN_MEAN_WORD_LENGTH,
            "mean_word_length_too_large": average_word_length > MAX_MEAN_WORD_LENGTH,
            "ellipsis_fraction_too_high": ellipsis_line_fraction > MAX_ELLIPSIS_LINE_FRACTION,
            "alphabetic_fraction_too_low": alphabetic_word_fraction < MIN_ALPHABETIC_WORD_FRACTION,
        },
    }


def reservoir_sample_documents(
    warc_paths: list[Path], num_samples: int, seed: int, min_text_chars: int
) -> tuple[list[dict[str, object]], dict[str, int]]:
    rng = random.Random(seed)
    reservoir: list[dict[str, object]] = []

    stats = {
        "num_response_records": 0,
        "num_extraction_failures": 0,
        "num_empty_or_short_text": 0,
        "num_eligible_documents": 0,
        "num_documents_passing_filter": 0,
        "num_documents_rejected_by_filter": 0,
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

        stats["num_eligible_documents"] += 1
        diagnostics = compute_quality_diagnostics(extracted_text)

        if diagnostics["passes_gopher_filter"]:
            stats["num_documents_passing_filter"] += 1
        else:
            stats["num_documents_rejected_by_filter"] += 1

        doc = {
            "source_warc_path": str(warc_path),
            "record_index": record_index,
            "target_uri": uri,
            "extracted_text": extracted_text,
            "diagnostics": diagnostics,
        }

        if len(reservoir) < num_samples:
            reservoir.append(doc)
            continue

        draw = rng.randint(1, stats["num_eligible_documents"])
        if draw <= num_samples:
            reservoir[draw - 1] = doc

    return reservoir, stats


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")


def main() -> None:
    args = parse_args()

    warc_paths = args.warc_paths or [DEFAULT_WARC_PATH]
    num_samples: int = args.num_samples
    seed: int = args.seed
    min_text_chars: int = args.min_text_chars
    output_dir: Path = args.output_dir

    if num_samples <= 0:
        raise ValueError("--num-samples must be positive.")

    sampled_docs, stats = reservoir_sample_documents(
        warc_paths=warc_paths,
        num_samples=num_samples,
        seed=seed,
        min_text_chars=min_text_chars,
    )

    if not sampled_docs:
        raise RuntimeError("No eligible documents were found for sampling.")

    sampled_docs.sort(key=lambda doc: (str(doc["source_warc_path"]), int(doc["record_index"])))

    samples_rows: list[dict[str, object]] = []
    prediction_rows: list[dict[str, object]] = []

    for sample_id, doc in enumerate(sampled_docs, start=1):
        diagnostics = dict(doc["diagnostics"])
        samples_rows.append(
            {
                "sample_id": sample_id,
                "source_warc_path": doc["source_warc_path"],
                "record_index": doc["record_index"],
                "target_uri": doc["target_uri"],
                "extracted_text": doc["extracted_text"],
            }
        )
        prediction_rows.append(
            {
                "sample_id": sample_id,
                "source_warc_path": doc["source_warc_path"],
                "record_index": doc["record_index"],
                "target_uri": doc["target_uri"],
                **diagnostics,
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    samples_path = output_dir / "samples.jsonl"
    predictions_path = output_dir / "predictions.jsonl"
    summary_path = output_dir / "summary.json"

    write_jsonl(samples_path, samples_rows)
    write_jsonl(predictions_path, prediction_rows)

    num_eligible = stats["num_eligible_documents"]
    summary = {
        "warc_paths": [str(path) for path in warc_paths],
        "num_samples_requested": num_samples,
        "num_samples_returned": len(samples_rows),
        "seed": seed,
        "min_text_chars": min_text_chars,
        **stats,
        "fractions": {
            "pass_fraction": stats["num_documents_passing_filter"] / num_eligible if num_eligible else 0.0,
            "reject_fraction": stats["num_documents_rejected_by_filter"] / num_eligible if num_eligible else 0.0,
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Wrote {samples_path}")
    print(f"Wrote {predictions_path}")
    print(f"Wrote {summary_path}")
    print(
        "Sampling stats: "
        f"{stats['num_response_records']} response records, "
        f"{stats['num_eligible_documents']} eligible documents, "
        f"{stats['num_extraction_failures']} extraction failures, "
        f"{stats['num_empty_or_short_text']} empty/short documents"
    )
    print(
        "Filter stats: "
        f"{stats['num_documents_passing_filter']} passed, "
        f"{stats['num_documents_rejected_by_filter']} rejected"
    )
    print(f"Returned {len(samples_rows)} sampled documents with seed={seed}")


if __name__ == "__main__":
    main()
