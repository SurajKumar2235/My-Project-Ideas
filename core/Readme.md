# Core Models and Migration Guide

This module defines the database schema for the project. It uses Tortoise ORM models in `core/models.py` and Aerich migrations in `migrations/models/`.

## Model Descriptions

### `User`
The primary identity model for every user in the system.
Fields:
- `id`: primary key.
- `github_id`: GitHub account identifier.
- `username`: human-readable login name.
- `email`: optional email address.
- `avatar_url`: profile image URL.
- `access_token`: optional GitHub access token.
- `telegram_id`: Telegram user identifier.
- `telegram_user_obj`: Telegram profile object stored as JSON.
- `active_repo`: currently selected repository for commands.
- `role`: authorization role string, defaulting to `user`.
- `created_at`: record creation timestamp.

### `ChannelRepo`
Maps a user to a repository and a Telegram channel or group.
- `repo`: repository identifier.
- `user`: foreign key to `User`.
- `channel_id`: Telegram channel ID.

This model is used to calculate subscription bonuses and to associate planning credits with active projects.

### `UserPlanningToken`
A fixed token used when generating a plan or draft.
- `user`: foreign key to `User`.
- `token`: unique token string.

This entity provides a stable reference for AI planning operations and helps the platform connect generated content back to the originating user.

### `TokenWallet`
Tracks a user's current planning credit balance.
Fields:
- `user`: one-to-one relation to `User`.
- `balance`: current available token balance.
- `last_refill_date`: date when daily credits were last granted.
- `created_at`: timestamp when wallet was created.
- `updated_at`: timestamp when wallet was last updated.

### `TokenTransaction`
Append-only ledger for every wallet event.
Fields:
- `user`: foreign key to `User`.
- `amount`: amount added or subtracted from balance.
- `type`: reason for the transaction (`daily_grant`, `spend`, `purchase`).
- `reason`: optional metadata string.
- `created_at`: timestamp for the transaction.

This ledger makes the subscription model auditable and allows recalculation of wallet state if needed.

### `Draft`
Stores generated plans or drafts.
Fields:
- `user`: foreign key to `User`.
- `chat_id`: Telegram chat context.
- `content`: generated draft text.
- `repo`: optional target repository.
- `created_at`: creation timestamp.

### `Lock`
Enforces atomic Kanban task ownership.
Fields:
- `repo`: repository containing the issue.
- `issue_number`: issue identifier.
- `locked_by_user`: optional `User` who claimed the lock.
- `locked_by_username`: optional username snapshot.
- `locked_at`: timestamp when the lock was claimed.
- `status`: task status, such as `todo`, `doing`, or `done`.

A unique constraint on `(repo, issue_number)` ensures only one lock row exists per issue.

## Subscription Model Architecture

The subscription model uses `TokenWallet` and `TokenTransaction` to deliver daily planning credits:

- Each user receives a daily refill based on their project participation.
- A typical refill rule is:
  - `daily_grant = BASE_DAILY_TOKENS + (PER_PROJECT_TOKENS * active_project_count)`
- `active_project_count` is determined by the number of `ChannelRepo` rows belonging to the user.
- `TokenWallet.balance` is the user's spendable credit.
- `TokenTransaction` tracks every refill, spend, and purchase.

This design supports:
- daily bonus calculation per project
- safe single-day refill behavior via `last_refill_date`
- rollback / audit of token usage
- carryover of unused credits if desired by the product rules

## How to Use Migrations

The project uses Aerich as the migration tool for Tortoise ORM. The migration files are stored in `migrations/models/`.

### Initialize a new database

If you are starting a fresh database:

```bash
python -m aerich init -t core.db_config.TORTOISE_ORM
python -m aerich init-db
```

### Create and apply changes

When you change `core/models.py`, create a migration and apply it:

```bash
python -m aerich migrate --name add_new_field
python -m aerich upgrade
```

### Inspect existing migrations

The existing migration history includes:
- `0_20260725223819_init.py`: initial schema for `users`, `drafts`, `locks`, and Aerich metadata.
- `1_20260725230626_update.py`: relaxed `NOT NULL` constraints for Telegram fields.
- `2_20260728215951_add_role_to_user.py`: added the `role` column to `users`.

### Troubleshooting

- Ensure `.env` contains a valid `DATABASE_URL` before running Aerich.
- If using SQLite, omit the URL and the system defaults to `sqlite://db.sqlite3`.
- Run migrations from the repository root so relative imports resolve correctly.
