from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "users" ADD "role" VARCHAR(50) NOT NULL DEFAULT 'user';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "users" DROP COLUMN "role";"""


MODELS_STATE = (
    "eJztmltz2jgUgP8K46d2Ju1QEkK2byQhLW0COwnd7bTT0ci2MF5sicpyEqbNf68kW75hu5"
    "gGLzB+g3Oxpc9HOkfH/qG5xESO9/qSwinT3rZ+aBi6iP9IK45aGlwsYrEQMKg70tIUJlIE"
    "dY9RaIgLTaHjIS4ykWdQe8FsgrkU+44jhMTghja2YpGP7e8+AoxYiM0Q5Yqv37jYxiZ6RJ"
    "76u5iDqY0cMzVS2xT3lnLAlgspG2J2JQ3F3XRgEMd3cWy8WLIZwZG1jeUULYQRhQyJyzPq"
    "i+GL0YXzVDMKRhqbBENM+JhoCn2HJaarg1imATAaT8DdYAKAVgGQQbCAy4fqydlbYgivOm"
    "9Oeidnx6cnZ9xEDjOS9J6CW8dgAkeJZzTRnqQeMhhYSMYxVGMGGcgje25bhXATTr8nrHiW"
    "IVaCmHEcV/VB/qvTOT7uddrHp2fdk16ve9aOaK+qyrCfD98J8tyA8GUSrB71KBLoCWYo4J"
    "VGP0GPReBjlwx4Pp09BF/CcDL4LAm6nvfdEYLRP/3bi/f92xc3/c8vpWYZaq7Ho3fKPAY+"
    "urgen2eQU7Qgq7wvZpDm81b2G8EOt4ldYa258BE4CFtsJraPbrcEvkLNrV5mqIaqTqDLRD"
    "RFAgeAOUF9yTXMdlFBYKc8M7jN0PW1+rGHkc5DCZpj7CzDwCiL/OHN4G7Sv/k7Ff6X/clA"
    "aDqp0FfSF6eZ5xRdpPXvcPK+Jf62voxHA4mXeMyi8o6x3eSLJsYEfUYAJg8AmolUp6SKWu"
    "qp+x6iuSmkMH8kPA4pf/xRkhZlz3Sem6MFrlW6V4Qi28If0VJCHvIRQWygHKhhifcpvMye"
    "wX1S0aOkcVhS+BDVicmg4nPnM0Ys2N37dxf9y4EmCevQmD9AaoIUaqEhHZKRRLarKrfjZi"
    "UQQ0vCEbMQYw6pXxNjruUU3FJeWm873GIL5fbXKKvZnsd12Hd1rvnWlOH/Yxlea2Gyayu8"
    "hsokFeoVwjfj1mSrnHOM2Kd46aYvgdiCpbRCJOd7NwX3WmEdwqteb6ccn6Hc3jH0e1JdKy"
    "al5TUv65jvVVlSsUd96UFjxCRaLSup215jIXXbhetIqMp2sGpnmVzfjfLEjq2hLR9q0tzq"
    "O97sGOV1Tze5YbZL5xyJP+ecox5L8TlHTKh5rXBY5xnLZjNfr/xiIeX2LJvoLlCu+b3CJl"
    "X4H9feO3fI2X7xjVxoO1UgRw7N6WYtwPCeby8U+DSHcvE7srTXIaCu+y0ZNAzkeTyZzhGu"
    "RD7j17Cvzp7xes6i0K2cOjOOTfLcLHlGGGWZTfT/Vp/Ch7vx6DfPIOmc7a7YBmv9bDm2t4"
    "dnwhK8gkr5asgG/lG6VyIusLoTMfsegard8YzbIexDNaRbSpxKNaOyr7HJpFoF+9hkaj6O"
    "KEZ/WB9HrHS9ijsycXjEX1dmcn7od/XxFjlQkl0NguxHnHv2/IuaYOn140Ae3SaIXotvzk"
    "m9e9+vFFBIaZttvT6itjHTchp7oeaorLUHY5umt1dz4by13t49ol64vNYtFRIuTXdpzeYH"
    "X1RVSt7A/ADpvmmvU4pxq0K6Urfmt9fFh7vib6+rHel2jXYdZ7oKFdHzJ7OnX8aAPo4="
)
