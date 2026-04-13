from __future__ import annotations

import argparse
import html
import json
import math
import re
from pathlib import Path
from statistics import fmean


TRAIN_LOSS_RE = re.compile(r"Training step\s+(\d+),\s+Loss:\s*([0-9.eE+-]+)")
ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Plot training loss, validation loss, and learning rate from a CS336 training log. "
            "The output is dependency-free SVG so it can run on the remote training machine "
            "without installing matplotlib."
        )
    )
    parser.add_argument("--training-log", type=Path, required=True, help="Path to the full training log.")
    parser.add_argument(
        "--validation-curve",
        type=Path,
        default=None,
        help="Optional validation_curve.json written by scripts/summarize_training_log.py.",
    )
    parser.add_argument("--output-svg", type=Path, required=True, help="Path for the SVG plot.")
    parser.add_argument(
        "--output-summary-json",
        type=Path,
        default=None,
        help="Optional path for a compact JSON summary of plotted data.",
    )
    parser.add_argument("--train-steps", type=int, default=100_000)
    parser.add_argument("--max-lr", type=float, default=1e-3)
    parser.add_argument("--min-lr", type=float, default=None)
    parser.add_argument("--warmup-ratio", type=float, default=0.01)
    parser.add_argument("--max-train-points", type=int, default=2_000)
    parser.add_argument("--title", default="Training Curves")
    return parser.parse_args()


def cosine_lr(
    step: int,
    *,
    max_learning_rate: float,
    min_learning_rate: float,
    warmup_iters: int,
    cosine_cycle_iters: int,
) -> float:
    if step < warmup_iters:
        return max_learning_rate * step / warmup_iters
    if step > cosine_cycle_iters:
        return min_learning_rate
    decay_ratio = (step - warmup_iters) / (cosine_cycle_iters - warmup_iters)
    coeff = 0.5 * (1.0 + math.cos(math.pi * decay_ratio))
    return min_learning_rate + coeff * (max_learning_rate - min_learning_rate)


def parse_train_loss(log_path: Path) -> list[tuple[int, float]]:
    # Tqdm writes carriage-return updates. Treating the whole log as text and using
    # finditer is more reliable than line-by-line parsing here.
    text = ANSI_RE.sub("", log_path.read_text(encoding="utf-8", errors="replace"))
    losses: dict[int, float] = {}
    for match in TRAIN_LOSS_RE.finditer(text):
        losses[int(match.group(1))] = float(match.group(2))
    return sorted(losses.items())


def parse_validation_loss(validation_curve_path: Path | None) -> tuple[list[tuple[int, float]], dict]:
    if validation_curve_path is None:
        return [], {}
    payload = json.loads(validation_curve_path.read_text(encoding="utf-8"))
    points = [(int(point["step"]), float(point["validation_loss"])) for point in payload["points"]]
    return points, payload


def downsample_average(points: list[tuple[int, float]], max_points: int) -> list[tuple[float, float]]:
    if len(points) <= max_points:
        return [(float(step), value) for step, value in points]
    bucket_size = math.ceil(len(points) / max_points)
    sampled: list[tuple[float, float]] = []
    for start in range(0, len(points), bucket_size):
        bucket = points[start : start + bucket_size]
        sampled.append((fmean(step for step, _ in bucket), fmean(value for _, value in bucket)))
    return sampled


def sample_lr(train_steps: int, *, max_lr: float, min_lr: float, warmup_ratio: float, max_points: int) -> list[tuple[float, float]]:
    warmup_iters = int(train_steps * warmup_ratio)
    if max_points >= train_steps:
        steps = range(train_steps + 1)
    else:
        steps = sorted({round(i * train_steps / max_points) for i in range(max_points + 1)})
    return [
        (
            float(step),
            cosine_lr(
                step,
                max_learning_rate=max_lr,
                min_learning_rate=min_lr,
                warmup_iters=warmup_iters,
                cosine_cycle_iters=train_steps,
            ),
        )
        for step in steps
    ]


def nice_ticks(vmin: float, vmax: float, count: int = 5) -> list[float]:
    if vmin == vmax:
        return [vmin]
    return [vmin + (vmax - vmin) * idx / (count - 1) for idx in range(count)]


class PlotArea:
    def __init__(self, x0: float, y0: float, width: float, height: float, x_min: float, x_max: float, y_min: float, y_max: float):
        self.x0 = x0
        self.y0 = y0
        self.width = width
        self.height = height
        self.x_min = x_min
        self.x_max = x_max
        self.y_min = y_min
        self.y_max = y_max

    def sx(self, x: float) -> float:
        return self.x0 + (x - self.x_min) / (self.x_max - self.x_min) * self.width

    def sy(self, y: float) -> float:
        return self.y0 + self.height - (y - self.y_min) / (self.y_max - self.y_min) * self.height


def polyline(points: list[tuple[float, float]], area: PlotArea) -> str:
    encoded = " ".join(f"{area.sx(x):.2f},{area.sy(y):.2f}" for x, y in points)
    return encoded


def render_axes(area: PlotArea, *, title: str, y_label: str, x_label: str | None = None) -> list[str]:
    parts = [
        f'<rect x="{area.x0}" y="{area.y0}" width="{area.width}" height="{area.height}" fill="#fbfaf6" stroke="#2b2a27" stroke-width="1"/>',
        f'<text x="{area.x0}" y="{area.y0 - 18}" class="panel-title">{html.escape(title)}</text>',
        f'<text x="{area.x0 - 54}" y="{area.y0 + area.height / 2}" class="axis-label" transform="rotate(-90 {area.x0 - 54} {area.y0 + area.height / 2})">{html.escape(y_label)}</text>',
    ]
    if x_label is not None:
        parts.append(f'<text x="{area.x0 + area.width / 2}" y="{area.y0 + area.height + 48}" class="axis-label" text-anchor="middle">{html.escape(x_label)}</text>')

    for tick in nice_ticks(area.x_min, area.x_max):
        x = area.sx(tick)
        parts.append(f'<line x1="{x:.2f}" y1="{area.y0}" x2="{x:.2f}" y2="{area.y0 + area.height}" class="grid"/>')
        parts.append(f'<text x="{x:.2f}" y="{area.y0 + area.height + 20}" class="tick" text-anchor="middle">{tick / 1000:.0f}k</text>')
    for tick in nice_ticks(area.y_min, area.y_max):
        y = area.sy(tick)
        parts.append(f'<line x1="{area.x0}" y1="{y:.2f}" x2="{area.x0 + area.width}" y2="{y:.2f}" class="grid"/>')
        parts.append(f'<text x="{area.x0 - 10}" y="{y + 4:.2f}" class="tick" text-anchor="end">{tick:.4g}</text>')
    return parts


def render_svg(
    *,
    train_points: list[tuple[float, float]],
    val_points: list[tuple[float, float]],
    lr_points: list[tuple[float, float]],
    train_steps: int,
    title: str,
    best: dict | None,
) -> str:
    width = 1180
    height = 780
    margin_left = 110
    plot_width = 990
    loss_area = PlotArea(margin_left, 110, plot_width, 330, 0.0, float(train_steps), 0.0, 1.0)
    lr_area = PlotArea(margin_left, 540, plot_width, 140, 0.0, float(train_steps), 0.0, 1.0)

    loss_values = [value for _, value in train_points] + [value for _, value in val_points]
    loss_min = min(loss_values)
    loss_max = max(loss_values)
    loss_pad = max((loss_max - loss_min) * 0.08, 0.05)
    loss_area.y_min = max(0.0, loss_min - loss_pad)
    loss_area.y_max = loss_max + loss_pad

    lr_values = [value for _, value in lr_points]
    lr_min = min(lr_values)
    lr_max = max(lr_values)
    lr_pad = max((lr_max - lr_min) * 0.08, 1e-6)
    lr_area.y_min = max(0.0, lr_min - lr_pad)
    lr_area.y_max = lr_max + lr_pad

    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1180" height="780" viewBox="0 0 1180 780">',
        "<style>",
        "text { font-family: Avenir, Helvetica, Arial, sans-serif; fill: #25211b; }",
        ".title { font-size: 26px; font-weight: 700; }",
        ".subtitle { font-size: 14px; fill: #5c554b; }",
        ".panel-title { font-size: 18px; font-weight: 700; }",
        ".axis-label { font-size: 13px; fill: #5c554b; }",
        ".tick { font-size: 12px; fill: #6b6257; }",
        ".grid { stroke: #ddd5c9; stroke-width: 1; }",
        ".train { fill: none; stroke: #1f6f8b; stroke-width: 1.8; opacity: 0.85; }",
        ".val { fill: none; stroke: #b5472a; stroke-width: 3.0; }",
        ".lr { fill: none; stroke: #526d2d; stroke-width: 2.6; }",
        ".marker { fill: #b5472a; stroke: white; stroke-width: 1.5; }",
        ".legend { font-size: 14px; }",
        "</style>",
        '<rect x="0" y="0" width="1180" height="780" fill="#f4efe6"/>',
        f'<text x="60" y="50" class="title">{html.escape(title)}</text>',
    ]
    if best is not None:
        parts.append(
            f'<text x="60" y="76" class="subtitle">Best validation loss: {best["validation_loss"]:.6f} at step {best["step"]}</text>'
        )

    parts.extend(render_axes(loss_area, title="Loss", y_label="cross entropy loss"))
    parts.append(f'<polyline class="train" points="{polyline(train_points, loss_area)}"/>')
    if val_points:
        parts.append(f'<polyline class="val" points="{polyline(val_points, loss_area)}"/>')
        for x, y in val_points:
            parts.append(f'<circle class="marker" cx="{loss_area.sx(x):.2f}" cy="{loss_area.sy(y):.2f}" r="3.2"/>')

    parts.extend(render_axes(lr_area, title="Learning Rate", y_label="lr", x_label="training step"))
    parts.append(f'<polyline class="lr" points="{polyline(lr_points, lr_area)}"/>')

    legend_y = 468
    parts.extend(
        [
            f'<line x1="{margin_left}" y1="{legend_y}" x2="{margin_left + 34}" y2="{legend_y}" class="train"/>',
            f'<text x="{margin_left + 44}" y="{legend_y + 5}" class="legend">train loss from tqdm log</text>',
            f'<line x1="{margin_left + 260}" y1="{legend_y}" x2="{margin_left + 294}" y2="{legend_y}" class="val"/>',
            f'<text x="{margin_left + 304}" y="{legend_y + 5}" class="legend">validation loss</text>',
            f'<line x1="{margin_left + 470}" y1="{legend_y}" x2="{margin_left + 504}" y2="{legend_y}" class="lr"/>',
            f'<text x="{margin_left + 514}" y="{legend_y + 5}" class="legend">learning-rate schedule</text>',
        ]
    )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main() -> None:
    args = parse_args()
    min_lr = args.min_lr if args.min_lr is not None else args.max_lr * 0.1
    val_raw, validation_payload = parse_validation_loss(args.validation_curve)
    train_steps = int(validation_payload.get("train_steps", args.train_steps)) if validation_payload else args.train_steps
    best = validation_payload.get("best") if validation_payload else None

    train_raw = parse_train_loss(args.training_log)
    if not train_raw:
        raise ValueError(f"No training-loss points found in {args.training_log}. Use the full tee log, not only a summarized tail.")

    train_points = downsample_average(train_raw, args.max_train_points)
    val_points = [(float(step), value) for step, value in val_raw]
    lr_points = sample_lr(
        train_steps,
        max_lr=args.max_lr,
        min_lr=min_lr,
        warmup_ratio=args.warmup_ratio,
        max_points=args.max_train_points,
    )

    args.output_svg.parent.mkdir(parents=True, exist_ok=True)
    args.output_svg.write_text(
        render_svg(
            train_points=train_points,
            val_points=val_points,
            lr_points=lr_points,
            train_steps=train_steps,
            title=args.title,
            best=best,
        ),
        encoding="utf-8",
    )

    summary = {
        "training_log": str(args.training_log),
        "validation_curve": str(args.validation_curve) if args.validation_curve else None,
        "output_svg": str(args.output_svg),
        "train_steps": train_steps,
        "train_loss_points_raw": len(train_raw),
        "train_loss_points_plotted": len(train_points),
        "validation_points": len(val_points),
        "best_validation": best,
        "lr": {
            "max_lr": args.max_lr,
            "min_lr": min_lr,
            "warmup_ratio": args.warmup_ratio,
        },
    }
    if args.output_summary_json is not None:
        args.output_summary_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_summary_json.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
