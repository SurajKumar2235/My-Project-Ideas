# Project Manager Bot (LogicalFire) 🚀

A full-stack, AI-powered project management platform bridging unstructured chat discussions and structured developer workflows. Captures project ideas from **Telegram** or **Web**, formats them into comprehensive technical specifications using **Groq AI (Llama 3.3)**, syncs them as **GitHub Issues**, and tracks task progress via an interactive **Kanban Board** with atomic task locking.

---

## 💡 Key Problems & Solutions

### The Problems
1. **Lost Ideas**: Unstructured feature requests and project concepts get buried in chat histories.
2. **Lack of Specification**: Quick idea notes lack technical requirements, milestone breakdowns, or open questions.
3. **Manual Overhead**: Converting chat ideas to issue trackers is slow, manual, and inconsistent.
4. **Task Collisions**: Multiple contributors often attempt to work on the same issue without real-time task lock visibility.

### The Solution
* **AI-Powered Structuring**: Uses high-capacity LLMs via the Groq API (`llama-3.3-70b-versatile`) to format raw text into detailed Markdown project plans.
* **Dual Interface**: Operate seamlessly from **Telegram** (`/plan`, `/push`, `/board`, `/repo`, `/login`) or via the modern **Web Dashboard**.
* **GitHub Sync & OAuth**: Authenticate via GitHub OAuth, target specific repositories, create `status:todo` labeled issues, and breakdown plans into actionable task checklists.
* **Interactive Kanban Board**: Real-time task board to view, claim (`Claim`), release (`Release`), or mark tasks done (`Mark Done`).
* **Atomic Locking**: Database task locking (`Lock` model) ensures single-claimant safety per card with automatic timeout expirations.

---

## 🏗️ Platform Architecture

```
                  ┌───────────────────────┐
                  │     Telegram User     │
                  └───────────┬───────────┘
                              │ Telegram Bot API
                              ▼
                  ┌───────────────────────┐
                  │     Telegram Bot      │
                  │   (python-telegram)   │
                  └───────────┬───────────┘
                              │ HTTP (X-Bot-Token)
                              ▼
┌──────────────┐  ┌───────────────────────┐  ┌──────────────┐
│  Groq API    │◄─┤   FastAPI Backend     ├─►│  GitHub API  │
│ (Llama 3.3)  │  │   (REST & Web UI)     │  │ (OAuth/Issues│
└──────────────┘  └───────────┬───────────┘  └──────────────┘
                              │ Tortoise ORM
                              ▼
                  ┌───────────────────────┐
                  │ PostgreSQL / SQLite   │
                  │     (User/Draft/Lock) │
                  └───────────────────────┘
```

---

## 📂 Project Structure

```
project_manager_bot/
├── api/                     # FastAPI Backend Server & Web UI
│   ├── auth.py              # GitHub OAuth & JWT Authentication
│   ├── main.py              # FastAPI Server entry point & CORS configuration
│   ├── README.md            # Backend REST API documentation
│   ├── routers/             # Domain endpoints (board, bot_api, drafts, push, repos, tasks)
│   └── static/              # Web Dashboard UI (HTML5, Vanilla CSS, JS)
├── bot/                     # Telegram Bot Client
│   ├── commands/            # Command handlers (/board, /plan, /push, /repo, /auth, /create_task)
│   ├── api_client.py        # Async HTTP client interfacing with FastAPI backend
│   ├── auth.py              # User verification and @admin_only decorator
│   ├── github_client.py     # GitHub REST API issue manager
│   ├── groq_client.py       # Groq LLM plan generation interface
│   ├── locking.py           # Kanban card locking & expiration engine
│   ├── main.py              # Bot polling loop initializer
│   ├── models.py            # Pydantic schemas
│   └── README.md            # Detailed Bot implementation guide
├── core/                    # Core Infrastructure & Database Models
│   ├── db_config.py         # Tortoise ORM database configuration
│   ├── models.py            # Database Entities (User, Draft, Lock)
│   └── Readme.md            # Core models and migration documentation
├── migrations/              # Aerich database migration files
├── main.py                  # Root entry point to launch Telegram bot
├── pyproject.toml           # UV project dependencies & configuration
└── README.md                # Project documentation root
```

## 🧠 Database Models & Subscription Architecture

The core database is defined in `core/models.py` using Tortoise ORM. It includes the following entities:

- `User`: primary identity for each person. Stores GitHub and Telegram link data, the current active repo, and a `role` value for permissions.
- `ChannelRepo`: maps a user to a GitHub repo and a Telegram channel/group. This row is used to calculate the per-project subscription bonus for daily token grants.
- `UserPlanningToken`: a fixed planning token assigned to a user when they register a project or request a plan. A planning action consumes a token and helps the bot associate AI-generated drafts with the requesting user.
- `TokenWallet`: subscription balance for planning credits. Each day, users receive a base grant plus an additional bonus for every active project they own.
- `TokenTransaction`: append-only ledger of every token movement, including daily grants, spend events, and top-up purchases.
- `Draft`: stores AI-generated draft content and the target repo or chat context.
- `Lock`: enforces atomic task ownership on GitHub issue locks for the Kanban board, with unique `(repo, issue_number)` semantics.

### Subscription Model Overview

The subscription model is implemented by `TokenWallet` and `TokenTransaction`:

- Every user gets a daily token refill based on a rule such as:
  - `daily_grant = BASE_DAILY_TOKENS + (PER_PROJECT_TOKENS * active_project_count)`
- `active_project_count` is derived from the number of `ChannelRepo` rows linked to the user.
- `TokenWallet.balance` is the user's current spendable planning credit. It is updated by daily refill grants and by spends when the user generates a plan or draft.
- `TokenTransaction` keeps an audit trail for each balance change, including:
  - `daily_grant` for scheduled subscription top-ups
  - `spend` for plan/draft generation or other token usage
  - `purchase` for manual top-ups or star purchases

This architecture keeps token accounting auditable, prevents double-grants by tracking `last_refill_date`, and allows unused credits to carry over unless business rules change.

### Migration Guide

This project uses Aerich with Tortoise ORM for database migrations. Existing migration files live under `migrations/models/`.

Common migration workflow:

1. Update `core/models.py` with the new field or model change.
2. Create a new migration from the repository root:
   ```bash
   uv run -m aerich migrate --name add_my_field
   ```
3. Apply the migration to the database:
   ```bash
   uv run -m aerich upgrade
   ```

If you are initializing a new database for the first time, run:

```bash
python -m aerich init -t core.db_config.TORTOISE_ORM
python -m aerich init-db
```

For an existing project, use `python -m aerich upgrade` after adding migrations.

> Note: make sure `DATABASE_URL` is configured in `.env` before running Aerich.

---

For module-specific walkthroughs:
* 📖 [Telegram Bot Walkthrough](bot/README.md)
* ⚡ [FastAPI Backend Documentation](api/README.md)
* 🧩 [Database Models & Migration Guide](core/Readme.md)

---

## 🛠️ Environment & Setup

### 1. Prerequisites
Ensure you have [`uv`](https://github.com/astral-sh/uv) or standard Python 3.13+ installed.

### 2. Configuration (`.env`)
Create a `.env` file in the root directory:

```env
# Database Settings
DATABASE_URL=postgres://user:password@localhost:5432/logicalfire_db
# (Fallback to SQLite 'db.sqlite3' if omitted)

# Backend Security
BOT_API_SECRET=your_secure_bot_secret_token
JWT_SECRET=your_super_secret_jwt_key
BACKEND_URL=http://localhost:8000

# GitHub OAuth Credentials
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
GITHUB_REDIRECT_URI=http://localhost:8000/auth/github/callback

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_telegram_bot_token

# Groq AI Settings
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL_REASONING=llama-3.3-70b-versatile
GROQ_MODEL_SMALL=llama-3.1-8b-instant

# Business Logic Configuration
LOCK_TIMEOUT_HOURS=24
ADMIN_USER_IDS=123456789,987654321
```

### 3. Installation
Install dependencies with `uv`:
```bash
uv sync
```

---

## 🚀 Running the Platform

### Start the FastAPI Backend Server
```bash
uv run uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```
* **Interactive API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **Web Dashboard**: [http://localhost:8000](http://localhost:8000)

### Start the Telegram Bot
In a separate terminal:
```bash
uv run main.py
```

---

## 💬 Bot Commands Reference

| Command | Description |
| :--- | :--- |
| `/start` | Welcome message and command guide. |
| `/login` | Link Telegram user account to GitHub OAuth. |
| `/logout` | Unlink GitHub account. |
| `/repo` | Select target GitHub repository for issues/board. |
| `/plan <idea>` | Format unstructured idea into AI Markdown plan draft. |
| `/edit <feedback>`| Request AI revisions on the current draft. |
| `/push` | Push approved draft to GitHub as a `status:todo` issue. |
| `/create_task [title]` | Manually create a task or bulk-parse checklist tasks from draft. |
| `/board` | Render interactive Kanban board (Claim/Release/Mark Done). |

---

## 📄 License
MIT License.
