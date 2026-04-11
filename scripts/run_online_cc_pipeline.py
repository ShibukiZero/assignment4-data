from __future__ import annotations

import argparse
import concurrent.futures
import gzip
import json
import random
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
    parser.add_argument("--download-timeout", type=int, default=60, help="Downloader network timeout in seconds.")
    parser.add_argument(
        "--download-file-timeout",
        type=int,
        default=600,
        help="Maximum wall-clock seconds allowed for one WET file download.",
    )
    parser.add_argument("--download-max-tries", type=int, default=3, help="Downloader retry count per file.")
    parser.add_argument(
        "--download-retry-wait",
        type=int,
        default=10,
        help="Seconds to wait between downloader retries.",
    )
    parser.add_argument(
        "--aria2-lowest-speed-limit",
        default="50K",
        help="aria2c lowest speed limit before retrying or failing a download.",
    )
    parser.add_argument("--stage1-workers", type=int, default=32, help="Stage-1 worker processes.")
    parser.add_argument("--stage2-workers", type=int, default=40, help="Stage-2 worker processes.")
    parser.add_argument("--phase3-chunk-docs", type=int, default=1000, help="Stage-2 phase-3 documents per task.")
    parser.add_argument("--tokenize-batch-size", type=int, default=256, help="Tokenizer document batch size.")
    parser.add_argument("--tokenizer", default=DEFAULT_TOKENIZER, help="GPT-2 tokenizer path or model name.")
    parser.add_argument("--lang-threshold", type=float, default=0.8, help="Stage-1 language threshold.")
    parser.add_argument("--quality-threshold", type=float, default=0.65, help="Stage-1 quality classifier threshold.")
    parser.add_argument("--review-chars", type=int, default=500, help="Preview characters for review logs.")
    parser.add_argument(
        "--selection",
        choices=("first", "last", "random"),
        default="random",
        help="Which WET paths to select from the crawl listing.",
    )
    parser.add_argument(
        "--selection-seed",
        type=int,
        default=13,
        help="Random seed used when --selection=random.",
    )
    parser.add_argument(
        "--keep-raw",
        action="store_true",
        help="Keep raw WET bucket files after successful stage-1 processing.",
    )
    parser.add_argument(
        "--keep-stage1",
        action="store_true",
        help="Keep stage-1 kept-doc files after stage-2 has written final outputs.",
    )
    parser.add_argument(
        "--keep-deduped-docs",
        action="store_true",
        help="Keep stage-2 deduped JSONL docs after successful tokenization.",
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


def select_wet_paths(all_paths: list[str], count: int, selection: str, seed: int) -> list[str]:
    if count <= 0:
        raise ValueError("wet-count must be positive.")
    if count > len(all_paths):
        raise ValueError(f"Requested {count} WET paths, but listing only has {len(all_paths)}.")
    if selection == "first":
        return all_paths[:count]
    if selection == "last":
        return all_paths[-count:]
    if selection == "random":
        rng = random.Random(seed)
        return rng.sample(all_paths, count)
    raise ValueError(f"Unsupported selection strategy: {selection}")


def ordered_wet_paths(all_paths: list[str], selection: str, seed: int) -> list[str]:
    if selection == "first":
        return list(all_paths)
    if selection == "last":
        return list(reversed(all_paths))
    if selection == "random":
        ordered_paths = list(all_paths)
        rng = random.Random(seed)
        rng.shuffle(ordered_paths)
        return ordered_paths
    raise ValueError(f"Unsupported selection strategy: {selection}")


def bucket_targets(total_count: int, bucket_size: int) -> list[int]:
    if total_count <= 0:
        raise ValueError("wet-count must be positive.")
    if bucket_size <= 0:
        raise ValueError("bucket-size must be positive.")
    return [
        min(bucket_size, total_count - index)
        for index in range(0, total_count, bucket_size)
    ]


def write_lines(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")


def wet_urls(relative_paths: list[str]) -> list[str]:
    return [f"https://data.commoncrawl.org/{relative_path}" for relative_path in relative_paths]


def delete_partial_downloads(output_path: Path) -> int:
    deleted_bytes = 0
    for path in (output_path, Path(f"{output_path}.aria2")):
        if path.exists():
            deleted_bytes += path.stat().st_size
            path.unlink()
    return deleted_bytes


def download_one_wet(
    *,
    relative_path: str,
    raw_bucket_dir: Path,
    download_timeout: int,
    download_file_timeout: int,
    download_max_tries: int,
    download_retry_wait: int,
    aria2_lowest_speed_limit: str,
) -> dict[str, Any]:
    url = wet_urls([relative_path])[0]
    output_path = raw_bucket_dir / Path(relative_path).name

    if shutil.which("aria2c"):
        command = [
            "aria2c",
            "--continue=true",
            "--split=8",
            "--max-connection-per-server=8",
            f"--connect-timeout={download_timeout}",
            f"--timeout={download_timeout}",
            f"--max-tries={download_max_tries}",
            f"--retry-wait={download_retry_wait}",
            f"--lowest-speed-limit={aria2_lowest_speed_limit}",
            f"--dir={raw_bucket_dir}",
            f"--out={output_path.name}",
            url,
        ]
    elif shutil.which("wget"):
        command = [
            "wget",
            f"--timeout={download_timeout}",
            f"--read-timeout={download_timeout}",
            f"--tries={download_max_tries}",
            f"--waitretry={download_retry_wait}",
            "-c",
            "-P",
            str(raw_bucket_dir),
            url,
        ]
    else:
        raise RuntimeError("Neither aria2c nor wget is available for downloading WET files.")

    start = time.time()
    try:
        completed = subprocess.run(
            command,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=download_file_timeout,
        )
    except subprocess.TimeoutExpired as exc:
        deleted_bytes = delete_partial_downloads(output_path)
        return {
            "relative_path": relative_path,
            "url": url,
            "output_path": str(output_path),
            "status": "skipped",
            "skip_reason": "timeout",
            "elapsed_seconds": time.time() - start,
            "deleted_partial_bytes": deleted_bytes,
            "error": repr(exc),
        }
    except subprocess.CalledProcessError as exc:
        deleted_bytes = delete_partial_downloads(output_path)
        return {
            "relative_path": relative_path,
            "url": url,
            "output_path": str(output_path),
            "status": "skipped",
            "skip_reason": "download_failed",
            "elapsed_seconds": time.time() - start,
            "deleted_partial_bytes": deleted_bytes,
            "returncode": exc.returncode,
            "stderr_tail": (exc.stderr or "")[-2000:],
        }

    if not output_path.exists() or output_path.stat().st_size == 0:
        deleted_bytes = delete_partial_downloads(output_path)
        return {
            "relative_path": relative_path,
            "url": url,
            "output_path": str(output_path),
            "status": "skipped",
            "skip_reason": "missing_output",
            "elapsed_seconds": time.time() - start,
            "deleted_partial_bytes": deleted_bytes,
            "returncode": completed.returncode,
        }

    return {
        "relative_path": relative_path,
        "url": url,
        "output_path": str(output_path),
        "status": "success",
        "elapsed_seconds": time.time() - start,
        "bytes": output_path.stat().st_size,
    }


def download_bucket(
    *,
    bucket_index: int,
    candidate_paths: list[str],
    target_count: int,
    raw_bucket_dir: Path,
    download_concurrency: int,
    download_timeout: int,
    download_file_timeout: int,
    download_max_tries: int,
    download_retry_wait: int,
    aria2_lowest_speed_limit: str,
    events_path: Path,
    cwd: Path,
    skip_download: bool,
) -> dict[str, Any]:
    raw_bucket_dir.mkdir(parents=True, exist_ok=True)
    successful_paths_file = raw_bucket_dir / "wet_paths.txt"
    successful_urls_file = raw_bucket_dir / "wet_urls.txt"
    attempted_paths_file = raw_bucket_dir / "attempted_wet_paths.txt"
    skipped_path = raw_bucket_dir / "skipped_wet_paths.jsonl"

    if target_count <= 0:
        raise ValueError("target_count must be positive.")
    if download_concurrency <= 0:
        raise ValueError("download_concurrency must be positive.")

    if skip_download:
        existing_paths = sorted(raw_bucket_dir.glob("*.warc.wet.gz"))
        existing_relative_paths = [path.name for path in existing_paths]
        write_lines(successful_paths_file, existing_relative_paths)
        write_lines(successful_urls_file, existing_relative_paths)
        append_event(
            events_path,
            "bucket_download_skipped",
            bucket_index=bucket_index,
            raw_bucket_dir=str(raw_bucket_dir),
            existing_file_count=len(existing_paths),
        )
        return {
            "bucket_index": bucket_index,
            "raw_bucket_dir": str(raw_bucket_dir),
            "wet_paths_file": str(successful_paths_file),
            "wet_urls_file": str(successful_urls_file),
            "attempted_wet_paths_file": str(attempted_paths_file),
            "skipped_wet_paths_file": str(skipped_path),
            "download_elapsed_seconds": 0.0,
            "attempted_count": 0,
            "successful_wet_count": len(existing_paths),
            "skipped_wet_count": 0,
            "downloaded_file_count": file_count(raw_bucket_dir, "*.warc.wet.gz"),
            "downloaded_bytes": directory_size_bytes(raw_bucket_dir),
            "successful_wet_paths": existing_relative_paths,
            "skipped_wet_paths": [],
        }

    append_event(
        events_path,
        "bucket_download_start",
        bucket_index=bucket_index,
        raw_bucket_dir=str(raw_bucket_dir),
        target_count=target_count,
    )
    start = time.time()
    candidate_index = 0
    successful: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    futures: dict[concurrent.futures.Future[dict[str, Any]], str] = {}

    def submit_next(executor: concurrent.futures.ThreadPoolExecutor) -> bool:
        nonlocal candidate_index
        if candidate_index >= len(candidate_paths):
            return False
        relative_path = candidate_paths[candidate_index]
        candidate_index += 1
        future = executor.submit(
            download_one_wet,
            relative_path=relative_path,
            raw_bucket_dir=raw_bucket_dir,
            download_timeout=download_timeout,
            download_file_timeout=download_file_timeout,
            download_max_tries=download_max_tries,
            download_retry_wait=download_retry_wait,
            aria2_lowest_speed_limit=aria2_lowest_speed_limit,
        )
        futures[future] = relative_path
        return True

    with concurrent.futures.ThreadPoolExecutor(max_workers=download_concurrency) as executor:
        while len(futures) < download_concurrency and len(successful) + len(futures) < target_count:
            if not submit_next(executor):
                break

        while len(successful) < target_count:
            if not futures:
                raise RuntimeError(
                    f"Bucket {bucket_index} only downloaded {len(successful)} of {target_count} WET files."
                )

            done, _pending = concurrent.futures.wait(
                futures,
                return_when=concurrent.futures.FIRST_COMPLETED,
            )
            for future in done:
                futures.pop(future)
                result = future.result()
                if result["status"] == "success":
                    successful.append(result)
                    append_event(
                        events_path,
                        "bucket_download_file_success",
                        bucket_index=bucket_index,
                        relative_path=result["relative_path"],
                        bytes=result["bytes"],
                        elapsed_seconds=result["elapsed_seconds"],
                    )
                else:
                    skipped.append(result)
                    append_event(
                        events_path,
                        "bucket_download_file_skipped",
                        bucket_index=bucket_index,
                        relative_path=result["relative_path"],
                        skip_reason=result["skip_reason"],
                        elapsed_seconds=result["elapsed_seconds"],
                        deleted_partial_bytes=result.get("deleted_partial_bytes", 0),
                    )

            while len(futures) < download_concurrency and len(successful) + len(futures) < target_count:
                if not submit_next(executor):
                    break

    successful_relative_paths = [entry["relative_path"] for entry in successful]
    attempted_relative_paths = successful_relative_paths + [entry["relative_path"] for entry in skipped]
    write_lines(successful_paths_file, successful_relative_paths)
    write_lines(successful_urls_file, wet_urls(successful_relative_paths))
    write_lines(attempted_paths_file, attempted_relative_paths)
    if skipped:
        with skipped_path.open("w", encoding="utf-8") as handle:
            for entry in skipped:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    else:
        skipped_path.write_text("", encoding="utf-8")

    elapsed = time.time() - start
    append_event(
        events_path,
        "bucket_download_end",
        bucket_index=bucket_index,
        raw_bucket_dir=str(raw_bucket_dir),
        target_count=target_count,
        successful_wet_count=len(successful),
        skipped_wet_count=len(skipped),
        attempted_count=len(attempted_relative_paths),
        elapsed_seconds=elapsed,
    )

    return {
        "bucket_index": bucket_index,
        "raw_bucket_dir": str(raw_bucket_dir),
        "wet_paths_file": str(successful_paths_file),
        "wet_urls_file": str(successful_urls_file),
        "attempted_wet_paths_file": str(attempted_paths_file),
        "skipped_wet_paths_file": str(skipped_path),
        "download_elapsed_seconds": elapsed,
        "target_wet_count": target_count,
        "attempted_count": len(attempted_relative_paths),
        "successful_wet_count": len(successful),
        "skipped_wet_count": len(skipped),
        "downloaded_file_count": file_count(raw_bucket_dir, "*.warc.wet.gz"),
        "downloaded_bytes": directory_size_bytes(raw_bucket_dir),
        "successful_wet_paths": successful_relative_paths,
        "skipped_wet_paths": skipped,
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
        "selection_seed": args.selection_seed,
        "download_concurrency": args.download_concurrency,
        "download_timeout": args.download_timeout,
        "download_file_timeout": args.download_file_timeout,
        "download_max_tries": args.download_max_tries,
        "download_retry_wait": args.download_retry_wait,
        "aria2_lowest_speed_limit": args.aria2_lowest_speed_limit,
        "stage1_workers": args.stage1_workers,
        "stage2_workers": args.stage2_workers,
        "phase3_chunk_docs": args.phase3_chunk_docs,
        "tokenize_batch_size": args.tokenize_batch_size,
        "tokenizer": args.tokenizer,
        "lang_threshold": args.lang_threshold,
        "quality_threshold": args.quality_threshold,
        "review_chars": args.review_chars,
        "keep_raw": args.keep_raw,
        "keep_stage1": args.keep_stage1,
        "keep_deduped_docs": args.keep_deduped_docs,
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

    allowed_precreated_paths = {"logs", "pipeline.pid"}
    if run_dir.exists() and not args.resume:
        unexpected_existing_paths = [
            path for path in run_dir.iterdir() if path.name not in allowed_precreated_paths
        ]
        if unexpected_existing_paths:
            raise FileExistsError(
                f"Run directory is not empty. Use --resume if intended: {run_dir}"
            )
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

    successful_paths_path = run_dir / "wet_paths.txt"
    successful_urls_path = run_dir / "wet_urls.txt"
    candidate_paths_path = run_dir / "candidate_wet_paths.txt"
    listing_gz_path = run_dir / "wet.paths.gz"
    if candidate_paths_path.exists():
        candidate_paths = [
            line.strip()
            for line in candidate_paths_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        append_event(
            events_path,
            "candidate_wet_paths_reused",
            candidate_wet_paths_file=str(candidate_paths_path),
            count=len(candidate_paths),
        )
    else:
        append_event(events_path, "wet_listing_download_start", crawl_id=args.crawl_id)
        all_paths = download_crawl_listing(args.crawl_id, listing_gz_path)
        candidate_paths = ordered_wet_paths(all_paths, args.selection, args.selection_seed)
        write_lines(candidate_paths_path, candidate_paths)
        append_event(
            events_path,
            "wet_listing_download_end",
            listing_gz_path=str(listing_gz_path),
            candidate_wet_paths_file=str(candidate_paths_path),
            candidate_count=len(candidate_paths),
            target_successful_wet_count=args.wet_count,
        )

    target_counts_by_bucket = bucket_targets(args.wet_count, args.bucket_size)
    candidate_cursor = 0
    successful_run_paths: list[str] = []
    stage1_bucket_summary_paths: list[Path] = []
    bucket_summary_paths: list[Path] = []

    if not args.skip_stage1:
        for bucket_index, target_count in enumerate(target_counts_by_bucket):
            bucket_summary_path = bucket_summary_dir / f"bucket_{bucket_index:05d}.json"
            stage1_bucket_output_dir = stage1_bucket_dir / f"bucket_{bucket_index:05d}"
            stage1_summary_path = stage1_bucket_output_dir / "aggregate_summary.json"

            if args.resume and bucket_summary_path.exists():
                bucket_summary = read_json(bucket_summary_path)
                if bucket_summary.get("status") == "stage1_complete":
                    append_event(events_path, "bucket_skipped_existing_success", bucket_index=bucket_index)
                    bucket_summary_paths.append(bucket_summary_path)
                    stage1_bucket_summary_paths.append(stage1_summary_path)
                    successful_run_paths.extend(bucket_summary.get("successful_wet_paths", []))
                    candidate_cursor += int(bucket_summary.get("attempted_count", target_count))
                    continue

            raw_bucket_dir = raw_dir / f"bucket_{bucket_index:05d}"
            bucket_record: dict[str, Any] = {
                "bucket_index": bucket_index,
                "status": "started",
                "started_at": utc_now(),
                "target_wet_count": target_count,
                "raw_bucket_dir": str(raw_bucket_dir),
                "stage1_output_dir": str(stage1_bucket_output_dir),
            }
            write_json(bucket_summary_path, bucket_record)
            append_event(events_path, "bucket_start", bucket_index=bucket_index, target_wet_count=target_count)

            download_summary = download_bucket(
                bucket_index=bucket_index,
                candidate_paths=candidate_paths[candidate_cursor:],
                target_count=target_count,
                raw_bucket_dir=raw_bucket_dir,
                download_concurrency=args.download_concurrency,
                download_timeout=args.download_timeout,
                download_file_timeout=args.download_file_timeout,
                download_max_tries=args.download_max_tries,
                download_retry_wait=args.download_retry_wait,
                aria2_lowest_speed_limit=args.aria2_lowest_speed_limit,
                events_path=events_path,
                cwd=cwd,
                skip_download=args.skip_download,
            )
            candidate_cursor += int(download_summary["attempted_count"])
            successful_run_paths.extend(download_summary["successful_wet_paths"])
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
        for bucket_summary_path in bucket_summary_paths:
            bucket_summary = read_json(bucket_summary_path)
            successful_run_paths.extend(bucket_summary.get("successful_wet_paths", []))
        append_event(events_path, "stage1_skipped", stage1_bucket_summary_count=len(stage1_bucket_summary_paths))

    write_lines(successful_paths_path, successful_run_paths)
    write_lines(successful_urls_path, wet_urls(successful_run_paths))
    append_event(
        events_path,
        "successful_wet_paths_written",
        wet_paths_file=str(successful_paths_path),
        wet_urls_file=str(successful_urls_path),
        successful_wet_count=len(successful_run_paths),
        attempted_candidate_count=candidate_cursor,
    )

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
        if not args.keep_stage1:
            stage2_command.append("--delete-input-after-write")
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
        deduped_docs_dir = stage2_dir / "deduped_docs"
        if args.keep_deduped_docs:
            append_event(
                events_path,
                "deduped_docs_cleanup_skipped",
                deduped_docs_dir=str(deduped_docs_dir),
            )
        elif deduped_docs_dir.exists():
            deduped_docs_bytes_before_cleanup = directory_size_bytes(deduped_docs_dir)
            append_event(
                events_path,
                "deduped_docs_cleanup_start",
                deduped_docs_dir=str(deduped_docs_dir),
                bytes_before_cleanup=deduped_docs_bytes_before_cleanup,
            )
            shutil.rmtree(deduped_docs_dir)
            append_event(
                events_path,
                "deduped_docs_cleanup_end",
                deduped_docs_dir=str(deduped_docs_dir),
                deleted_bytes=deduped_docs_bytes_before_cleanup,
            )
    else:
        append_event(events_path, "tokenize_skipped", tokenized_bin=str(tokenized_bin))

    stage2_summary = read_json(stage2_summary_path) if stage2_summary_path.exists() else {}
    tokenized_summary = read_json(tokenized_summary_path) if tokenized_summary_path.exists() else {}
    deduped_docs_dir = stage2_dir / "deduped_docs"
    final_report = {
        "status": "complete",
        "completed_at": utc_now(),
        "total_elapsed_seconds": time.time() - run_start,
        "manifest_path": str(manifest_path),
        "events_path": str(events_path),
        "candidate_wet_paths_file": str(candidate_paths_path),
        "wet_paths_file": str(successful_paths_path),
        "wet_urls_file": str(successful_urls_path),
        "successful_wet_count": len(successful_run_paths),
        "attempted_candidate_count": candidate_cursor,
        "bucket_summary_paths": [str(path) for path in bucket_summary_paths],
        "stage1_rollup_path": str(stage1_rollup_path),
        "stage1_rollup": stage1_rollup,
        "stage2_summary_path": str(stage2_summary_path),
        "stage2_summary": stage2_summary,
        "tokenized_bin": str(tokenized_bin),
        "tokenized_summary_path": str(tokenized_summary_path),
        "tokenized_summary": tokenized_summary,
        "deduped_docs_dir": str(deduped_docs_dir),
        "deduped_docs_retained": deduped_docs_dir.exists(),
        "keep_deduped_docs": args.keep_deduped_docs,
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
