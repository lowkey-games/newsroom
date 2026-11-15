# Редакция «Срочно в эфир»

Служба для игры на Roblox «Срочно в эфир» (Breaking News Studio). Раз в 15 минут собирает новости из RSS изданий
и открытых Telegram-каналов, склеивает одну историю из разных источников и выкладывает два файла:

- `https://<аккаунт>.github.io/<репозиторий>/stories-en.json`
- `https://<аккаунт>.github.io/<репозиторий>/stories-ru.json`

В файлах только наш текст, рубрика и счётчики «сколько изданий» и «сколько каналов». Названий изданий,
ссылок и цитат нет.

Код живёт в репозитории игры (`newsroom/`), сюда его копирует `newsroom/deploy/export.sh`. Править там,
потом пересобрать и запушить сюда.

## Кто пишет текст

| Режим | Что нужно | Что на доске |
| --- | --- | --- |
| без ИИ (по умолчанию) | ничего | строка из общих фактов: «Arkane · закрытие · 13 ноября», только на языке заметок |
| Cloudflare Workers AI | бесплатный аккаунт Cloudflare | фраза своими словами на двух языках, Llama 3.3 70B, до 10 000 «нейронов» в сутки |

Режим выбирается сам по секретам: есть Cloudflare — он, нет — без ИИ.
Если модель недоступна или кончился суточный лимит, в этот проход работает строка из фактов.

## Настройка один раз

1. Settings → Pages → Build and deployment → Source: **GitHub Actions**.
2. Actions → newsroom → Run workflow. Через пару минут файлы появятся по адресам выше.
3. Адреса вписать в игру: Configs, ключ `Fetch`, поле `Newsroom` с `EN` и `RU`.

Чтобы включить бесплатный пересказ (Cloudflare):

1. Завести аккаунт на cloudflare.com, бесплатный план.
2. В панели Cloudflare: Workers AI → Use REST API. Скопировать Account ID, затем «Create a Workers AI API Token»
   → Create API Token → скопировать токен.
3. Здесь: Settings → Secrets and variables → Actions → New repository secret: `CLOUDFLARE_ACCOUNT_ID`
   и `CLOUDFLARE_API_TOKEN`.

Необязательные переменные (Settings → Secrets and variables → Actions → Variables):

| Переменная | По умолчанию | Что меняет |
| --- | --- | --- |
| `NEWSROOM_REWRITER` | по секретам | `facts` или `cloudflare`: выбрать режим явно |
| `NEWSROOM_NEURONS_PER_DAY` | `9000` | суточный потолок Cloudflare, бесплатно 10 000 |
| `NEWSROOM_CF_MODEL` | `@cf/meta/llama-3.3-70b-instruct-fp8-fast` | модель Cloudflare |
| `NEWSROOM_SINGLE_AFTER` | не задана | через сколько секунд показывать новость из одного издания |

Секрет `GNEWS_API_KEY` нужен, только если включить источники GNews в `newsroom/sources.json`.

## Что проверить, если доска пустая

- Actions → последний запуск: шаг «Проход редакции» печатает отчёт: режим, ленты, истории, строки, сбой модели.
- `python -m newsroom show --edition ru` локально покажет, что на доске и почему остальное отклонено.
