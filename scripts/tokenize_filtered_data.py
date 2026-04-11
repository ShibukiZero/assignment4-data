from __future__ import annotations

import argparse
import glob
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import time

import numpy as np
from transformers import AutoTokenizer
from xopen import xopen


DEFAULT_TOKENIZER_PATH = "/root/autodl-tmp/tokenizers/gpt2"
DEFAULT_OUTPUT_PATH = Path("/root/autodl-tmp/tokenized/filtered_train_gpt2.bin")


@dataclass
class FileStats:
    documents: int = 0
    skipped_missing_text: int = 0
    tokens: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Tokenize filtered Chapter 4 JSONL documents with the GPT-2 tokenizer, "
            "append EOS after every document, and serialize the result as a uint16 .bin file."
        )
    )
    parser.add_argument(
        "--input-glob",
        required=True,
        help="Glob pattern for final filtered/deduped JSONL files, e.g. '.../deduped_docs/*.jsonl'.",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Path to the output uint16 token .bin file.",
    )
    parser.add_argument(
        "--summary-path",
        type=Path,
        default=None,
        help="Path to a JSON summary. Defaults to '<output-path>.summary.json'.",
    )
    parser.add_argument(
        "--tokenizer",
        default=DEFAULT_TOKENIZER_PATH,
        help="Tokenizer path or model name. Use the same GPT-2 tokenizer as the Paloma validation bin.",
    )
    parser.add_argument(
        "--text-field",
        default="text",
        help="JSON field containing the filtered document text.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=256,
        help="Number of documents to batch per tokenizer call.",
    )
    parser.add_argument(
        "--max-docs",
        type=int,
        default=None,
        help="Optional cap for quick smoke tests. Omit for the full dataset.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow replacing an existing output .bin or summary file.",
    )
    return parser.parse_args()


def flush_token_batch(
    *,
    tokenizer,
    output_handle,
    texts: list[str],
    file_names: list[str],
    eos_token_id: int,
) -> tuple[int, Counter[str]]:
    if not texts:
        return 0, Counter()

    encoded_batch = tokenizer(
        texts,
        add_special_tokens=False,
        return_attention_mask=False,
        return_token_type_ids=False,
    )["input_ids"]

    flat_ids: list[int] = []
    token_counts_by_file: Counter[str] = Counter()
    for file_name, token_ids in zip(file_names, encoded_batch, strict=True):
        flat_ids.extend(token_ids)
        flat_ids.append(eos_token_id)
        token_counts_by_file[file_name] += len(token_ids) + 1

    token_array = np.asarray(flat_ids, dtype=np.uint16)
    token_array.tofile(output_handle)
    return len(flat_ids), token_counts_by_file


def main() -> None:
    args = parse_args()
    total_start = time.time()

    if args.batch_size <= 0:
        raise ValueError("batch_size must be positive.")
    if args.max_docs is not None and args.max_docs <= 0:
        raise ValueError("max_docs must be positive when provided.")

    input_paths = sorted(Path(path) for path in glob.glob(args.input_glob))
    if not input_paths:
        raise FileNotFoundError(f"No filtered JSONL files matched input glob: {args.input_glob}")

    output_path: Path = args.output_path
    summary_path: Path = args.summary_path or output_path.with_suffix(output_path.suffix + ".summary.json")
    for path in (output_path, summary_path):
        if path.exists() and not args.overwrite:
            raise FileExistsError(f"Refusing to overwrite existing file without --overwrite: {path}")

    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer)
    if tokenizer.eos_token_id is None:
        raise ValueError("Tokenizer does not define an eos_token_id.")
    max_uint16 = np.iinfo(np.uint16).max
    if len(tokenizer) > max_uint16 + 1 or tokenizer.eos_token_id > max_uint16:
        raise ValueError(
            "Tokenizer ids do not fit in uint16. Use a GPT-2 tokenizer or change the serialization dtype."
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    aggregate = Counter()
    per_file_stats: dict[str, dict[str, int]] = {}
    current_batch: list[str] = []
    current_batch_file_names: list[str] = []

    def flush_current_batch(output_handle) -> None:
        if not current_batch:
            return

        token_count, token_counts_by_file = flush_token_batch(
            tokenizer=tokenizer,
            output_handle=output_handle,
            texts=current_batch,
            file_names=current_batch_file_names,
            eos_token_id=tokenizer.eos_token_id,
        )
        aggregate["num_tokens"] += token_count

        for source_name, per_file_token_count in token_counts_by_file.items():
            per_file_stats[source_name]["tokens"] += per_file_token_count

        current_batch.clear()
        current_batch_file_names.clear()

    with output_path.open("wb") as output_handle:
        for input_path in input_paths:
            source_name = input_path.name
            per_file_stats[source_name] = FileStats().__dict__.copy()

            with xopen(input_path, "rt") as source:
                for line_number, line in enumerate(source, start=1):
                    if args.max_docs is not None and aggregate["num_documents"] >= args.max_docs:
                        break

                    line = line.strip()
                    if not line:
                        continue

                    payload = json.loads(line)
                    text = payload.get(args.text_field)
                    if not isinstance(text, str) or not text.strip():
                        aggregate["num_skipped_missing_text"] += 1
                        per_file_stats[source_name]["skipped_missing_text"] += 1
                        continue

                    current_batch.append(text)
                    current_batch_file_names.append(source_name)
                    aggregate["num_documents"] += 1
                    per_file_stats[source_name]["documents"] += 1

                    if len(current_batch) >= args.batch_size:
                        flush_current_batch(output_handle)

            if args.max_docs is not None and aggregate["num_documents"] >= args.max_docs:
                break

        flush_current_batch(output_handle)

    report = {
        "input_glob": args.input_glob,
        "num_input_files": len(input_paths),
        "output_path": str(output_path),
        "summary_path": str(summary_path),
        "tokenizer": args.tokenizer,
        "text_field": args.text_field,
        "batch_size": args.batch_size,
        "max_docs": args.max_docs,
        "dtype": "uint16",
        "eos_token_id": tokenizer.eos_token_id,
        "vocab_size": tokenizer.vocab_size,
        "tokenizer_length": len(tokenizer),
        "total_elapsed_seconds": time.time() - total_start,
        "output_bytes": output_path.stat().st_size,
        "aggregate_counts": dict(aggregate),
        "per_file_stats": per_file_stats,
    }
    summary_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Wrote token bin: {output_path}")
    print(f"Wrote summary: {summary_path}")
    print(f"Documents: {aggregate['num_documents']}")
    print(f"Tokens: {aggregate['num_tokens']}")
    print(f"Elapsed seconds: {report['total_elapsed_seconds']:.2f}")


if __name__ == "__main__":
    main()
