"""Состояние редакции между проходами: истории (склейки), кэш лент, результаты пересказа."""
from __future__ import annotations

import hashlib
import json
import os

from . import dedup
from .parse import Item
from .safety import Safety

MAX_AGE = 24 * 3600  # старее заметки не берём
KEEP = 48 * 3600  # столько храним историю в состоянии
WINDOW = 36 * 3600  # заметки дальше по времени в одну историю не склеиваем
RUMOR_CATEGORIES = {"games", "tech", "football", "sport"}  # слухи только про игры, технику и трансферы, не про людей
# Новость одного издания можно показать через столько секунд после выхода (переменная NEWSROOM_SINGLE_AFTER).
# По умолчанию нельзя совсем: чужой эксклюзив без ссылки не пересказываем
SINGLE_AFTER = float(os.environ["NEWSROOM_SINGLE_AFTER"]) if os.environ.get("NEWSROOM_SINGLE_AFTER") else None


def load(path: str) -> dict:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"clusters": {}, "feeds": {}, "seen": {}}


def save(state: dict, path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def usable_title(title: str) -> bool:
    return 18 <= len(title) <= 220 and len(title.split()) >= 3


def ingest(state: dict, items: list[Item], sources: dict[str, dict], safety: Safety, now: float) -> dict:
    """Новые заметки → истории. Возвращает счётчики для отчёта."""
    stats = {"new": 0, "old": 0, "short": 0, "stop": 0, "dup": 0, "joined": 0, "created": 0}
    clusters: dict = state["clusters"]
    seen: dict = state["seen"]
    sigs = {cid: dedup.signature(c["items"][0]["title"]) for cid, c in clusters.items()}
    for it in items:
        src = sources.get(it.source)
        if not src:
            continue
        key = it.source + "|" + dedup.norm(it.title)
        if key in seen:
            stats["dup"] += 1
            continue
        seen[key] = now
        published = min(it.published or now, now)
        if now - published > MAX_AGE:
            stats["old"] += 1
            continue
        if not usable_title(it.title):
            stats["short"] += 1
            continue
        hit = safety.check(it.title + " . " + " . ".join(it.tags))
        if hit:
            stats["stop"] += 1
            continue
        stats["new"] += 1
        owner = (it.outlet or src["owner"]).lower() if src["kind"] == "gnews" else src["owner"]
        entry = {
            "source": it.source,
            "owner": owner,
            "type": src["type"],
            "title": it.title,
            "summary": it.summary[:400],
            "published": published,
            "category": src["category"],
            "link": it.link,
            "tags": list(it.tags)[:6],
        }
        sig = dedup.signature(it.title)
        target = None
        for cid, c in clusters.items():
            if c["lang"] != src["lang"] or abs(c["published"] - published) > WINDOW:
                continue
            if dedup.same(sigs[cid], sig):
                target = c
                break
        if target:
            if not any(e["owner"] == owner for e in target["items"]):
                target["items"].append(entry)
                target["updated"] = now
                target["category"] = majority_category(target)
                stats["joined"] += 1
            target["published"] = min(target["published"], published)
        else:
            cid = hashlib.sha1((src["lang"] + "|" + dedup.norm(it.title)).encode("utf-8")).hexdigest()[:8]
            while cid in clusters:
                cid = "%08x" % ((int(cid, 16) + 1) % 0xFFFFFFFF)
            clusters[cid] = {
                "id": cid,
                "lang": src["lang"],
                "category": src["category"],
                "created": now,
                "updated": now,
                "published": published,
                "items": [entry],
                "rewrite": None,
            }
            sigs[cid] = sig
            stats["created"] += 1
    # уборка
    for cid in [cid for cid, c in clusters.items() if now - c["published"] > KEEP]:
        del clusters[cid]
    for k in [k for k, t in seen.items() if now - t > KEEP]:
        del seen[k]
    return stats


# при равенстве голосов узкая рубрика важнее общей: новость из Billboard и BBC — музыка, а не звёзды;
# кино из IGN и Variety — звёзды, а не игры
SPECIFIC = ["music", "football", "science", "fashion", "stars", "games", "tech", "sport", "weird"]


def majority_category(c: dict) -> str:
    votes: dict[str, int] = {}
    for e in c["items"]:
        cat = e.get("category") or c["category"]
        votes[cat] = votes.get(cat, 0) + 1
    best = max(votes.values())
    tied = [k for k, v in votes.items() if v == best]
    if len(tied) > 1 and "sport" in tied:
        # теннисистка в ленте моды и в спортивной: вид спорта в тексте решает в пользу спорта
        from . import topics
        text = " ".join(e["title"] + " " + e.get("summary", "") for e in c["items"])
        if topics.of("sport", text)[1] not in (None, "other"):
            return "sport"
    return min(tied, key=lambda k: SPECIFIC.index(k) if k in SPECIFIC else 99)


def counts(c: dict) -> tuple[int, int]:
    """(изданий, соцсетей) с разными владельцами."""
    outlets = {e["owner"] for e in c["items"] if e["type"] == "outlet"}
    social = {e["owner"] for e in c["items"] if e["type"] == "social"} - outlets
    return len(outlets), len(social)


def trust(c: dict, now: float | None = None) -> str | None:
    """media — есть издание и ещё хотя бы один независимый источник; rumor — только каналы.
    Одиночная заметка (эксклюзив одного источника) на доску не идёт, если не задан SINGLE_AFTER."""
    o, s = counts(c)
    if o >= 2 or (o >= 1 and s >= 1):
        return "media"
    if o == 1 and SINGLE_AFTER is not None and now is not None and now - c["published"] >= SINGLE_AFTER:
        return "media"
    if o == 0 and s >= 2 and c["category"] in RUMOR_CATEGORIES:
        return "rumor"
    return None


def pending(state: dict, now: float, limit: int) -> list[dict]:
    """Истории, которые пора пересказать моделью: прошли порог источников, модель их ещё не пересказала
    и пробовала меньше трёх раз. Строка из фактов (mode facts) — временная, модель может её заменить."""
    out = []
    for c in sorted(state["clusters"].values(), key=lambda c: -c["published"]):
        if now - c["published"] > MAX_AGE or not trust(c, now):
            continue
        rw = c.get("rewrite")
        if rw and (rw["status"] == "blocked" or (rw["status"] == "ok" and rw.get("mode") != "facts")
                   or rw.get("attempts", 0) >= 3):
            continue
        out.append(c)
        if len(out) >= limit:
            break
    return out
