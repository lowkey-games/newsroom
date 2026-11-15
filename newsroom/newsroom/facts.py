"""Строка без ИИ: только то, что подтвердили минимум два независимых источника.

Имена и названия, событие из своего словаря и числа с единицами складываются через « · »:
«Arkane · закрытие · 13 ноября». Чужих формулировок нет, только факты. Перевода нет: строка
выходит в той версии игры, на языке которой написаны заметки."""
from __future__ import annotations

import re

from .text import NUMBER, fold, numbers

SEP = " · "
MAX_LEN = 72
MAX_NAMES = 3

# Событие: метки на двух языках и слова-признаки. «слово*» — начало слова, иначе слово целиком,
# фраза с пробелом ищется как есть. Порядок решает при равенстве: выше — конкретнее.
# cats — только для этих рубрик.
EVENTS: list[dict] = [
    {"en": "retirement", "ru": "завершение карьеры", "t_en": ["retire*"],
     "t_ru": ["завершил* карьер*", "завершит* карьер*", "завершени* карьер*", "заверша* карьер*"]},
    {"en": "leak", "ru": "утечка", "t_en": ["leak*"], "t_ru": ["утечк*", "слил*", "слив*", "утек*", "утёк*"]},
    {"en": "trailer", "ru": "трейлер", "t_en": ["trailer*", "teaser*"], "t_ru": ["трейлер*", "тизер*"]},
    {"en": "delay", "ru": "перенос", "t_en": ["delay*", "postpon*", "pushed back"],
     "t_ru": ["перенес*", "перенос*", "перенёс*", "отложен*", "отложил*"]},
    {"en": "cancelled", "ru": "отмена", "t_en": ["cancel*", "scrapped"], "t_ru": ["отмен*"]},
    {"en": "closure", "ru": "закрытие", "t_en": ["closure*", "shut down", "shutdown", "shuts down", "closes", "closed"],
     "t_ru": ["закрыт*", "закроют", "закрыва*", "закрыл*"]},
    {"en": "transfer", "ru": "переход", "t_en": ["transfer*", "signs for", "joins", "signing"],
     "t_ru": ["переход*", "перейд*", "трансфер*"]},
    {"en": "injury", "ru": "травма", "t_en": ["injur*"], "t_ru": ["травм*"]},
    {"en": "award", "ru": "награда", "t_en": ["award*", "prize*", "nominat*", "honour*", "honor*"],
     "t_ru": ["преми*", "наград*", "номинац*", "орден*"]},
    {"en": "record", "ru": "рекорд", "t_en": ["record", "records", "record-breaking"], "t_ru": ["рекорд*"]},
    {"en": "goal", "ru": "гол", "t_en": ["goal", "goals", "scores", "scored", "hat-trick", "brace"],
     "t_ru": ["гол", "гола", "голов", "голы", "голом", "забил", "забила", "забили", "хет-трик*", "дубль"]},
    {"en": "win", "ru": "победа", "t_en": ["win", "wins", "won", "beat", "beats", "victory", "triumph*"],
     "t_ru": ["побед*", "обыгра*", "выигра*"]},
    {"en": "new album", "ru": "новый альбом", "t_en": ["album*"], "t_ru": ["альбом*"], "cats": {"music", "stars"}},
    {"en": "new song", "ru": "новый трек", "t_en": ["single", "song", "songs", "track"], "t_ru": ["трек*", "сингл*", "песн*"],
     "cats": {"music", "stars"}},
    {"en": "music video", "ru": "клип", "t_en": ["music video", "video"], "t_ru": ["клип*"], "cats": {"music", "stars"}},
    {"en": "tour", "ru": "тур", "t_en": ["tour", "tours", "touring"], "t_ru": ["тур", "тура", "туре", "турне", "гастрол*"],
     "cats": {"music", "stars"}},
    {"en": "concert", "ru": "концерт", "t_en": ["concert*", "gig", "gigs"], "t_ru": ["концерт*"], "cats": {"music", "stars"}},
    {"en": "festival", "ru": "фестиваль", "t_en": ["festival*"], "t_ru": ["фестивал*"], "cats": {"music", "stars"}},
    {"en": "charts", "ru": "чарты", "t_en": ["chart*", "hot 100", "billboard 200", "number one"], "t_ru": ["чарт*", "хит-парад*"],
     "cats": {"music"}},
    {"en": "birthday", "ru": "день рождения", "t_en": ["birthday"], "t_ru": ["день рождения", "дня рождения"], "cats": {"music", "stars"}},
    {"en": "update", "ru": "обновление", "t_en": ["update*", "patch*"], "t_ru": ["обновлени*", "патч*"]},
    {"en": "sequel", "ru": "продолжение", "t_en": ["sequel*", "remake*", "remaster*"],
     "t_ru": ["сиквел*", "ремейк*", "ремастер*", "продолжени*"]},
    {"en": "release", "ru": "выход", "t_en": ["release*", "out now", "available now", "arrives", "premiere*", "debut*"],
     "t_ru": ["выйдет", "выход", "выхода", "вышел", "вышла", "вышло", "релиз*", "стартует", "премьер*"]},
    {"en": "launch", "ru": "запуск", "t_en": ["launch*", "liftoff", "lift-off"], "t_ru": ["запуск*", "запустил*", "запустят"]},
    {"en": "reveal", "ru": "анонс", "t_en": ["announc*", "unveil*", "reveal*"],
     "t_ru": ["анонс*", "представил*", "представила", "представят", "показал*", "показала"]},
    {"en": "return", "ru": "возвращение", "t_en": ["return*", "comeback"], "t_ru": ["возвращ*", "вернул*", "вернет*", "вернёт*"]},
    {"en": "new season", "ru": "новый сезон", "t_en": ["season*"], "t_ru": ["сезон*"], "cats": {"stars", "fashion", "games"}},
    {"en": "filming", "ru": "съёмки", "t_en": ["filming", "shooting begins", "production begins"], "t_ru": ["съемк*", "съёмк*"]},
    {"en": "casting", "ru": "кастинг", "t_en": ["cast", "casting", "screen test*", "audition*", "role"],
     "t_ru": ["каст*", "кинопроб*", "сыграет", "роль", "роли"]},
    {"en": "pre-orders", "ru": "предзаказы", "t_en": ["pre-order*", "preorder*"], "t_ru": ["предзаказ*"]},
    {"en": "sales", "ru": "продажи", "t_en": ["sales", "sold", "copies"], "t_ru": ["продаж*", "продан*", "копий"]},
    {"en": "players", "ru": "аудитория", "t_en": ["players", "player count", "concurrent*", "audience"],
     "t_ru": ["аудитори*", "игроков", "онлайн*"]},
    {"en": "deal", "ru": "сделка", "t_en": ["deal", "deals", "acquir*", "acquisition*", "buyer*", "bought"],
     "t_ru": ["сделк*", "купил*", "купить", "покупк*", "покупател*", "приобр*"]},
    {"en": "price", "ru": "цена", "t_en": ["price*", "pricier", "cheaper"], "t_ru": ["цена", "цены", "цену", "стоимост*", "подорож*", "подешев*"]},
    {"en": "vulnerability", "ru": "уязвимость", "t_en": ["vulnerab*", "exploit*", "breach*"], "t_ru": ["уязвимост*", "взлом*"]},
    {"en": "collab", "ru": "коллаборация", "t_en": ["collab*", "crossover*"], "t_ru": ["коллаб*", "кроссовер*"]},
    {"en": "baby news", "ru": "пополнение в семье",
     "t_en": ["baby", "born", "birth", "grandfather", "grandmother", "grandchild*", "grandson*", "granddaughter*"],
     "t_ru": ["родил*", "рождени*", "дедушк*", "дедом", "бабушк*", "внук*", "внучк*", "малыш*"]},
    {"en": "engagement", "ru": "помолвка", "t_en": ["engage*", "proposal", "proposed"], "t_ru": ["помолв*"]},
    {"en": "wedding", "ru": "свадьба", "t_en": ["wedding*", "married", "marries", "marry"], "t_ru": ["свадьб*", "женил*", "замуж*"]},
    {"en": "new look", "ru": "новый образ", "t_en": ["look", "dress", "outfit*", "makeover", "hairstyle", "haircut", "bob"],
     "t_ru": ["образ*", "плать*", "стрижк*", "прическ*", "причёск*"], "cats": {"stars", "fashion"}},
    {"en": "departure", "ru": "уход", "t_en": ["leave", "leaves", "leaving", "exit*", "quit*", "depart*", "exodus"],
     "t_ru": ["ушел", "ушёл", "уходит", "уход*", "покида*", "покинул*", "покинет"]},
    {"en": "match", "ru": "матч", "t_en": ["derby", "match", "clash", "fixture"], "t_ru": ["матч*", "дерби"]},
    {"en": "discovery", "ru": "открытие", "t_en": ["discover*", "detect*"], "t_ru": ["обнаружил*", "обнаружен*", "открыли"]},
    {"en": "free", "ru": "бесплатно", "t_en": ["free"], "t_ru": ["бесплатн*", "раздач*", "раздают"]},
]

MONTHS_EN = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
             "november", "december", "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec"]
MONTHS_RU = ["январ", "феврал", "март", "апрел", "мая", "май", "июн", "июл", "август", "сентябр", "октябр", "ноябр", "декабр"]
DAYS = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
        "понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"}

# Единица после числа: без неё голое число на доске ничего не скажет
UNITS = ("million", "millions", "billion", "billions", "thousand", "m", "bn", "percent", "years", "year", "goals", "goal",
         "points", "players", "copies", "signatures", "people", "fans", "views", "days", "hours", "minutes",
         "episodes", "games", "matches", "seasons", "km", "miles", "units",
         "млн", "млрд", "тыс", "миллион*", "миллиард*", "тысяч*", "процент*", "лет", "год*", "гол*", "очк*", "игрок*",
         "копий", "копии", "подпис*", "человек", "фанат*", "зрител*", "просмотр*", "дней", "дня", "день", "час*",
         "минут*", "сери*", "матч*", "сезон*", "км", "руб*", "долл*", "евро", "заказ*")

# Слова с заглавной, которые не имена
CAP_STOP = {"сми", "upd", "видео", "фото", "breaking", "exclusive", "live", "watch", "video", "photos", "report",
            "reports", "i", "the", "a", "an", "it", "its", "this", "that", "new", "why", "how", "what", "who", "when",
            "here", "there", "after", "as", "in", "on", "for", "and", "but", "or", "with", "from", "by", "at", "to",
            "game", "games", "plus", "free", "official", "update", "trailer", "review", "everybody", "final",
            "out", "up", "off", "back", "down", "over", "into", "about", "says", "after", "before", "more",
            "мы", "я", "он", "она", "они", "это", "как", "что", "почему", "где", "когда", "кто", "все", "новый", "новая",
            "внимание", "срочно", "официально", "слух", "слухи", "инсайдер", "инсайдеры", "источник", "источники",
            "в", "во", "на", "с", "со", "по", "для", "из", "от", "до", "о", "об", "у", "к", "за", "при", "без", "над",
            "под", "и", "а", "но", "не", "ни", "же", "ли", "бы", "то", "так", "уже", "еще", "ещё", "только", "также"}
CAP_STOP |= DAYS
WEAK = set(MONTHS_EN)  # месяц продолжает имя («Stephanie March»), но имя с него не начинается
BRIDGE = {"of", "the", "de", "la", "le", "van", "von", "da", "del", "a", "an", "&", ":"}

TOKEN = re.compile(r"[^\W_][\w'’\-]*(?:[.,]\d+)*|[&:]", re.UNICODE)
QUOTED = re.compile(r"[«“‘\"]([^«»“”‘’\"]{2,60})[»”’\"]")
LATIN = re.compile(r"[A-Za-z]")
CYR = re.compile(r"[А-Яа-яЁё]")
# прилагательное в косвенном падеже: «Итогового (турнира)» — часть названия, одно на доске не читается
RU_ADJ = re.compile(r"(?:ого|его|ому|ему|ыми|ими)$")


def _match(word: str, triggers: list[str]) -> bool:
    for t in triggers:
        if " " in t:
            continue
        if t.endswith("*"):
            if word.startswith(t[:-1]):
                return True
        elif word == t:
            return True
    return False


def _phrase_hit(folded: str, triggers: list[str]) -> bool:
    for t in triggers:
        if " " not in t:
            continue
        pat = r"\b" + r"\s+".join(re.escape(p.rstrip("*")) + (r"\w*" if p.endswith("*") else "") for p in t.split()) + r"\b"
        if re.search(pat, folded):
            return True
    return False


def _bare(w: str) -> str:
    return re.sub(r"['’]s$", "", fold(w))


def stem(w: str) -> str:
    w = _bare(w)
    return w[:max(4, len(w) - 2)] if len(w) >= 5 else w


def _same_word(a: str, b: str) -> bool:
    """Одно слово в разных падежах: «Спартак» и «Спартака»."""
    fa, fb = _bare(a), _bare(b)
    if fa == fb:
        return True
    if len(fa) < 4 or len(fb) < 4 or fa[0].isdigit() or fb[0].isdigit():
        return False
    if CYR.match(fa) and abs(len(fa) - len(fb)) <= 1 and fa[:-1] == fb[:len(fa) - 1]:
        return True  # «Лига» и «Лиге»
    return fb.startswith(stem(fa)) or fa.startswith(stem(fb))


def _abbrev(a: str, b: str) -> bool:
    """«Man Utd» — сокращение «Manchester United»: буквы по порядку и та же первая."""
    fa, fb = _bare(a), _bare(b)
    if not fa or not fb or fa[0] != fb[0] or len(fa) >= len(fb):
        return False
    it = iter(fb)
    return all(ch in it for ch in fa)


def _is_titlecase(title: str) -> bool:
    ws = [w for w in re.findall(r"[A-Za-z][A-Za-z'’\-]*", title) if len(w) >= 4]
    return len(ws) >= 3 and sum(w[0].isupper() for w in ws) / len(ws) >= 0.6


def _segments(text: str) -> list[str]:
    """Куски, где первое слово стоит в начале фразы: предложения и части после тире."""
    return [p for p in re.split(r"(?<=[.!?…])\s+|\s+[—–]\s+|\s+-\s+|\n+", text) if p.strip()]


def _tokens(text: str) -> list[str]:
    text = text.replace("‐", "-").replace("‑", "-")
    out = []
    for t in TOKEN.findall(text):
        t = t.rstrip("'’-")
        # «Effect-themed» → «Effect»: хвост через дефис не часть имени
        m = re.match(r"^([A-Z][A-Za-z]+)-([a-z]{4,})$", t)
        if m:
            t = m.group(1)
        if t:
            out.append(t)
    return out


class _Quoted(list):
    """Название в кавычках: берётся только целиком."""


class _Text:
    """Заголовок или подводка одного источника, разобранные на слова."""

    def __init__(self, owner: str, text: str, title: bool, ru: bool):
        self.owner, self.title, self.ru = owner, title, ru
        self.tc = title and not ru and _is_titlecase(text)
        self.text = text
        self.segs = [_tokens(seg) for seg in _segments(text)]
        self.words = [t for seg in self.segs for t in seg if t not in "&:"]

    def positions(self):
        """(слово, в начале фразы) — после двоеточия тоже начало: «СМИ: Arkane…»."""
        for seg in self.segs:
            prev = None
            for i, t in enumerate(seg):
                yield t, i == 0 or prev == ":"
                prev = t


class _Cluster:
    def __init__(self, cluster: dict):
        self.ru = cluster["lang"] == "ru"
        self.category = cluster.get("category", "")
        self.texts: list[_Text] = []
        self.owners: list[str] = []
        for e in sorted(cluster["items"], key=lambda e: e.get("published", 0)):
            o = e.get("owner") or e["source"]
            if o not in self.owners:
                self.owners.append(o)
            self.texts.append(_Text(o, e["title"], True, self.ru))
            if e.get("summary"):
                self.texts.append(_Text(o, e["summary"][:400], False, self.ru))
        lower: set[str] = set()
        caps_any: dict[str, set[str]] = {}
        caps_sure: dict[str, set[str]] = {}
        known: set[str] = set()
        for t in self.texts:
            for w, initial in t.positions():
                if w in "&:" or w[0].isdigit():
                    continue
                if w[0].islower():
                    lower.add(stem(w))
                    continue
                b = _bare(w)
                caps_any.setdefault(b, set()).add(t.owner)
                if t.tc and not initial:
                    continue  # в заголовке «Каждое Слово С Заглавной» заглавная сама ничего не значит
                caps_sure.setdefault(b, set()).add(t.owner)
                if not initial and not (w.isupper() and len(w) > 5):
                    known.add(b)
        self.lower = lower

        def owners(d: dict[str, set[str]], b: str) -> set[str]:
            return set().union(*[o for v, o in d.items() if _same_word(b, v)])
        # слово в начале фразы — имя, если оно с заглавной у двух источников (хотя бы раз не в «Каждом Слове
        # С Заглавной») и нигде не написано строчными. Падежи считаются одним словом: «Спартак», «Спартака»
        for b in caps_any:
            if stem(b) not in lower and len(owners(caps_any, b)) >= 2 and owners(caps_sure, b):
                known.add(b)
        self.known_words = known
        self.known = {stem(b) for b in known}
        # пара слов с заглавной у двух источников — имя, даже в заголовках «Каждое Слово С Заглавной»:
        # «Stephanie March»
        pairs: dict[tuple, set[str]] = {}
        for t in self.texts:
            for seg in t.segs:
                for a, b in zip(seg, seg[1:]):
                    if a[:1].isupper() and b[:1].isupper() and _bare(a) not in CAP_STOP and _bare(b) not in CAP_STOP:
                        pairs.setdefault((_bare(a), _bare(b)), set()).add(t.owner)
        triggers = [t for ev in EVENTS for t in ev["t_en"] + ev["t_ru"]]
        for (a, b), who in pairs.items():
            if len(who) >= 2 and stem(a) not in lower and stem(b) not in lower \
                    and not _match(a, triggers) and not _match(b, triggers):
                self.known_words |= {a, b}  # «BioWare Closure» — не имя: closure — слово события
        if not self.ru:
            self.known_words = {b for b in self.known_words if stem(b) not in lower}
        self.known = {stem(b) for b in self.known_words}

    def is_known(self, w: str) -> bool:
        b = _bare(w)
        return stem(b) in self.known or any(_same_word(b, k) for k in self.known_words)

    def proper(self, w: str, initial: bool, t: _Text) -> bool:
        f = _bare(w)
        st = stem(w)
        if f in CAP_STOP or (f in WEAK and not self.is_known(w)) or w[0].isdigit() or not w[0].isalpha():
            return False
        if t.ru and LATIN.match(w):
            return w[0].isupper() or any(ch.isdigit() for ch in w)
        if w.isupper() and len(w) >= 2:
            if len(w) <= 5 and st not in self.lower:
                return True  # UFC, HLX, КХЛ
            return self.is_known(w) and st not in self.lower
        if not w[0].isupper():
            return False
        if initial or t.tc:
            return self.is_known(w)
        if CYR.match(w) and st in self.lower:
            return False
        return True

    def spans(self, t: _Text) -> list[list[str]]:
        out: list[list[str]] = []
        for seg in t.segs:
            cur: list[str] = []
            pend: list[str] = []
            prev = None
            for i, w in enumerate(seg):
                initial = i == 0 or prev == ":"
                prev = w
                if cur and (w in "&:" or fold(w) in BRIDGE):
                    pend.append(w)
                    continue
                script_break = cur and t.ru and bool(LATIN.match(w)) != bool(LATIN.match(cur[-1])) \
                    and not cur[-1][0].isdigit() and not w[0].isdigit()
                if self.proper(w, initial, t) and not script_break:
                    cur += pend + [w]
                    pend = []
                    continue
                if cur and not pend and (fold(w) in WEAK or re.fullmatch(r"\d{1,2}|\d{1,3}(?:[,.]\d{3})+", w)):
                    cur.append(w)  # «Stephanie March», «Battlefield 6», «Warhammer 40,000»
                    continue
                if cur:
                    out.append(cur)
                cur, pend = [], []
                if self.proper(w, initial, t):
                    cur = [w]
            if cur:
                out.append(cur)
        for m in QUOTED.finditer(t.text):
            inner = _tokens(m.group(1))
            ws = [w for w in inner if w not in "&:"]
            common = all(stem(w) in self.lower or _bare(w) in CAP_STOP for w in ws if not w[0].isdigit())
            if 1 <= len(ws) <= 6 and m.group(1).strip()[:1].isupper() and not common:
                out.append(_Quoted(inner))
        return out

    def has(self, owner: str, key: list[str], titles_only: bool = False) -> bool:
        words = [w for t in self.texts if t.owner == owner and (t.title or not titles_only) for w in t.words]
        return all(any(_same_word(k, w) for w in words) for k in key)


def _key(span: list[str]) -> list[str]:
    return [w for w in span if fold(w) not in BRIDGE]


def _surface(span: list[str]) -> str:
    s = ""
    for t in span:
        if t == ":":
            s += ":"
        elif t == "&":
            s += " &"
        else:
            s += (" " if s else "") + t
    return re.sub(r"['’]s$", "", s.strip(" :"))


def _glossary(cl: _Cluster) -> list[dict]:
    from .checks import GLOSSARY
    out = []
    for en, ru in GLOSSARY:
        term = ru if cl.ru else en
        key = _tokens(term)
        title = {o for o in cl.owners if cl.has(o, key, True)}
        if sum(cl.has(o, key) for o in cl.owners) >= 2 and title:
            out.append({"key": key, "form": term, "title": title, "fixed": True})
    return out


def _names(cl: _Cluster) -> list[str]:
    cands: list[dict] = []
    for t in cl.texts:
        seen_here: set[str] = set()
        for span in cl.spans(t):
            n = len(span)
            whole_only = isinstance(span, _Quoted)
            for size in range(n, 0 if not whole_only else n - 1, -1):
                for a in range(0, n - size + 1):
                    sub = span[a:a + size]
                    if fold(sub[0]) in BRIDGE or fold(sub[-1]) in BRIDGE:
                        continue
                    key = _key(sub)
                    if not key or all(k[0].isdigit() for k in key) or _bare(key[0]) in WEAK:
                        continue
                    form = _surface(sub)
                    if form in seen_here:
                        continue
                    seen_here.add(form)
                    cands.append({"key": key, "form": form, "in_title": t.title})
    # одно имя в разных падежах и сокращениях — одна запись
    merged: list[dict] = []
    for c in cands:
        for m in merged:
            if len(m["key"]) == len(c["key"]) and all(
                    _same_word(a, b) or _abbrev(a, b) or _abbrev(b, a) for a, b in zip(m["key"], c["key"])):
                m["forms"][c["form"]] = m["forms"].get(c["form"], 0) + (2 if c["in_title"] else 1)
                if len(c["key"]) and len(c["form"]) > len(m["longest"]):
                    m["longest"] = c["form"]
                break
        else:
            merged.append({"key": c["key"], "forms": {c["form"]: 2 if c["in_title"] else 1}, "longest": c["form"]})
    confirmed = []
    for m in merged:
        keys = [m["key"]] + [_key(_tokens(f)) for f in m["forms"]]
        mention = {o for o in cl.owners if any(cl.has(o, k) for k in keys)}
        title = {o for o in cl.owners if any(cl.has(o, k, True) for k in keys)}
        if len(mention) >= 2 and title:
            # «XBOX» и «Xbox» — одна запись, на доске обычное написание
            groups: dict[str, list] = {}
            for f, k in m["forms"].items():
                groups.setdefault(fold(f), []).append((f, k))
            top = max(groups.values(), key=lambda g: (sum(k for _, k in g), -min(len(f) for f, _ in g)))
            form = sorted(top, key=lambda fk: (fk[0].isupper(), -fk[1]))[0][0]
            confirmed.append({"key": _key(_tokens(form)), "form": form, "title": title, "mention": mention})
    fixed = _glossary(cl)
    pool = sorted(fixed + confirmed, key=lambda c: (-len(c["title"]) - (0.5 if c.get("fixed") else 0), -len(c["key"])))
    chosen: list[dict] = []
    for c in pool:
        if any(any(_same_word(a, b) or _abbrev(a, b) or _abbrev(b, a) for a in c["key"] for b in ch["key"]) for ch in chosen):
            continue
        chosen.append(c)
    # достроить: «Hatton» → «Tyrrell Hatton», «Half-Life» → «Half-Life 3», «Effect» → «Mass Effect»,
    # если полное имя есть у двух источников
    for ch in chosen:
        if ch.get("fixed"):
            continue
        for c in confirmed:
            if len(c["key"]) != len(ch["key"]) + 1 or len(c["mention"]) < 2:
                continue
            before = all(_same_word(a, b) for a, b in zip(c["key"][1:], ch["key"])) and not c["key"][0][0].isdigit()
            after = all(_same_word(a, b) for a, b in zip(c["key"], ch["key"])) and c["key"][-1][0].isdigit()
            if before or after:
                ch["form"], ch["key"] = c["form"], c["key"]
                break
    final: list[dict] = []
    for ch in chosen:
        if not any(any(_same_word(a, b) for a in ch["key"] for b in f["key"]) for f in final):
            final.append(ch)
    final = [c for c in final if not (len(c["key"]) == 1 and CYR.match(c["form"]) and RU_ADJ.search(fold(c["form"])))]
    best = max((len(c["title"]) for c in final), default=0)
    return [c["form"] for c in final if len(c["title"]) >= min(2, best)]


def _event(cl: _Cluster, names: list[str]) -> str | None:
    lang = "ru" if cl.ru else "en"
    name_words = {_bare(w) for n in names for w in _tokens(n)}
    best, best_n = None, 1
    for titles_only in (True, False):
        for ev in EVENTS:
            if ev.get("cats") and cl.category not in ev["cats"]:
                continue
            trig = ev["t_" + lang]
            if any(_match(w, trig) for w in name_words):
                continue  # «Mercury Prize» уже говорит о премии
            n = 0
            for o in cl.owners:
                ts = [t for t in cl.texts if t.owner == o and (t.title or not titles_only)]
                ws = [_bare(w) for t in ts for w in t.words]
                joined = " ".join(ws)
                if any(_match(w, trig) for w in ws) or _phrase_hit(joined, trig):
                    n += 1
            if n > best_n:
                best, best_n = ev[lang], n
        if best:
            return best
    return None


def _unit(word: str) -> bool:
    f = fold(word)
    return _match(f, list(UNITS)) or any(f.startswith(m) for m in MONTHS_EN + MONTHS_RU) or f == "%"


def _numbers(cl: _Cluster, names: list[str]) -> list[str]:
    """Числа, которые есть минимум у двух источников, с единицей: «13 ноября», «$800 million», «982-й гол»."""
    per: dict[str, set[str]] = {}
    for t in cl.texts:
        for n in numbers(t.text):
            per.setdefault(n, set()).add(t.owner)
    shared = {n for n, who in per.items() if len(who) >= 2}
    in_names = set().union(*(numbers(n) for n in names)) if names else set()
    out: list[str] = []
    used: set[str] = set()
    for t in cl.texts:
        if not t.title:
            continue
        for m in NUMBER.finditer(t.text):
            val = next(iter(numbers(m.group(0))), None)
            if val not in shared or val in used or val in in_names:
                continue
            pre = t.text[max(0, m.start() - 1):m.start()]
            cur = pre if pre and pre in "$€£₽" else ""
            phrase = cur + m.group(0)
            tail = re.match(r"(-[а-яa-z]{1,3})?(\s?%)?(\s+([^\W\d_][\w\-]*))?(\s+(\d{4}))?", t.text[m.end():])
            ok = bool(cur)
            if tail.group(1):
                phrase += tail.group(1)
                ok = True
            if tail.group(2):
                phrase += "%"
                ok = True
            if tail.group(4) and _unit(tail.group(4)):
                word = tail.group(4)
                phrase += " " + (word if word[:1].isupper() and any(fold(word).startswith(mo) for mo in MONTHS_EN) else word.lower())
                ok = True
                year = tail.group(6)
                if year and any(fold(word).startswith(mo) for mo in MONTHS_EN + MONTHS_RU) and year in shared:
                    phrase += " " + year
                    used.add(year)
            if ok:
                out.append(phrase)
                used.add(val)
    return out


def line(cluster: dict) -> tuple[str | None, str]:
    """Строка для доски и пояснение, почему её нет."""
    r = summary(cluster)
    return r["text"], r["why"]


LABELS = {"en": ("Who", "What", "Numbers"), "ru": ("Кто", "Что", "Цифры")}


def summary(cluster: dict) -> dict:
    """Строка для доски, подробности для кнопки «Подробнее» и слова для поиска. Всё из общих фактов."""
    out = {"text": None, "why": "", "details": "", "search": ""}
    cl = _Cluster(cluster)
    if len(cl.owners) < 2:
        out["why"] = "один источник"
        return out
    names = _names(cl)
    if not names:
        out["why"] = "нет общих имён"
        return out
    event = _event(cl, names)
    nums = _numbers(cl, names)
    lang = "ru" if cl.ru else "en"
    out["search"] = " ".join(names[:3] + ([event] if event else []))
    who, what, num = LABELS[lang]
    rows = [f"{who}: {', '.join(names[:6])}"] + ([f"{what}: {event}"] if event else []) + \
        ([f"{num}: {', '.join(nums[:4])}"] if nums else [])
    # подробности нужны, только если в них есть то, что не влезло в строку
    if len(names) > MAX_NAMES or len(nums) > 2:
        out["details"] = "\n".join(rows)
    # порядок имён — как в заголовке, где общих имён больше всего
    titles = [t.text for t in cl.texts if t.title]
    lead = fold(max(titles, key=lambda t: sum(_bare(n.split()[0])[:4] in fold(t) for n in names)))

    def pos(n: str) -> int:
        i = lead.find(_bare(n.split()[0])[:4])
        return i if i >= 0 else 999
    names = sorted(names, key=pos)[:MAX_NAMES]
    if event and any(_same_word(w, x) or fold(x).startswith(fold(w)) for p in nums for x in re.findall(r"\w+", p)
                     for w in event.split()):
        event = None  # «982-й гол» уже говорит, что был гол
    parts = names + ([event] if event else []) + nums[:2]
    while len(SEP.join(parts)) > MAX_LEN and len(parts) > 2:
        parts.pop()
    if len(parts) < 2:
        out["why"] = "мало общих фактов"
        return out
    text = SEP.join(parts)
    if len(text) > MAX_LEN:
        out["why"] = "длинно"
        return out
    out["text"] = text
    return out


class FactsRewriter:
    """Без модели: строка из общих фактов. История выходит только на языке заметок."""

    model = "facts"
    usage = {"input": 0, "output": 0, "calls": 0}

    def rewrite(self, clusters: list[dict]) -> list[dict]:
        out = []
        for c in clusters:
            text, why = line(c)
            out.append({"id": c["id"], "allow": True, "mode": "facts", "category": c["category"],
                        "audience": c["lang"], "en": text if c["lang"] == "en" else "",
                        "ru": text if c["lang"] == "ru" else "", "reason": why})
        return out
