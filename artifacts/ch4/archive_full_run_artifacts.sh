#!/usr/bin/env bash
set -euo pipefail

# Archive only writeup-sized evidence from the full Chapter 4 run.
# This intentionally does not copy raw WET files, stage-1 kept docs,
# stage-2 deduped text shards, temporary work directories, or tokenized .bin files.

RUN_DIR="${1:-/root/autodl-tmp/processed/online_cc_5000_success_counted_20260411_112746}"
ARCHIVE_DIR="${2:-artifacts/ch4/full_5000_wet_run}"

mkdir -p "$ARCHIVE_DIR"/{logs,stage1,stage2,tokenized,bucket_summaries}

copy_if_exists() {
  local src="$1"
  local dst="$2"
  if [[ -e "$src" ]]; then
    mkdir -p "$(dirname "$dst")"
    cp -a "$src" "$dst"
    echo "archived: $src -> $dst"
  else
    echo "missing, skipped: $src"
  fi
}

copy_glob_if_exists() {
  local pattern="$1"
  local dst_dir="$2"
  mkdir -p "$dst_dir"
  shopt -s nullglob
  local paths=( $pattern )
  shopt -u nullglob
  if (( ${#paths[@]} == 0 )); then
    echo "missing, skipped glob: $pattern"
    return
  fi
  cp -a "${paths[@]}" "$dst_dir"/
  echo "archived glob: $pattern -> $dst_dir"
}

{
  echo "# Full Chapter 4 Run Artifact Manifest"
  echo
  echo "- Created at: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  echo "- Run directory: $RUN_DIR"
  echo "- Archive directory: $ARCHIVE_DIR"
  echo
  echo "## Remote Sizes"
  for path in \
    "$RUN_DIR/raw" \
    "$RUN_DIR/stage1" \
    "$RUN_DIR/stage2" \
    "$RUN_DIR/stage2/deduped_docs" \
    "$RUN_DIR/stage2/review_logs" \
    "$RUN_DIR/tokenized"; do
    if [[ -e "$path" ]]; then
      du -sh "$path"
    else
      echo "missing $path"
    fi
  done
} > "$ARCHIVE_DIR/manifest.md"

copy_if_exists "$RUN_DIR/run_manifest.json" "$ARCHIVE_DIR/run_manifest.json"
copy_if_exists "$RUN_DIR/events.jsonl" "$ARCHIVE_DIR/events.jsonl"
copy_if_exists "$RUN_DIR/final_report.json" "$ARCHIVE_DIR/final_report.json"
# Path lists can be large and are not needed for the writeup. Archive counts
# and provenance via summaries/manifests instead.
copy_if_exists "$RUN_DIR/inspection_samples.md" "$ARCHIVE_DIR/inspection_samples.md"

copy_if_exists "$RUN_DIR/stage1/aggregate_summary.json" "$ARCHIVE_DIR/stage1/aggregate_summary.json"
copy_if_exists "$RUN_DIR/stage2/aggregate_summary.json" "$ARCHIVE_DIR/stage2/aggregate_summary.json"

copy_glob_if_exists "$RUN_DIR/logs/*.log" "$ARCHIVE_DIR/logs"
copy_glob_if_exists "$RUN_DIR/bucket_summaries/*.json" "$ARCHIVE_DIR/bucket_summaries"
copy_glob_if_exists "$RUN_DIR/tokenized/*.summary.json" "$ARCHIVE_DIR/tokenized"

{
  echo
  echo "## Archived Files"
  find "$ARCHIVE_DIR" -type f | sort
} >> "$ARCHIVE_DIR/manifest.md"

tar -czf "$ARCHIVE_DIR.tar.gz" -C "$(dirname "$ARCHIVE_DIR")" "$(basename "$ARCHIVE_DIR")"
du -sh "$ARCHIVE_DIR" "$ARCHIVE_DIR.tar.gz"
echo "Archive ready: $ARCHIVE_DIR.tar.gz"
