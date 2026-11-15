"""Проверки пересказа кодом, без модели: новых имён и чисел нет, формулировка своя, длина под доску."""
from __future__ import annotations

import re

from difflib import SequenceMatcher

from .text import fold, has_cyrillic, numbers, skeleton, words

MIN_LEN, MAX_LEN = 20, 95


def _caps(title: str) -> list[str]:
    """Слова с заглавной не в начале фразы: имена, клубы, игры."""
    out = []
    for i, raw in enumerate(title.split()):
        core = raw.strip("«»\"'“”‘’()[],.:;!?—–-")
        if i == 0 or len(core) < 3:
            continue
        if core[:1].isupper():
            out.append(core)
    return out


def longest_common_run(a: list[str], b: list[str]) -> int:
    best = 0
    prev = [0] * (len(b) + 1)
    for i in range(1, len(a) + 1):
        cur = [0] * (len(b) + 1)
        for j in range(1, len(b) + 1):
            if a[i - 1] == b[j - 1]:
                cur[j] = prev[j - 1] + 1
                best = max(best, cur[j])
        prev = cur
    return best


def _spans(text: str) -> list[str]:
    """Подряд идущие слова с заглавной: «Петр Ян», «Аль-Насра», «Law & Order»."""
    out, cur = [], []
    for raw in text.split():
        core = raw.strip("«»\"'“”‘’()[],.:;!?—–-")
        if core[:1].isupper() or (cur and core in ("&", "of", "the", "de")):
            cur.append(core)
            if raw[-1:] in ",.:;!?»\"”)":
                out.append(" ".join(cur))
                cur = []
        elif cur:
            out.append(" ".join(cur))
            cur = []
    if cur:
        out.append(" ".join(cur))
    return out


def _runs(text: str, longest: int = 4) -> set[str]:
    parts = text.split()
    return {" ".join(parts[i:j]) for i in range(len(parts)) for j in range(i + 1, min(len(parts), i + longest) + 1)}


def same_name(form: str, source: str) -> bool:
    """Одно имя в двух языках: совпадают согласные после транслитерации (падежи и гласные не мешают).
    Подходит и часть source: «Реал» для «Real Madrid»."""
    sf = skeleton(form)
    if not sf:
        return fold(form) == fold(source)
    for r in _runs(source):
        sr = skeleton(r)
        if sr and abs(len(sr) - len(sf)) <= 1 and SequenceMatcher(None, sf, sr).ratio() >= 0.8:
            return True
    return False


def in_sources(form: str, hay: str) -> bool:
    """Каждое слово имени есть в заметках, с поправкой на падеж: «Реалу» при «Реал»."""
    for w in words(form):
        if len(w) < 3 or w in hay:
            continue
        if len(w) < 5 or w[:max(4, len(w) - 2)] not in hay:
            return False
    return True


# Устойчивые названия, которые переводят, а не транслитерируют. Пополнять по отказам «не сходится».
GLOSSARY = [
    ("Champions League", "Лига чемпионов"), ("Europa League", "Лига Европы"), ("Conference League", "Лига конференций"),
    ("Premier League", "Премьер-лига"), ("World Cup", "чемпионат мира"), ("Ballon d'Or", "Золотой мяч"),
    ("Olympics", "Олимпиада"), ("Olympic Games", "Олимпийские игры"), ("Formula 1", "Формула-1"),
    ("Saudi Arabia", "Саудовская Аравия"), ("United States", "США"), ("Russia", "Россия"), ("Japan", "Япония"),
    ("England", "Англия"), ("Spain", "Испания"), ("France", "Франция"), ("Germany", "Германия"), ("Italy", "Италия"),
    ("Portugal", "Португалия"), ("Brazil", "Бразилия"), ("Argentina", "Аргентина"),
    ("NASA", "НАСА"), ("Oscar", "Оскар"), ("Grammy", "Грэмми"), ("Netflix", "Netflix"),
]


def _stems_in(term: str, hay: str) -> bool:
    """Все слова термина есть в тексте без последних букв: «Лига чемпионов» в «Лиге чемпионов»."""
    return all(w[:max(3, len(w) - 2)] in hay for w in words(term))


def _glossary_ok(form: str, hay: str) -> bool:
    f = fold(form)
    for en, ru in GLOSSARY:
        if (_stems_in(en, f) and _stems_in(ru, hay)) or (_stems_in(ru, f) and _stems_in(en, hay)):
            return True
    return False


def check_names(names: list, lang: str, text: str, source_text: str, same_lang: bool) -> str | None:
    """Имена из ответа модели: {"source", "en", "ru"}. Имя на языке заметок есть в заметках, имя на другом
    языке читается как одно из имён в заметках. Так ловятся выдуманные имена, лишние имена
    («Луис Роналду», когда в заметках «Криштиану Роналду») и неверная транслитерация («Elya Vild»)."""
    hay = fold(source_text)
    spans = _spans(source_text)
    forms = set()
    for n in names or []:
        if not isinstance(n, dict):
            continue
        form = (n.get(lang) or "").strip()
        if not form:
            continue
        forms.update(words(form))
        if same_lang:
            if not in_sources(form, hay):
                return "имени нет в заметках: " + form
        elif not (in_sources(form, hay) or any(same_name(form, sp) for sp in spans) or _glossary_ok(form, hay)):
            return "имя не сходится с заметками: " + form
    if not same_lang:
        for cap in _caps(text):
            ws = words(cap)
            if ws and not any(w in forms or w in hay for w in ws):
                return "имя не из списка модели: " + cap
    return None


def check_details(text: str, lang: str, source_titles: list[str], source_text: str, same_lang: bool) -> str | None:
    """Подробности для кнопки «Подробнее»: пусто можно; иначе те же правила, что у заголовка, длиннее."""
    if not text:
        return None
    if not (30 <= len(text) <= 260):
        return f"длина {len(text)}"
    if re.search(r"[!?]", text):
        return "восклицание или вопрос"
    if lang == "ru" and not has_cyrillic(text):
        return "русский текст без кириллицы"
    extra = numbers(text) - numbers(source_text)
    if extra:
        return "числа не из источников: " + ", ".join(sorted(extra))
    if same_lang:
        tw = words(text)
        for st in source_titles:
            if longest_common_run(tw, words(st)) >= 5:
                return "пять слов подряд из заголовка источника"
        if longest_common_run(tw, words(source_text)) >= 7:
            return "семь слов подряд из заметки"
    return None


def check(text: str, lang: str, source_titles: list[str], source_text: str, same_lang: bool) -> str | None:
    """Причина отказа или None. same_lang: пересказ на языке источников (тогда проверяем имена и копирование)."""
    if not (MIN_LEN <= len(text) <= MAX_LEN):
        return f"длина {len(text)}"
    if re.search(r"[!?]", text):
        return "восклицание или вопрос"
    if lang == "ru" and not has_cyrillic(text):
        return "русский пересказ без кириллицы"
    extra = numbers(text) - numbers(source_text)
    if extra:
        return "числа не из источников: " + ", ".join(sorted(extra))
    if same_lang:
        hay = fold(source_text)
        for name in _caps(text):
            if fold(name) not in hay and not any(w in hay for w in words(name) if len(w) >= 4):
                return "имя не из источников: " + name
        tw = words(text)
        for st in source_titles:
            sw = words(st)
            if longest_common_run(tw, sw) >= 5:
                return "совпадает с заголовком источника пятью словами подряд"
            if tw and len(set(tw) & set(sw)) / len(set(tw)) >= 0.8:
                return "почти те же слова, что у источника"
    return None
