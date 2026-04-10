from __future__ import annotations

import re


EMAIL_PLACEHOLDER = "|||EMAIL_ADDRESS|||"
PHONE_PLACEHOLDER = "|||PHONE_NUMBER|||"
IP_PLACEHOLDER = "|||IP_ADDRESS|||"


EMAIL_PATTERN = re.compile(
    r"(?<![\w.+-])"
    r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})"
    r"(?![\w.-])"
)

# Cover common US formats such as:
# 2831823829, 283-182-3829, (283)-182-3829, (283) 182 3829, +1 283-182-3829
PHONE_PATTERN = re.compile(
    r"(?<!\d)"
    r"(?:\+?1[\s.-]?)?"
    r"(?:\(\d{3}\)|\d{3})"
    r"(?:[\s.-]?\d{3})"
    r"[\s.-]?\d{4}"
    r"(?!\d)"
)

OCTET = r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
IP_PATTERN = re.compile(rf"(?<!\d)({OCTET}\.{OCTET}\.{OCTET}\.{OCTET})(?!\d)")


def mask_emails(text: str) -> tuple[str, int]:
    """Replace email addresses with a fixed placeholder."""

    return EMAIL_PATTERN.subn(EMAIL_PLACEHOLDER, text)


def mask_phone_numbers(text: str) -> tuple[str, int]:
    """Replace common US phone-number formats with a fixed placeholder."""

    return PHONE_PATTERN.subn(PHONE_PLACEHOLDER, text)


def mask_ips(text: str) -> tuple[str, int]:
    """Replace IPv4 addresses with a fixed placeholder."""

    return IP_PATTERN.subn(IP_PLACEHOLDER, text)
