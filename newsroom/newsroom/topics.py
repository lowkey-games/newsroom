"""Виды спорта внутри рубрики «Спорт». Словарь один: src/shared/Topics.luau игры, здесь он читается как данные."""
from __future__ import annotations

import os
import re

from .safety import Rule
from .text import words

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOPICS_LUAU = os.path.join(ROOT, "src", "shared", "Topics.luau")


def _parse(path: str) -> tuple[dict[str, list[str]], dict[str, list[Rule]]]:
    with open(path, encoding="utf-8") as f:
        src = f.read()
    subs: dict[str, list[str]] = {}
    block = src[src.index("Topics.Sub = {") + len("Topics.Sub = {"):src.index("Topics.Icons")]
    for m in re.finditer(r"(\w+) = \{([^}]*)\}", block):
        subs[m.group(1)] = re.findall(r'"([^"]*)"', m.group(2))
    body = src[src.index("local WORDS"):src.index("-- конец словаря")]
    rules: dict[str, list[Rule]] = {}
    for m in re.finditer(r"\n\t(\w+) = \{(.*?)\n?\t?\},", body, re.S):
        rules[m.group(1)] = [Rule(e) for e in re.findall(r'"([^"]*)"', m.group(2))]
    return subs, rules


SUBS, RULES = _parse(TOPICS_LUAU)


def _hit(ws: list[str], name: str) -> bool:
    return any(rule.match_at(ws, i) for rule in RULES.get(name, []) for i in range(len(ws)))


def of(category: str, text: str) -> tuple[str, str | None]:
    """(рубрика, вид спорта). Спортивная история про футбол уходит в «Футбол», как в игре (Topics.of)."""
    sub = SUBS.get(category)
    if not sub:
        return category, None
    ws = words(text)
    for t in sub:
        if t != "other" and _hit(ws, t):
            return category, t
    if category == "sport" and not _hit(ws, "usfootball") and _hit(ws, "football"):
        return "football", None
    return category, "other"


def link_words(link: str) -> str:
    """Путь статьи словами: вид спорта почти всегда в адресе (bbc.com/sport/tennis/…)."""
    m = re.match(r"^\w+://[^/]+(/.*)$", link or "")
    return re.sub(r"[/\-_.?=&]", " ", m.group(1)) if m else ""
