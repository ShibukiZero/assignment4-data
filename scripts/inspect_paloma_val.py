from __future__ import annotations

import argparse
import gzip
import json
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_INPUT_DIR = Path("data/raw/paloma/c4_100_domains/val")
DEFAULT_OUTPUT_DIR = Path("runs/paloma_probe")
MAX_PREVIEW_CHARS = 500


@dataclass
class FileSummary:
    filename: str
    first_record_keys: list[str]
    candidate_string_lengths: dict[str, int]
    num_records: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect Paloma c4_100_domains validation jsonl.gz files and write a compact "
            "report for downstream tokenization scripting."
        )
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help="Directory containing Paloma validation .jsonl.gz files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where the inspection report will be written.",
    )
    return parser.parse_args()


def shorten(text: str, max_chars: int = MAX_PREVIEW_CHARS) -> str:
    text = text.replace("\n", "\\n")
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def is_candidate_text_field(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def inspect_file(path: Path) -> tuple[FileSummary, dict[str, str], Counter[str], Counter[str]]:
    previews: dict[str, str] = {}
    first_record_string_lengths: dict[str, int] = {}
    keys_counter: Counter[str] = Counter()
    nonempty_string_counter: Counter[str] = Counter()
    num_records = 0
    first_record: dict[str, Any] | None = None

    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError(f"{path} contains a non-object JSON line.")

            num_records += 1
            for key in record:
                keys_counter[key] += 1
            for key, value in record.items():
                if is_candidate_text_field(value):
                    nonempty_string_counter[key] += 1

            if first_record is None:
                first_record = record

    if first_record is None:
        raise ValueError(f"{path} does not contain any JSON records.")

    for key, value in first_record.items():
        if is_candidate_text_field(value):
            first_record_string_lengths[key] = len(value)
            previews[key] = shorten(value)

    summary = FileSummary(
        filename=path.name,
        first_record_keys=sorted(first_record.keys()),
        candidate_string_lengths=first_record_string_lengths,
        num_records=num_records,
    )
    return summary, previews, keys_counter, nonempty_string_counter


def recommend_text_field(lengths: dict[str, list[int]], presence_counts: Counter[str], num_files: int) -> str | None:
    if not lengths:
        return None

    candidates: list[tuple[int, float, str]] = []
    for field, observed_lengths in lengths.items():
        presence = presence_counts[field]
        avg_len = statistics.mean(observed_lengths)
        candidates.append((presence, avg_len, field))

    # Prefer a field that appears in the first record of every file and has the largest average length.
    candidates.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    best_presence, _, best_field = candidates[0]
    if best_presence < num_files:
        return None
    return best_field


def main() -> None:
    args = parse_args()
    input_dir: Path = args.input_dir
    output_dir: Path = args.output_dir

    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")

    files = sorted(input_dir.glob("*.jsonl.gz"))
    if not files:
        raise FileNotFoundError(f"No .jsonl.gz files found in: {input_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    file_summaries: list[FileSummary] = []
    aggregate_key_counts: Counter[str] = Counter()
    aggregate_nonempty_string_counts: Counter[str] = Counter()
    first_record_field_lengths: dict[str, list[int]] = defaultdict(list)
    preview_by_field: dict[str, str] = {}
    total_records = 0

    for path in files:
        summary, previews, keys_counter, nonempty_string_counter = inspect_file(path)
        file_summaries.append(summary)
        aggregate_key_counts.update(keys_counter)
        aggregate_nonempty_string_counts.update(nonempty_string_counter)
        total_records += summary.num_records

        for field, length in summary.candidate_string_lengths.items():
            first_record_field_lengths[field].append(length)
            preview_by_field.setdefault(field, previews[field])

    recommended_field = recommend_text_field(
        lengths=first_record_field_lengths,
        presence_counts=Counter({k: len(v) for k, v in first_record_field_lengths.items()}),
        num_files=len(files),
    )

    report = {
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "num_files": len(files),
        "total_records": total_records,
        "recommended_text_field": recommended_field,
        "aggregate_key_counts": dict(sorted(aggregate_key_counts.items())),
        "aggregate_nonempty_string_counts": dict(sorted(aggregate_nonempty_string_counts.items())),
        "candidate_first_record_length_stats": {
            field: {
                "files_present_in": len(lengths),
                "min_length": min(lengths),
                "max_length": max(lengths),
                "avg_length": statistics.mean(lengths),
            }
            for field, lengths in sorted(first_record_field_lengths.items())
        },
        "field_previews": {field: preview_by_field[field] for field in sorted(preview_by_field)},
        "file_summaries": [
            {
                "filename": summary.filename,
                "num_records": summary.num_records,
                "first_record_keys": summary.first_record_keys,
                "candidate_string_lengths": summary.candidate_string_lengths,
            }
            for summary in file_summaries
        ],
    }

    json_path = output_dir / "report.json"
    md_path = output_dir / "report.md"

    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    md_lines = [
        "# Paloma Validation Inspection Report",
        "",
        f"- Input directory: `{input_dir}`",
        f"- Number of files: `{len(files)}`",
        f"- Total records: `{total_records}`",
        f"- Recommended text field: `{recommended_field}`",
        "",
        "## Candidate Text Fields",
        "",
    ]

    for field, stats in report["candidate_first_record_length_stats"].items():
        md_lines.append(
            f"- `{field}`: present in `{stats['files_present_in']}` files, "
            f"avg first-record length `{stats['avg_length']:.1f}`, "
            f"min `{stats['min_length']}`, max `{stats['max_length']}`"
        )

    md_lines.extend(["", "## Field Previews", ""])
    for field, preview in report["field_previews"].items():
        md_lines.append(f"### `{field}`")
        md_lines.append("")
        md_lines.append("```text")
        md_lines.append(preview)
        md_lines.append("```")
        md_lines.append("")

    md_lines.extend(["## First File Summary", ""])
    first_summary = report["file_summaries"][0]
    md_lines.append(f"- Filename: `{first_summary['filename']}`")
    md_lines.append(f"- Num records: `{first_summary['num_records']}`")
    md_lines.append(f"- First record keys: `{', '.join(first_summary['first_record_keys'])}`")

    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Recommended text field: {recommended_field}")


if __name__ == "__main__":
    main()
