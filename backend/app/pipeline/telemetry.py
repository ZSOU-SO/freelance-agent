from __future__ import annotations

import re


_SECRET_PATTERN = re.compile(r"sk-[A-Za-z0-9_-]{8,}")


def sanitize_error(exc: Exception, max_length: int = 300) -> str:
    message = f"{type(exc).__name__}: {exc}".replace("\r", " ").replace("\n", " ")
    message = _SECRET_PATTERN.sub("[redacted]", message)
    return message[:max_length]

