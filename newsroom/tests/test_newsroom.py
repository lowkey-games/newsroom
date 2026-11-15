"""Проверки редакции без сети и без ключа: python -m unittest discover -s tests (из папки newsroom)."""
from __future__ import annotations

import glob
import http.server
import json
import os
import sys
import tempfile
import threading
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from newsroom import checks, dedup, facts, publish, store  # noqa: E402
from newsroom.parse import Item, parse_feed, parse_gnews, parse_telegram  # noqa: E402
from newsroom.run import apply_rewrites, make_rewriter, run_once  # noqa: E402
from newsroom.safety import Safety  # noqa: E402
from newsroom.text import numbers, words  # noqa: E402

GAME_FIXTURES = os.path.join(os.path.dirname(os.path.dirname(HERE)), "tests", "fixtures")
NOW = 1792800000.0


class TextTests(unittest.TestCase):
    def test_words(self):
        self.assertEqual(words("Ronaldo’s last game, Ёлка!"), ["ronaldo", "last", "game", "елка"])
        self.assertEqual(words("Mbappé scores"), ["mbappe", "scores"])

    def test_numbers(self):
        self.assertEqual(numbers("after 22 years, $1,000 and 2,5 млн"), {"22", "1000", "2.5"})
        self.assertEqual(numbers("1 000 человек"), {"1000"})
        self.assertEqual(numbers("starts January 13, 2027"), {"13", "2027"})
        self.assertEqual(numbers("стартует 13 января 2027 года"), {"13", "2027"})

    def test_skeleton(self):
        same = [("Elijah Wood", "Элайджа Вуд"), ("Kylian Mbappe", "Килиан Мбаппе"), ("Chelsea", "Челси"),
                ("Tottenham", "Тоттенхэм"), ("Barcelona", "Барселоной"), ("Michael Jackson", "Майкл Джексон"),
                ("Shakhtar", "Шахтёр"), ("Manchester United", "Манчестер Юнайтед"), ("Реалу", "Real Madrid"),
                ("Роналду", "Cristiano Ronaldo")]
        for a, b in same:
            self.assertTrue(checks.same_name(a, b), (a, b))
        self.assertFalse(checks.same_name("Elya Vild", "Элайджа Вуд"))
        self.assertFalse(checks.same_name("Lord of the Rings", "Властелин колец"))
        self.assertFalse(checks.same_name("Luis Ronaldo", "Криштиану Роналду"))
        self.assertTrue(checks.same_name("Petr Yan", "чемпион UFC Петр Ян в пятый раз"))


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.s = Safety()

    def test_blocks_like_game(self):
        self.assertEqual(self.s.check("Trump visits Iowa")[0], "politics")
        self.assertEqual(self.s.check("Actor dies at 93")[0], "violence")
        self.assertEqual(self.s.check("Погиб водитель")[0], "ru")
        self.assertIsNone(self.s.check("Arsenal win the penalty shootout"))
        self.assertIsNone(self.s.check("Real Madrid beat Barcelona in El Clasico"))


class ParseTests(unittest.TestCase):
    def test_rss_fixtures(self):
        for path in glob.glob(os.path.join(GAME_FIXTURES, "*.xml")):
            with open(path, encoding="utf-8", errors="replace") as f:
                body = f.read()
            items = parse_feed(body, "x")
            if os.path.getsize(path) > 1000:
                self.assertTrue(items, os.path.basename(path))
                self.assertTrue(all(i.title for i in items[:5]), os.path.basename(path))

    def test_telegram(self):
        # своя страница той же разметки, что у t.me/s/<канал>: чужих постов в репозитории не держим
        with open(os.path.join(HERE, "fixtures", "tg_sample.html"), encoding="utf-8") as f:
            page = f.read()
        items = parse_telegram(page, "tg")
        self.assertEqual(len(items), 12)  # пост без текста (только фото) пропущен
        self.assertEqual(items[0].title, "Новая консоль покажется на выставке в ноябре")
        self.assertEqual(items[0].summary, "Компания подтвердила дату презентации.")
        self.assertEqual(items[1].summary, "Подробности:")
        self.assertTrue(items[2].title.endswith("кадры уже на следующей неделе."), items[2].title)
        self.assertEqual(items[0].link, "https://t.me/sample/101")
        for it in items:
            self.assertTrue(it.published > 0)
            self.assertNotIn("http", it.title)
            self.assertLessEqual(len(it.title), 160)

    def test_gnews(self):
        body = json.dumps({"articles": [{"title": "Kane &amp; Bayern win", "url": "u", "publishedAt": "2026-10-22T15:56:36Z",
                                         "source": {"name": "Sky Sports"}}, {"title": 5}]})
        items = parse_gnews(body, "gn")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "Kane & Bayern win")
        self.assertEqual(items[0].outlet, "Sky Sports")


def item(source, title, summary="", age=600):
    return Item(source=source, title=title, summary=summary, published=NOW - age)


SOURCES = {
    "a": {"id": "a", "kind": "rss", "category": "football", "lang": "en", "type": "outlet", "owner": "bbc"},
    "a2": {"id": "a2", "kind": "rss", "category": "sport", "lang": "en", "type": "outlet", "owner": "bbc"},
    "b": {"id": "b", "kind": "rss", "category": "football", "lang": "en", "type": "outlet", "owner": "sky"},
    "t1": {"id": "t1", "kind": "telegram", "category": "games", "lang": "en", "type": "social", "owner": "chan1"},
    "t2": {"id": "t2", "kind": "telegram", "category": "games", "lang": "en", "type": "social", "owner": "chan2"},
    "r": {"id": "r", "kind": "rss", "category": "football", "lang": "ru", "type": "outlet", "owner": "se"},
}


class StoreTests(unittest.TestCase):
    def test_cluster_and_trust(self):
        st = {"clusters": {}, "feeds": {}, "seen": {}}
        store.ingest(st, [item("a", "Mbappe scores twice as Real Madrid beat Barcelona")], SOURCES, Safety(), NOW)
        self.assertEqual(len(st["clusters"]), 1)
        c = next(iter(st["clusters"].values()))
        self.assertIsNone(store.trust(c), "один источник — эксклюзив, на доску нельзя")
        # то же издание другой лентой не добавляет независимости
        store.ingest(st, [item("a2", "Real Madrid beat Barcelona as Mbappe scores twice")], SOURCES, Safety(), NOW)
        self.assertIsNone(store.trust(c))
        store.ingest(st, [item("b", "Mbappe double gives Real Madrid win over Barcelona")], SOURCES, Safety(), NOW)
        self.assertEqual(len(st["clusters"]), 1)
        self.assertEqual(store.trust(c), "media")
        self.assertEqual(store.counts(c), (2, 0))

    def test_rumor_only_from_channels(self):
        st = {"clusters": {}, "feeds": {}, "seen": {}}
        store.ingest(st, [item("t1", "Insider says Half-Life 3 trailer comes next month"),
                          item("t2", "Half-Life 3 trailer next month, insider claims")], SOURCES, Safety(), NOW)
        c = next(iter(st["clusters"].values()))
        self.assertEqual(store.trust(c), "rumor")

    def test_old_and_stop(self):
        st = {"clusters": {}, "feeds": {}, "seen": {}}
        stats = store.ingest(st, [item("a", "Old match report from two days ago here", age=3 * 86400),
                                  item("b", "Footballer arrested after night out in town")], SOURCES, Safety(), NOW)
        self.assertEqual(stats["old"], 1)
        self.assertEqual(stats["stop"], 1)
        self.assertEqual(st["clusters"], {})


class CheckTests(unittest.TestCase):
    titles = ["Ronaldo leaves Portugal national team after 22 years", "Cristiano Ronaldo retires from international football"]
    text = " ".join(titles) + " Ronaldo, 41, played 22 years for Portugal."

    def test_good(self):
        self.assertIsNone(checks.check("Ronaldo ends his Portugal career after 22 years", "en", self.titles, self.text, True))
        self.assertIsNone(checks.check("Роналду завершил карьеру в сборной Португалии после 22 лет", "ru", self.titles, self.text, False))

    def test_new_number(self):
        self.assertIn("числа", checks.check("Ronaldo ends his Portugal career after 23 years", "en", self.titles, self.text, True))

    def test_new_name(self):
        self.assertIn("имя", checks.check("Ronaldo ends his Portugal career, Messi reacts", "en", self.titles, self.text, True))

    def test_copy(self):
        self.assertIsNotNone(checks.check("Ronaldo leaves Portugal national team after 22 years", "en", self.titles, self.text, True))

    def test_names(self):
        ok = [{"source": "Ronaldo", "en": "Ronaldo", "ru": "Роналду"}, {"source": "Portugal", "en": "Portugal", "ru": "Португалии"}]
        ru = "Роналду завершил карьеру в сборной Португалии после 22 лет"
        self.assertIsNone(checks.check_names(ok, "ru", ru, self.text, False))
        invented = ok + [{"source": "Elijah Wood", "en": "Elijah Wood", "ru": "Элайджа Вуд"}]
        self.assertIn("не сходится", checks.check_names(invented, "ru", ru, self.text, False))
        wrong = [{"source": "Ronaldo", "en": "Ronaldo", "ru": "Роберто"}]
        self.assertIn("не сходится", checks.check_names(wrong, "ru", "Роберто завершил карьеру в сборной", self.text, False))
        league = [{"source": "Лиге чемпионов", "en": "Champions League", "ru": "Лиге чемпионов"}]
        self.assertIsNone(checks.check_names(league, "en", "Daku wants to play in the Champions League",
                                             "Даку хочет сыграть в Лиге чемпионов", False))
        self.assertIn("не из списка", checks.check_names(ok[:1], "ru", ru, self.text, False))
        extra = [{"source": "Ronaldo", "en": "Cristiano Ronaldo", "ru": "Роналду"}]
        self.assertIsNone(checks.check_names(extra, "en", "Cristiano Ronaldo retires", self.text, True))
        extra = [{"source": "Ronaldo", "en": "Luis Ronaldo", "ru": "Роналду"}]
        self.assertIn("нет в заметках", checks.check_names(extra, "en", "Luis Ronaldo retires", self.text, True))

    def test_style(self):
        self.assertIsNotNone(checks.check("Ronaldo quits Portugal!", "en", self.titles, self.text, True))


class PublishTests(unittest.TestCase):
    def test_editions_and_no_outlet_names(self):
        st = {"clusters": {}, "feeds": {}, "seen": {}}
        store.ingest(st, [item("a", "Mbappe scores twice as Real Madrid beat Barcelona"),
                          item("b", "Mbappe double gives Real Madrid win over Barcelona")], SOURCES, Safety(), NOW)
        c = next(iter(st["clusters"].values()))
        apply_rewrites(st, [c], [{"id": c["id"], "allow": True, "reason": "", "category": "football", "audience": "global",
                                  "en": "Two Mbappe goals give Real Madrid the win against Barcelona",
                                  "ru": "Два гола Мбаппе принесли «Реалу» победу над «Барселоной»", "names": [{"source": "Mbappe", "en": "Mbappe", "ru": "Мбаппе"},
                                            {"source": "Real Madrid", "en": "Real Madrid", "ru": "Реалу"},
                                            {"source": "Barcelona", "en": "Barcelona", "ru": "Барселоной"}]}], NOW, "test")
        self.assertEqual(c["rewrite"]["status"], "ok", c["rewrite"])
        en = publish.edition_stories(st, "EN", NOW)
        ru = publish.edition_stories(st, "RU", NOW)
        self.assertEqual(len(en), 1)
        self.assertEqual(ru[0]["title"], "Два гола Мбаппе принесли «Реалу» победу над «Барселоной»")
        self.assertEqual(set(en[0]), {"id", "title", "category", "outlets", "social", "trust", "published", "mode", "fake",
                                      "details", "search", "topic"})
        self.assertEqual(en[0]["search"], "Mbappe Real Madrid Barcelona")
        self.assertEqual(en[0]["mode"], "ai")


class OneEditionTests(unittest.TestCase):
    def test_bad_translation_drops_only_that_edition(self):
        st = {"clusters": {}, "feeds": {}, "seen": {}}
        store.ingest(st, [item("a", "Mbappe scores twice as Real Madrid beat Barcelona"),
                          item("b", "Mbappe double gives Real Madrid win over Barcelona")], SOURCES, Safety(), NOW)
        c = next(iter(st["clusters"].values()))
        stats = apply_rewrites(st, [c], [{"id": c["id"], "allow": True, "reason": "", "category": "football", "audience": "global",
                                          "en": "Two Mbappe goals give Real Madrid the win against Barcelona",
                                          "ru": "Два гола Мапе принесли «Реалу» победу над «Барселоной»",
                                          "names": [{"source": "Mbappe", "en": "Mbappe", "ru": "Мапе"}]}], NOW, "test")
        self.assertEqual(stats["one_edition"], 1)
        self.assertEqual(len(publish.edition_stories(st, "EN", NOW)), 1)
        self.assertEqual(publish.edition_stories(st, "RU", NOW), [])


def cluster(lang, category, *pairs):
    """История из заметок разных владельцев: (владелец, заголовок, подводка)."""
    return {"id": "x1", "lang": lang, "category": category,
            "items": [{"owner": o, "source": o, "title": t, "summary": sm, "published": NOW - 100 * i, "type": "outlet"}
                      for i, (o, t, sm) in enumerate(pairs)]}


class FactsTests(unittest.TestCase):
    """Строка без ИИ: только общие для двух источников имена, событие и числа."""

    def test_closure_with_date(self):
        c = cluster("ru", "games",
                    ("a", "Студии Arkane дали время до 13 ноября, потом её закроют", "Владелец ищет покупателя для Arkane."),
                    ("b", "Arkane могут закрыть, если до 13 ноября не найдётся покупатель", ""))
        self.assertEqual(facts.line(c)[0], "Arkane · закрытие · 13 ноября")

    def test_titlecase_and_money(self):
        c = cluster("en", "games",
                    ("a", "Xbox Reportedly Wanted $800 Million From Netflix For Movie Rights", "Xbox and Netflix talked."),
                    ("b", "Xbox asked Netflix for $800 million in exchange for film rights, report says", ""))
        text = facts.line(c)[0]
        for part in ("Xbox", "Netflix", "$800 million"):
            self.assertIn(part, text)
        self.assertNotIn("Reportedly", text)

    def test_cases_merge_and_fixed_names(self):
        c = cluster("ru", "football",
                    ("a", "Нападающий «Спартака» мечтает сыграть в Лиге чемпионов", ""),
                    ("b", "«Спартак» снова не попал в Лигу чемпионов", ""))
        self.assertEqual(facts.line(c)[0], "Спартак · Лига чемпионов")

    def test_ordinal_goal(self):
        c = cluster("ru", "football",
                    ("a", "Роналду забил 982-й гол за карьеру", ""),
                    ("b", "У Роналду теперь 982 гола: последний он забил головой", ""))
        self.assertIn(facts.line(c)[0], ("Роналду · 982-й гол", "Роналду · 982 гола"))  # без «гол · 982 гола»

    def test_shouting_is_not_a_name(self):
        c = cluster("en", "stars",
                    ("a", "Raye wins the Mercury Prize for her second album", ""),
                    ("b", "Delighted Raye WINS the Mercury Prize at the London ceremony", ""))
        text = facts.line(c)[0]
        self.assertTrue(text.startswith("Raye · Mercury Prize"), text)
        self.assertNotIn("WINS", text)

    def test_music(self):
        c = cluster("en", "music",
                    ("a", "Drake announces release date for new album Iceman", ""),
                    ("b", "Iceman, the next Drake album, arrives in November", ""))
        r = facts.summary(c)
        self.assertIn("Drake", r["text"])
        self.assertIn("new album", r["text"])
        self.assertIn("Drake", r["search"])

    def test_details_check(self):
        titles = ["Arkane has until November 13 to find a buyer or the studio closes"]
        text = titles[0] + " The owner is looking for a buyer for the Lyon team that made Dishonored."
        self.assertIsNone(checks.check_details("", "en", titles, text, True))
        self.assertIsNone(checks.check_details("The Lyon team behind Dishonored needs a new owner before November 13",
                                               "en", titles, text, True))
        self.assertIn("пять слов", checks.check_details("Arkane has until November 13 to find a buyer, says the report",
                                                         "en", titles, text, True))
        self.assertIn("числа", checks.check_details("The Lyon team behind Dishonored needs a new owner before November 20",
                                                    "en", titles, text, True))

    def test_not_enough(self):
        self.assertIsNone(facts.line(cluster("en", "games", ("a", "Big Game Studio Ships Update", "")))[0])
        c = cluster("ru", "games", ("a", "Обновление вышло вчера вечером", ""), ("b", "Вечером вышло новое обновление", ""))
        self.assertIsNone(facts.line(c)[0])

    def test_facts_mode_end_to_end(self):
        for k in [k for k in os.environ if k.startswith(("NEWSROOM_", "CLOUDFLARE_")) or k.endswith("_API_KEY")]:
            os.environ.pop(k, None)
        self.assertIsInstance(make_rewriter(), facts.FactsRewriter)
        with tempfile.TemporaryDirectory() as tmp:
            src_path = os.path.join(tmp, "sources.json")
            with open(src_path, "w") as f:
                json.dump({"sources": list(SOURCES.values())}, f)
            items = [item("a", "Mbappe scores twice as Real Madrid beat Barcelona"),
                     item("b", "Mbappe double gives Real Madrid win over Barcelona")]
            report = run_once(os.path.join(tmp, "state.json"), os.path.join(tmp, "out"), sources_path=src_path,
                              items=items, now=NOW)
            self.assertEqual(report["rewriter"], "facts")
            with open(os.path.join(tmp, "out", "stories-en.json"), encoding="utf-8") as f:
                en = json.load(f)["stories"]
            with open(os.path.join(tmp, "out", "stories-ru.json"), encoding="utf-8") as f:
                ru = json.load(f)["stories"]
        self.assertEqual(len(en), 1)
        self.assertEqual(en[0]["mode"], "facts")
        self.assertIn("Mbappe", en[0]["title"])
        self.assertEqual(ru, [])  # перевода нет: английская история только в английской версии

    def test_bad_model_text_falls_back_to_facts(self):
        st = {"clusters": {}, "feeds": {}, "seen": {}}
        store.ingest(st, [item("a", "Mbappe scores twice as Real Madrid beat Barcelona"),
                          item("b", "Mbappe double gives Real Madrid win over Barcelona")], SOURCES, Safety(), NOW)
        c = next(iter(st["clusters"].values()))
        stats = apply_rewrites(st, [c], [{"id": c["id"], "allow": True, "category": "football", "audience": "global",
                                          "en": "Mbappe scores twice as Real Madrid beat Barcelona",
                                          "ru": "Мбаппе забил дважды", "names": []}], NOW, "test")
        self.assertEqual(stats["facts"], 1)
        self.assertEqual(c["rewrite"]["mode"], "facts")
        self.assertTrue(c["rewrite"]["ai_failed"])
        self.assertIn("Mbappe", c["rewrite"]["en"])


class TopicsTests(unittest.TestCase):
    """Словарь видов спорта общий с игрой (src/shared/Topics.luau)."""

    def test_topics(self):
        from newsroom import topics
        self.assertEqual(topics.of("sport", "Ovechkin scores twice as Capitals win in NHL"), ("sport", "hockey"))
        self.assertEqual(topics.of("sport", "Верстаппен выиграл Гран-при Бразилии"), ("sport", "motor"))
        self.assertEqual(topics.of("sport", "Дзюба забил в матче РПЛ"), ("football", None))
        self.assertEqual(topics.of("sport", "Olympic swimmer breaks world record"), ("sport", "other"))
        self.assertEqual(topics.of("games", "New NHL game announced"), ("games", None))
        self.assertIn("golf", topics.SUBS["sport"])


class FakeCloudflare(http.server.BaseHTTPRequestHandler):
    """Подмена Workers AI: запоминает запрос и отвечает пересказом."""
    last: dict = {}

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeCloudflare.last = {"path": self.path, "body": body, "auth": self.headers.get("Authorization")}
        clusters = json.loads(body["messages"][1]["content"])["clusters"]
        stories = [{"id": c["id"], "allow": True, "reason": "", "category": "football", "audience": "global",
                    "en": "Two Mbappe goals give Real Madrid the win against Barcelona",
                    "ru": "Два гола Мбаппе принесли «Реалу» победу над «Барселоной»",
                    "names": [{"source": "Mbappe", "en": "Mbappe", "ru": "Мбаппе"},
                              {"source": "Real Madrid", "en": "Real Madrid", "ru": "Реалу"},
                              {"source": "Barcelona", "en": "Barcelona", "ru": "Барселоной"}]} for c in clusters]
        out = {"result": {"response": {"stories": stories}, "usage": {"prompt_tokens": 2000, "completion_tokens": 300}},
               "success": True}
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


class CloudflareTests(unittest.TestCase):
    def run_with(self, limit):
        srv = http.server.HTTPServer(("127.0.0.1", 0), FakeCloudflare)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        env = {"CLOUDFLARE_API_BASE": f"http://127.0.0.1:{srv.server_port}", "CLOUDFLARE_ACCOUNT_ID": "acc",
               "CLOUDFLARE_API_TOKEN": "tok", "NEWSROOM_NEURONS_PER_DAY": str(limit), "NEWSROOM_REWRITER": ""}
        old = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                src_path = os.path.join(tmp, "sources.json")
                with open(src_path, "w") as f:
                    json.dump({"sources": list(SOURCES.values())}, f)
                items = [item("a", "Mbappe scores twice as Real Madrid beat Barcelona"),
                         item("b", "Mbappe double gives Real Madrid win over Barcelona")]
                state_path = os.path.join(tmp, "state.json")
                report = run_once(state_path, os.path.join(tmp, "out"), sources_path=src_path, items=items, now=NOW)
                with open(os.path.join(tmp, "out", "stories-ru.json"), encoding="utf-8") as f:
                    ru = json.load(f)["stories"]
                with open(os.path.join(tmp, "out", "stories-en.json"), encoding="utf-8") as f:
                    en = json.load(f)["stories"]
                with open(state_path, encoding="utf-8") as f:
                    budget = json.load(f).get("budget")
        finally:
            srv.shutdown()
            srv.server_close()
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        return report, en, ru, budget

    def test_free_model_and_budget(self):
        report, en, ru, budget = self.run_with(9000)
        self.assertEqual(report["rewriter"], "@cf/meta/llama-3.3-70b-instruct-fp8-fast")
        self.assertIn("/accounts/acc/ai/run/@cf/meta/llama-3.3-70b-instruct-fp8-fast", FakeCloudflare.last["path"])
        self.assertEqual(FakeCloudflare.last["auth"], "Bearer tok")
        self.assertEqual(FakeCloudflare.last["body"]["response_format"]["type"], "json_schema")
        self.assertEqual(ru[0]["mode"], "ai")
        self.assertGreater(budget["neurons"], 100)  # 2000 и 300 токенов ≈ 115 нейронов

    def test_out_of_budget_uses_facts(self):
        report, en, ru, budget = self.run_with(1)
        self.assertIn("OutOfBudget", report["model_stopped"])
        self.assertEqual(en[0]["mode"], "facts")
        self.assertEqual(ru, [])


if __name__ == "__main__":
    unittest.main()
