from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from fastwarc.warc import ArchiveIterator, WarcRecordType

from cs336_data.html_text import extract_text_from_html_bytes
from cs336_data.pii import (
    EMAIL_PATTERN,
    IP_PATTERN,
    PHONE_PATTERN,
    mask_emails,
    mask_ips,
    mask_phone_numbers,
)


DEFAULT_WARC_PATH = Path("data/raw/cc_samples/example.warc.gz")
DEFAULT_OUTPUT_DIR = Path("runs/pii_audit")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Randomly sample extracted documents that trigger at least one PII mask, "
            "and write review-friendly artifacts for manual false-positive/false-negative auditing."
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
        help="Number of random documents with at least one replacement to sample.",
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
        help="Directory where the review artifacts will be written.",
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


def gather_matches(text: str) -> dict[str, list[str]]:
    return {
        "emails": [match.group(0) for match in EMAIL_PATTERN.finditer(text)],
        "phone_numbers": [match.group(0) for match in PHONE_PATTERN.finditer(text)],
        "ip_addresses": [match.group(0) for match in IP_PATTERN.finditer(text)],
    }


def apply_all_masks(text: str) -> tuple[str, dict[str, int], dict[str, list[str]]]:
    matches = gather_matches(text)

    masked_text, email_count = mask_emails(text)
    masked_text, phone_count = mask_phone_numbers(masked_text)
    masked_text, ip_count = mask_ips(masked_text)

    counts = {
        "emails": email_count,
        "phone_numbers": phone_count,
        "ip_addresses": ip_count,
        "total": email_count + phone_count + ip_count,
    }
    return masked_text, counts, matches


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
        "num_documents_with_any_mask": 0,
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
        masked_text, counts, matches = apply_all_masks(extracted_text)

        if counts["total"] <= 0:
            continue

        stats["num_documents_with_any_mask"] += 1
        doc = {
            "source_warc_path": str(warc_path),
            "record_index": record_index,
            "target_uri": uri,
            "original_text": extracted_text,
            "masked_text": masked_text,
            "matches": matches,
            "counts": counts,
        }

        if len(reservoir) < num_samples:
            reservoir.append(doc)
            continue

        draw = rng.randint(1, stats["num_documents_with_any_mask"])
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
        raise RuntimeError("No documents with PII replacements were found.")

    sampled_docs.sort(key=lambda doc: (str(doc["source_warc_path"]), int(doc["record_index"])))

    sample_rows: list[dict[str, object]] = []

    for sample_id, doc in enumerate(sampled_docs, start=1):
        counts = dict(doc["counts"])
        matches = dict(doc["matches"])
        sample_rows.append(
            {
                "sample_id": sample_id,
                "source_warc_path": doc["source_warc_path"],
                "record_index": doc["record_index"],
                "target_uri": doc["target_uri"],
                "counts": counts,
                "matches": matches,
                "original_text": doc["original_text"],
                "masked_text": doc["masked_text"],
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    samples_path = output_dir / "samples.jsonl"
    summary_path = output_dir / "summary.json"

    write_jsonl(samples_path, sample_rows)
    summary = {
        "warc_paths": [str(path) for path in warc_paths],
        "num_samples_requested": num_samples,
        "num_samples_returned": len(sample_rows),
        "seed": seed,
        "min_text_chars": min_text_chars,
        **stats,
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Wrote {samples_path}")
    print(f"Wrote {summary_path}")
    print(
        "Sampling stats: "
        f"{stats['num_response_records']} response records, "
        f"{stats['num_eligible_documents']} eligible documents, "
        f"{stats['num_documents_with_any_mask']} documents with at least one mask, "
        f"{stats['num_extraction_failures']} extraction failures, "
        f"{stats['num_empty_or_short_text']} empty/short documents"
    )
    print(f"Returned {len(sample_rows)} sampled documents with seed={seed}")


if __name__ == "__main__":
    main()
