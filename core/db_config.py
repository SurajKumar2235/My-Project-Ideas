import os
from dotenv import load_dotenv

# Load environmental variables
load_dotenv()

db_url = os.environ.get("DATABASE_URL")
if db_url:
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgres://", 1)
    if "?" in db_url:
        base_url = db_url.split("?")[0]
        db_url = f"{base_url}?ssl=true"
else:
    db_url = "sqlite://db.sqlite3"

TORTOISE_ORM = {
    "connections": {"default": db_url},
    "apps": {
        "models": {
            "models": ["core.models", "aerich.models"],
            "default_connection": "default",
        }
    },
    "use_tz": True,
    "timezone": "UTC"
}
