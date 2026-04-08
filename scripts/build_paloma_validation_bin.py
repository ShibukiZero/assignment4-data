from __future__ import annotations

import argparse
import gzip
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from transformers import AutoTokenizer


DEFAULT_INPUT_DIR = Path("/root/autodl-tmp/raw/paloma/c4_100_domains/val")
DEFAULT_TOKENIZER_DIR = Path("/root/autodl-tmp/tokenizers/gpt2")
DEFAULT_OUTPUT_PATH = Path("/root/autodl-tmp/tokenized/tokenized_paloma_c4_100_domains_validation.bin")
DEFAULT_LOG_PATH = Path(".agents/logs/paloma_build/report.json")


@dataclass
class BuildStats:
    num_files: int = 0
    num_documents: int = 0
    num_skipped_missing_text: int = 0
    num_tokens: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build the Assignment 4 Paloma validation .bin file from "
            "c4_100_domains/val/*.jsonl.gz using the GPT-2 tokenizer."
        )
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help="Directory containing Paloma c4_100_domains validation .jsonl.gz files.",
    )
    parser.add_argument(
        "--tokenizer-dir",
        type=Path,
        default=DEFAULT_TOKENIZER_DIR,
        help="Directory containing the GPT-2 tokenizer files.",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Path to the output .bin file.",
    )
    parser.add_argument(
        "--log-path",
        type=Path,
        default=DEFAULT_LOG_PATH,
        help="Path to the build report JSON file.",
    )
    parser.add_argument(
        "--text-field",
        default="text",
        help="JSON field containing the document text. Probe output recommended `text`.",
    )
    return parser.parse_args()


def iter_documents(input_dir: Path, text_field: str):
    for path in sorted(input_dir.glob("*.jsonl.gz")):
        yield path, None, None
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line_number, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError(f"{path}:{line_number} is not a JSON object.")
                yield path, line_number, record.get(text_field)


def main() -> None:
    args = parse_args()

    input_dir: Path = args.input_dir
    tokenizer_dir: Path = args.tokenizer_dir
    output_path: Path = args.output_path
    log_path: Path = args.log_path
    text_field: str = args.text_field

    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")
    if not tokenizer_dir.exists():
        raise FileNotFoundError(f"Tokenizer directory does not exist: {tokenizer_dir}")

    input_files = sorted(input_dir.glob("*.jsonl.gz"))
    if not input_files:
        raise FileNotFoundError(f"No .jsonl.gz files found in: {input_dir}")

    tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_dir))
    if tokenizer.eos_token_id is None:
        raise ValueError("Tokenizer does not define an eos_token_id.")

    all_ids: list[int] = []
    stats = BuildStats(num_files=len(input_files))
    per_file_documents: dict[str, int] = {}

    current_file: Path | None = None
    current_file_docs = 0

    for file_path, line_number, maybe_text in iter_documents(input_dir, text_field):
        if line_number is None:
            if current_file is not None:
                per_file_documents[current_file.name] = current_file_docs
            current_file = file_path
            current_file_docs = 0
            print(f"Processing {file_path.name}")
            continue

        text = maybe_text if isinstance(maybe_text, str) else ""
        if not text.strip():
            stats.num_skipped_missing_text += 1
            continue

        token_ids = tokenizer.encode(text)
        token_ids.append(tokenizer.eos_token_id)
        all_ids.extend(token_ids)

        current_file_docs += 1
        stats.num_documents += 1
        stats.num_tokens += len(token_ids)

    if current_file is not None:
        per_file_documents[current_file.name] = current_file_docs

    output_path.parent.mkdir(parents=True, exist_ok=True)
    ids_array = np.array(all_ids, dtype=np.uint16)
    ids_array.tofile(output_path)

    log_path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "input_dir": str(input_dir),
        "tokenizer_dir": str(tokenizer_dir),
        "text_field": text_field,
        "output_path": str(output_path),
        "num_files": stats.num_files,
        "num_documents": stats.num_documents,
        "num_skipped_missing_text": stats.num_skipped_missing_text,
        "num_tokens": stats.num_tokens,
        "dtype": "uint16",
        "per_file_documents": per_file_documents,
    }
    log_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Wrote {output_path}")
    print(f"Wrote {log_path}")
    print(f"Documents: {stats.num_documents}")
    print(f"Tokens: {stats.num_tokens}")


if __name__ == "__main__":
    main()
