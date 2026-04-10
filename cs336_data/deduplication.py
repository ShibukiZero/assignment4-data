from __future__ import annotations

import hashlib
import os
from collections import Counter
from pathlib import Path

from xopen import xopen


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
