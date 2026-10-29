from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "repo_stars_remaining" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "repo" VARCHAR(255) NOT NULL UNIQUE,
    "channel_id" BIGINT NOT NULL,
    "user_id" INT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
COMMENT ON TABLE "repo_stars_remaining" IS 'Maps a user to a repo and a Telegram group/channel.';
        CREATE TABLE IF NOT EXISTS "token_transactions" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "amount" INT NOT NULL,
    "type" VARCHAR(20) NOT NULL,
    "reason" VARCHAR(255),
    "created_at" TIMESTAMPTZ NOT NULL,
    "user_id" INT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
COMMENT ON TABLE "token_transactions" IS 'Audit log of every token movement for a user''s wallet — daily';
        CREATE TABLE IF NOT EXISTS "token_wallets" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "balance" INT NOT NULL,
    "last_refill_date" DATE,
    "created_at" TIMESTAMPTZ NOT NULL,
    "updated_at" TIMESTAMPTZ NOT NULL,
    "user_id" INT NOT NULL UNIQUE REFERENCES "users" ("id") ON DELETE CASCADE
);
COMMENT ON TABLE "token_wallets" IS 'Tracks a user''s daily planning-token balance under the';
        CREATE TABLE IF NOT EXISTS "user_planning_tokens" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "token" VARCHAR(255) NOT NULL UNIQUE,
    "user_id" INT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
COMMENT ON TABLE "user_planning_tokens" IS 'Fixed token used to identify a user when generating a plan/draft.';
        ALTER TABLE "users" ADD "allowed_commands" JSONB;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "users" DROP COLUMN "allowed_commands";
        DROP TABLE IF EXISTS "token_transactions";
        DROP TABLE IF EXISTS "user_planning_tokens";
        DROP TABLE IF EXISTS "repo_stars_remaining";
        DROP TABLE IF EXISTS "token_wallets";"""


MODELS_STATE = (
    "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"
)
