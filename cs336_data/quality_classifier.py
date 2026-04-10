from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import fasttext

from cs336_data.langid import normalize_text_for_fasttext


def _candidate_model_paths() -> list[Path]:
    candidates: list[Path] = []

    env_path = os.environ.get("CS336_QUALITY_MODEL_PATH")
    if env_path:
        candidates.append(Path(env_path))

    candidates.extend(
        [
            Path(__file__).resolve().parent / "assets" / "quality_classifier_fasttext.bin",
            Path("/root/autodl-tmp/quality_classifier/models/quality_classifier_fasttext.bin"),
        ]
    )
    return candidates


def resolve_quality_classifier_model_path() -> Path:
    for path in _candidate_model_paths():
        if path.exists():
            return path

    checked_paths = ", ".join(str(path) for path in _candidate_model_paths())
    raise FileNotFoundError(
        "Could not find the trained quality-classifier model. Set "
        f"CS336_QUALITY_MODEL_PATH or place the model in one of: {checked_paths}"
    )


@lru_cache(maxsize=1)
def load_quality_classifier() -> fasttext.FastText._FastText:
    model_path = resolve_quality_classifier_model_path()
    return fasttext.load_model(str(model_path))


def normalize_quality_label(label: str) -> str:
    if label.startswith("__label__"):
        label = label.removeprefix("__label__")
    return label


def classify_quality(text: str) -> tuple[str, float]:
    normalized_text = normalize_text_for_fasttext(text)
    if not normalized_text:
        return "", 0.0

    model = load_quality_classifier()
    labels, scores = model.predict(normalized_text, k=1)

    predicted_label = normalize_quality_label(labels[0])
    return predicted_label, float(scores[0])
