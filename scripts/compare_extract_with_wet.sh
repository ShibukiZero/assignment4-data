#!/usr/bin/env bash

set -euo pipefail

warc_path="${1:-data/raw/cc_samples/example.warc.gz}"
wet_path="${2:-data/raw/cc_samples/example.warc.wet.gz}"
output_dir="${3:-runs/extract_text_compare}"

mkdir -p "$output_dir"

my_extract_path="$output_dir/my_extract.txt"
wet_extract_path="$output_dir/wet_extract.txt"
diff_path="$output_dir/diff.txt"
report_path="$output_dir/report.md"

uv run python - "$warc_path" "$wet_path" "$my_extract_path" "$wet_extract_path" "$report_path" <<'PY'
from __future__ import annotations

import sys
from pathlib import Path

from fastwarc.warc import ArchiveIterator, WarcRecordType

from cs336_data.html_text import extract_text_from_html_bytes


warc_path = Path(sys.argv[1])
wet_path = Path(sys.argv[2])
my_extract_path = Path(sys.argv[3])
wet_extract_path = Path(sys.argv[4])
report_path = Path(sys.argv[5])

target_uri = None
html_bytes = None
wet_text = None

with warc_path.open("rb") as f:
    for record in ArchiveIterator(f):
        if record.record_type == WarcRecordType.response:
            target_uri = record.headers.get("WARC-Target-URI")
            html_bytes = record.reader.read()
            break

if target_uri is None or html_bytes is None:
    raise RuntimeError("Could not find the first response record in the WARC file.")

my_text = extract_text_from_html_bytes(html_bytes)

with wet_path.open("rb") as f:
    for record in ArchiveIterator(f):
        if record.record_type == WarcRecordType.conversion:
            uri = record.headers.get("WARC-Target-URI")
            if uri == target_uri:
                wet_text = record.reader.read().decode("utf-8", errors="replace")
                break

if wet_text is None:
    raise RuntimeError(f"Could not find a matching WET record for {target_uri}.")

my_extract_path.write_text(my_text, encoding="utf-8")
wet_extract_path.write_text(wet_text, encoding="utf-8")

def preview_block(label: str, text: str, max_lines: int = 40) -> str:
    lines = text.splitlines()
    shown = lines[:max_lines]
    body = "\n".join(shown)
    return f"## {label}\n\n```text\n{body}\n```"

report = [
    "# Extract vs WET Comparison",
    "",
    f"- Target URI: `{target_uri}`",
    f"- My extract path: `{my_extract_path}`",
    f"- WET extract path: `{wet_extract_path}`",
    "",
    preview_block("My Extract Preview", my_text),
    "",
    preview_block("WET Extract Preview", wet_text),
    "",
]

report_path.write_text("\n".join(report), encoding="utf-8")
PY

diff -u "$wet_extract_path" "$my_extract_path" > "$diff_path" || true

{
  printf '\n## Diff Preview\n\n'
  printf '```diff\n'
  sed -n '1,160p' "$diff_path"
  printf '\n```\n'
} >> "$report_path"

printf 'Wrote comparison report to %s\n' "$report_path"
printf 'Wrote raw diff to %s\n' "$diff_path"
