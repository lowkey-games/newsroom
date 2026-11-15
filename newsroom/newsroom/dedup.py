"""Одна история из разных источников: та же логика, что в src/shared/Dedup.luau игры."""
from __future__ import annotations

from .text import fold, words

STOP = set("""
a an the and or but of to in on at for from by with as is are was were be been being it its this that these those
after before over under into out up down about than then so not no yes will would can could should may might must
has have had do does did his her their our your my he she they we you i me him them us who whom what which when where
why how all any some more most new says said say just now get gets got make makes made one two three first last
vs v amid via per off again also still back set sets day days week year years time
и в во на с со к ко по за из у о об от до для не но а же ли что как это его ее её их он она они мы вы я
бы был была были было будет будут есть при под над без через после перед между так уже еще ещё все всё только
""".split())

GENERIC = set("""
world cup league premier champions europa united city club team teams game games season final finals match
matches win wins won lose loses lost loss draw draws goal goals star stars fans fan record women men womens mens
manager coach player players report show shows film films series music album song new big top best update updates
launch launches launched release released price prices apple google meta microsoft sony nintendo xbox playstation
мира чемпионат лига клуб команда матч игра игры сезон финал звезда фанаты рекорд новый новая новое
""".split())

OVERLAP = 0.5
MIN_SHARED = 2


def signature(title: str) -> dict[str, float]:
    caps = set()
    for i, raw in enumerate(title.split()):
        if i == 0:
            continue
        c = raw[:1]
        if c.isupper():
            caps.update(words(raw))
    sig: dict[str, float] = {}
    for w in words(title):
        if w in STOP or len(w) < 3 or w in sig:
            continue
        sig[w] = 0.5 if w in GENERIC else (2.0 if w in caps else 1.0)
    return sig


def same(a: dict[str, float], b: dict[str, float]) -> bool:
    shared_w = 0.0
    shared_n = 0
    strong = 0
    for w, wa in a.items():
        wb = b.get(w)
        if wb is not None:
            shared_w += max(wa, wb)
            shared_n += 1
            if wa >= 1 and wb >= 1:
                strong += 1
    base = min(sum(a.values()), sum(b.values()))
    if base <= 0:
        return False
    return shared_w / base >= OVERLAP and shared_n >= MIN_SHARED and strong >= 2


def norm(title: str) -> str:
    return " ".join(words(fold(title)))
