# Project Manager Bot (Telegram ➜ GitHub Idea Bot)

A Telegram Bot that captures raw, unstructured project ideas from team chats, structures them using AI (via the Groq API), saves them as local project plan files, pushes them to GitHub Issues, and tracks progress using an interactive Kanban board directly in the chat.

## 💡 The Problem This Solves

User/Devloper often discuss a large volume of project ideas, feature requests, and tasks in messaging channels. However:
1. **Ideas get lost** in chat history.
2. **Ideas are unstructured**, lacking technical requirements, scope, milestones, or open questions.
3. **Transition to issue trackers is slow** and manual, requiring copy-pasting and formatting.
4. **Lack of quick assignments** directly where discussions happen.

### 🚀 The Solution
This bot solves these issues by:
* **AI-Assisted Formatting**: Automatically structures any quick idea description into a fully fleshed-out Technical Implementation Plan using high-quality LLMs.
* **Local Persistence**: Saves the formatted plans directly in the local workspace workspace as `.md` files, named after the project title.
* **GitHub Sync**: Creates GitHub issues labeled `status:todo` with a single command.
* **Interactive Kanban Board**: Enables team members to view, claim (`Claim`), release (`Release`), or finish (`Mark Done`) tasks using inline buttons directly in Telegram.
* **Atomic SQLite Locks**: Guards tasks so only the claimant can release or mark a task done, preventing collision.

---

## 🛠️ Configuration & Setup

### 1. Prerequisites
Ensure you have `uv` installed (or use standard Python virtual environments).

### 2. Environment Setup
Create a `.env` file in the root directory (see `.env` format):
```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
GITHUB_TOKEN=your_github_personal_access_token
GITHUB_REPO=your_github_username/your_repository_name
GROQ_API_KEY=your_groq_api_key

# Model Settings
GROQ_MODEL_REASONING=llama-3.3-70b-versatile
GROQ_MODEL_SMALL=llama-3.1-8b-instant

# Lock Expiration Settings
LOCK_TIMEOUT_HOURS=24

# Access Control Settings (comma-separated telegram user IDs)
ADMIN_USER_IDS=123456789,987654321
```

### 3. Installation
Install dependencies and set up the virtual environment:
```bash
uv init
uv sync
```

### 4. Running the Bot
Start the bot using `uv`:
```bash
uv run main.py
```

---

## 📂 Project Structure

```
project_manager_bot/
├── bot/
│   ├── commands/            # Telegram command implementation files
│   │   ├── board.py         # /board command and inline callbacks
│   │   ├── create_task.py   # /create-task manual and bulk creation
│   │   ├── plan.py          # /plan AI formatter & local file creator
│   │   └── push.py          # /push draft to GitHub issue
│   ├── auth.py              # User verification and @admin_only decorator
│   ├── db.py                # SQLite session management & query operations
│   ├── github_client.py     # GitHub API issue creator and label updater
│   ├── groq_client.py       # Groq API project plan formatting client
│   ├── locking.py           # Atomic card locking and expiration business logic
│   ├── main.py              # Bot initializer and background jobs
│   └── models.py            # Pydantic schemas for Database mapping
├── main.py                  # Root entry point
├── pyproject.toml           # Project dependencies config
└── README.md                # Root documentation
```

For a detailed walkthrough of each module's internal functions, classes, and routing, refer to the [Bot Walkthrough README](bot/README.md).
