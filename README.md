# Telegram Content Bot

![Python](https://img.shields.io/badge/Python-3.12+-blue)
![aiogram](https://img.shields.io/badge/aiogram-3.x-blue)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-asyncpg-336791)
![Redis](https://img.shields.io/badge/Redis-FSM_storage-red)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-412991)
![Tests](https://img.shields.io/badge/tests-pytest-green)

A Telegram bot that generates social media posts via OpenAI and publishes them to a channel — either immediately or at a scheduled time.

## ✨ Features

- `/generate` — starts an FSM conversation flow to collect a topic
- GPT-4o-mini generates a post draft based on the topic
- Inline keyboard: **Post now** publishes to the Telegram channel instantly; **Schedule** lets the user pick a UTC time
- Scheduled posts are persisted to PostgreSQL and polled every minute by an APScheduler background job
- FSM state survives process restarts via Redis storage
- Graceful error handling for OpenAI rate limits, connection errors, and API failures
- Authorization middleware restricts access to a whitelist of allowed user IDs

## 🏗 Architecture

```
User → Telegram → aiogram Dispatcher
                      │
                      ├── handlers/generate.py   (FSM flow: topic → draft → post/schedule)
                      ├── handlers/start.py       (catch-all /start)
                      │
                      ├── services/ai.py          (OpenAI API call)
                      ├── services/scheduler.py   (APScheduler job — polls DB every 60s)
                      │
                      ├── db/pool.py              (asyncpg connection pool)
                      └── db/queries.py           (save / fetch-due / mark-sent)
```

**Request flow — "Schedule" path:**

1. User sends `/generate` → bot sets FSM state `waiting_for_topic`
2. User sends topic → `handle_topic` calls OpenAI, stores draft in FSM data, advances to `reviewing_post`
3. User taps **Schedule** → bot sets state `waiting_for_time`
4. User sends `HH:MM` → `handle_time` validates, saves row to `scheduled_posts`, clears FSM
5. APScheduler fires `post_due_items` every minute → fetches due rows → sends to channel → marks `sent`

FSM state is stored in Redis so restarts don't lose in-progress conversations. The DB pool is initialized once at startup and shared across all handlers via `db.pool.get_pool()`.

## 🛠 Tech Stack

| Layer | Library | Purpose |
|---|---|---|
| Bot framework | aiogram 3.x | Async Telegram API, FSM, routing, middleware |
| AI | openai 2.x | GPT-4o-mini post generation |
| Database | asyncpg | Async PostgreSQL driver |
| Scheduler | APScheduler | Background job for due posts |
| FSM storage | redis-py (async) | Persist state across restarts |
| Config | python-dotenv | `.env` loading |
| Tests | pytest + pytest-asyncio + pytest-cov | Unit & integration tests with coverage |

## 📁 Project Structure

```
tel-bot/
├── bot.py                   # Entry point: dispatcher, lifecycle hooks, polling
├── handlers/
│   ├── generate.py          # /generate FSM flow (topic → draft → post/schedule)
│   └── start.py             # /start catch-all
├── services/
│   ├── ai.py                # generate_post() — OpenAI call
│   └── scheduler.py         # post_due_items() + AsyncIOScheduler instance
├── db/
│   ├── pool.py              # asyncpg pool lifecycle
│   └── queries.py           # save_scheduled_post / fetch_due_posts / mark_sent
├── middlewares/
│   └── auth.py              # AuthMiddleware — outer middleware for user whitelist
├── tests/
│   ├── conftest.py          # db_pool fixture for integration tests
│   ├── unit/
│   │   ├── test_handlers.py
│   │   ├── test_scheduler.py
│   │   ├── test_ai.py
│   │   └── test_auth_middleware.py
│   └── integration/
│       └── test_db_queries.py
├── .env.example
├── pytest.ini
└── requirements.txt
```

## ⚙️ Environment Variables

Copy `.env.example` to `.env` and fill in:

| Variable | Description | Example |
|---|---|---|
| `BOT_TOKEN` | Telegram bot token from [@BotFather](https://t.me/BotFather) | `7123456789:AAF...` |
| `OPENAI_API_KEY` | OpenAI API key | `sk-proj-...` |
| `DATABASE_URL` | asyncpg-compatible PostgreSQL DSN | `postgresql://user:pass@localhost:5432/telbot` |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379` |
| `CHANNEL_ID` | Telegram channel ID (bot must be admin) | `-1001234567890` |
| `ALLOWED_USERS` | Comma-separated Telegram user IDs allowed to use the bot | `123456789,987654321` |

> Get the channel ID by forwarding a message from it to [@userinfobot](https://t.me/userinfobot).

## 🚀 Running Locally

**Prerequisites:** Python 3.11+, PostgreSQL, Redis running locally.

```bash
git clone <repo-url>
cd tel-bot

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# fill in .env

python bot.py
```

The bot creates the `scheduled_posts` table automatically on first startup via `CREATE TABLE IF NOT EXISTS`.

## 🧪 Running Tests

**Prerequisites:** A `telbot_test` database accessible at the URL in `tests/conftest.py`.

```bash
# create the test DB (one-time setup)
psql -U postgres -c "CREATE DATABASE telbot_test;"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE telbot_test TO botuser;"

# run all tests with coverage
pytest

# coverage report is printed to terminal and written to coverage.lcov
# open it in VS Code with the Coverage Gutters extension for gutter highlights
```

Unit tests mock all external dependencies (Telegram, OpenAI, DB) with `unittest.mock`. Integration tests in `tests/integration/` connect to the real `telbot_test` database.

## 🗄 Database Schema

```sql
CREATE TABLE IF NOT EXISTS scheduled_posts (
    id        SERIAL PRIMARY KEY,
    user_id   BIGINT NOT NULL,
    post_text TEXT NOT NULL,
    post_at   TIMESTAMPTZ NOT NULL,
    status    TEXT NOT NULL DEFAULT 'pending'
);
```

The scheduler polls `WHERE post_at <= NOW() AND status = 'pending'` every minute and updates matching rows to `status = 'sent'` after delivery.

## 📋 Implementation Notes

- **Async throughout** — `asyncpg` for non-blocking DB I/O, `AsyncIOScheduler` for the background job, `redis-py` async client for FSM storage. No blocking calls on the event loop.
- **FSM state isolation** — each user's state and data dict are keyed by `(chat_id, user_id)` in Redis. Concurrent users don't interfere.
- **Past-time scheduling** — if the user sends a time that has already passed today, the bot silently schedules it for the same time tomorrow.
- **Scheduler misfire tolerance** — `misfire_grace_time=30` on the APScheduler job allows up to 30 seconds of startup jitter before a firing is considered missed, preventing spurious "run time missed" log warnings.
- **Retry-friendly validation** — invalid time input leaves the FSM in `waiting_for_time` so the user can correct it without restarting the whole flow.
- **Test isolation** — the `db_pool` fixture truncates `scheduled_posts` with `RESTART IDENTITY` before and after each integration test, ensuring a clean slate with reset auto-increment IDs.
- **Outer middleware for auth** — `AuthMiddleware` is registered as `outer_middleware` on both `dp.message` and `dp.callback_query`. Outer middleware runs before aiogram evaluates any filters or selects a handler, so unauthorized users are rejected at the pipeline entrance — no routing, no FSM access, no DB touch.
