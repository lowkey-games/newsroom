"""Бесплатный пересказ: Workers AI в Cloudflare, общая инструкция и схема ответа из rewrite.py.

На бесплатном плане 10 000 «нейронов» в сутки (сброс в 00:00 UTC). Расход считаем сами по токенам
и останавливаемся раньше лимита: дальше в этот день работает строка из фактов (facts.py).
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.request

from .rewrite import SCHEMA, SYSTEM, batch_payload

MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
# нейронов на миллион токенов: вход, выход (developers.cloudflare.com/workers-ai/platform/pricing, 24.10.2026)
NEURONS = {MODEL: (26668, 204805)}
JSON_HINT = """

Answer with JSON only, no other text: {"stories": [{"id": "...", "allow": true, "reason": "", "category": "...",
"audience": "global", "en": "...", "ru": "...", "details_en": "...", "details_ru": "...",
"names": [{"source": "...", "en": "...", "ru": "..."}]}]}"""


class OutOfBudget(Exception):
    pass


def loose_json(text: str) -> dict:
    """Ответ модели бывает с текстом вокруг JSON: берём первый объект целиком."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except ValueError:
        return {}


class CloudflareRewriter:
    """Ключи в CLOUDFLARE_ACCOUNT_ID и CLOUDFLARE_API_TOKEN. Модель меняется переменной NEWSROOM_CF_MODEL,
    суточный потолок — NEWSROOM_NEURONS_PER_DAY (по умолчанию 9000 из 10 000 бесплатных)."""

    def __init__(self, budget: dict | None = None):
        self.account = os.environ["CLOUDFLARE_ACCOUNT_ID"]
        self.token = os.environ["CLOUDFLARE_API_TOKEN"]
        self.model = os.environ.get("NEWSROOM_CF_MODEL") or MODEL
        self.limit = float(os.environ.get("NEWSROOM_NEURONS_PER_DAY") or 9000)
        self.base = os.environ.get("CLOUDFLARE_API_BASE") or "https://api.cloudflare.com/client/v4"
        self.budget = budget if budget is not None else {}
        self.usage = {"input": 0, "output": 0, "calls": 0, "neurons": 0.0}

    def neurons(self, tokens_in: float, tokens_out: float) -> float:
        a, b = NEURONS.get(self.model, NEURONS[MODEL])
        return (tokens_in * a + tokens_out * b) / 1_000_000

    def rewrite(self, clusters: list[dict]) -> list[dict]:
        day = time.strftime("%Y-%m-%d", time.gmtime())
        if self.budget.get("day") != day:
            self.budget.clear()
            self.budget.update(day=day, neurons=0.0)
        payload = batch_payload(clusters)
        # токен — примерно 3 знака; на ответ закладываем 220 токенов на историю
        guess = self.neurons(len(SYSTEM + payload) / 3, 220 * len(clusters))
        if self.budget["neurons"] + guess > self.limit:
            raise OutOfBudget(f"за сутки потрачено {self.budget['neurons']:.0f} из {self.limit:.0f} нейронов")
        body = {
            "messages": [{"role": "system", "content": SYSTEM + JSON_HINT}, {"role": "user", "content": payload}],
            "response_format": {"type": "json_schema", "json_schema": SCHEMA},
            "max_tokens": 4096,
            "temperature": 0.2,
        }
        req = urllib.request.Request(
            f"{self.base}/accounts/{self.account}/ai/run/{self.model}",
            data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read())
        result = data.get("result") or {}
        out = result.get("response")
        usage = result.get("usage") or {}
        t_in = usage.get("prompt_tokens") or len(SYSTEM + payload) / 3
        t_out = usage.get("completion_tokens") or len(json.dumps(out, ensure_ascii=False)) / 3
        spent = self.neurons(t_in, t_out)
        self.budget["neurons"] += spent
        self.usage["calls"] += 1
        self.usage["input"] += int(t_in)
        self.usage["output"] += int(t_out)
        self.usage["neurons"] += round(spent, 1)
        if isinstance(out, str):
            out = loose_json(out)
        if not isinstance(out, dict):
            return []
        return [r for r in out.get("stories") or [] if isinstance(r, dict)]
