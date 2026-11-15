"""Загрузка источников: вежливо (ETag, If-Modified-Since), параллельно, с таймаутом."""
from __future__ import annotations

import gzip
import os
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from .parse import Item, parse_feed, parse_gnews, parse_telegram

UA = "BreakingNewsStudio/1.0 (news board for a Roblox game)"
MAX_BYTES = 2_000_000


def source_url(src: dict) -> str | None:
    if src["kind"] == "telegram":
        return f"https://t.me/s/{src['url']}"
    if src["kind"] == "gnews":
        key = os.environ.get("GNEWS_API_KEY")
        if not key:
            return None
        return f"https://gnews.io/api/v4/{src['url']}&apikey={key}"
    return src["url"]


def fetch_one(src: dict, cache: dict) -> tuple[list[Item], dict]:
    """Заметки источника и новое состояние кэша {etag, modified, status}."""
    url = source_url(src)
    state = dict(cache.get(src["id"]) or {})
    if not url:
        state["status"] = "no key"
        return [], state
    headers = {"User-Agent": UA, "Accept-Encoding": "gzip"}
    if src["kind"] == "telegram":
        headers["User-Agent"] = "Mozilla/5.0 (compatible; " + UA + ")"
    if state.get("etag"):
        headers["If-None-Match"] = state["etag"]
    if state.get("modified"):
        headers["If-Modified-Since"] = state["modified"]
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read(MAX_BYTES)
            if r.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            body = raw.decode("utf-8", errors="replace")
            state["etag"] = r.headers.get("ETag")
            state["modified"] = r.headers.get("Last-Modified")
            state["status"] = str(r.status)
    except urllib.error.HTTPError as e:
        state["status"] = str(e.code)
        return [], state
    except Exception as e:  # сеть, таймаут, DNS: источник пропускаем до следующего прохода
        state["status"] = "error: " + type(e).__name__ + " " + str(getattr(e, "reason", e))[:80]
        return [], state
    if src["kind"] == "telegram":
        items = parse_telegram(body, src["id"])
    elif src["kind"] == "gnews":
        items = parse_gnews(body, src["id"])
    else:
        items = parse_feed(body, src["id"])
    return items, state


def fetch_all(sources: list[dict], cache: dict, workers: int = 3) -> tuple[list[Item], dict]:
    items: list[Item] = []
    new_cache = dict(cache)
    retry = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for src, (got, state) in zip(sources, pool.map(lambda s: fetch_one(s, cache), sources)):
            if state.get("status", "").startswith("error"):
                retry.append(src)
                continue
            items.extend(got)
            new_cache[src["id"]] = state
    # сетевые сбои повторяем по одному: параллельные соединения иногда обрываются
    for src in retry:
        time.sleep(1.0)
        got, state = fetch_one(src, cache)
        items.extend(got)
        new_cache[src["id"]] = state
    return items, new_cache
