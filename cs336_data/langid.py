from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
import re

import fasttext


def _candidate_model_paths() -> list[Path]:
    """Return likely locations for the fastText language-ID model.

    Check an explicit environment variable first, then fall back to a few
    assignment-specific defaults. This keeps the adapter simple while making it
    easy to point the code at a local model file.
    """

    candidates: list[Path] = []

    env_path = os.environ.get("CS336_LID_MODEL_PATH")
    if env_path:
        candidates.append(Path(env_path))

    candidates.extend(
        [
            Path(__file__).resolve().parent / "assets" / "lid.176.bin",
            Path(__file__).resolve().parents[1] / "models" / "lid.176.bin",
            Path("/data/classifiers/lid.176.bin"),
        ]
    )
    return candidates


def resolve_language_id_model_path() -> Path:
    """Find the first existing model path or raise a clear error."""

    for path in _candidate_model_paths():
        if path.exists():
            return path

    checked_paths = ", ".join(str(path) for path in _candidate_model_paths())
    raise FileNotFoundError(
        "Could not find fastText language-ID model. Set CS336_LID_MODEL_PATH "
        f"or place lid.176.bin in one of: {checked_paths}"
    )


@lru_cache(maxsize=1)
def load_language_identifier() -> fasttext.FastText._FastText:
    """Load the fastText language-ID model once per process."""

    model_path = resolve_language_id_model_path()
    return fasttext.load_model(str(model_path))


def normalize_fasttext_language_label(label: str) -> str:
    """Convert fastText labels like '__label__en' into assignment-friendly IDs."""

    if label.startswith("__label__"):
        label = label.removeprefix("__label__")

    # The tests expect plain 'zh' rather than a script-specific label.
    if label.startswith("zh"):
        return "zh"

    return label


def normalize_text_for_fasttext(text: str) -> str:
    """Convert multiline page text into a single fastText-friendly line."""

    return re.sub(r"\s+", " ", text).strip()


def identify_language(text: str) -> tuple[str, float]:
    """Predict the main language in a Unicode string.

    This returns the top fastText label plus its confidence score. We keep the
    prediction logic small and explicit so it is easy to inspect before adding
    any later thresholding policy for filtering.
    """

    normalized_text = normalize_text_for_fasttext(text)

    if not normalized_text:
        return "", 0.0

    model = load_language_identifier()
    labels, scores = model.predict(normalized_text, k=1)

    normalized_label = normalize_fasttext_language_label(labels[0])
    return normalized_label, float(scores[0])
