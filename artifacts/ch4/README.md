# Chapter 4 Artifacts

This directory is for small, writeup-oriented evidence from the Chapter 4 full data run.

## Archive Locally

Use `archive_full_run_artifacts.sh` on the remote server after stage 2 inspection and tokenization summaries are available. The script archives:

- `run_manifest.json`, `events.jsonl`, and `final_report.json` when present.
- `inspection_samples.md`.
- Stage-1 and stage-2 aggregate summaries.
- Pipeline log files.
- Bucket summary JSON files.
- Tokenization summary JSON files.
- A small `manifest.md` with remote data sizes.

Large candidate/successful WET path lists are intentionally skipped by default; the writeup should rely on the manifest, bucket summaries, and aggregate summaries for provenance and counts.

## Do Not Archive In Git

Do not copy large data products into the repository:

- Raw WET files.
- Stage-1 kept document JSONL shards.
- Stage-2 deduped document JSONL shards.
- Stage-2 temporary work directories.
- Tokenized training `.bin` files.

Keep those on the data disk or delete them after the smaller evidence files and final tokenized artifact are safely handled.

## Remote-Only Checks

These are better checked on the server terminal rather than stored in git:

- `df -h /root/autodl-tmp`.
- `du -sh` for raw, stage1, stage2, and tokenized directories.
- `ps` output for currently running processes.
- Large review logs or per-document data shards.
