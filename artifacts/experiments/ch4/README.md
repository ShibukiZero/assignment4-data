# Chapter 4 Artifacts

This directory is for small, writeup-oriented evidence from the Chapter 4 full data run.

## Archived Evidence

The `full_5000_wet_run/` directory contains the small, writeup-sized evidence
preserved from the full data run:

- `run_manifest.json`, `events.jsonl`, and `final_report.json` when present.
- `inspection_samples.md`.
- Stage-1 and stage-2 aggregate summaries.
- Pipeline log files.
- Bucket summary JSON files.
- Tokenization summary JSON files.
- A small `manifest.md` with run data sizes.

Large candidate/successful WET path lists are intentionally skipped by default; the writeup should rely on the manifest, bucket summaries, and aggregate summaries for provenance and counts.

## Do Not Archive In Git

Do not copy large data products into the repository:

- Raw WET files.
- Stage-1 kept document JSONL shards.
- Stage-2 deduped document JSONL shards.
- Stage-2 temporary work directories.
- Tokenized training `.bin` files.

Keep those on the data disk or delete them after the smaller evidence files and final tokenized artifact are safely handled.

## Training Run

The `training_run/` directory contains lightweight evidence for the final GPT-2-small-shaped training run used in the `train_model` writeup section: the SVG learning curve, parsed validation-loss JSON/Markdown, run metadata, final status, and configuration snapshots. It intentionally excludes the full model checkpoint, the full training log, and tokenized `.bin` files.

## Local Checks

These are better checked in the run environment rather than stored in git:

- `df -h` for the data and run directories.
- `du -sh` for raw, stage1, stage2, and tokenized directories.
- `ps` output for currently running processes.
- Large review logs or per-document data shards.
