from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from cs336_data.langid import normalize_text_for_fasttext


DEFAULT_POSITIVE_DOCS_PATH = Path("/root/autodl-tmp/quality_classifier/positives/candidate_positive_docs.jsonl")
DEFAULT_NEGATIVE_DOCS_PATH = Path("/root/autodl-tmp/quality_classifier/negatives/candidate_negative_docs.jsonl")
DEFAULT_DATA_OUTPUT_DIR = Path("/root/autodl-tmp/quality_classifier/datasets")
DEFAULT_LOG_OUTPUT_DIR = Path(".agents/logs/quality_classifier_dataset")
DEFAULT_TRAIN_PATH = DEFAULT_DATA_OUTPUT_DIR / "fasttext_quality_train.txt"
DEFAULT_DEV_PATH = DEFAULT_DATA_OUTPUT_DIR / "fasttext_quality_dev.txt"
DEFAULT_DEV_RECORDS_PATH = DEFAULT_DATA_OUTPUT_DIR / "quality_dev_records.jsonl"
DEFAULT_SUMMARY_PATH = DEFAULT_LOG_OUTPUT_DIR / "summary.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Assemble balanced fastText train/dev files for the quality classifier "
            "from the prepared positive and negative candidate pools."
        )
    )
    parser.add_argument(
        "--positive-docs-path",
        type=Path,
        default=DEFAULT_POSITIVE_DOCS_PATH,
        help="Path to the accepted positive candidate documents JSONL file.",
    )
    parser.add_argument(
        "--negative-docs-path",
        type=Path,
        default=DEFAULT_NEGATIVE_DOCS_PATH,
        help="Path to the candidate negative documents JSONL file.",
    )
    parser.add_argument(
        "--train-output-path",
        type=Path,
        default=DEFAULT_TRAIN_PATH,
        help="Path to the output fastText training file.",
    )
    parser.add_argument(
        "--dev-output-path",
        type=Path,
        default=DEFAULT_DEV_PATH,
        help="Path to the output fastText development file.",
    )
    parser.add_argument(
        "--dev-records-path",
        type=Path,
        default=DEFAULT_DEV_RECORDS_PATH,
        help="Path to the JSONL file with dev-set metadata and text for auditing.",
    )
    parser.add_argument(
        "--summary-path",
        type=Path,
        default=DEFAULT_SUMMARY_PATH,
        help="Path to the compact JSON summary for this dataset assembly run.",
    )
    parser.add_argument(
        "--dev-fraction",
        type=float,
        default=0.1,
        help="Fraction of each class to reserve for the dev split.",
    )
    parser.add_argument(
        "--negatives-per-positive",
        type=float,
        default=1.0,
        help="Number of negative examples to sample for each retained positive example.",
    )
    parser.add_argument(
        "--min-text-chars",
        type=int,
        default=200,
        help="Minimum normalized text length required for a row to be kept.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Random seed for reproducible dataset sampling and splitting.",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if not 0.0 < args.dev_fraction < 1.0:
        raise ValueError("--dev-fraction must lie strictly between 0 and 1.")
    if args.negatives_per_positive <= 0:
        raise ValueError("--negatives-per-positive must be positive.")
    if args.min_text_chars <= 0:
        raise ValueError("--min-text-chars must be positive.")


def pick_source_url(row: dict[str, object], default_keys: list[str]) -> str | None:
    for key in default_keys:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def load_candidate_examples(
    path: Path,
    *,
    label: str,
    url_keys: list[str],
    min_text_chars: int,
) -> tuple[list[dict[str, object]], dict[str, int]]:
    if not path.exists():
        raise FileNotFoundError(f"Input candidate file does not exist: {path}")

    stats = {
        "num_input_rows": 0,
        "num_empty_text_rows": 0,
        "num_too_short_rows": 0,
        "num_duplicate_text_rows": 0,
        "num_kept_rows": 0,
    }

    examples: list[dict[str, object]] = []
    seen_texts: set[str] = set()

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            row = json.loads(line)
            stats["num_input_rows"] += 1

            text_value = row.get("extracted_text")
            if not isinstance(text_value, str):
                stats["num_empty_text_rows"] += 1
                continue

            normalized_text = normalize_text_for_fasttext(text_value)
            if not normalized_text:
                stats["num_empty_text_rows"] += 1
                continue

            if len(normalized_text) < min_text_chars:
                stats["num_too_short_rows"] += 1
                continue

            if normalized_text in seen_texts:
                stats["num_duplicate_text_rows"] += 1
                continue

            seen_texts.add(normalized_text)
            source_url = pick_source_url(row, url_keys)

            examples.append(
                {
                    "label": label,
                    "source_url": source_url,
                    "text": normalized_text,
                }
            )
            stats["num_kept_rows"] += 1

    return examples, stats


def drop_cross_class_duplicates(
    positives: list[dict[str, object]],
    negatives: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, int]]:
    positive_texts = {row["text"] for row in positives}
    filtered_negatives = [row for row in negatives if row["text"] not in positive_texts]

    stats = {
        "num_cross_class_duplicates_removed_from_negatives": len(negatives) - len(filtered_negatives),
    }
    return positives, filtered_negatives, stats


def sample_balanced_examples(
    positives: list[dict[str, object]],
    negatives: list[dict[str, object]],
    *,
    negatives_per_positive: float,
    seed: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, int]]:
    rng = random.Random(seed)

    if not positives:
        raise RuntimeError("No positive examples are available after preprocessing.")
    if not negatives:
        raise RuntimeError("No negative examples are available after preprocessing.")

    num_positive = len(positives)
    target_negative = min(len(negatives), max(1, int(round(num_positive * negatives_per_positive))))

    sampled_positives = list(positives)
    sampled_negatives = list(negatives)
    rng.shuffle(sampled_negatives)
    sampled_negatives = sampled_negatives[:target_negative]

    stats = {
        "num_sampled_positive_examples": len(sampled_positives),
        "num_sampled_negative_examples": len(sampled_negatives),
    }
    return sampled_positives, sampled_negatives, stats


def split_examples(
    rows: list[dict[str, object]],
    *,
    dev_fraction: float,
    seed: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    rng = random.Random(seed)
    shuffled = list(rows)
    rng.shuffle(shuffled)

    if len(shuffled) == 1:
        return shuffled, []

    dev_count = max(1, int(round(len(shuffled) * dev_fraction)))
    dev_count = min(dev_count, len(shuffled) - 1)

    dev_rows = shuffled[:dev_count]
    train_rows = shuffled[dev_count:]
    return train_rows, dev_rows


def write_fasttext_file(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(f"__label__{row['label']} {row['text']}\n")


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")


def main() -> None:
    args = parse_args()
    validate_args(args)

    positive_examples, positive_stats = load_candidate_examples(
        args.positive_docs_path,
        label="wiki",
        url_keys=["final_url", "input_url"],
        min_text_chars=args.min_text_chars,
    )
    negative_examples, negative_stats = load_candidate_examples(
        args.negative_docs_path,
        label="cc",
        url_keys=["target_uri", "source_url"],
        min_text_chars=args.min_text_chars,
    )

    positive_examples, negative_examples, overlap_stats = drop_cross_class_duplicates(
        positive_examples,
        negative_examples,
    )
    sampled_positives, sampled_negatives, sample_stats = sample_balanced_examples(
        positive_examples,
        negative_examples,
        negatives_per_positive=args.negatives_per_positive,
        seed=args.seed,
    )

    positive_train, positive_dev = split_examples(
        sampled_positives,
        dev_fraction=args.dev_fraction,
        seed=args.seed,
    )
    negative_train, negative_dev = split_examples(
        sampled_negatives,
        dev_fraction=args.dev_fraction,
        seed=args.seed + 1,
    )

    train_rows = list(positive_train) + list(negative_train)
    dev_rows = list(positive_dev) + list(negative_dev)

    rng = random.Random(args.seed + 2)
    rng.shuffle(train_rows)
    rng.shuffle(dev_rows)

    write_fasttext_file(args.train_output_path, train_rows)
    write_fasttext_file(args.dev_output_path, dev_rows)

    dev_record_rows = [
        {
            "label": row["label"],
            "source_url": row["source_url"],
            "text": row["text"],
        }
        for row in dev_rows
    ]
    write_jsonl(args.dev_records_path, dev_record_rows)

    summary = {
        "positive_docs_path": str(args.positive_docs_path),
        "negative_docs_path": str(args.negative_docs_path),
        "train_output_path": str(args.train_output_path),
        "dev_output_path": str(args.dev_output_path),
        "dev_records_path": str(args.dev_records_path),
        "dev_fraction": args.dev_fraction,
        "negatives_per_positive": args.negatives_per_positive,
        "min_text_chars": args.min_text_chars,
        "seed": args.seed,
        "positive_pool_stats": positive_stats,
        "negative_pool_stats": negative_stats,
        **overlap_stats,
        **sample_stats,
        "train_counts": {
            "wiki": len(positive_train),
            "cc": len(negative_train),
            "total": len(train_rows),
        },
        "dev_counts": {
            "wiki": len(positive_dev),
            "cc": len(negative_dev),
            "total": len(dev_rows),
        },
        "output_sizes_bytes": {
            "train": args.train_output_path.stat().st_size,
            "dev": args.dev_output_path.stat().st_size,
            "dev_records": args.dev_records_path.stat().st_size,
        },
        "dev_preview": [
            {
                "label": row["label"],
                "source_url": row["source_url"],
                "text_preview": row["text"][:200],
            }
            for row in dev_record_rows[:10]
        ],
    }
    args.summary_path.parent.mkdir(parents=True, exist_ok=True)
    args.summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print(f"Wrote {args.train_output_path}")
    print(f"Wrote {args.dev_output_path}")
    print(f"Wrote {args.dev_records_path}")
    print(f"Wrote {args.summary_path}")
    print(
        "Dataset stats: "
        f"{len(sampled_positives)} positives and {len(sampled_negatives)} negatives sampled; "
        f"{len(train_rows)} train rows, {len(dev_rows)} dev rows"
    )


if __name__ == "__main__":
    main()
