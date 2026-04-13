from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from transformers import AutoTokenizer


DEFAULT_BIN_PATH = Path("/root/autodl-tmp/tokenized/tokenized_paloma_c4_100_domains_validation.bin")
DEFAULT_TOKENIZER_PATH = "/root/autodl-tmp/tokenizers/gpt2"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Peek at the Paloma C4 100 domains validation bin in the same spirit "
            "as the assignment handout: load the tokenized .bin file, decode a "
            "prefix, and optionally show the first few EOS-delimited document spans."
        )
    )
    parser.add_argument(
        "--bin-path",
        type=Path,
        default=DEFAULT_BIN_PATH,
        help="Path to the tokenized Paloma validation .bin file.",
    )
    parser.add_argument(
        "--tokenizer",
        default=DEFAULT_TOKENIZER_PATH,
        help="Tokenizer path or model name. Defaults to the self-hosted GPT-2 cache path.",
    )
    parser.add_argument(
        "--preview-tokens",
        type=int,
        default=2000,
        help="How many tokens from the front of the bin to decode as one preview block.",
    )
    parser.add_argument(
        "--preview-docs",
        type=int,
        default=3,
        help="How many EOS-delimited documents to preview from the front of the bin.",
    )
    parser.add_argument(
        "--preview-chars",
        type=int,
        default=1200,
        help="Maximum decoded characters to print per preview section.",
    )
    return parser.parse_args()


def shorten(text: str, limit: int) -> str:
    compact = text.replace("\n", "\\n")
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


def first_document_token_spans(tokens: np.ndarray, eos_token_id: int, max_docs: int) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    start = 0

    for index, token_id in enumerate(tokens):
        if token_id != eos_token_id:
            continue
        spans.append((start, index))
        start = index + 1
        if len(spans) >= max_docs:
            break

    if len(spans) < max_docs and start < len(tokens):
        spans.append((start, len(tokens)))

    return spans[:max_docs]


def main() -> None:
    args = parse_args()

    if not args.bin_path.exists():
        raise FileNotFoundError(f"Validation bin not found: {args.bin_path}")

    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer)
    data = np.fromfile(args.bin_path, dtype=np.uint16)

    print(f"Validation bin: {args.bin_path}")
    print(f"Total tokens: {len(data)}")
    print(f"Tokenizer: {args.tokenizer}")
    print(f"EOS token id: {tokenizer.eos_token_id}")
    print()

    preview_slice = data[: args.preview_tokens]
    decoded_prefix = tokenizer.decode(preview_slice.tolist())
    print(f"=== First {len(preview_slice)} tokens decoded ===")
    print(shorten(decoded_prefix, args.preview_chars))
    print()

    print(f"=== First {args.preview_docs} EOS-delimited documents ===")
    spans = first_document_token_spans(data, tokenizer.eos_token_id, args.preview_docs)
    for doc_index, (start, stop) in enumerate(spans, start=1):
        doc_tokens = data[start:stop]
        decoded_doc = tokenizer.decode(doc_tokens.tolist())
        print(f"[Document {doc_index}] token_span=[{start}, {stop}) token_count={len(doc_tokens)}")
        print(shorten(decoded_doc, args.preview_chars))
        print()


if __name__ == "__main__":
    main()
