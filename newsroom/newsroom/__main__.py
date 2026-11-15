"""Запуск редакции.

  python -m newsroom run [--fake] [--state state/newsroom.json] [--out public]
      один проход: собрать ленты и каналы, написать текст о новых историях, записать файлы
  python -m newsroom serve [--port 8787] [--out public]
      раздать файлы для проверки игры локально
  python -m newsroom show [--edition ru] [--state ...]
      что сейчас на доске и почему отклонено остальное
"""
from __future__ import annotations

import argparse
import functools
import http.server
import json
import os
import time

from . import store
from .run import HERE, run_once


def main() -> None:
    ap = argparse.ArgumentParser(prog="newsroom")
    ap.add_argument("cmd", choices=["run", "serve", "show"])
    ap.add_argument("--fake", action="store_true", help="без модели: заголовки как есть, помечены поддельными")
    ap.add_argument("--state", default=os.path.join(HERE, "state", "newsroom.json"))
    ap.add_argument("--out", default=os.path.join(HERE, "public"))
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--edition", default="en")
    ap.add_argument("--max", type=int, default=40, help="пересказов за проход")
    args = ap.parse_args()
    if args.cmd == "run":
        t0 = time.time()
        report = run_once(args.state, args.out, fake=args.fake, max_rewrites=args.max)
        report["seconds"] = round(time.time() - t0, 1)
        print(json.dumps(report, ensure_ascii=False, indent=1))
    elif args.cmd == "serve":
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=args.out)
        print(f"раздаю {args.out} на http://127.0.0.1:{args.port}/")
        http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler).serve_forever()
    elif args.cmd == "show":
        state = store.load(args.state)
        path = os.path.join(args.out, f"stories-{args.edition.lower()}.json")
        doc = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {"stories": []}
        print(f"на доске {len(doc['stories'])}:")
        for s in doc["stories"][:40]:
            print(f"  {s['category']:<9} {s['trust']:<6} {s['outlets']}+{s['social']}  {s['title']}")
        failed = [c for c in state["clusters"].values() if (c.get("rewrite") or {}).get("status") in ("failed", "blocked")]
        print(f"\nотклонено и не прошло проверку {len(failed)}:")
        for c in failed[:30]:
            rw = c["rewrite"]
            print(f"  {rw['status']:<8} {rw.get('reason','')[:60]:<60} | {c['items'][0]['title'][:70]}")


if __name__ == "__main__":
    main()
