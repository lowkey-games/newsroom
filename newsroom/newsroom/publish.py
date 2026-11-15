"""Файлы для игры: stories-en.json и stories-ru.json. В них только наш пересказ и счётчики источников."""
from __future__ import annotations

import json
import os

from . import dedup, topics
from .store import MAX_AGE, counts, trust

LIMIT = 150


def edition_stories(state: dict, edition: str, now: float) -> list[dict]:
    lang = edition.lower()
    out = []
    for c in state["clusters"].values():
        rw = c.get("rewrite") or {}
        if rw.get("status") != "ok" or now - c["published"] > MAX_AGE:
            continue
        if rw.get("audience") not in ("global", lang):
            continue
        title = rw.get(lang) or ""
        if not title:
            continue
        t = trust(c, now)
        if not t:
            continue
        o, s = counts(c)
        # вид спорта по всем заметкам истории: подводки точнее короткой строки на доске
        category, topic = topics.of(rw.get("category") or c["category"], " . ".join(
            e["title"] + " . " + e.get("summary", "") + " " + " ".join(e.get("tags", [])) + " " + topics.link_words(e.get("link", ""))
            for e in c["items"]))
        out.append({
            "id": c["id"],
            "title": title,
            "category": category,
            "topic": topic or "",
            "outlets": o,
            "social": s,
            "trust": t,
            "published": int(c["published"]),
            # ai — пересказ модели, facts — строка из фактов без ИИ, fake — проверка без модели
            "mode": rw.get("mode") or ("fake" if rw.get("fake") else "ai"),
            # «Подробнее»: свои подробности и слова для поиска, без ссылок и названий изданий
            "details": rw.get("details_" + lang) or "",
            "search": rw.get("search_" + lang) or "",
            "fake": bool(rw.get("fake")),
        })
    out.sort(key=lambda s: -s["published"])
    # одна история могла прийти из английских и из русских источников: склеиваем по пересказу
    merged: list[dict] = []
    sigs: list[dict] = []
    for s in out:
        sig = dedup.signature(s["title"])
        twin = next((m for m, ms in zip(merged, sigs) if dedup.same(ms, sig)), None)
        if twin:
            twin["outlets"] = max(twin["outlets"], s["outlets"])
            twin["social"] = max(twin["social"], s["social"])
            if s["trust"] == "media":
                twin["trust"] = "media"
            continue
        merged.append(s)
        sigs.append(sig)
    return merged[:LIMIT]


def write(state: dict, out_dir: str, now: float) -> dict[str, int]:
    os.makedirs(out_dir, exist_ok=True)
    written = {}
    for edition in ("EN", "RU"):
        stories = edition_stories(state, edition, now)
        doc = {"version": 1, "edition": edition, "generated": int(now), "stories": stories}
        path = os.path.join(out_dir, f"stories-{edition.lower()}.json")
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, path)
        written[edition] = len(stories)
    return written
