from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


DEFAULT_INPUT_DOCS_PATH = Path("data/quality_classifier/positives/candidate_positive_docs.jsonl")
DEFAULT_OUTPUT_DIR = Path("runs/quality_classifier_positive_pool_audit")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Randomly sample accepted positive candidates for manual quality audit."
        )
    )
    parser.add_argument(
        "--input-docs-path",
        type=Path,
        default=DEFAULT_INPUT_DOCS_PATH,
        help="Path to the JSONL file containing accepted positive candidate documents.",
    )
    parser.add_argument(
        "--num-samples",
        type=int,
        default=20,
        help="Number of positive candidate documents to sample.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Random seed for reproducible sampling.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where the sample and summary files will be written.",
    )
    return parser.parse_args()


def reservoir_sample_rows(
    input_docs_path: Path,
    *,
    num_samples: int,
    seed: int,
) -> tuple[list[dict[str, object]], dict[str, int]]:
    if not input_docs_path.exists():
        raise FileNotFoundError(f"Input docs path does not exist: {input_docs_path}")

    rng = random.Random(seed)
    reservoir: list[dict[str, object]] = []

    stats = {
        "num_input_rows": 0,
    }

    with input_docs_path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            row = json.loads(line)
            stats["num_input_rows"] += 1

            if len(reservoir) < num_samples:
                reservoir.append(row)
                continue

            draw = rng.randint(1, stats["num_input_rows"])
            if draw <= num_samples:
                reservoir[draw - 1] = row

    return reservoir, stats


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")


def main() -> None:
    args = parse_args()

    input_docs_path: Path = args.input_docs_path
    num_samples: int = args.num_samples
    seed: int = args.seed
    output_dir: Path = args.output_dir

    if num_samples <= 0:
        raise ValueError("--num-samples must be positive.")

    sampled_rows, stats = reservoir_sample_rows(
        input_docs_path,
        num_samples=num_samples,
        seed=seed,
    )

    if not sampled_rows:
        raise RuntimeError("No rows were available for sampling.")

    samples_rows: list[dict[str, object]] = []
    for sample_id, row in enumerate(sampled_rows, start=1):
        samples_rows.append(
            {
                "sample_id": sample_id,
                "input_url": row.get("input_url"),
                "final_url": row.get("final_url"),
                "http_status": row.get("http_status"),
                "content_type": row.get("content_type"),
                "downloaded_bytes": row.get("downloaded_bytes"),
                "language_label": row.get("language_label"),
                "language_score": row.get("language_score"),
                "passes_gopher_filter": row.get("passes_gopher_filter"),
                "extracted_text": row.get("extracted_text"),
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    samples_path = output_dir / "samples.jsonl"
    summary_path = output_dir / "summary.json"

    write_jsonl(samples_path, samples_rows)

    summary = {
        "input_docs_path": str(input_docs_path),
        "num_samples_requested": num_samples,
        "num_samples_returned": len(samples_rows),
        "seed": seed,
        **stats,
        "sample_preview_urls": [row["final_url"] for row in samples_rows[:10]],
    }
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print(f"Wrote {samples_path}")
    print(f"Wrote {summary_path}")
    print(
        f"Sampled {len(samples_rows)} rows from {stats['num_input_rows']} accepted positive candidates."
    )


if __name__ == "__main__":
    main()
