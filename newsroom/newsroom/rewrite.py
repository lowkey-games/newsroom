"""Инструкция и схема ответа для пересказа историй моделью. Одна пачка историй за запрос, ответ строго по JSON-схеме.

Модель решает три вещи: можно ли показывать историю, как её пересказать своими словами (по-английски
и по-русски) и кому она интересна. Проверка пересказа кодом — в checks.py.
"""
from __future__ import annotations

import json

CATEGORIES = ["football", "sport", "games", "tech", "stars", "music", "fashion", "science", "weird"]

SYSTEM = """You are the copy desk of a Roblox game where players watch a big board with fresh news.
Teenagers and streamers read it aloud. You get story clusters: several short reports about one event
from different outlets or social channels. For every cluster return one entry.

Decide "allow". Set it to false when the cluster involves any of: politicians, governments, elections,
political parties, royals, officials, wars, armies, terrorism, crime, police, courts, lawsuits, prisons,
death or dying, serious illness, injuries from accidents, disasters, violence, weapons, drugs, alcohol,
smoking, gambling or betting, sex, nudity, bodies or dieting, dating scandals, divorce, religion, race,
immigration, protests, money troubles of real people, layoffs, or anything sad, scary, cruel, hateful
or controversial. Also false when the reports are not news (ads, deals, quizzes, opinion columns,
reviews, live blogs, newsletters) or when they describe different events. When unsure, false.
Light news is welcome: results, transfers and records in sport, video games, gadgets and apps, films,
TV and music releases, celebrities' work and fashion, science, space, animals, food and harmless
curiosities.

When allowed, write the headline twice: "en" in English and "ru" in Russian.
- State only facts that appear in the reports. If reports disagree, keep only what they agree on.
  Never add a name, number, date, place or detail that is not in the reports.
- Use your own words. Do not reuse the wording of any report and do not quote anyone.
- One neutral sentence, 6 to 12 words, at most 90 characters. No opinion, no clickbait, no question
  marks, no exclamation marks, no emojis, no period at the end.
- Keep names of people, clubs, games and products exactly as in the reports; in Russian use the
  usual Russian spelling of foreign names.
- If every report in the cluster comes from social channels (type "social"), the news is unconfirmed:
  say so in the wording ("reportedly", "is said to", "по данным инсайдеров", "по слухам").

Then write "details_en" and "details_ru" for viewers who tap "more": one or two short sentences, at most
220 characters, with the most useful facts from the reports that the headline left out (who, what, when,
where, numbers). Same rules as the headline: only facts from the reports, your own words, no quotes, no
opinion. Leave them empty when the reports have nothing more to add.

Also return "category" (the best fit for the event), "audience" ("global" when players in both
English- and Russian-speaking countries would care, "en" for mostly UK/US interest, "ru" for mostly
Russia/CIS interest) and "names": every name of a person, team, club, company, game, show or product
in your headlines, each as {"source": exactly as written in a report, "en": as in your English
headline, "ru": as in your Russian headline}. Transliterate foreign names carefully; when unsure how a
name is written in the other language, keep the original spelling.
When allow is false, leave "en", "ru" and the details empty and put a short reason in "reason"."""

SCHEMA = {
    "type": "object",
    "properties": {
        "stories": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "allow": {"type": "boolean"},
                    "reason": {"type": "string"},
                    "category": {"type": "string", "enum": CATEGORIES},
                    "audience": {"type": "string", "enum": ["global", "en", "ru"]},
                    "en": {"type": "string"},
                    "ru": {"type": "string"},
                    "details_en": {"type": "string"},
                    "details_ru": {"type": "string"},
                    "names": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"source": {"type": "string"}, "en": {"type": "string"}, "ru": {"type": "string"}},
                            "required": ["source", "en", "ru"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["id", "allow", "reason", "category", "audience", "en", "ru", "details_en", "details_ru", "names"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["stories"],
    "additionalProperties": False,
}


def batch_payload(clusters: list[dict]) -> str:
    """Что видит модель: истории без служебных полей, у каждой заметки тип источника."""
    data = []
    for c in clusters:
        data.append({
            "id": c["id"],
            "category_hint": c["category"],
            "reports": [
                {"type": e["type"], "title": e["title"], "text": e["summary"][:300]}
                for e in c["items"][:6]
            ],
        })
    return json.dumps({"clusters": data}, ensure_ascii=False)


class Refused(Exception):
    pass


class FakeRewriter:
    """Для проверок без ключа: берёт первый заголовок как есть и помечает пересказ поддельным."""

    usage = {"input": 0, "output": 0, "calls": 0}

    def rewrite(self, clusters: list[dict]) -> list[dict]:
        out = []
        for c in clusters:
            title = c["items"][0]["title"][:90]
            out.append({
                "id": c["id"], "allow": True, "reason": "", "category": c["category"], "audience": "global",
                "en": title if c["lang"] == "en" else "[ru] " + title,
                "ru": title if c["lang"] == "ru" else "[en] " + title,
                "names": [], "fake": True,
            })
        return out
