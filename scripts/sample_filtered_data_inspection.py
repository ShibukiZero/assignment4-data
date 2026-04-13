from __future__ import annotations

import argparse
import glob
import json
import random
from pathlib import Path

from xopen import xopen


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sample kept and removed/modified examples from the Chapter 4 "
            "filtered-data pipeline for manual inspection."
        )
    )
    parser.add_argument(
        "--kept-glob",
        required=True,
        help="Glob pattern for final kept/deduped JSONL files.",
    )
    parser.add_argument(
        "--review-glob",
        required=True,
        help="Glob pattern for review-log JSONL files.",
    )
    parser.add_argument(
        "--output-md",
        required=True,
        help="Markdown report path to write.",
    )
    parser.add_argument(
        "--num-kept",
        type=int,
        default=5,
        help="Number of kept examples to sample.",
    )
    parser.add_argument(
        "--num-review",
        type=int,
        default=5,
        help="Number of removed/modified examples to sample.",
    )
    parser.add_argument(
        "--preview-chars",
        type=int,
        default=1200,
        help="Maximum characters to include for each text excerpt.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=13,
        help="Random seed for reproducible sampling.",
    )
    return parser.parse_args()


def sample_jsonl_records(paths: list[Path], sample_size: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    samples: list[dict] = []
    records_seen = 0

    for path in paths:
        with xopen(path, "rt") as handle:
            for line in handle:
                records_seen += 1
                payload = json.loads(line)
                payload["_sample_source_path"] = str(path)

                if len(samples) < sample_size:
                    samples.append(payload)
                    continue

                replacement_index = rng.randrange(records_seen)
                if replacement_index < sample_size:
                    samples[replacement_index] = payload

    return samples


def preview_text(payload: dict, preview_chars: int) -> str:
    text = payload.get("text") or payload.get("text_preview") or ""
    compact = "\n".join(line.rstrip() for line in text.strip().splitlines())
    return compact[:preview_chars]


def write_record_section(
    *,
    lines: list[str],
    title: str,
    records: list[dict],
    preview_chars: int,
) -> None:
    lines.append(f"## {title}")
    lines.append("")

    for index, payload in enumerate(records, start=1):
        lines.append(f"### Example {index}")
        lines.append("")
        lines.append(f"- Source JSONL: `{payload.get('_sample_source_path', '')}`")
        lines.append(f"- Source WET: `{payload.get('source_wet_path', '')}`")
        lines.append(f"- URL: `{payload.get('target_uri', '')}`")
        lines.append(f"- Domain: `{payload.get('registered_domain', '')}`")
        lines.append(f"- Decision: `{payload.get('decision', '')}`")

        if "drop_reason" in payload:
            lines.append(f"- Drop reason: `{payload['drop_reason']}`")
        if "language" in payload:
            lines.append(
                f"- Language: `{payload.get('language')}` ({payload.get('language_score')})"
            )
        if "quality_label" in payload:
            lines.append(
                f"- Quality: `{payload.get('quality_label')}` ({payload.get('quality_score')})"
            )
        if "dedup" in payload:
            lines.append(f"- Dedup metadata: `{json.dumps(payload['dedup'], ensure_ascii=False)}`")

        lines.append("")
        lines.append("Excerpt:")
        lines.append("")
        lines.append("```text")
        lines.append(preview_text(payload, preview_chars))
        lines.append("```")
        lines.append("")
        lines.append("Manual note:")
        lines.append("- TODO: Comment on whether this example is suitable for language modeling.")
        lines.append("")


def main() -> None:
    args = parse_args()

    kept_paths = sorted(Path(path) for path in glob.glob(args.kept_glob))
    review_paths = sorted(Path(path) for path in glob.glob(args.review_glob))

    if not kept_paths:
        raise FileNotFoundError(f"No kept JSONL files matched: {args.kept_glob}")
    if not review_paths:
        raise FileNotFoundError(f"No review JSONL files matched: {args.review_glob}")

    kept_samples = sample_jsonl_records(kept_paths, args.num_kept, args.seed)
    review_samples = sample_jsonl_records(
        review_paths,
        args.num_review,
        args.seed + 1,
    )

    lines: list[str] = [
        "# Filtered Data Inspection Samples",
        "",
        "This report is for manual inspection before writing the final assignment response.",
        "",
        "## Sampling Config",
        "",
        f"- Kept glob: `{args.kept_glob}`",
        f"- Review glob: `{args.review_glob}`",
        f"- Seed: `{args.seed}`",
        f"- Kept examples: `{len(kept_samples)}`",
        f"- Review examples: `{len(review_samples)}`",
        "",
    ]

    write_record_section(
        lines=lines,
        title="Kept Examples",
        records=kept_samples,
        preview_chars=args.preview_chars,
    )
    write_record_section(
        lines=lines,
        title="Removed Or Modified Examples",
        records=review_samples,
        preview_chars=args.preview_chars,
    )

    output_path = Path(args.output_md)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote inspection report to {output_path}")


if __name__ == "__main__":
    main()
