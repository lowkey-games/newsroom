"""Стоп-слова. Источник один: src/shared/Safety.luau игры, здесь он читается как данные."""
from __future__ import annotations

import os
import re

from .text import words

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SAFETY_LUAU = os.path.join(ROOT, "src", "shared", "Safety.luau")


def _parse_lists(path: str) -> dict[str, list[str]]:
    with open(path, encoding="utf-8") as f:
        src = f.read()
    body = src[src.index("local LISTS"):src.index("type Rule")]
    lists: dict[str, list[str]] = {}
    for m in re.finditer(r"\n\t(\w+) = \{(.*?)\n\t\},", body, re.S):
        lists[m.group(1)] = re.findall(r'"([^"]*)"', m.group(2))
    return lists


class Rule:
    def __init__(self, entry: str):
        self.entry = entry
        self.words: list[str] = []
        self.prefix: list[bool] = []
        for part in entry.split():
            is_prefix = part.endswith("*")
            if is_prefix:
                part = part[:-1]
            ws = words(part)
            for i, w in enumerate(ws):
                self.words.append(w)
                self.prefix.append(is_prefix and i == len(ws) - 1)

    def match_at(self, ws: list[str], i: int) -> bool:
        for k, rw in enumerate(self.words):
            if i + k >= len(ws):
                return False
            w = ws[i + k]
            if self.prefix[k]:
                if not w.startswith(rw):
                    return False
            elif w != rw:
                return False
        return bool(self.words)


class Safety:
    def __init__(self, path: str = SAFETY_LUAU):
        self.lists = {name: [Rule(e) for e in entries] for name, entries in _parse_lists(path).items()}

    def check(self, text: str) -> tuple[str, str] | None:
        """Первое сработавшее правило (список, запись) или None."""
        ws = words(text)
        for name, rules in self.lists.items():
            for rule in rules:
                for i in range(len(ws)):
                    if rule.match_at(ws, i):
                        return name, rule.entry
        return None
