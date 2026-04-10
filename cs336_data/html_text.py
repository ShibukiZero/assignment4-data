from __future__ import annotations

from resiliparse.extract.html2text import extract_plain_text
from resiliparse.parse.encoding import bytes_to_str, detect_encoding


def decode_html_bytes(html_bytes: bytes) -> str:
    """Decode raw HTML bytes into a Unicode string.

    We first try UTF-8 because it is the most common web encoding. If that
    fails, fall back to Resiliparse's encoding detector and its more robust
    byte-to-string conversion helper.
    """

    try:
        return html_bytes.decode("utf-8")
    except UnicodeDecodeError:
        detected_encoding = detect_encoding(html_bytes)
        return bytes_to_str(html_bytes, detected_encoding)


def extract_text_from_html_bytes(html_bytes: bytes) -> str:
    """Extract visible plain text from raw HTML bytes."""

    decoded_html = decode_html_bytes(html_bytes)
    return extract_plain_text(decoded_html)
