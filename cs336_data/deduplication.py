from __future__ import annotations

import hashlib
import itertools
import os
from collections import Counter
from pathlib import Path
import re
import unicodedata

from xopen import xopen


MAX_HASH_VALUE = (1 << 64) - 1
WHITESPACE_RE = re.compile(r"\s+")


def hash_line(line: str) -> bytes:
    """Return a fixed-size digest for a line.

    The assignment explicitly suggests hashing lines before counting so the
    counter keys stay bounded in size even when the raw lines are long.
    """

    return hashlib.blake2b(line.encode("utf-8"), digest_size=16).digest()


def count_line_hashes(input_files: list[os.PathLike]) -> Counter[bytes]:
    """Count how often each line hash appears across the full corpus."""

    counts: Counter[bytes] = Counter()
    for input_file in input_files:
        with xopen(input_file, "rt") as handle:
            for line in handle:
                counts[hash_line(line)] += 1
    return counts


def exact_line_deduplication(
    input_files: list[os.PathLike], output_directory: os.PathLike
) -> None:
    """Rewrite each file while dropping any line repeated in the corpus."""

    output_dir = Path(output_directory)
    output_dir.mkdir(parents=True, exist_ok=True)

    line_hash_counts = count_line_hashes(input_files)

    for input_file in input_files:
        input_path = Path(input_file)
        output_path = output_dir / input_path.name

        with xopen(input_path, "rt") as source, xopen(output_path, "wt") as sink:
            for line in source:
                # Keep only corpus-unique lines; repeated lines are removed
                # everywhere rather than retaining a single copy.
                if line_hash_counts[hash_line(line)] == 1:
                    sink.write(line)


def normalize_document_for_deduplication(text: str) -> str:
    """Normalize text before MinHash/LSH and Jaccard comparison."""

    decomposed_text = unicodedata.normalize("NFD", text).lower()
    normalized_chars: list[str] = []

    for char in decomposed_text:
        if unicodedata.combining(char):
            continue

        if char.isspace():
            normalized_chars.append(" ")
            continue

        if unicodedata.category(char).startswith("P"):
            normalized_chars.append(" ")
            continue

        normalized_chars.append(char)

    normalized_text = "".join(normalized_chars)
    return WHITESPACE_RE.sub(" ", normalized_text).strip()


def document_word_ngrams(text: str, ngrams: int) -> set[tuple[str, ...]]:
    """Convert normalized text into a set of word n-grams."""

    words = text.split()
    if not words:
        return set()

    if len(words) < ngrams:
        return {tuple(words)}

    return {
        tuple(words[index : index + ngrams])
        for index in range(len(words) - ngrams + 1)
    }


def hash_ngram(ngram: tuple[str, ...], seed: int) -> int:
    """Hash one n-gram under a deterministic seed-specific hash function."""

    payload = f"{seed}\x1f{' '.join(ngram)}".encode("utf-8")
    digest = hashlib.blake2b(payload, digest_size=8).digest()
    return int.from_bytes(digest, byteorder="big", signed=False)


def compute_minhash_signature(
    ngram_set: set[tuple[str, ...]], num_hashes: int
) -> tuple[int, ...]:
    """Build a MinHash signature for one document."""

    if not ngram_set:
        return tuple(MAX_HASH_VALUE for _ in range(num_hashes))

    signature: list[int] = []
    for seed in range(num_hashes):
        min_hash = min(hash_ngram(ngram, seed) for ngram in ngram_set)
        signature.append(min_hash)
    return tuple(signature)


def candidate_duplicate_pairs(
    signatures: list[tuple[int, ...]], num_bands: int
) -> set[tuple[int, int]]:
    """Use LSH bands to find candidate duplicate document pairs."""

    if not signatures:
        return set()

    rows_per_band = len(signatures[0]) // num_bands
    buckets: dict[tuple[int, tuple[int, ...]], list[int]] = {}

    for doc_index, signature in enumerate(signatures):
        for band_index in range(num_bands):
            start = band_index * rows_per_band
            stop = start + rows_per_band
            band_key = (band_index, signature[start:stop])
            buckets.setdefault(band_key, []).append(doc_index)

    pairs: set[tuple[int, int]] = set()
    for doc_indices in buckets.values():
        if len(doc_indices) < 2:
            continue
        for left, right in itertools.combinations(doc_indices, 2):
            pairs.add((left, right))

    return pairs


def jaccard_similarity(
    left_ngrams: set[tuple[str, ...]], right_ngrams: set[tuple[str, ...]]
) -> float:
    """Compute the true Jaccard similarity for a candidate pair."""

    if not left_ngrams and not right_ngrams:
        return 1.0
    if not left_ngrams or not right_ngrams:
        return 0.0

    intersection = len(left_ngrams & right_ngrams)
    union = len(left_ngrams | right_ngrams)
    return intersection / union


def find_root(parents: list[int], index: int) -> int:
    """Return the representative for one union-find set."""

    while parents[index] != index:
        parents[index] = parents[parents[index]]
        index = parents[index]
    return index


def union_sets(parents: list[int], left: int, right: int) -> None:
    """Merge two union-find sets."""

    left_root = find_root(parents, left)
    right_root = find_root(parents, right)
    if left_root != right_root:
        parents[right_root] = left_root


def minhash_deduplication(
    input_files: list[os.PathLike],
    num_hashes: int,
    num_bands: int,
    ngrams: int,
    jaccard_threshold: float,
    output_directory: os.PathLike,
) -> None:
    """Rewrite only the documents that survive fuzzy deduplication."""

    if num_hashes <= 0 or num_bands <= 0 or ngrams <= 0:
        raise ValueError("num_hashes, num_bands, and ngrams must be positive.")
    if num_hashes % num_bands != 0:
        raise ValueError("num_hashes must be evenly divisible by num_bands.")

    output_dir = Path(output_directory)
    output_dir.mkdir(parents=True, exist_ok=True)

    input_paths = [Path(path) for path in input_files]
    document_ngrams: list[set[tuple[str, ...]]] = []
    signatures: list[tuple[int, ...]] = []

    for input_path in input_paths:
        with xopen(input_path, "rt") as handle:
            original_text = handle.read()

        normalized_text = normalize_document_for_deduplication(original_text)
        ngram_set = document_word_ngrams(normalized_text, ngrams)

        document_ngrams.append(ngram_set)
        signatures.append(compute_minhash_signature(ngram_set, num_hashes))

    candidate_pairs = candidate_duplicate_pairs(signatures, num_bands)

    parents = list(range(len(input_paths)))
    for left, right in candidate_pairs:
        similarity = jaccard_similarity(document_ngrams[left], document_ngrams[right])
        if similarity >= jaccard_threshold:
            union_sets(parents, left, right)

    # Keep one stable representative per duplicate cluster so the output is
    # deterministic across runs and easy to compare in tests.
    survivors_by_root: dict[int, int] = {}
    for index in range(len(input_paths)):
        root = find_root(parents, index)
        survivors_by_root[root] = min(survivors_by_root.get(root, index), index)

    survivor_indices = set(survivors_by_root.values())
    for index, input_path in enumerate(input_paths):
        if index not in survivor_indices:
            continue

        output_path = output_dir / input_path.name
        with xopen(input_path, "rt") as source, xopen(output_path, "wt") as sink:
            sink.write(source.read())
