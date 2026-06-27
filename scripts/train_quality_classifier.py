from __future__ import annotations

import argparse
import json
from pathlib import Path

import fasttext


DEFAULT_DATASET_DIR = Path("data/quality_classifier/datasets")
DEFAULT_MODEL_DIR = Path("models")
DEFAULT_LOG_DIR = Path("runs/quality_classifier_training")

DEFAULT_TRAIN_PATH = DEFAULT_DATASET_DIR / "fasttext_quality_train.txt"
DEFAULT_DEV_PATH = DEFAULT_DATASET_DIR / "fasttext_quality_dev.txt"
DEFAULT_MODEL_PATH = DEFAULT_MODEL_DIR / "quality_classifier_fasttext.bin"
DEFAULT_SUMMARY_PATH = DEFAULT_LOG_DIR / "summary.json"
DEFAULT_DEV_PREDICTIONS_PATH = DEFAULT_MODEL_DIR / "quality_dev_predictions.jsonl"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Train a fastText quality classifier on the assembled wiki-vs-cc "
            "dataset and evaluate it on the held-out dev split."
        )
    )
    parser.add_argument(
        "--train-path",
        type=Path,
        default=DEFAULT_TRAIN_PATH,
        help="Path to the fastText training file.",
    )
    parser.add_argument(
        "--dev-path",
        type=Path,
        default=DEFAULT_DEV_PATH,
        help="Path to the fastText development file.",
    )
    parser.add_argument(
        "--model-path",
        type=Path,
        default=DEFAULT_MODEL_PATH,
        help="Path where the trained fastText model will be saved.",
    )
    parser.add_argument(
        "--summary-path",
        type=Path,
        default=DEFAULT_SUMMARY_PATH,
        help="Path to the compact JSON summary for this training run.",
    )
    parser.add_argument(
        "--dev-predictions-path",
        type=Path,
        default=DEFAULT_DEV_PREDICTIONS_PATH,
        help="Path to the JSONL file containing per-example dev predictions.",
    )
    parser.add_argument("--lr", type=float, default=0.5, help="fastText learning rate.")
    parser.add_argument("--epoch", type=int, default=25, help="Number of fastText epochs.")
    parser.add_argument("--wordNgrams", type=int, default=2, help="Maximum word n-gram size.")
    parser.add_argument("--dim", type=int, default=100, help="Embedding dimension.")
    parser.add_argument("--bucket", type=int, default=200000, help="fastText hashing bucket size.")
    parser.add_argument("--minCount", type=int, default=1, help="Minimum token count.")
    parser.add_argument("--loss", type=str, default="softmax", help="fastText loss name.")
    return parser.parse_args()


def normalize_label(label: str) -> str:
    if label.startswith("__label__"):
        return label.removeprefix("__label__")
    return label


def parse_fasttext_line(line: str) -> tuple[str, str]:
    stripped = line.rstrip("\n")
    if not stripped:
        raise ValueError("Encountered an empty fastText line.")

    first_space = stripped.find(" ")
    if first_space == -1:
        raise ValueError(f"Malformed fastText line without text payload: {stripped!r}")

    label = stripped[:first_space]
    text = stripped[first_space + 1 :]
    return normalize_label(label), text


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")


def evaluate_on_dev(
    model: fasttext.FastText._FastText,
    dev_path: Path,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    if not dev_path.exists():
        raise FileNotFoundError(f"Dev file does not exist: {dev_path}")

    prediction_rows: list[dict[str, object]] = []
    correct = 0
    total = 0
    per_label = {
        "wiki": {"gold": 0, "predicted": 0, "correct": 0},
        "cc": {"gold": 0, "predicted": 0, "correct": 0},
    }

    with dev_path.open("r", encoding="utf-8") as f:
        for index, line in enumerate(f, start=1):
            if not line.strip():
                continue

            gold_label, text = parse_fasttext_line(line)
            predicted_labels, scores = model.predict(text, k=1)
            predicted_label = normalize_label(predicted_labels[0])
            confidence = float(scores[0])

            total += 1
            per_label.setdefault(gold_label, {"gold": 0, "predicted": 0, "correct": 0})
            per_label.setdefault(predicted_label, {"gold": 0, "predicted": 0, "correct": 0})
            per_label[gold_label]["gold"] += 1
            per_label[predicted_label]["predicted"] += 1

            is_correct = predicted_label == gold_label
            if is_correct:
                correct += 1
                per_label[gold_label]["correct"] += 1

            prediction_rows.append(
                {
                    "dev_index": index,
                    "gold_label": gold_label,
                    "predicted_label": predicted_label,
                    "confidence": confidence,
                    "is_correct": is_correct,
                    "text_preview": text[:200],
                }
            )

    accuracy = correct / total if total else 0.0
    label_metrics: dict[str, dict[str, float | int]] = {}
    for label, counts in per_label.items():
        precision = counts["correct"] / counts["predicted"] if counts["predicted"] else 0.0
        recall = counts["correct"] / counts["gold"] if counts["gold"] else 0.0
        label_metrics[label] = {
            "gold": counts["gold"],
            "predicted": counts["predicted"],
            "correct": counts["correct"],
            "precision": precision,
            "recall": recall,
        }

    return prediction_rows, {
        "num_dev_examples": total,
        "num_correct": correct,
        "accuracy": accuracy,
        "label_metrics": label_metrics,
    }


def main() -> None:
    args = parse_args()

    if not args.train_path.exists():
        raise FileNotFoundError(f"Training file does not exist: {args.train_path}")
    if not args.dev_path.exists():
        raise FileNotFoundError(f"Dev file does not exist: {args.dev_path}")

    args.model_path.parent.mkdir(parents=True, exist_ok=True)
    args.summary_path.parent.mkdir(parents=True, exist_ok=True)
    args.dev_predictions_path.parent.mkdir(parents=True, exist_ok=True)

    model = fasttext.train_supervised(
        input=str(args.train_path),
        lr=args.lr,
        epoch=args.epoch,
        wordNgrams=args.wordNgrams,
        dim=args.dim,
        bucket=args.bucket,
        minCount=args.minCount,
        loss=args.loss,
    )
    model.save_model(str(args.model_path))

    fasttext_test = model.test(str(args.dev_path))
    prediction_rows, custom_metrics = evaluate_on_dev(model, args.dev_path)
    write_jsonl(args.dev_predictions_path, prediction_rows)

    summary = {
        "train_path": str(args.train_path),
        "dev_path": str(args.dev_path),
        "model_path": str(args.model_path),
        "dev_predictions_path": str(args.dev_predictions_path),
        "hyperparameters": {
            "lr": args.lr,
            "epoch": args.epoch,
            "wordNgrams": args.wordNgrams,
            "dim": args.dim,
            "bucket": args.bucket,
            "minCount": args.minCount,
            "loss": args.loss,
        },
        "fasttext_test_metrics": {
            "num_examples": fasttext_test[0],
            "precision_at_1": fasttext_test[1],
            "recall_at_1": fasttext_test[2],
        },
        "custom_dev_metrics": custom_metrics,
        "model_size_bytes": args.model_path.stat().st_size,
        "dev_predictions_size_bytes": args.dev_predictions_path.stat().st_size,
        "prediction_preview": prediction_rows[:10],
    }
    args.summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print(f"Saved model to {args.model_path}")
    print(f"Wrote dev predictions to {args.dev_predictions_path}")
    print(f"Wrote summary to {args.summary_path}")
    print(
        "Dev metrics: "
        f"{custom_metrics['num_correct']} / {custom_metrics['num_dev_examples']} correct "
        f"({custom_metrics['accuracy']:.4f} accuracy)"
    )


if __name__ == "__main__":
    main()
