from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "users" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "github_id" BIGINT UNIQUE,
    "username" VARCHAR(255) NOT NULL,
    "email" VARCHAR(255),
    "avatar_url" TEXT,
    "access_token" TEXT,
    "telegram_id" BIGINT NOT NULL UNIQUE,
    "telegram_user_obj" JSONB NOT NULL,
    "active_repo" VARCHAR(255),
    "created_at" TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS "drafts" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "chat_id" BIGINT NOT NULL,
    "content" TEXT NOT NULL,
    "repo" VARCHAR(255),
    "created_at" TIMESTAMPTZ NOT NULL,
    "user_id" INT NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "locks" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "repo" VARCHAR(255) NOT NULL,
    "issue_number" INT NOT NULL,
    "locked_by_username" VARCHAR(255),
    "locked_at" TIMESTAMPTZ,
    "status" VARCHAR(50) NOT NULL,
    "locked_by_user_id" INT REFERENCES "users" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_locks_repo_cd0dbd" UNIQUE ("repo", "issue_number")
);
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSONB NOT NULL
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """


MODELS_STATE = (
    "eJztmltz2jgUgP8K46d2JtuhJIRs30hCWrYJdBLvbqedjka2hdFiS1SWkzDd/PdK8t3YDk"
    "6BBdZvcC629OlI50jyD82lFnK8N5cMTrj2rvVDI9BF4kdWcdTS4HyeiKWAQ8NRlpY0USJo"
    "eJxBUz5oAh0PCZGFPJPhOceUCCnxHUcKqSkMMbETkU/wdx8BTm3Ep4gJxddvQoyJhR6RF/"
    "2dz8AEI8fKtBRb8t1KDvhirmRDwq+UoXybAUzq+C5JjOcLPqUktsZEddFGBDHIkXw8Z75s"
    "vmxd2M+oR0FLE5OgiSkfC02g7/BUdw2QyDQARmMd3A10ALQagExKJFzRVE/13pZN+K3z9q"
    "R3cnZ8enImTFQzY0nvKXh1AiZwVHhGuvak9JDDwEIxTqCaU8hBEdlzbJfCTTk9TzjiWYU4"
    "EiSMk7jaHuTfO53j416nfXx61j3p9bpn7Zj2sqoK+/nwvSQvDKiYJsHsiYYihZ4SjgJeWf"
    "Q6eiwDn7jkwIvu7CH4Cob64LMi6Hred0cKRn/1by8+9G9f3fQ/v1aaRai5Ho/eR+YJ8NHF"
    "9fg8h5yhOV3mfTGFrJh3ZP8i2OEysSusNRc+AgcRm0/l8tHtVsCPUAur1zmqoaoT6HIRzZ"
    "DEAWBBUF8KDccuKgnsjGcOtxW6vol+7GGki1CC1pg4izAwqiJ/eDO40/s3nzLhf9nXB1LT"
    "yYR+JH11mhun+CGtv4f6h5b82/oyHg0UXupxm6k3Jnb6F022CfqcAkIfALRSqS6SRtQyo+"
    "57iBWmkNL8kfI4pPzxS0lalj2TWWGOlriW6V5RhrBNPqKFgjwULYLERAVQwxLvz/Axewb3"
    "KYqeSJqEJYMPcZ2YDirRd9FjxIPVvX930b8caIqwAc3ZA2QWyKCWGtqhOUlsu6xyO25eAg"
    "m0FRzZC9nmkPo1NWdaQcGt5JX1tiMsNlBuf42zGvY8oSO+awjNt6YM/w/L8K0WJrs2w7dQ"
    "mWRCvUb45tyabFWwj5HrlCjdjAWQS7CS1ojkYu+m4F4prEN49evtjOMayu0dQ78n1XXEpL"
    "K8FmUd9706Uyrx2F560Di1qLaVmdRtrzCRuu3SeSRVVStYvb1Moe+L8sSOzaENb2qy3La3"
    "vdkxyqvubgrDbJf2OQp/wT4nGpbyfY7sUHOtcFj7GRvzqW/UvljIuK1lEd0Fylu+V3hJFf"
    "7LtffObXI2X3wjF2KnDuTYodndrAQY3ovlhQGfFVAuvyPLeh0C6m3fkkHTRJ4nkukMkVrk"
    "c34N+/rsuajnbAbd2qkz57iek6r/YfaMOao6mxr/LA/DH3fj0TODkHbOH69gk7f+bTnY28"
    "fDwwq+Ekv1fMiH/lH2tEQ+YHkt4vgegbrn4zm3Q1iJmvv75v5+bff3Swcz5YcGSXgkHwDm"
    "0lLod/XxFjlQkV0Ogvx3hns2/mXnNNn540AR3RaIb25fzim6Ht6vNaqU0iZPnvqIYXOqFZ"
    "w9hZqjqtMnmNg0x09bLu02dvx0j5gXTq9VK4aUS3MAsuL+XEyqOjVZYH6AdN+2V7mSElal"
    "dJVuxc+Dy7cf5Z8HN5uO5zYdNSqi9Sezp5/nsdBg"
)
