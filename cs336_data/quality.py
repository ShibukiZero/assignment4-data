from __future__ import annotations

import re


MIN_WORDS = 50
MAX_WORDS = 100_000
MIN_MEAN_WORD_LENGTH = 3.0
MAX_MEAN_WORD_LENGTH = 10.0
MAX_ELLIPSIS_LINE_FRACTION = 0.30
MIN_ALPHABETIC_WORD_FRACTION = 0.80

WORD_PATTERN = re.compile(r"\w+(?:[-']\w+)*", flags=re.UNICODE)


def extract_word_like_tokens(text: str) -> list[str]:
    """Extract simple word-like tokens for the Gopher-style heuristics.

    We intentionally keep tokenization lightweight and regex-based so the
    filter remains easy to inspect and does not depend on external NLP tools.
    """

    return WORD_PATTERN.findall(text)


def fraction_of_lines_ending_with_ellipsis(text: str) -> float:
    """Return the fraction of non-empty lines that end with '...'."""

    non_empty_lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    if not non_empty_lines:
        return 0.0

    ellipsis_lines = sum(line.endswith("...") for line in non_empty_lines)
    return ellipsis_lines / len(non_empty_lines)


def fraction_of_words_with_alphabetic_character(words: list[str]) -> float:
    """Return the share of tokens that contain at least one alphabetic char."""

    if not words:
        return 0.0

    alphabetic_words = sum(any(char.isalpha() for char in word) for word in words)
    return alphabetic_words / len(words)


def mean_word_length(words: list[str]) -> float:
    """Return the mean token length across the extracted word list."""

    if not words:
        return 0.0

    return sum(len(word) for word in words) / len(words)


def passes_gopher_quality_filters(text: str) -> bool:
    """Apply the assignment's subset of Gopher quality heuristics."""

    words = extract_word_like_tokens(text)
    word_count = len(words)
    if word_count < MIN_WORDS or word_count > MAX_WORDS:
        return False

    average_length = mean_word_length(words)
    if average_length < MIN_MEAN_WORD_LENGTH or average_length > MAX_MEAN_WORD_LENGTH:
        return False

    if fraction_of_lines_ending_with_ellipsis(text) > MAX_ELLIPSIS_LINE_FRACTION:
        return False

    if fraction_of_words_with_alphabetic_character(words) < MIN_ALPHABETIC_WORD_FRACTION:
        return False

    return True
