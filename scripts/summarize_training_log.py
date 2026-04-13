from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


EVAL_RE = re.compile(r"Estimated validation loss:\s*([0-9.eE+-]+)")
FINAL_RE = re.compile(r"Final estimated validation loss:\s*([0-9.eE+-]+)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract validation-loss points from the provided training log and write "
            "a compact JSON/Markdown summary for the assignment writeup."
        )
    )
    parser.add_argument("log_path", type=Path, help="Path to the training log written by run_training_your_data.sh.")
    parser.add_argument("--eval-interval", type=int, default=2_000, help="Training steps between validation runs.")
    parser.add_argument("--train-steps", type=int, default=100_000, help="Final training step count.")
    parser.add_argument("--output-json", type=Path, default=None, help="Optional JSON output path.")
    parser.add_argument("--output-md", type=Path, default=None, help="Optional Markdown output path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.eval_interval <= 0:
        raise ValueError("--eval-interval must be positive.")
    if args.train_steps <= 0:
        raise ValueError("--train-steps must be positive.")

    eval_losses: list[float] = []
    final_loss: float | None = None
    for line in args.log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        eval_match = EVAL_RE.search(line)
        if eval_match:
            eval_losses.append(float(eval_match.group(1)))
            continue

        final_match = FINAL_RE.search(line)
        if final_match:
            final_loss = float(final_match.group(1))

    points = [
        {"step": (idx + 1) * args.eval_interval, "validation_loss": loss}
        for idx, loss in enumerate(eval_losses)
    ]
    if final_loss is not None:
        points.append({"step": args.train_steps, "validation_loss": final_loss})

    if not points:
        raise ValueError(f"No validation-loss lines found in {args.log_path}.")

    best = min(points, key=lambda point: point["validation_loss"])
    summary = {
        "log_path": str(args.log_path),
        "eval_interval": args.eval_interval,
        "train_steps": args.train_steps,
        "num_points": len(points),
        "best": best,
        "points": points,
    }

    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    if args.output_md is not None:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        rows = [
            "# Training Validation Loss Summary",
            "",
            f"- Log path: `{args.log_path}`",
            f"- Best validation loss: `{best['validation_loss']}` at step `{best['step']}`",
            f"- Number of validation points: `{len(points)}`",
            "",
            "| Step | Validation loss |",
            "| --- | --- |",
        ]
        rows.extend(f"| {point['step']} | {point['validation_loss']} |" for point in points)
        args.output_md.write_text("\n".join(rows) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
