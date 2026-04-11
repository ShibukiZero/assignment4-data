from __future__ import annotations

import argparse
import gzip
import json
import shutil
import subprocess
import sys
import time
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_CRAWL_ID = "CC-MAIN-2026-12"
DEFAULT_TOKENIZER = "/root/autodl-tmp/tokenizers/gpt2"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download Common Crawl WET files in buckets, run stage-1 filtering as each "
            "bucket lands, delete consumed raw files when requested, then run global "
            "stage-2 deduplication and GPT-2 tokenization. The script writes a manifest, "
            "append-only event log, per-bucket summaries, and a final report for writeup "
            "and recovery evidence."
        )
    )
    parser.add_argument("--crawl-id", default=DEFAULT_CRAWL_ID, help="Common Crawl crawl ID.")
    parser.add_argument("--run-dir", type=Path, required=True, help="Top-level output directory for this run.")
    parser.add_argument("--wet-count", type=int, default=5000, help="Number of WET files to process.")
    parser.add_argument("--bucket-size", type=int, default=50, help="Number of WET files per download/stage-1 bucket.")
    parser.add_argument("--download-concurrency", type=int, default=8, help="Concurrent WET downloads per bucket.")
    parser.add_argument("--stage1-workers", type=int, default=24, help="Stage-1 worker processes.")
    parser.add_argument("--stage2-workers", type=int, default=32, help="Stage-2 worker processes.")
    parser.add_argument("--phase3-chunk-docs", type=int, default=1000, help="Stage-2 phase-3 documents per task.")
    parser.add_argument("--tokenize-batch-size", type=int, default=256, help="Tokenizer document batch size.")
    parser.add_argument("--tokenizer", default=DEFAULT_TOKENIZER, help="GPT-2 tokenizer path or model name.")
    parser.add_argument("--lang-threshold", type=float, default=0.8, help="Stage-1 language threshold.")
    parser.add_argument("--quality-threshold", type=float, default=0.65, help="Stage-1 quality classifier threshold.")
    parser.add_argument("--review-chars", type=int, default=500, help="Preview characters for review logs.")
    parser.add_argument(
        "--selection",
        choices=("first", "last"),
        default="first",
        help="Which WET paths to select from the crawl listing.",
    )
    parser.add_argument(
        "--keep-raw",
        action="store_true",
        help="Keep raw WET bucket files after successful stage-1 processing.",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Use already present raw bucket files instead of downloading them.",
    )
    parser.add_argument(
        "--skip-stage1",
        action="store_true",
        help="Skip bucket download/stage-1 and proceed to global stage-2/tokenization.",
    )
    parser.add_argument("--skip-stage2", action="store_true", help="Skip global stage-2.")
    parser.add_argument("--skip-tokenize", action="store_true", help="Skip final tokenization.")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Allow using an existing run directory and skip buckets with success summaries.",
    )
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def append_event(events_path: Path, event_type: str, **payload: Any) -> None:
    events_path.parent.mkdir(parents=True, exist_ok=True)
    event = {"timestamp": utc_now(), "event": event_type, **payload}
    with events_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def run_command(
    command: list[str],
    *,
    cwd: Path,
    events_path: Path,
    event_name: str,
    extra: dict[str, Any] | None = None,
) -> float:
    extra = extra or {}
    append_event(events_path, f"{event_name}_start", command=command, **extra)
    start = time.time()
    try:
        subprocess.run(command, cwd=cwd, check=True)
    except Exception as exc:
        append_event(
            events_path,
            f"{event_name}_failure",
            command=command,
            elapsed_seconds=time.time() - start,
            error=repr(exc),
            **extra,
        )
        raise
    elapsed = time.time() - start
    append_event(events_path, f"{event_name}_end", command=command, elapsed_seconds=elapsed, **extra)
    return elapsed


def command_output(command: list[str], cwd: Path) -> str | None:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except Exception:
        return None
    return completed.stdout.strip()


def disk_snapshot(path: Path) -> dict[str, Any]:
    usage = shutil.disk_usage(path)
    return {
        "path": str(path),
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
    }


def directory_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            total += item.stat().st_size
    return total


def file_count(path: Path, pattern: str) -> int:
    if not path.exists():
        return 0
    return sum(1 for item in path.glob(pattern) if item.is_file())


def download_crawl_listing(crawl_id: str, listing_gz_path: Path) -> list[str]:
    listing_gz_path.parent.mkdir(parents=True, exist_ok=True)
    listing_url = f"https://data.commoncrawl.org/crawl-data/{crawl_id}/wet.paths.gz"
    urllib.request.urlretrieve(listing_url, listing_gz_path)

    with gzip.open(listing_gz_path, "rt", encoding="utf-8") as handle:
        return [line.strip() for line in handle if line.strip()]


def select_wet_paths(all_paths: list[str], count: int, selection: str) -> list[str]:
    if count <= 0:
        raise ValueError("wet-count must be positive.")
    if count > len(all_paths):
        raise ValueError(f"Requested {count} WET paths, but listing only has {len(all_paths)}.")
    if selection == "first":
        return all_paths[:count]
    if selection == "last":
        return all_paths[-count:]
    raise ValueError(f"Unsupported selection strategy: {selection}")


def bucketed(paths: list[str], bucket_size: int) -> list[list[str]]:
    if bucket_size <= 0:
        raise ValueError("bucket-size must be positive.")
    return [paths[index : index + bucket_size] for index in range(0, len(paths), bucket_size)]


def write_lines(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")


def wet_urls(relative_paths: list[str]) -> list[str]:
    return [f"https://data.commoncrawl.org/{relative_path}" for relative_path in relative_paths]


def download_bucket(
    *,
    bucket_index: int,
    bucket_paths: list[str],
    raw_bucket_dir: Path,
    download_concurrency: int,
    events_path: Path,
    cwd: Path,
    skip_download: bool,
) -> dict[str, Any]:
    raw_bucket_dir.mkdir(parents=True, exist_ok=True)
    paths_file = raw_bucket_dir / "wet_paths.txt"
    urls_file = raw_bucket_dir / "wet_urls.txt"
    write_lines(paths_file, bucket_paths)
    write_lines(urls_file, wet_urls(bucket_paths))

    if not skip_download:
        if shutil.which("aria2c"):
            command = [
                "aria2c",
                "--continue=true",
                f"--max-concurrent-downloads={download_concurrency}",
                "--split=8",
                "--max-connection-per-server=8",
                f"--dir={raw_bucket_dir}",
                f"--input-file={urls_file}",
            ]
        elif shutil.which("wget"):
            command = [
                "bash",
                "-lc",
                f"xargs -n 1 -P {download_concurrency} wget -c -P {raw_bucket_dir} < {urls_file}",
            ]
        else:
            raise RuntimeError("Neither aria2c nor wget is available for downloading WET files.")
        elapsed = run_command(
            command,
            cwd=cwd,
            events_path=events_path,
            event_name="bucket_download",
            extra={"bucket_index": bucket_index, "raw_bucket_dir": str(raw_bucket_dir)},
        )
    else:
        append_event(
            events_path,
            "bucket_download_skipped",
            bucket_index=bucket_index,
            raw_bucket_dir=str(raw_bucket_dir),
        )
        elapsed = 0.0

    return {
        "bucket_index": bucket_index,
        "raw_bucket_dir": str(raw_bucket_dir),
        "wet_paths_file": str(paths_file),
        "wet_urls_file": str(urls_file),
        "download_elapsed_seconds": elapsed,
        "downloaded_file_count": file_count(raw_bucket_dir, "*.warc.wet.gz"),
        "downloaded_bytes": directory_size_bytes(raw_bucket_dir),
    }


def write_stage1_rollup(stage1_bucket_summaries: list[Path], rollup_path: Path) -> dict[str, Any]:
    aggregate = Counter()
    total_elapsed = 0.0
    per_bucket: list[dict[str, Any]] = []
    for summary_path in stage1_bucket_summaries:
        summary = read_json(summary_path)
        aggregate.update(summary.get("aggregate_counts", {}))
        total_elapsed += float(summary.get("total_elapsed_seconds", 0.0))
        per_bucket.append(
            {
                "summary_path": str(summary_path),
                "num_input_files": summary.get("num_input_files"),
                "total_elapsed_seconds": summary.get("total_elapsed_seconds"),
                "aggregate_counts": summary.get("aggregate_counts", {}),
            }
        )

    rollup = {
        "bucket_summary_paths": [str(path) for path in stage1_bucket_summaries],
        "num_buckets": len(stage1_bucket_summaries),
        "sum_bucket_elapsed_seconds": total_elapsed,
        "aggregate_counts": dict(aggregate),
        "per_bucket": per_bucket,
    }
    write_json(rollup_path, rollup)
    return rollup


def build_manifest(args: argparse.Namespace, run_dir: Path, cwd: Path) -> dict[str, Any]:
    return {
        "created_at": utc_now(),
        "crawl_id": args.crawl_id,
        "wet_count": args.wet_count,
        "bucket_size": args.bucket_size,
        "selection": args.selection,
        "download_concurrency": args.download_concurrency,
        "stage1_workers": args.stage1_workers,
        "stage2_workers": args.stage2_workers,
        "phase3_chunk_docs": args.phase3_chunk_docs,
        "tokenize_batch_size": args.tokenize_batch_size,
        "tokenizer": args.tokenizer,
        "lang_threshold": args.lang_threshold,
        "quality_threshold": args.quality_threshold,
        "review_chars": args.review_chars,
        "keep_raw": args.keep_raw,
        "skip_download": args.skip_download,
        "skip_stage1": args.skip_stage1,
        "skip_stage2": args.skip_stage2,
        "skip_tokenize": args.skip_tokenize,
        "run_dir": str(run_dir),
        "cwd": str(cwd),
        "python_executable": sys.executable,
        "argv": sys.argv,
        "git_branch": command_output(["git", "branch", "--show-current"], cwd),
        "git_commit": command_output(["git", "rev-parse", "HEAD"], cwd),
        "nproc": command_output(["nproc"], cwd),
        "disk_snapshot": disk_snapshot(run_dir.parent),
        "layout": {
            "raw": str(run_dir / "raw"),
            "stage1": str(run_dir / "stage1"),
            "stage2": str(run_dir / "stage2"),
            "tokenized": str(run_dir / "tokenized"),
            "bucket_summaries": str(run_dir / "bucket_summaries"),
            "logs": str(run_dir / "logs"),
        },
    }


def main() -> None:
    args = parse_args()
    run_start = time.time()
    cwd = Path.cwd()
    run_dir: Path = args.run_dir

    if run_dir.exists() and any(run_dir.iterdir()) and not args.resume:
        raise FileExistsError(f"Run directory is not empty. Use --resume if intended: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)

    events_path = run_dir / "events.jsonl"
    manifest_path = run_dir / "run_manifest.json"
    bucket_summary_dir = run_dir / "bucket_summaries"
    raw_dir = run_dir / "raw"
    stage1_dir = run_dir / "stage1"
    stage1_bucket_dir = stage1_dir / "buckets"
    stage2_dir = run_dir / "stage2"
    tokenized_dir = run_dir / "tokenized"
    logs_dir = run_dir / "logs"
    for path in (bucket_summary_dir, raw_dir, stage1_bucket_dir, tokenized_dir, logs_dir):
        path.mkdir(parents=True, exist_ok=True)

    manifest = build_manifest(args, run_dir, cwd)
    write_json(manifest_path, manifest)
    append_event(events_path, "run_start", manifest_path=str(manifest_path))

    selected_paths_path = run_dir / "wet_paths.txt"
    selected_urls_path = run_dir / "wet_urls.txt"
    listing_gz_path = run_dir / "wet.paths.gz"
    if selected_paths_path.exists():
        selected_paths = [
            line.strip()
            for line in selected_paths_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if not selected_urls_path.exists():
            write_lines(selected_urls_path, wet_urls(selected_paths))
        append_event(
            events_path,
            "wet_paths_reused",
            wet_paths_file=str(selected_paths_path),
            count=len(selected_paths),
        )
    else:
        append_event(events_path, "wet_listing_download_start", crawl_id=args.crawl_id)
        all_paths = download_crawl_listing(args.crawl_id, listing_gz_path)
        selected_paths = select_wet_paths(all_paths, args.wet_count, args.selection)
        write_lines(selected_paths_path, selected_paths)
        write_lines(selected_urls_path, wet_urls(selected_paths))
        append_event(
            events_path,
            "wet_listing_download_end",
            listing_gz_path=str(listing_gz_path),
            wet_paths_file=str(selected_paths_path),
            wet_urls_file=str(selected_urls_path),
            selected_count=len(selected_paths),
        )

    bucket_paths_list = bucketed(selected_paths, args.bucket_size)
    stage1_bucket_summary_paths: list[Path] = []
    bucket_summary_paths: list[Path] = []

    if not args.skip_stage1:
        for bucket_index, bucket_paths in enumerate(bucket_paths_list):
            bucket_summary_path = bucket_summary_dir / f"bucket_{bucket_index:05d}.json"
            stage1_bucket_output_dir = stage1_bucket_dir / f"bucket_{bucket_index:05d}"
            stage1_summary_path = stage1_bucket_output_dir / "aggregate_summary.json"

            if args.resume and bucket_summary_path.exists():
                bucket_summary = read_json(bucket_summary_path)
                if bucket_summary.get("status") == "stage1_complete":
                    append_event(events_path, "bucket_skipped_existing_success", bucket_index=bucket_index)
                    bucket_summary_paths.append(bucket_summary_path)
                    stage1_bucket_summary_paths.append(stage1_summary_path)
                    continue

            raw_bucket_dir = raw_dir / f"bucket_{bucket_index:05d}"
            bucket_record: dict[str, Any] = {
                "bucket_index": bucket_index,
                "status": "started",
                "started_at": utc_now(),
                "wet_path_count": len(bucket_paths),
                "raw_bucket_dir": str(raw_bucket_dir),
                "stage1_output_dir": str(stage1_bucket_output_dir),
            }
            write_json(bucket_summary_path, bucket_record)
            append_event(events_path, "bucket_start", bucket_index=bucket_index, wet_path_count=len(bucket_paths))

            download_summary = download_bucket(
                bucket_index=bucket_index,
                bucket_paths=bucket_paths,
                raw_bucket_dir=raw_bucket_dir,
                download_concurrency=args.download_concurrency,
                events_path=events_path,
                cwd=cwd,
                skip_download=args.skip_download,
            )
            bucket_record.update(download_summary)
            write_json(bucket_summary_path, bucket_record)

            stage1_command = [
                sys.executable,
                "scripts/filter_cc_wet_stage1.py",
                "--input-glob",
                str(raw_bucket_dir / "*.warc.wet.gz"),
                "--output-dir",
                str(stage1_bucket_output_dir),
                "--workers",
                str(args.stage1_workers),
                "--lang-threshold",
                str(args.lang_threshold),
                "--quality-threshold",
                str(args.quality_threshold),
                "--review-chars",
                str(args.review_chars),
            ]
            stage1_elapsed = run_command(
                stage1_command,
                cwd=cwd,
                events_path=events_path,
                event_name="bucket_stage1",
                extra={"bucket_index": bucket_index, "stage1_output_dir": str(stage1_bucket_output_dir)},
            )
            stage1_summary = read_json(stage1_summary_path)
            bucket_record.update(
                {
                    "stage1_elapsed_seconds": stage1_elapsed,
                    "stage1_summary_path": str(stage1_summary_path),
                    "stage1_aggregate_counts": stage1_summary.get("aggregate_counts", {}),
                }
            )

            raw_bytes_before_cleanup = directory_size_bytes(raw_bucket_dir)
            bucket_record["raw_bytes_before_cleanup"] = raw_bytes_before_cleanup
            if args.keep_raw:
                bucket_record["raw_cleanup"] = "kept"
                append_event(events_path, "bucket_raw_cleanup_skipped", bucket_index=bucket_index)
            else:
                append_event(
                    events_path,
                    "bucket_raw_cleanup_start",
                    bucket_index=bucket_index,
                    raw_bucket_dir=str(raw_bucket_dir),
                    raw_bytes_before_cleanup=raw_bytes_before_cleanup,
                )
                shutil.rmtree(raw_bucket_dir)
                append_event(
                    events_path,
                    "bucket_raw_cleanup_end",
                    bucket_index=bucket_index,
                    raw_bucket_dir=str(raw_bucket_dir),
                    deleted_bytes=raw_bytes_before_cleanup,
                )
                bucket_record["raw_cleanup"] = "deleted"
                bucket_record["raw_deleted_bytes"] = raw_bytes_before_cleanup

            bucket_record["status"] = "stage1_complete"
            bucket_record["ended_at"] = utc_now()
            write_json(bucket_summary_path, bucket_record)
            bucket_summary_paths.append(bucket_summary_path)
            stage1_bucket_summary_paths.append(stage1_summary_path)
            append_event(
                events_path,
                "bucket_end",
                bucket_index=bucket_index,
                bucket_summary_path=str(bucket_summary_path),
            )
    else:
        stage1_bucket_summary_paths = sorted(stage1_bucket_dir.glob("bucket_*/aggregate_summary.json"))
        bucket_summary_paths = sorted(bucket_summary_dir.glob("bucket_*.json"))
        append_event(events_path, "stage1_skipped", stage1_bucket_summary_count=len(stage1_bucket_summary_paths))

    stage1_rollup_path = stage1_dir / "aggregate_summary.json"
    stage1_rollup = write_stage1_rollup(stage1_bucket_summary_paths, stage1_rollup_path)
    append_event(events_path, "stage1_rollup_written", stage1_rollup_path=str(stage1_rollup_path))

    stage2_summary_path = stage2_dir / "aggregate_summary.json"
    if not args.skip_stage2:
        stage2_command = [
            sys.executable,
            "scripts/dedup_stage2.py",
            "--input-glob",
            str(stage1_bucket_dir / "*" / "kept_docs" / "*.jsonl"),
            "--output-dir",
            str(stage2_dir),
            "--workers",
            str(args.stage2_workers),
            "--phase3-chunk-docs",
            str(args.phase3_chunk_docs),
            "--review-chars",
            str(args.review_chars),
        ]
        run_command(
            stage2_command,
            cwd=cwd,
            events_path=events_path,
            event_name="stage2",
            extra={"stage2_output_dir": str(stage2_dir)},
        )
    else:
        append_event(events_path, "stage2_skipped", stage2_output_dir=str(stage2_dir))

    tokenized_bin = tokenized_dir / "filtered_train_gpt2.bin"
    tokenized_summary_path = tokenized_dir / "filtered_train_gpt2.summary.json"
    if not args.skip_tokenize:
        tokenize_command = [
            sys.executable,
            "scripts/tokenize_filtered_data.py",
            "--input-glob",
            str(stage2_dir / "deduped_docs" / "*.jsonl"),
            "--output-path",
            str(tokenized_bin),
            "--summary-path",
            str(tokenized_summary_path),
            "--tokenizer",
            args.tokenizer,
            "--batch-size",
            str(args.tokenize_batch_size),
        ]
        run_command(
            tokenize_command,
            cwd=cwd,
            events_path=events_path,
            event_name="tokenize",
            extra={"tokenized_bin": str(tokenized_bin)},
        )
    else:
        append_event(events_path, "tokenize_skipped", tokenized_bin=str(tokenized_bin))

    stage2_summary = read_json(stage2_summary_path) if stage2_summary_path.exists() else {}
    tokenized_summary = read_json(tokenized_summary_path) if tokenized_summary_path.exists() else {}
    final_report = {
        "status": "complete",
        "completed_at": utc_now(),
        "total_elapsed_seconds": time.time() - run_start,
        "manifest_path": str(manifest_path),
        "events_path": str(events_path),
        "wet_paths_file": str(selected_paths_path),
        "wet_urls_file": str(selected_urls_path),
        "bucket_summary_paths": [str(path) for path in bucket_summary_paths],
        "stage1_rollup_path": str(stage1_rollup_path),
        "stage1_rollup": stage1_rollup,
        "stage2_summary_path": str(stage2_summary_path),
        "stage2_summary": stage2_summary,
        "tokenized_bin": str(tokenized_bin),
        "tokenized_summary_path": str(tokenized_summary_path),
        "tokenized_summary": tokenized_summary,
        "final_disk_snapshot": disk_snapshot(run_dir.parent),
    }
    final_report_path = run_dir / "final_report.json"
    write_json(final_report_path, final_report)
    append_event(events_path, "run_end", final_report_path=str(final_report_path))

    print(f"Run complete: {run_dir}")
    print(f"Manifest: {manifest_path}")
    print(f"Events: {events_path}")
    print(f"Final report: {final_report_path}")
    print(f"Stage 1 rollup: {stage1_rollup_path}")
    print(f"Stage 2 summary: {stage2_summary_path}")
    print(f"Tokenized summary: {tokenized_summary_path}")


if __name__ == "__main__":
    main()
