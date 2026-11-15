"""Один проход редакции: собрать, склеить, пересказать новое, проверить, записать файлы для игры."""
from __future__ import annotations

import json
import os
import time

from . import checks, facts, publish, store
from .fetch import fetch_all
from .rewrite import FakeRewriter, Refused
from .safety import Safety

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_sources(path: str | None = None) -> list[dict]:
    with open(path or os.path.join(HERE, "sources.json"), encoding="utf-8") as f:
        return [s for s in json.load(f)["sources"] if s.get("enabled", True)]


def _paid():
    """Платный режим лежит в отдельном модуле paid.py, в публичной копии его нет"""
    try:
        from . import paid
    except ImportError:
        return None
    return paid


def make_rewriter(fake: bool = False):
    """Кто пишет текст: NEWSROOM_REWRITER = cloudflare | paid | facts. Без переменной — по ключам:
    есть Cloudflare — он (бесплатно), есть ключ платной модели — она, иначе строка из фактов без ИИ."""
    if fake:
        return FakeRewriter()
    mode = (os.environ.get("NEWSROOM_REWRITER") or "").strip().lower()
    paid = _paid()
    if not mode:
        mode = "cloudflare" if os.environ.get("CLOUDFLARE_API_TOKEN") else \
            "paid" if paid and paid.available() else "facts"
    if mode == "cloudflare" and os.environ.get("CLOUDFLARE_API_TOKEN") and os.environ.get("CLOUDFLARE_ACCOUNT_ID"):
        from .cloudflare import CloudflareRewriter
        return CloudflareRewriter()
    if mode == "paid" and paid and paid.available():
        return paid.make()
    return facts.FactsRewriter()  # режим без ключа тоже сюда: доска не остаётся пустой


def facts_rewrite(c: dict, now: float, attempts: int, note: str = "") -> bool:
    """Строка из общих фактов вместо пересказа. True, если получилась."""
    r = facts.summary(c)
    text = r["text"]
    if not text:
        c["rewrite"] = {"status": "failed", "mode": "facts", "reason": (note + "; " if note else "") + r["why"],
                        "attempts": attempts, "at": now}
        return False
    lang = c["lang"]
    other = "ru" if lang == "en" else "en"
    c["rewrite"] = {"status": "ok", "mode": "facts", lang: text, other: "", "details_" + lang: r["details"],
                    "details_" + other: "", "search_" + lang: r["search"], "search_" + other: "",
                    "category": c["category"], "audience": lang, "attempts": attempts, "at": now, "model": "facts"}
    if note:
        c["rewrite"]["ai_failed"] = note
    return True


def refresh_facts(state: dict, now: float) -> dict:
    """Строки из фактов пересчитываем каждый проход: пришёл новый источник — строка точнее."""
    stats = {"ok": 0, "failed": 0}
    for c in state["clusters"].values():
        if now - c["published"] > store.MAX_AGE or not store.trust(c, now):
            continue
        rw = c.get("rewrite") or {}
        if rw.get("status") == "blocked" or (rw.get("status") == "ok" and rw.get("mode") != "facts"):
            continue
        # пока модель не справилась (или её нет), на доске строка из фактов
        note = rw.get("ai_failed") or ("" if rw.get("mode") == "facts" else rw.get("reason", ""))
        ok = facts_rewrite(c, now, rw.get("attempts", 0), note)
        if ok and rw.get("draft"):
            c["rewrite"]["draft"] = rw["draft"]
        stats["ok" if ok else "failed"] += 1
    return stats


def apply_rewrites(state: dict, clusters: list[dict], results: list[dict], now: float, model: str) -> dict:
    stats = {"ok": 0, "blocked": 0, "failed": 0, "one_edition": 0, "facts": 0}
    by_id = {r.get("id"): r for r in results}
    for c in clusters:
        r = by_id.get(c["id"])
        prev = c.get("rewrite") or {}
        attempts = prev.get("attempts", 0) + 1
        if r and r.get("mode") == "facts":
            ok = facts_rewrite(c, now, attempts)
            stats["facts" if ok else "failed"] += 1
            continue
        if not r:
            c["rewrite"] = {"status": "failed", "reason": "нет ответа модели", "attempts": attempts, "at": now}
            stats["failed"] += 1
            continue
        if not r.get("allow"):
            c["rewrite"] = {"status": "blocked", "reason": r.get("reason", ""), "attempts": attempts, "at": now, "model": model}
            stats["blocked"] += 1
            continue
        titles = [e["title"] for e in c["items"]]
        text = " \n".join(e["title"] + " " + e["summary"] for e in c["items"])
        problems = {}
        if not r.get("fake"):
            for lang in ("en", "ru"):
                same = lang == c["lang"]
                p = (checks.check(r.get(lang, ""), lang, titles, text, same_lang=same)
                     or checks.check_names(r.get("names"), lang, r.get(lang, ""), text, same_lang=same))
                if p:
                    problems[lang] = p
        # пересказ на языке заметок обязателен; перевод с ошибкой в имени убирает историю только из второй версии
        problem = next((f"{lang}: {p}" for lang, p in problems.items() if lang == c["lang"] or len(problems) == 2), None)
        if problem:
            # модель решила, что историю показывать можно, но текст не прошёл проверку: строка из фактов
            if facts_rewrite(c, now, attempts, problem):
                c["rewrite"]["draft"] = {"en": r.get("en"), "ru": r.get("ru"), "model": model}
                stats["facts"] += 1
            else:
                c["rewrite"].update(model=model, draft={"en": r.get("en"), "ru": r.get("ru")})
                stats["failed"] += 1
            continue
        # подробности: не прошли проверку — история выходит без них
        details = {}
        for lang in ("en", "ru"):
            d = (r.get("details_" + lang) or "").strip()
            if d and not r.get("fake"):
                same = lang == c["lang"]
                if checks.check_details(d, lang, titles, text, same) or \
                        checks.check_names(r.get("names"), lang, d, text, same_lang=same):
                    d = ""
            details["details_" + lang] = d
            details["search_" + lang] = " ".join(
                (n.get(lang) or "").strip() for n in (r.get("names") or [])[:3] if isinstance(n, dict) and n.get(lang))
        c["rewrite"] = {
            **details,
            "status": "ok", "mode": "fake" if r.get("fake") else "ai",
            "en": r["en"].strip().rstrip("."), "ru": r["ru"].strip().rstrip("."),
            "category": r.get("category") or c["category"], "audience": r.get("audience", "global"),
            "attempts": attempts, "at": now, "model": model, "fake": bool(r.get("fake")),
        }
        for lang, p in problems.items():
            c["rewrite"][lang] = ""
            c["rewrite"]["dropped"] = {"lang": lang, "reason": p, "draft": r.get(lang)}
            stats["one_edition"] += 1
        stats["ok"] += 1
    return stats


def run_once(state_path: str, out_dir: str, fake: bool = False, max_rewrites: int = 40, batch: int = 10,
             sources_path: str | None = None, items=None, now: float | None = None, rewriter=None) -> dict:
    now = now or time.time()
    sources = load_sources(sources_path)
    by_id = {s["id"]: s for s in sources}
    state = store.load(state_path)
    if items is None:
        items, state["feeds"] = fetch_all(sources, state.get("feeds", {}))
    ingest = store.ingest(state, items, by_id, Safety(), now)
    rw = rewriter or make_rewriter(fake)
    if hasattr(rw, "budget"):
        rw.budget = state.setdefault("budget", {})
    model = getattr(rw, "model", "fake")
    totals = {"ok": 0, "blocked": 0, "failed": 0, "one_edition": 0, "facts": 0}
    todo = [] if isinstance(rw, facts.FactsRewriter) else store.pending(state, now, max_rewrites)
    stopped = None
    for i in range(0, len(todo), batch):
        part = todo[i:i + batch]
        try:
            results = rw.rewrite(part)
        except Refused:
            # пачку отклонили целиком: по одной, чтобы не потерять безобидные истории
            results = []
            for c in part:
                try:
                    results.extend(rw.rewrite([c]))
                except Refused as e:
                    results.append({"id": c["id"], "allow": False, "reason": f"отказ модели: {e}"})
        except Exception as e:  # лимит, сеть, ответ не по схеме: остальное в этот проход — строкой из фактов
            stopped = f"{type(e).__name__}: {str(e)[:160]}"
            break
        st = apply_rewrites(state, part, results, now, model)
        for k in totals:
            totals[k] += st[k]
    if stopped:
        for c in todo[i:]:
            prev = c.get("rewrite") or {}
            if facts_rewrite(c, now, prev.get("attempts", 0), "модель недоступна"):
                totals["facts"] += 1
    refreshed = refresh_facts(state, now)
    written = publish.write(state, out_dir, now)
    store.save(state, state_path)
    feeds_ok = sum(1 for f in state["feeds"].values() if f.get("status") in ("200", "304"))
    report = {
        "items": len(items), "ingest": ingest, "rewriter": model, "rewrite": totals, "facts": refreshed,
        "pending": len(todo), "feeds": f"{feeds_ok}/{len(state['feeds'])}", "written": written,
        "usage": getattr(rw, "usage", {}),
    }
    if stopped:
        report["model_stopped"] = stopped
    return report
