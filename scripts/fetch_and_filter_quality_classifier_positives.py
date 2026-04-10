from __future__ import annotations

import argparse
import json
import re
import socket
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

from cs336_data.html_text import extract_text_from_html_bytes
from cs336_data.langid import identify_language
from cs336_data.quality import passes_gopher_quality_filters


DEFAULT_INPUT_URLS_PATH = Path("/root/autodl-tmp/quality_classifier/positives/sampled_positive_urls.txt")
DEFAULT_DATA_OUTPUT_DIR = Path("/root/autodl-tmp/quality_classifier/positives")
DEFAULT_LOG_OUTPUT_DIR = Path(".agents/logs/quality_classifier_positive_texts")
DEFAULT_OUTPUT_DOCS_PATH = DEFAULT_DATA_OUTPUT_DIR / "candidate_positive_docs.jsonl"
DEFAULT_OUTPUT_RESULTS_PATH = DEFAULT_DATA_OUTPUT_DIR / "fetch_results.jsonl"
DEFAULT_OUTPUT_SUMMARY_PATH = DEFAULT_LOG_OUTPUT_DIR / "summary.json"

DEFAULT_ALLOWED_CONTENT_TYPES = {
    "application/xhtml+xml",
    "text/html",
}

DEFAULT_EXACT_BLOCKED_HOSTS = {
    "aboutus.com",
    "books.google.com",
    "dashboard.wikiedu.org",
    "doi.org",
    "entities.oclc.org",
    "search.worldcat.org",
    "viaf.org",
    "web.archive.org",
    "www.dnsstuff.com",
    "www.google.com",
    "www.hearxgroup.com",
    "www.minorplanet.info",
    "www.stopforumspam.com",
}

DEFAULT_BLOCKED_HOST_SUFFIXES = {
    ".wmcloud.org",
    ".toolforge.org",
    ".wmflabs.org",
}

DEFAULT_NAVIGATION_KEYWORDS = {
    "about",
    "archives",
    "calendar",
    "careers",
    "catalog",
    "contact",
    "cookie",
    "donate",
    "faq",
    "favorites",
    "home",
    "jobs",
    "language",
    "login",
    "membership",
    "menu",
    "newsletter",
    "policy",
    "press",
    "privacy",
    "register",
    "search",
    "shop",
    "sign",
    "sitemap",
    "subscribe",
    "support",
    "terms",
    "tickets",
    "watch",
}

USER_AGENT = (
    "Mozilla/5.0 (compatible; CS336Assignment4PositiveSampler/1.0; "
    "+https://cs336.stanford.edu/)"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch and lightly filter candidate positive URLs for the quality "
            "classifier. This stage keeps the large outputs on the data disk and "
            "writes only a compact summary to `.agents/logs/`."
        )
    )
    parser.add_argument(
        "--input-urls-path",
        type=Path,
        default=DEFAULT_INPUT_URLS_PATH,
        help="Path to the newline-delimited candidate positive URL list.",
    )
    parser.add_argument(
        "--output-docs-path",
        type=Path,
        default=DEFAULT_OUTPUT_DOCS_PATH,
        help="Path to the JSONL file containing accepted positive text documents.",
    )
    parser.add_argument(
        "--output-results-path",
        type=Path,
        default=DEFAULT_OUTPUT_RESULTS_PATH,
        help="Path to the JSONL file containing per-URL fetch and filtering outcomes.",
    )
    parser.add_argument(
        "--output-summary-path",
        type=Path,
        default=DEFAULT_OUTPUT_SUMMARY_PATH,
        help="Path to the compact JSON summary for this run.",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=32,
        help="Number of concurrent URL fetch workers.",
    )
    parser.add_argument(
        "--connect-timeout-seconds",
        type=float,
        default=5.0,
        help="Socket timeout used for each URL fetch.",
    )
    parser.add_argument(
        "--max-download-bytes",
        type=int,
        default=1_000_000,
        help="Maximum number of response bytes to download per page.",
    )
    parser.add_argument(
        "--min-text-chars",
        type=int,
        default=400,
        help="Minimum extracted-text length required for an accepted positive page.",
    )
    parser.add_argument(
        "--required-language",
        type=str,
        default="en",
        help="Keep only pages whose top language-ID label matches this value.",
    )
    parser.add_argument(
        "--min-language-score",
        type=float,
        default=0.6,
        help="Minimum language-ID confidence required for accepted positive pages.",
    )
    return parser.parse_args()


def iter_input_urls(path: Path) -> Iterable[str]:
    if not path.exists():
        raise FileNotFoundError(f"Input URL list does not exist: {path}")

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            url = line.strip()
            if url:
                yield url


def classify_url_heuristic(url: str) -> str | None:
    parsed = urlsplit(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    query = parse_qs(parsed.query, keep_blank_values=True)
    path_segments = [segment for segment in path.split("/") if segment]

    if host in DEFAULT_EXACT_BLOCKED_HOSTS:
        if host == "web.archive.org":
            return "archive_page"
        if host in {"www.google.com", "books.google.com"}:
            return "google_page"
        if host == "doi.org":
            return "doi_redirector"
        if host == "search.worldcat.org":
            return "catalog_search_page"
        if host == "viaf.org":
            return "identifier_page"
        if host == "dashboard.wikiedu.org":
            return "dashboard_page"
        if host == "www.hearxgroup.com":
            return "marketing_homepage"
        if host in {"aboutus.com", "entities.oclc.org", "www.dnsstuff.com", "www.minorplanet.info", "www.stopforumspam.com"}:
            return "service_or_tool_site"

    for suffix in DEFAULT_BLOCKED_HOST_SUFFIXES:
        if host.endswith(suffix):
            return "wiki_tool_page"

    if host == "www.olympedia.org" and path.startswith("/athletes/"):
        return "structured_reference_page"
    if host == "www.itis.gov" and "/servlet/singlerpt/" in path:
        return "structured_reference_page"
    if host == "www.overstrand.gov.za" and path in {"", "/"}:
        return "municipal_homepage"

    if not path_segments and query:
        return "homepage_with_query"
    if host == "www.google.com" and path == "/search":
        return "search_results_page"
    if "search" in query and host not in {"www.latimes.com"}:
        return "query_search_page"

    return None


def split_path_segments(path: str) -> list[str]:
    return [segment for segment in path.split("/") if segment]


def count_long_prose_spans(text: str) -> int:
    spans = re.split(r"(?:\n{2,}|(?<=[.!?])\s+)", text)
    count = 0
    for span in spans:
        cleaned = span.strip()
        if not cleaned:
            continue

        words = cleaned.split()
        if len(words) >= 12 and len(cleaned) >= 80:
            count += 1

    return count


def count_navigation_keyword_hits(text: str, *, max_chars: int = 1500) -> int:
    snippet = text[:max_chars].lower()
    return sum(
        len(re.findall(rf"\b{re.escape(keyword)}\b", snippet))
        for keyword in DEFAULT_NAVIGATION_KEYWORDS
    )


def classify_fetch_error(exc: Exception) -> str:
    if isinstance(exc, HTTPError):
        return f"http_error_{exc.code}"

    if isinstance(exc, URLError):
        reason = exc.reason
        if isinstance(reason, socket.timeout):
            return "timeout"
        if isinstance(reason, str) and "timed out" in reason.lower():
            return "timeout"
        if isinstance(reason, OSError):
            return "connection_error"
        return "url_error"

    if isinstance(exc, TimeoutError):
        return "timeout"

    return "fetch_error"


def fetch_single_url(
    url: str,
    *,
    timeout_seconds: float,
    max_download_bytes: int,
) -> dict[str, object]:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
        },
    )

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            final_url = response.geturl()
            http_status = getattr(response, "status", None) or response.getcode()
            content_type = response.headers.get_content_type()

            if content_type not in DEFAULT_ALLOWED_CONTENT_TYPES:
                return {
                    "input_url": url,
                    "final_url": final_url,
                    "http_status": int(http_status),
                    "content_type": content_type,
                    "outcome": "reject",
                    "reason": "non_html_content_type",
                }

            chunks: list[bytes] = []
            total_bytes = 0

            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break

                total_bytes += len(chunk)
                if total_bytes > max_download_bytes:
                    return {
                        "input_url": url,
                        "final_url": final_url,
                        "http_status": int(http_status),
                        "content_type": content_type,
                        "downloaded_bytes": total_bytes,
                        "outcome": "reject",
                        "reason": "response_too_large",
                    }

                chunks.append(chunk)

            return {
                "input_url": url,
                "final_url": final_url,
                "http_status": int(http_status),
                "content_type": content_type,
                "downloaded_bytes": total_bytes,
                "html_bytes": b"".join(chunks),
                "outcome": "fetched",
            }
    except Exception as exc:
        return {
            "input_url": url,
            "final_url": None,
            "http_status": None,
            "content_type": None,
            "outcome": "reject",
            "reason": classify_fetch_error(exc),
        }


def process_fetched_page(
    fetch_result: dict[str, object],
    *,
    min_text_chars: int,
    required_language: str,
    min_language_score: float,
) -> tuple[dict[str, object], dict[str, object] | None]:
    final_url = str(fetch_result["final_url"])
    url_heuristic_reason = classify_url_heuristic(final_url)
    if url_heuristic_reason is not None:
        result_row = {
            "input_url": fetch_result["input_url"],
            "final_url": final_url,
            "http_status": fetch_result["http_status"],
            "content_type": fetch_result["content_type"],
            "downloaded_bytes": fetch_result["downloaded_bytes"],
            "outcome": "reject",
            "reason": url_heuristic_reason,
        }
        return result_row, None

    html_bytes = bytes(fetch_result["html_bytes"])

    try:
        extracted_text = extract_text_from_html_bytes(html_bytes)
    except Exception:
        result_row = {
            "input_url": fetch_result["input_url"],
            "final_url": final_url,
            "http_status": fetch_result["http_status"],
            "content_type": fetch_result["content_type"],
            "downloaded_bytes": fetch_result["downloaded_bytes"],
            "outcome": "reject",
            "reason": "extraction_failure",
        }
        return result_row, None

    stripped_text = extracted_text.strip()
    if len(stripped_text) < min_text_chars:
        result_row = {
            "input_url": fetch_result["input_url"],
            "final_url": final_url,
            "http_status": fetch_result["http_status"],
            "content_type": fetch_result["content_type"],
            "downloaded_bytes": fetch_result["downloaded_bytes"],
            "extracted_text_chars": len(stripped_text),
            "outcome": "reject",
            "reason": "text_too_short",
        }
        return result_row, None

    path_depth = len(split_path_segments(urlsplit(final_url).path))
    long_prose_spans = count_long_prose_spans(stripped_text)
    navigation_keyword_hits = count_navigation_keyword_hits(stripped_text)

    if path_depth <= 1 and navigation_keyword_hits >= 10 and long_prose_spans < 4:
        result_row = {
            "input_url": fetch_result["input_url"],
            "final_url": final_url,
            "http_status": fetch_result["http_status"],
            "content_type": fetch_result["content_type"],
            "downloaded_bytes": fetch_result["downloaded_bytes"],
            "extracted_text_chars": len(stripped_text),
            "path_depth": path_depth,
            "long_prose_spans": long_prose_spans,
            "navigation_keyword_hits": navigation_keyword_hits,
            "outcome": "reject",
            "reason": "homepage_like_navigation",
        }
        return result_row, None

    if navigation_keyword_hits >= 18 and long_prose_spans < 3:
        result_row = {
            "input_url": fetch_result["input_url"],
            "final_url": final_url,
            "http_status": fetch_result["http_status"],
            "content_type": fetch_result["content_type"],
            "downloaded_bytes": fetch_result["downloaded_bytes"],
            "extracted_text_chars": len(stripped_text),
            "path_depth": path_depth,
            "long_prose_spans": long_prose_spans,
            "navigation_keyword_hits": navigation_keyword_hits,
            "outcome": "reject",
            "reason": "navigation_heavy_page",
        }
        return result_row, None

    language_label, language_score = identify_language(stripped_text)
    if language_label != required_language or language_score < min_language_score:
        result_row = {
            "input_url": fetch_result["input_url"],
            "final_url": final_url,
            "http_status": fetch_result["http_status"],
            "content_type": fetch_result["content_type"],
            "downloaded_bytes": fetch_result["downloaded_bytes"],
            "extracted_text_chars": len(stripped_text),
            "path_depth": path_depth,
            "long_prose_spans": long_prose_spans,
            "navigation_keyword_hits": navigation_keyword_hits,
            "language_label": language_label,
            "language_score": language_score,
            "outcome": "reject",
            "reason": "language_filtered",
        }
        return result_row, None

    passes_gopher_filter = passes_gopher_quality_filters(stripped_text)
    if not passes_gopher_filter:
        result_row = {
            "input_url": fetch_result["input_url"],
            "final_url": final_url,
            "http_status": fetch_result["http_status"],
            "content_type": fetch_result["content_type"],
            "downloaded_bytes": fetch_result["downloaded_bytes"],
            "extracted_text_chars": len(stripped_text),
            "path_depth": path_depth,
            "long_prose_spans": long_prose_spans,
            "navigation_keyword_hits": navigation_keyword_hits,
            "language_label": language_label,
            "language_score": language_score,
            "passes_gopher_filter": False,
            "outcome": "reject",
            "reason": "gopher_filtered",
        }
        return result_row, None

    result_row = {
        "input_url": fetch_result["input_url"],
        "final_url": final_url,
        "http_status": fetch_result["http_status"],
        "content_type": fetch_result["content_type"],
        "downloaded_bytes": fetch_result["downloaded_bytes"],
        "extracted_text_chars": len(stripped_text),
        "path_depth": path_depth,
        "long_prose_spans": long_prose_spans,
        "navigation_keyword_hits": navigation_keyword_hits,
        "language_label": language_label,
        "language_score": language_score,
        "passes_gopher_filter": True,
        "outcome": "keep",
        "reason": "accepted_positive_candidate",
    }
    doc_row = {
        "input_url": fetch_result["input_url"],
        "final_url": final_url,
        "http_status": fetch_result["http_status"],
        "content_type": fetch_result["content_type"],
        "downloaded_bytes": fetch_result["downloaded_bytes"],
        "path_depth": path_depth,
        "long_prose_spans": long_prose_spans,
        "navigation_keyword_hits": navigation_keyword_hits,
        "language_label": language_label,
        "language_score": language_score,
        "passes_gopher_filter": True,
        "extracted_text": stripped_text,
    }
    return result_row, doc_row


def write_jsonl_row(handle, row: dict[str, object]) -> None:
    handle.write(json.dumps(row, ensure_ascii=False))
    handle.write("\n")


def main() -> None:
    args = parse_args()

    input_urls_path: Path = args.input_urls_path
    output_docs_path: Path = args.output_docs_path
    output_results_path: Path = args.output_results_path
    output_summary_path: Path = args.output_summary_path
    max_workers: int = args.max_workers
    timeout_seconds: float = args.connect_timeout_seconds
    max_download_bytes: int = args.max_download_bytes
    min_text_chars: int = args.min_text_chars
    required_language: str = args.required_language
    min_language_score: float = args.min_language_score

    if max_workers <= 0:
        raise ValueError("--max-workers must be positive.")
    if timeout_seconds <= 0:
        raise ValueError("--connect-timeout-seconds must be positive.")
    if max_download_bytes <= 0:
        raise ValueError("--max-download-bytes must be positive.")
    if min_text_chars <= 0:
        raise ValueError("--min-text-chars must be positive.")
    if not 0.0 <= min_language_score <= 1.0:
        raise ValueError("--min-language-score must lie in [0, 1].")

    input_urls = list(iter_input_urls(input_urls_path))
    if not input_urls:
        raise RuntimeError("Input URL list is empty.")

    output_docs_path.parent.mkdir(parents=True, exist_ok=True)
    output_results_path.parent.mkdir(parents=True, exist_ok=True)
    output_summary_path.parent.mkdir(parents=True, exist_ok=True)

    stats = Counter()
    rejection_reasons = Counter()
    kept_final_domains = Counter()
    kept_preview: list[dict[str, object]] = []
    rejected_preview: list[dict[str, object]] = []

    stats["num_input_urls"] = len(input_urls)

    with (
        output_docs_path.open("w", encoding="utf-8", newline="\n") as docs_f,
        output_results_path.open("w", encoding="utf-8", newline="\n") as results_f,
        ThreadPoolExecutor(max_workers=max_workers) as executor,
    ):
        pending: dict[Future[dict[str, object]], str] = {}
        url_iter = iter(input_urls)

        def submit_one() -> bool:
            try:
                url = next(url_iter)
            except StopIteration:
                return False

            heuristic_reason = classify_url_heuristic(url)
            if heuristic_reason is not None:
                result_row = {
                    "input_url": url,
                    "final_url": None,
                    "http_status": None,
                    "content_type": None,
                    "outcome": "reject",
                    "reason": heuristic_reason,
                }
                write_jsonl_row(results_f, result_row)
                stats["num_processed_urls"] += 1
                rejection_reasons[heuristic_reason] += 1
                if len(rejected_preview) < 5:
                    rejected_preview.append(result_row)
                return True

            future = executor.submit(
                fetch_single_url,
                url,
                timeout_seconds=timeout_seconds,
                max_download_bytes=max_download_bytes,
            )
            pending[future] = url
            stats["num_fetch_attempted"] += 1
            return True

        max_pending = max_workers * 2
        while len(pending) < max_pending and submit_one():
            pass

        while pending:
            done, _ = wait(set(pending.keys()), return_when=FIRST_COMPLETED)
            for future in done:
                fetch_result = future.result()
                pending.pop(future, None)

                if fetch_result["outcome"] == "reject":
                    result_row = {
                        "input_url": fetch_result["input_url"],
                        "final_url": fetch_result["final_url"],
                        "http_status": fetch_result["http_status"],
                        "content_type": fetch_result["content_type"],
                        "outcome": "reject",
                        "reason": fetch_result["reason"],
                    }
                    if "downloaded_bytes" in fetch_result:
                        result_row["downloaded_bytes"] = fetch_result["downloaded_bytes"]
                    write_jsonl_row(results_f, result_row)
                    stats["num_processed_urls"] += 1
                    rejection_reasons[str(fetch_result["reason"])] += 1
                    if len(rejected_preview) < 5:
                        rejected_preview.append(result_row)
                else:
                    stats["num_fetch_succeeded"] += 1
                    result_row, doc_row = process_fetched_page(
                        fetch_result,
                        min_text_chars=min_text_chars,
                        required_language=required_language,
                        min_language_score=min_language_score,
                    )
                    write_jsonl_row(results_f, result_row)
                    stats["num_processed_urls"] += 1

                    if doc_row is None:
                        rejection_reasons[str(result_row["reason"])] += 1
                        if len(rejected_preview) < 5:
                            rejected_preview.append(result_row)
                    else:
                        write_jsonl_row(docs_f, doc_row)
                        stats["num_docs_kept"] += 1
                        final_domain = urlsplit(str(doc_row["final_url"])).netloc.lower()
                        kept_final_domains[final_domain] += 1
                        if len(kept_preview) < 5:
                            kept_preview.append(
                                {
                                    "final_url": doc_row["final_url"],
                                    "language_score": doc_row["language_score"],
                                    "downloaded_bytes": doc_row["downloaded_bytes"],
                                    "text_preview": doc_row["extracted_text"][:200],
                                }
                            )

                while len(pending) < max_pending and submit_one():
                    pass

    output_docs_size_bytes = output_docs_path.stat().st_size if output_docs_path.exists() else 0
    output_results_size_bytes = output_results_path.stat().st_size if output_results_path.exists() else 0

    summary = {
        "input_urls_path": str(input_urls_path),
        "output_docs_path": str(output_docs_path),
        "output_results_path": str(output_results_path),
        "output_docs_size_bytes": output_docs_size_bytes,
        "output_results_size_bytes": output_results_size_bytes,
        "max_workers": max_workers,
        "connect_timeout_seconds": timeout_seconds,
        "max_download_bytes": max_download_bytes,
        "min_text_chars": min_text_chars,
        "required_language": required_language,
        "min_language_score": min_language_score,
        **stats,
        "fractions": {
            "fetch_attempt_fraction": stats["num_fetch_attempted"] / stats["num_input_urls"]
            if stats["num_input_urls"]
            else 0.0,
            "fetch_success_fraction": stats["num_fetch_succeeded"] / stats["num_fetch_attempted"]
            if stats["num_fetch_attempted"]
            else 0.0,
            "kept_fraction_of_all_inputs": stats["num_docs_kept"] / stats["num_input_urls"]
            if stats["num_input_urls"]
            else 0.0,
            "kept_fraction_of_fetch_attempts": stats["num_docs_kept"] / stats["num_fetch_attempted"]
            if stats["num_fetch_attempted"]
            else 0.0,
        },
        "rejection_reasons": dict(rejection_reasons.most_common()),
        "top_kept_final_domains": [
            {"domain": domain, "count": count}
            for domain, count in kept_final_domains.most_common(20)
        ],
        "kept_preview": kept_preview,
        "rejected_preview": rejected_preview,
    }
    output_summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print(f"Wrote {output_docs_path}")
    print(f"Wrote {output_results_path}")
    print(f"Wrote {output_summary_path}")
    print(
        "Fetch/filter stats: "
        f"{stats['num_input_urls']} input URLs, "
        f"{stats['num_fetch_attempted']} fetch attempts, "
        f"{stats['num_fetch_succeeded']} fetched HTML pages, "
        f"{stats['num_docs_kept']} accepted positive candidates"
    )
    print("Top rejection reasons:")
    for reason, count in rejection_reasons.most_common(10):
        print(f"  {reason}: {count}")


if __name__ == "__main__":
    main()
