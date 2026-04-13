from __future__ import annotations

import argparse
import concurrent.futures
import glob
import json
from collections import Counter
from pathlib import Path
import time
from urllib.parse import urlparse

from fastwarc.warc import ArchiveIterator, WarcRecordType
from tldextract import TLDExtract
from xopen import xopen

from cs336_data.harmful_content import classify_nsfw, classify_toxic_speech
from cs336_data.langid import identify_language
from cs336_data.pii import mask_emails, mask_ips, mask_phone_numbers
from cs336_data.quality import passes_gopher_quality_filters
from cs336_data.quality_classifier import classify_quality


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the Chapter 4 stage-1 filtering pipeline over a directory of "
            "Common Crawl WET files. This stage only applies document-local "
            "filters so it can later be used both for the current 50-file "
            "sample and for a larger download+process workflow."
        )
    )
    parser.add_argument(
        "--input-glob",
        required=True,
        help="Glob pattern for WET files, e.g. '/root/autodl-tmp/raw/CC-MAIN-2026-12_wet_sample/*.warc.wet.gz'.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory where kept docs, review logs, and summaries will be written.",
    )
    parser.add_argument(
        "--lang-threshold",
        type=float,
        default=0.8,
        help="Minimum fastText confidence for keeping English documents.",
    )
    parser.add_argument(
        "--quality-threshold",
        type=float,
        default=0.65,
        help="Minimum quality-classifier score when the predicted label is 'wiki'.",
    )
    parser.add_argument(
        "--review-chars",
        type=int,
        default=500,
        help="Number of masked text characters to keep in review logs.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of WET files to process in parallel.",
    )
    return parser.parse_args()


def registered_domain_from_url(extractor: TLDExtract, url: str) -> str:
    extracted = extractor(url)
    if not extracted.domain:
        return ""
    if extracted.suffix:
        return f"{extracted.domain}.{extracted.suffix}"
    return extracted.domain


def text_preview(text: str, review_chars: int) -> str:
    compact = " ".join(text.split())
    return compact[:review_chars]


def apply_pii_masks(text: str) -> tuple[str, dict[str, int]]:
    masked_text, email_count = mask_emails(text)
    masked_text, phone_count = mask_phone_numbers(masked_text)
    masked_text, ip_count = mask_ips(masked_text)
    return masked_text, {
        "emails": email_count,
        "phones": phone_count,
        "ips": ip_count,
    }


def wet_records(input_path: Path):
    with xopen(input_path, "rb") as handle:
        for record in ArchiveIterator(handle, record_types=WarcRecordType.conversion):
            target_uri = record.headers.get("WARC-Target-URI")
            if not target_uri:
                continue

            raw_bytes = record.reader.read()
            text = raw_bytes.decode("utf-8", errors="ignore")
            yield {
                "target_uri": target_uri,
                "record_id": record.record_id,
                "text": text,
            }


def evaluate_document(
    *,
    extractor: TLDExtract,
    source_wet_path: Path,
    record_id: str,
    target_uri: str,
    text: str,
    lang_threshold: float,
    quality_threshold: float,
    review_chars: int,
) -> tuple[str, dict]:
    stripped_text = text.strip()
    domain = registered_domain_from_url(extractor, target_uri)
    parsed_url = urlparse(target_uri)

    base_record = {
        "source_wet_path": str(source_wet_path),
        "record_id": record_id,
        "target_uri": target_uri,
        "registered_domain": domain,
        "url_scheme": parsed_url.scheme,
    }

    if not stripped_text:
        return "empty_text", {
            **base_record,
            "decision": "drop",
            "drop_reason": "empty_text",
            "text_preview": "",
        }

    language, language_score = identify_language(stripped_text)
    if language != "en" or language_score < lang_threshold:
        return "language", {
            **base_record,
            "decision": "drop",
            "drop_reason": "language",
            "language": language,
            "language_score": language_score,
            "text_preview": text_preview(stripped_text, review_chars),
        }

    nsfw_label, nsfw_score = classify_nsfw(stripped_text)
    toxic_label, toxic_score = classify_toxic_speech(stripped_text)
    if nsfw_label == "nsfw" or toxic_label == "toxic":
        return "harmful", {
            **base_record,
            "decision": "drop",
            "drop_reason": "harmful",
            "language": language,
            "language_score": language_score,
            "nsfw_label": nsfw_label,
            "nsfw_score": nsfw_score,
            "toxic_label": toxic_label,
            "toxic_score": toxic_score,
            "text_preview": text_preview(stripped_text, review_chars),
        }

    if not passes_gopher_quality_filters(stripped_text):
        return "gopher_quality", {
            **base_record,
            "decision": "drop",
            "drop_reason": "gopher_quality",
            "language": language,
            "language_score": language_score,
            "nsfw_label": nsfw_label,
            "nsfw_score": nsfw_score,
            "toxic_label": toxic_label,
            "toxic_score": toxic_score,
            "text_preview": text_preview(stripped_text, review_chars),
        }

    quality_label, quality_score = classify_quality(stripped_text)
    if quality_label != "wiki" or quality_score < quality_threshold:
        return "quality_classifier", {
            **base_record,
            "decision": "drop",
            "drop_reason": "quality_classifier",
            "language": language,
            "language_score": language_score,
            "nsfw_label": nsfw_label,
            "nsfw_score": nsfw_score,
            "toxic_label": toxic_label,
            "toxic_score": toxic_score,
            "quality_label": quality_label,
            "quality_score": quality_score,
            "text_preview": text_preview(stripped_text, review_chars),
        }

    masked_text, pii_counts = apply_pii_masks(stripped_text)
    pii_any = any(count > 0 for count in pii_counts.values())

    return "keep", {
        **base_record,
        "decision": "keep",
        "language": language,
        "language_score": language_score,
        "nsfw_label": nsfw_label,
        "nsfw_score": nsfw_score,
        "toxic_label": toxic_label,
        "toxic_score": toxic_score,
        "quality_label": quality_label,
        "quality_score": quality_score,
        "pii_counts": pii_counts,
        "pii_modified": pii_any,
        "text": masked_text,
        "text_preview": text_preview(masked_text, review_chars),
    }


def process_single_wet_file(
    input_path: str,
    output_dir: str,
    lang_threshold: float,
    quality_threshold: float,
    review_chars: int,
) -> str:
    input_path_obj = Path(input_path)
    output_dir_obj = Path(output_dir)

    kept_dir = output_dir_obj / "kept_docs"
    review_dir = output_dir_obj / "review_logs"
    summary_dir = output_dir_obj / "summaries"
    kept_dir.mkdir(parents=True, exist_ok=True)
    review_dir.mkdir(parents=True, exist_ok=True)
    summary_dir.mkdir(parents=True, exist_ok=True)
    extractor = TLDExtract(suffix_list_urls=None)

    kept_path = kept_dir / f"{input_path_obj.name}.jsonl"
    review_path = review_dir / f"{input_path_obj.name}.jsonl"
    summary_path = summary_dir / f"{input_path_obj.name}.json"

    counters = Counter()
    start_time = time.time()

    with xopen(kept_path, "wt") as kept_handle, xopen(review_path, "wt") as review_handle:
        for record in wet_records(input_path_obj):
            counters["records_seen"] += 1

            decision_key, payload = evaluate_document(
                extractor=extractor,
                source_wet_path=input_path_obj,
                record_id=record["record_id"],
                target_uri=record["target_uri"],
                text=record["text"],
                lang_threshold=lang_threshold,
                quality_threshold=quality_threshold,
                review_chars=review_chars,
            )
            counters[f"decision_{decision_key}"] += 1

            if payload["decision"] == "keep":
                kept_payload = dict(payload)
                kept_handle.write(json.dumps(kept_payload, ensure_ascii=False) + "\n")
                counters["pii_modified_docs"] += int(kept_payload["pii_modified"])
            else:
                review_handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    elapsed_seconds = time.time() - start_time
    summary = {
        "source_wet_path": str(input_path_obj),
        "kept_docs_path": str(kept_path),
        "review_log_path": str(review_path),
        "elapsed_seconds": elapsed_seconds,
        "counts": dict(counters),
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    return str(summary_path)


def load_summary(summary_path: Path) -> dict:
    return json.loads(summary_path.read_text(encoding="utf-8"))


def main() -> None:
    args = parse_args()

    input_paths = sorted(Path(path) for path in glob.glob(args.input_glob))
    if not input_paths:
        raise FileNotFoundError(f"No WET files matched input glob: {args.input_glob}")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    aggregate = Counter()
    file_summaries: list[dict] = []
    worker_count = min(args.workers, len(input_paths))

    total_start = time.time()
    with concurrent.futures.ProcessPoolExecutor(max_workers=worker_count) as executor:
        futures: list[concurrent.futures.Future[str]] = []
        for input_path in input_paths:
            future = executor.submit(
                process_single_wet_file,
                str(input_path),
                str(output_dir),
                args.lang_threshold,
                args.quality_threshold,
                args.review_chars,
            )
            futures.append(future)

        for future in concurrent.futures.as_completed(futures):
            summary_path = Path(future.result())
            summary = load_summary(summary_path)
            file_summaries.append(summary)
            aggregate.update(summary["counts"])

    aggregate_summary = {
        "input_glob": args.input_glob,
        "num_input_files": len(input_paths),
        "lang_threshold": args.lang_threshold,
        "quality_threshold": args.quality_threshold,
        "review_chars": args.review_chars,
        "workers": worker_count,
        "total_elapsed_seconds": time.time() - total_start,
        "aggregate_counts": dict(aggregate),
        "per_file_summary_paths": [str((output_dir / "summaries" / f"{path.name}.json")) for path in input_paths],
    }
    (output_dir / "aggregate_summary.json").write_text(
        json.dumps(aggregate_summary, indent=2, ensure_ascii=False) + "\n"
    )


if __name__ == "__main__":
    main()
