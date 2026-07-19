# Telegram → GitHub Idea Bot: Implementation Plan

## 1. Goal Recap

- `/plan <idea>` → Claude formats a rough idea into structured markdown, returned as a draft for review.
- `/push` → Pushes the last drafted markdown as a GitHub Issue (labeled `status:todo`).
- `/board` → Renders open issues grouped by status (`todo` / `doing` / `done`) with inline buttons.
- Claiming a card ("Move to Doing") locks it to one user in a multi-user channel; others are blocked until release or expiry.

---

## 2. Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Bot framework | `python-telegram-bot` v21+ (async) | Mature, handles inline keyboards + callback queries cleanly |
| Backend | FastAPI (you already use this) | Webhook endpoint for Telegram, shared codebase style |
| DB | SQLite (start), Postgres (later if scaling) | Atomic UPDATE-based locking works on both |
| GitHub access | `httpx` direct to REST API (or PyGithub) | Issues + labels + assignees API |
| AI formatting | Claude API (Messages endpoint) | Already your stack |
| Hosting | Any box/VM with webhook (or long polling for dev) | Telegram webhooks need HTTPS |

---

## 3. Data Model

```sql
-- Drafts: /plan output waiting to be pushed
CREATE TABLE drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Locks: source of truth for card claims (mirrors GitHub assignee)
CREATE TABLE locks (
    issue_number INTEGER PRIMARY KEY,
    repo TEXT NOT NULL,
    locked_by_user_id INTEGER,
    locked_by_username TEXT,
    locked_at TIMESTAMP,
    status TEXT DEFAULT 'todo'   -- todo | doing | done
);
```

Keep `locks` as your source of truth. GitHub (labels + assignee) is a **mirror** you sync to after every state change — never trust GitHub as authoritative for concurrent writes, since its API has no compare-and-swap.

---

## 4. Project Structure

```
telegram-idea-bot/
├── bot/
│   ├── main.py              # bot init, command/callback handlers
│   ├── commands/
│   │   ├── plan.py          # /plan handler
│   │   ├── push.py          # /push handler
│   │   └── board.py         # /board handler + callback query handler
│   ├── github_client.py     # create_issue, assign, relabel, list_issues
│   ├── claude_client.py     # format_idea_to_markdown()
│   ├── db.py                # sqlite connection + queries
│   └── locking.py           # claim_card(), release_card(), expire_stale_locks()
├── requirements.txt
└── .env                     # BOT_TOKEN, GITHUB_TOKEN, ANTHROPIC_API_KEY, REPO
```

---

## 5. Build Phases

### Phase 1 — Skeleton bot (½ day)
- Register bot with BotFather, get token.
- Basic `python-telegram-bot` app with `/start` and echo handler.
- Confirm webhook or polling works end-to-end.

### Phase 2 — `/plan` (½–1 day)
- Handler takes free text after `/plan`.
- Call Claude with a fixed system prompt (idea → structured markdown: Title, Problem, Proposed Solution, Tech Stack, Milestones, Open Questions).
- Save result to `drafts` table, reply with the markdown in a code block so it's copy-friendly.

### Phase 3 — `/push` (½ day)
- Fetch latest draft for that `chat_id`/`user_id`.
- Call GitHub Issues API: create issue, title = first line of draft, body = rest, label `status:todo`.
- Insert a row in `locks` with `status='todo'`, no owner.
- Reply with the issue link.

### Phase 4 — `/board` (1 day)
- Query `locks` grouped by status, join with cached issue titles (or fetch live from GitHub).
- Render one message per column or one message with three sections.
- Each `todo` card gets an inline button: `➡️ Claim & Start`.
- Each `doing` card owned by the tapping user gets `✅ Mark Done` and `🔓 Release`.

### Phase 5 — Locking logic (1 day, the core piece)
- `claim_card(issue_number, user)`:
  ```python
  cur = db.execute(
      "UPDATE locks SET locked_by_user_id=?, locked_by_username=?, locked_at=?, status='doing' "
      "WHERE issue_number=? AND locked_by_user_id IS NULL",
      (user.id, user.username, now(), issue_number)
  )
  if cur.rowcount == 0:
      return "already_claimed"
  else:
      github_client.assign_and_relabel(issue_number, user.username, "status:doing")
      return "claimed"
  ```
- `release_card(issue_number, user)` — only succeeds if `locked_by_user_id == user.id` (or user is admin).
- On any claim/release, **edit the original board message** (not send a new one) so the channel doesn't fill with duplicate boards — use `edit_message_reply_markup` or re-render full text via `edit_message_text`.

### Phase 6 — Expiry job (½ day)
- Background task (APScheduler or a simple loop) every N minutes:
  - Find locks older than threshold (e.g. 24h) still `doing`.
  - Release them, unassign on GitHub, post a note in the channel.

### Phase 7 — Polish (ongoing)
- Permissions: who can `/push`? Anyone in the channel, or admins only?
- Error handling: GitHub rate limits, Claude API failures — fall back gracefully, don't lose the draft.
- `/mydrafts` or `/cancel` to manage pending drafts.

---

## 6. Key Risk Points to Watch

- **Callback query staleness**: always re-fetch lock state from DB inside the callback handler before acting — never trust what button the user saw, since the board may have changed since it was rendered for them.
- **Telegram message edit limits**: editing the same message repeatedly is fine, but Telegram rate-limits edits (~1/sec per chat) — batch rapid updates if multiple claims happen quickly.
- **GitHub API rate limits**: 5000 req/hr authenticated — fine at small scale, but don't call GitHub on every `/board` view; cache issue lists locally and refresh periodically or on webhook from GitHub.
- **Webhook vs polling**: polling is easier for local dev, but you'll want a real webhook (FastAPI endpoint) for production so it works in group channels reliably.

---

## 7. Suggested Build Order (Summary)

1. Skeleton bot + `/start`
2. `/plan` with Claude formatting
3. `/push` to GitHub Issues
4. `/board` read-only rendering
5. Claim/release logic with atomic locking
6. Expiry job
7. Permissions + error handling polish

Each phase is independently testable before moving to the next — you can demo a working `/plan → /push` loop before touching the Kanban/locking complexity at all.