from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "users" ALTER COLUMN "telegram_id" DROP NOT NULL;
        ALTER TABLE "users" ALTER COLUMN "telegram_user_obj" DROP NOT NULL;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "users" ALTER COLUMN "telegram_id" SET NOT NULL;
        ALTER TABLE "users" ALTER COLUMN "telegram_user_obj" SET NOT NULL;"""


MODELS_STATE = (
    "eJztmltz2jgUgP8K46d2Ju1QEkK2byQhLW0CO4m722mno5FtYbzYEpXlJEyb/15JvhvbxT"
    "R4DeM3OBcjfT7SOUfih+IQA9nu60sKZ0x52/mhYOgg/iGtOOoocLmMxULAoGZLS0OYSBHU"
    "XEahLh40g7aLuMhArk6tJbMI5lLs2bYQEp0bWtiMRR62vnsIMGIiNkeUK75+42ILG+gRue"
    "HX5QLMLGQbqZFahvhtKQdstZSyMWZX0lD8mgZ0YnsOjo2XKzYnOLK2sJyiiTCikCHxeEY9"
    "MXwxumCe4Yz8kcYm/hATPgaaQc9mielqIJYpAEymKrgbqQAoFQDpBAu4fKiunL0phvCq9+"
    "ZkcHJ2fHpyxk3kMCPJ4Mn/6RiM7yjxTFTlSeohg76FZBxD1eeQgTyy55ZZCDfh9HvCIc8y"
    "xKEgZhzHVX2Q/+r1jo8Hve7x6Vn/ZDDon3Uj2uuqMuzn43eCPDcgfJn4qyd8FQn0BDPk80"
    "qjV9FjEfjYJQOeT2cPwZcwVEefJUHHdb/bQjD5Z3h78X54++Jm+Pml1KwCzfV08i40j4FP"
    "Lq6n5xnkFC3JOu+LOaT5vEP7rWAH20RTWCsOfAQ2wiabi+2j3y+BH6LmVi8zVANVz9dlIp"
    "oigQPAnKC+5BpmOaggsFOeGdxG4Po6/LCHkc5DCRpTbK+CwCiL/PHN6E4d3vydCv/LoToS"
    "ml4q9EPpi9PMe4oe0vl3rL7viK+dL9PJSOIlLjOp/MXYTv2iiDFBjxGAyQOARiLVhdKQWu"
    "qtey6iuSmkMH8kPA4pf/xRkhZlz2yRm6MFrnW6V4Qiy8Qf0UpCHvMRQayjHKhBifcpeMye"
    "wX0KoyeUxmFJ4UNUJyaDis+dzxgxf3cf3l0ML0eKJKxBffEAqQFSqIWG9EhGEtmuq5yek5"
    "VADE0JR8xCjDmgfk30hZJTcEt5ab1tc4sdlNtfo6xmuS7XYc/RuOZbW4b/j2V4rYVJ01Z4"
    "DZVJKtQrhG/Grc1WOX2M2Kd46aatgNiCpbRCJOd7twX3RmEdwKteb6ccn6Hcbhj6PamuQy"
    "al5TUv65jnVllSsUd96UFhxCBKLSup391gIfW7hetIqMp2sGq9TK7vVnmiYWtox01Nmlt9"
    "7U3DKG/a3eSGWZP6HIk/p88JX0txnyMm1F4rHFY/Y1ps7mmVLxZSbs+yiTaBcs33CttU4X"
    "9cezeuydl98Y0caNlVIEcObXezEWB4z7cXCjyaQ7n4jiztdQio674lg7qOXJcn0wXClchn"
    "/Fr21dkzXs+ZFDqVU2fGsU2e2yXPCKMss4n23/pb+HA3nfzmHSSds6crls46Pzu25e5hT1"
    "iCV1ApXw3ZwD9Kn5WIB6zvRMy6R6Dq6XjG7RD2ofb2vr29f7bb+7VjmeIjgzg84r//ZZJS"
    "4Hf18RbZUJJdD4Lsvwz37P0XndKk148NeXQbILq33Z5TeDm8X3tUIaVdnjsNEbX0uZJz8h"
    "RojsrOnmBs0x4+1VzZ7ezw6R5RN1hem1YMCZf2+GPD7pwvqio1mW9+gHTfdDe5kOJWhXSl"
    "bsM/Bxd3H8V/Dq7WczSNdh1NR4WK6PmT2dMvEoLPyg=="
)
