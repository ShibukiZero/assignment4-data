from __future__ import annotations

import argparse
import gzip
import json
import random
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


DEFAULT_INPUT_PATH = Path("data/raw/wikipedia/extracted_urls.txt.gz")
DEFAULT_DATA_OUTPUT_DIR = Path("data/quality_classifier/positives")
DEFAULT_LOG_OUTPUT_DIR = Path("runs/quality_classifier_positive_urls")
DEFAULT_OUTPUT_URLS_PATH = DEFAULT_DATA_OUTPUT_DIR / "sampled_positive_urls.txt"
DEFAULT_OUTPUT_SUMMARY_PATH = DEFAULT_LOG_OUTPUT_DIR / "summary.json"

# These extensions are usually not useful for building a text quality classifier
# because they are likely to be binaries, media files, downloads, or documents
# that do not behave like ordinary HTML pages.
DEFAULT_BLOCKED_EXTENSIONS = {
    ".7z",
    ".avi",
    ".bin",
    ".bz2",
    ".csv",
    ".doc",
    ".docx",
    ".epub",
    ".gif",
    ".gz",
    ".iso",
    ".jar",
    ".jpeg",
    ".jpg",
    ".json",
    ".mov",
    ".mp3",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".ods",
    ".odp",
    ".odt",
    ".pdf",
    ".png",
    ".ppt",
    ".pptx",
    ".rar",
    ".svg",
    ".tar",
    ".tgz",
    ".tsv",
    ".txt",
    ".wav",
    ".webm",
    ".webp",
    ".xls",
    ".xlsx",
    ".xml",
    ".zip",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare candidate positive URLs for the quality classifier by sampling "
            "Wikipedia external links, lightly filtering them, and writing a deduplicated "
            "URL list suitable for downstream fetching with wget."
        )
    )
    parser.add_argument(
        "--input-path",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help="Path to the gzipped file containing one Wikipedia external URL per line.",
    )
    parser.add_argument(
        "--num-urls",
        type=int,
        default=5000,
        help="Final number of candidate positive URLs to write.",
    )
    parser.add_argument(
        "--oversample-factor",
        type=int,
        default=5,
        help=(
            "Reservoir sample this many times the final target before applying exact "
            "deduplication and per-domain caps."
        ),
    )
    parser.add_argument(
        "--max-urls-per-domain",
        type=int,
        default=20,
        help="Maximum number of retained URLs from the same registered host.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Random seed for reproducible sampling.",
    )
    parser.add_argument(
        "--output-urls-path",
        type=Path,
        default=DEFAULT_OUTPUT_URLS_PATH,
        help=(
            "Path to the output text file containing one sampled URL per line. "
            "This should usually point to a data directory rather than a review-log directory."
        ),
    )
    parser.add_argument(
        "--output-summary-path",
        type=Path,
        default=DEFAULT_OUTPUT_SUMMARY_PATH,
        help="Path to the JSON summary describing the filtering and sampling process.",
    )
    return parser.parse_args()


def open_text_for_read(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return path.open("rt", encoding="utf-8", errors="replace")


def normalize_url(raw_url: str) -> str | None:
    raw_url = raw_url.strip()
    if not raw_url:
        return None

    try:
        parsed = urlsplit(raw_url)
    except ValueError:
        return None

    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        return None

    if not parsed.netloc:
        return None

    host = parsed.netloc.lower()
    path = parsed.path or "/"

    # Drop fragments because they do not affect the fetched page content.
    # Keep query strings because they can select distinct content.
    return urlunsplit((scheme, host, path, parsed.query, ""))


def looks_like_fetchable_webpage(url: str) -> bool:
    parsed = urlsplit(url)
    path = parsed.path.lower()

    for suffix in DEFAULT_BLOCKED_EXTENSIONS:
        if path.endswith(suffix):
            return False

    return True


def reservoir_sample_candidate_urls(
    input_path: Path,
    *,
    sample_size: int,
    seed: int,
) -> tuple[list[str], dict[str, int]]:
    rng = random.Random(seed)
    reservoir: list[str] = []

    stats = {
        "num_raw_urls": 0,
        "num_invalid_or_unsupported_urls": 0,
        "num_blocked_by_extension": 0,
        "num_candidate_urls": 0,
    }

    with open_text_for_read(input_path) as src:
        for raw_url in src:
            stats["num_raw_urls"] += 1

            normalized_url = normalize_url(raw_url)
            if normalized_url is None:
                stats["num_invalid_or_unsupported_urls"] += 1
                continue

            if not looks_like_fetchable_webpage(normalized_url):
                stats["num_blocked_by_extension"] += 1
                continue

            stats["num_candidate_urls"] += 1

            if len(reservoir) < sample_size:
                reservoir.append(normalized_url)
                continue

            draw = rng.randint(1, stats["num_candidate_urls"])
            if draw <= sample_size:
                reservoir[draw - 1] = normalized_url

    return reservoir, stats


def dedupe_and_cap_domains(
    sampled_urls: list[str],
    *,
    num_urls: int,
    max_urls_per_domain: int,
    seed: int,
) -> tuple[list[str], dict[str, int]]:
    rng = random.Random(seed)
    shuffled_urls = list(sampled_urls)
    rng.shuffle(shuffled_urls)

    kept_urls: list[str] = []
    seen_urls: set[str] = set()
    domain_counts: Counter[str] = Counter()

    stats = {
        "num_duplicates_within_sample_pool": 0,
        "num_rejected_by_domain_cap": 0,
    }

    for url in shuffled_urls:
        if url in seen_urls:
            stats["num_duplicates_within_sample_pool"] += 1
            continue

        domain = urlsplit(url).netloc.lower()
        if domain_counts[domain] >= max_urls_per_domain:
            stats["num_rejected_by_domain_cap"] += 1
            continue

        seen_urls.add(url)
        domain_counts[domain] += 1
        kept_urls.append(url)

        if len(kept_urls) >= num_urls:
            break

    return kept_urls, stats


def write_url_list(path: Path, urls: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for url in urls:
            f.write(url)
            f.write("\n")


def main() -> None:
    args = parse_args()

    input_path: Path = args.input_path
    num_urls: int = args.num_urls
    oversample_factor: int = args.oversample_factor
    max_urls_per_domain: int = args.max_urls_per_domain
    seed: int = args.seed
    output_urls_path: Path = args.output_urls_path
    output_summary_path: Path = args.output_summary_path

    if not input_path.exists():
        raise FileNotFoundError(f"Input path does not exist: {input_path}")
    if num_urls <= 0:
        raise ValueError("--num-urls must be positive.")
    if oversample_factor <= 0:
        raise ValueError("--oversample-factor must be positive.")
    if max_urls_per_domain <= 0:
        raise ValueError("--max-urls-per-domain must be positive.")

    reservoir_size = num_urls * oversample_factor
    sampled_urls, sample_stats = reservoir_sample_candidate_urls(
        input_path=input_path,
        sample_size=reservoir_size,
        seed=seed,
    )
    final_urls, postprocess_stats = dedupe_and_cap_domains(
        sampled_urls,
        num_urls=num_urls,
        max_urls_per_domain=max_urls_per_domain,
        seed=seed,
    )

    if not final_urls:
        raise RuntimeError("No positive candidate URLs survived filtering and sampling.")

    final_domain_counts = Counter(urlsplit(url).netloc.lower() for url in final_urls)

    write_url_list(output_urls_path, final_urls)
    output_urls_size_bytes = output_urls_path.stat().st_size

    summary = {
        "input_path": str(input_path),
        "output_urls_path": str(output_urls_path),
        "num_urls_requested": num_urls,
        "num_urls_returned": len(final_urls),
        "output_urls_size_bytes": output_urls_size_bytes,
        "oversample_factor": oversample_factor,
        "reservoir_size": reservoir_size,
        "max_urls_per_domain": max_urls_per_domain,
        "seed": seed,
        **sample_stats,
        **postprocess_stats,
        "top_domains": [
            {"domain": domain, "count": count}
            for domain, count in final_domain_counts.most_common(20)
        ],
        "sample_preview_urls": final_urls[:10],
        "suggested_wget_command": (
            f"wget --timeout=5 -i {output_urls_path} "
            f"--warc-file={output_urls_path.with_suffix('')} -O /dev/null"
        ),
    }
    output_summary_path.parent.mkdir(parents=True, exist_ok=True)
    output_summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print(f"Wrote {output_urls_path}")
    print(f"Wrote {output_summary_path}")
    print(
        "Sampling stats: "
        f"{sample_stats['num_raw_urls']} raw URLs, "
        f"{sample_stats['num_candidate_urls']} candidate URLs after filtering, "
        f"{len(final_urls)} final URLs kept"
    )
    print(
        "Post-processing stats: "
        f"{postprocess_stats['num_duplicates_within_sample_pool']} duplicates dropped, "
        f"{postprocess_stats['num_rejected_by_domain_cap']} URLs dropped by domain cap"
    )
    print("Suggested next step:")
    print(summary["suggested_wget_command"])


if __name__ == "__main__":
    main()
