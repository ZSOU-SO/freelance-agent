from __future__ import annotations

import os
from urllib.parse import urlparse


def json_object_model_settings():
    """Return Chat Completions settings compatible with DeepSeek's JSON mode."""
    from agents import ModelSettings

    extra_body: dict[str, object] = {
        "response_format": {"type": "json_object"},
    }
    base_url = os.getenv("OPENAI_BASE_URL", "").strip()
    if urlparse(base_url).hostname == "api.deepseek.com":
        # DeepSeek reasoning mode does not support this pipeline's JSON/tool calls.
        extra_body["thinking"] = {"type": "disabled"}
    return ModelSettings(extra_body=extra_body)
