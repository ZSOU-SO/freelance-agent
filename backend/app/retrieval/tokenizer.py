from __future__ import annotations

import re
import unicodedata


_TECH_TOKEN = re.compile(r"[a-z0-9_+#.-]+")
_CHINESE_CHAR = re.compile(r"[\u4e00-\u9fff]")


class CaseTokenizer:
    def __init__(self) -> None:
        self.stop_phrases = (
            "开发",
            "一个",
            "项目",
            "系统",
            "使用",
            "需要",
            "the",
            "and",
            "with",
        )

    def tokenize(self, text: str) -> list[str]:
        normalized = unicodedata.normalize("NFKC", text).lower()
        for phrase in self.stop_phrases:
            normalized = normalized.replace(phrase, "")

        tokens = [
            token
            for token in _TECH_TOKEN.findall(normalized)
            if token not in self.stop_phrases and token.strip(".-")
        ]
        chinese = "".join(_CHINESE_CHAR.findall(normalized))
        if len(chinese) == 1:
            tokens.append(chinese)
        elif len(chinese) > 1:
            tokens.extend(chinese[index : index + 2] for index in range(len(chinese) - 1))
        return tokens

