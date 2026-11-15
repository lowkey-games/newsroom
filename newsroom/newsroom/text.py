"""Слова и нормализация текста для фильтра, склейки и проверок."""
from __future__ import annotations

import html
import re
import unicodedata

WORD = re.compile(r"[^\W_]+(?:['’][^\W_]+)*", re.UNICODE)


def fold(s: str) -> str:
    """Нижний регистр, ё → е, латиница без диакритики."""
    s = s.casefold().replace("ё", "е")
    out = []
    for ch in s:
        if "a" <= ch <= "z" or not ("À" <= ch <= "ɏ"):
            out.append(ch)
        else:
            base = unicodedata.normalize("NFD", ch)[0]
            out.append(base)
    return "".join(out)


def words(s: str) -> list[str]:
    """Слова в нижнем регистре; притяжательное 's отбрасывается, апостроф внутри склеивает (don't → dont)."""
    out = []
    for m in WORD.finditer(s):
        w = fold(m.group(0))
        w = re.sub(r"['’]s$", "", w)
        w = w.replace("'", "").replace("’", "")
        if w:
            out.append(w)
    return out


def clean_html(s: str | None) -> str:
    """CDATA, сущности, теги, пробелы. Двойное кодирование раскрывается вторым проходом."""
    if not s:
        return ""
    s = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", s, flags=re.S)
    s = html.unescape(html.unescape(s))
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = s.replace(" ", " ").replace("​", "").replace("­", "")
    s = re.sub(r"[ \t\r\f\v]+", " ", s)
    s = re.sub(r"\s*\n\s*", "\n", s)
    return s.strip()


NUMBER = re.compile(r"\d{1,3}(?:[ ,.\u00a0\u202f]\d{3})+(?!\d)|\d+(?:[.,]\d+)?")
GROUPED = re.compile(r"\d{1,3}(?:[ ,.\u00a0\u202f]\d{3})+")


def numbers(s: str) -> set[str]:
    """Числа текста в общем виде: 1,000 и 1 000 → 1000, 2,5 → 2.5. «13, 2027» — два числа, 13 и 2027."""
    found = set()
    for m in NUMBER.finditer(s):
        raw = m.group(0)
        if GROUPED.fullmatch(raw):
            raw = re.sub(r"[ ,.\u00a0\u202f]", "", raw)
        found.add(raw.replace(",", "."))
    return found


TRANSLIT = dict(zip(
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
    ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t", "u",
     "f", "kh", "ts", "ch", "sh", "shch", "", "y", "", "e", "yu", "ya"]))


def latin(s: str) -> str:
    return "".join(TRANSLIT.get(ch, ch) for ch in fold(s))


def skeleton(name: str) -> str:
    """Согласные имени после транслитерации: «Элайджа Вуд» и «Elijah Wood» дают одно и то же."""
    s = latin(name)
    for a, b in (("dzh", "j"), ("dj", "j"), ("zh", "j"), ("shch", "6"), ("sch", "6"), ("sh", "6"), ("ch", "4"),
                 ("kh", "h"), ("ck", "k"), ("ph", "f"), ("ts", "c"), ("tz", "c"), ("w", "v"), ("q", "k"), ("x", "ks")):
        s = s.replace(a, b)
    s = re.sub(r"c(?=[eiy])", "s", s).replace("c", "k")
    s = re.sub(r"[^a-z46]", "", s)
    s = re.sub(r"[aeiouyh]", "", s)
    return re.sub(r"(.)\1+", r"\1", s)


def has_cyrillic(s: str) -> bool:
    return re.search(r"[а-яёА-ЯЁ]", s) is not None
