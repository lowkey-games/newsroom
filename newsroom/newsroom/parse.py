"""Разбор источников в заметки: RSS 2.0, Atom, публичный предпросмотр Telegram-канала, ответ GNews."""
from __future__ import annotations

import email.utils
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .text import clean_html


@dataclass
class Item:
    source: str  # id источника из sources.json
    title: str
    summary: str = ""
    link: str = ""
    published: float = 0.0  # unix
    tags: list[str] = field(default_factory=list)
    outlet: str | None = None  # издание внутри агрегатора (GNews)


def parse_date(s: str | None) -> float:
    if not s:
        return 0.0
    s = clean_html(s).strip()
    try:
        dt = email.utils.parsedate_to_datetime(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except (TypeError, ValueError, IndexError):
        pass
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except ValueError:
        return 0.0


def _elements(block: str, tag: str) -> list[tuple[str, str]]:
    """(открывающий тег, содержимое) для <tag ...>...</tag> и <tag .../>"""
    out = []
    pat = re.compile(r"<" + re.escape(tag) + r"(\s[^>]*)?(/>|>(.*?)</" + re.escape(tag) + r">)", re.S)
    for m in pat.finditer(block):
        out.append((m.group(1) or "", m.group(3) or ""))
    return out


def _child(block: str, tag: str) -> str | None:
    els = _elements(block, tag)
    return els[0][1] if els else None


def _attr(open_attrs: str, name: str) -> str | None:
    m = re.search(r"\s" + name + r'\s*=\s*"([^"]*)"', open_attrs) or re.search(r"\s" + name + r"\s*=\s*'([^']*)'", open_attrs)
    return clean_html(m.group(1)) if m else None


def parse_feed(body: str, source: str) -> list[Item]:
    items: list[Item] = []
    if "<item" in body:
        for _, b in _elements(body, "item"):
            items.append(Item(
                source=source,
                title=clean_html(_child(b, "title")),
                summary=clean_html(_child(b, "description"))[:600],
                link=clean_html(_child(b, "link")),
                published=parse_date(_child(b, "pubDate") or _child(b, "dc:date")),
                tags=[t for t in (clean_html(c) for _, c in _elements(b, "category")) if t],
            ))
    elif "<entry" in body:
        for _, b in _elements(body, "entry"):
            link = ""
            for attrs, _ in _elements(b, "link"):
                href = _attr(attrs, "href")
                if href and (not link or 'rel="alternate"' in attrs):
                    link = href
            tags = []
            for attrs, inner in _elements(b, "category"):
                t = _attr(attrs, "term") or clean_html(inner)
                if t:
                    tags.append(t)
            items.append(Item(
                source=source,
                title=clean_html(_child(b, "title")),
                summary=clean_html(_child(b, "summary") or _child(b, "content"))[:600],
                link=link,
                published=parse_date(_child(b, "published") or _child(b, "updated")),
                tags=tags,
            ))
    return items


def parse_telegram(page: str, source: str) -> list[Item]:
    """Публичный предпросмотр t.me/s/<канал>: у поста нет заголовка, берём первую строку или фразу."""
    items: list[Item] = []
    for block in re.split(r'<div class="tgme_widget_message_wrap', page)[1:]:
        post = re.search(r'data-post="([^"]+)"', block)
        text_m = re.search(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', block, re.S)
        when = re.search(r'<time[^>]*datetime="([^"]+)"', block)
        if not text_m:
            continue
        text = clean_html(text_m.group(1))
        # ссылки, хэштеги и эмодзи-подписи каналу не нужны
        text = re.sub(r"https?://\S+", "", text)
        text = re.sub(r"(^|\s)[#@]\w+", " ", text)
        first, _, rest = text.partition("\n")
        first = _strip_emoji(first).strip(" .:—-–|")
        if len(first) > 160:
            # длинный первый абзац: до конца первой фразы
            m = re.match(r"(.{30,160}?[.!?])\s", first + " ")
            first = m.group(1) if m else first[:160]
        items.append(Item(
            source=source,
            title=first.strip(),
            summary=_strip_emoji(rest).strip()[:600],
            link=f"https://t.me/{post.group(1)}" if post else "",
            published=parse_date(when.group(1)) if when else 0.0,
        ))
    return items


EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿️‍⃣\U000E0020-\U000E007F]")


def _strip_emoji(s: str) -> str:
    return re.sub(r"\s{2,}", " ", EMOJI.sub(" ", s)).strip()


def parse_gnews(body: str, source: str) -> list[Item]:
    try:
        data = json.loads(body)
    except ValueError:
        return []
    items = []
    for a in data.get("articles") or []:
        if not isinstance(a, dict) or not isinstance(a.get("title"), str):
            continue
        src = a.get("source") if isinstance(a.get("source"), dict) else {}
        items.append(Item(
            source=source,
            title=clean_html(a["title"]),
            summary=clean_html(a.get("description") or "")[:600],
            link=a.get("url") or "",
            published=parse_date(a.get("publishedAt")),
            outlet=src.get("name") if isinstance(src.get("name"), str) else None,
        ))
    return items
