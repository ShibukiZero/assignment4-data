from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from fastwarc.warc import ArchiveIterator, WarcRecordType

from cs336_data.html_text import extract_text_from_html_bytes
from cs336_data.langid import identify_language


DEFAULT_WARC_PATH = Path("data/raw/cc_samples/example.warc.gz")
DEFAULT_OUTPUT_DIR = Path("runs/langid_audit")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Randomly sample extracted documents from one or more WARC files and write "
            "separate artifacts for manual language review and classifier predictions."
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
        doc = {
            "source_warc_path": str(warc_path),
            "record_index": record_index,
            "target_uri": uri,
            "extracted_text": extracted_text,
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
        text = str(doc["extracted_text"])
        predicted_language, confidence = identify_language(text)

        samples_rows.append(
            {
                "sample_id": sample_id,
                "source_warc_path": doc["source_warc_path"],
                "record_index": doc["record_index"],
                "target_uri": doc["target_uri"],
                "extracted_text": text,
            }
        )
        prediction_rows.append(
            {
                "sample_id": sample_id,
                "source_warc_path": doc["source_warc_path"],
                "record_index": doc["record_index"],
                "target_uri": doc["target_uri"],
                "predicted_language": predicted_language,
                "confidence": confidence,
            }
        )

    samples_path = output_dir / "samples.jsonl"
    predictions_path = output_dir / "predictions.jsonl"

    write_jsonl(samples_path, samples_rows)
    write_jsonl(predictions_path, prediction_rows)

    print(f"Wrote {samples_path}")
    print(f"Wrote {predictions_path}")
    print(
        "Sampling stats: "
        f"{stats['num_response_records']} response records, "
        f"{stats['num_eligible_documents']} eligible documents, "
        f"{stats['num_extraction_failures']} extraction failures, "
        f"{stats['num_empty_or_short_text']} empty/short documents"
    )
    print(f"Returned {len(samples_rows)} sampled documents with seed={seed}")


if __name__ == "__main__":
    main()
