from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

import fasttext


def _normalize_text_for_fasttext(text: str) -> str:
    """Convert multiline page text into a single fastText-friendly line."""

    return re.sub(r"\s+", " ", text).strip()


def _candidate_model_paths(filename: str, env_var: str) -> list[Path]:
    candidates: list[Path] = []

    env_path = os.environ.get(env_var)
    if env_path:
        candidates.append(Path(env_path))

    candidates.extend(
        [
            Path(__file__).resolve().parent / "assets" / filename,
            Path("/data/classifiers") / filename,
            Path("/root/autodl-tmp/models") / filename,
        ]
    )
    return candidates


def _resolve_model_path(filename: str, env_var: str) -> Path:
    for path in _candidate_model_paths(filename, env_var):
        if path.exists():
            return path

    checked_paths = ", ".join(str(path) for path in _candidate_model_paths(filename, env_var))
    raise FileNotFoundError(
        f"Could not find model {filename}. Set {env_var} or place the model in one of: {checked_paths}"
    )


@lru_cache(maxsize=1)
def load_nsfw_classifier() -> fasttext.FastText._FastText:
    model_path = _resolve_model_path(
        filename="dolma_fasttext_nsfw_jigsaw_model.bin",
        env_var="CS336_NSFW_MODEL_PATH",
    )
    return fasttext.load_model(str(model_path))


@lru_cache(maxsize=1)
def load_toxic_classifier() -> fasttext.FastText._FastText:
    model_path = _resolve_model_path(
        filename="dolma_fasttext_hatespeech_jigsaw_model.bin",
        env_var="CS336_TOXIC_MODEL_PATH",
    )
    return fasttext.load_model(str(model_path))


def _strip_fasttext_prefix(label: str) -> str:
    if label.startswith("__label__"):
        return label.removeprefix("__label__")
    return label


def _normalize_binary_label(
    raw_label: str,
    *,
    positive_aliases: set[str],
    negative_aliases: set[str],
    positive_output: str,
    negative_output: str,
) -> str:
    label = _strip_fasttext_prefix(raw_label).strip().lower()
    compact = label.replace("_", "").replace("-", "")

    if label in positive_aliases or compact in {alias.replace("_", "").replace("-", "") for alias in positive_aliases}:
        return positive_output
    if label in negative_aliases or compact in {alias.replace("_", "").replace("-", "") for alias in negative_aliases}:
        return negative_output

    # Many binary fastText classifiers use 0/1-style labels.
    if label in {"1", "true", "yes", "pos", "positive"}:
        return positive_output
    if label in {"0", "false", "no", "neg", "negative"}:
        return negative_output

    raise ValueError(
        "Unrecognized classifier label "
        f"{raw_label!r}. Update the normalization aliases for this model."
    )


def classify_nsfw(text: str) -> tuple[str, float]:
    """Classify a text as NSFW or non-NSFW."""

    normalized_text = _normalize_text_for_fasttext(text)
    if not normalized_text:
        return "non-nsfw", 0.0

    model = load_nsfw_classifier()
    labels, scores = model.predict(normalized_text, k=1)
    label = _normalize_binary_label(
        labels[0],
        positive_aliases={"nsfw", "obscene", "sexual", "unsafe"},
        negative_aliases={"non-nsfw", "safe", "clean", "normal", "notnsfw"},
        positive_output="nsfw",
        negative_output="non-nsfw",
    )
    return label, float(scores[0])


def classify_toxic_speech(text: str) -> tuple[str, float]:
    """Classify a text as toxic or non-toxic."""

    normalized_text = _normalize_text_for_fasttext(text)
    if not normalized_text:
        return "non-toxic", 0.0

    model = load_toxic_classifier()
    labels, scores = model.predict(normalized_text, k=1)
    label = _normalize_binary_label(
        labels[0],
        positive_aliases={"toxic", "hate", "hatespeech", "offensive"},
        negative_aliases={"non-toxic", "nontoxic", "neutral", "clean", "safe"},
        positive_output="toxic",
        negative_output="non-toxic",
    )
    return label, float(scores[0])
