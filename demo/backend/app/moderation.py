from __future__ import annotations

import re

_URL = re.compile(r"(https?://|www\.)", re.IGNORECASE)
_FLOOD = re.compile(r"(.)\1{11,}", re.DOTALL)
_UNSAFE = re.compile(
    r"(儿童色情|未成年色情|恋童|幼女性|幼男性|child\s*porn|loli\s*sex)",
    re.IGNORECASE,
)


def moderate(text: str) -> str | None:
    """Return a rejection code, or None when the comment may be stored.

    This is a local keyword filter. It is not an AI moderation service.
    """
    body = text.strip()
    if not body or len(body) > 400:
        return "length"
    if _URL.search(body):
        return "url"
    if _FLOOD.search(body):
        return "flood"
    if _UNSAFE.search(body):
        return "safety"
    return None
