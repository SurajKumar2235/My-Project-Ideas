import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Ensure the project root is on PYTHONPATH so sibling packages like `bot` can be imported
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from bot import db
from api.auth import router as auth_router
from api.routers.drafts import router as drafts_router
from api.routers.push import router as push_router
from api.routers.tasks import router as tasks_router
from api.routers.board import router as board_router
from api.routers.repos import router as repos_router
from api.routers.bot_api import router as bot_api_router

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Tortoise ORM for API server...")
    from tortoise import Tortoise
    from core.db_config import TORTOISE_ORM
    try:
        await Tortoise.init(
            config=TORTOISE_ORM,
            _enable_global_fallback=True
        )
        await Tortoise.generate_schemas()
        logger.info("Tortoise ORM initialized and schemas generated successfully.")
        
        # Deduplicate user records in DB
        from core.models import User
        all_users = await User.all().order_by("telegram_id", "-id")
        seen_tg_ids = set()
        for user_row in all_users:
            if user_row.telegram_id:
                if user_row.telegram_id in seen_tg_ids:
                    logger.info(f"Removing duplicate user record ID {user_row.id} for Telegram ID {user_row.telegram_id}")
                    try:
                        await user_row.delete()
                    except Exception as de:
                        logger.warning(f"Could not delete duplicate user {user_row.id}: {de}")
                else:
                    seen_tg_ids.add(user_row.telegram_id)

        # Initialize default superadmin users from ADMIN_USER_IDS
        admin_ids_str = os.environ.get("ADMIN_USER_IDS", "")
        admin_ids = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip().isdigit()]
        for admin_tg_id in admin_ids:
            u = await User.filter(telegram_id=admin_tg_id).order_by("-id").first()
            if u:
                if u.role not in ("admin", "superadmin"):
                    u.role = "superadmin"
                    await u.save()
                    logger.info(f"Promoted Telegram ID {admin_tg_id} to superadmin.")
            else:
                await User.create(
                    telegram_id=admin_tg_id,
                    username=f"Superadmin_{admin_tg_id}",
                    role="superadmin"
                )
                logger.info(f"Created default superadmin DB record for Telegram ID {admin_tg_id}.")
    except Exception as e:
        logger.exception("Failed to initialize Tortoise ORM:")
    yield
    logger.info("Closing Tortoise ORM connections...")
    await Tortoise.close_connections()


app = FastAPI(
    title="LogicalFire - AI Project Manager API & Platform",
    description=(
        "Complete REST APIs for LogicalFire Telegram/Web Project Manager Bot with GitHub OAuth, "
        "Groq Plan Formatting, GitHub Issue Creation, and Interactive Kanban Board."
    ),
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static Files Mount
STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Include Routers
app.include_router(auth_router)
app.include_router(drafts_router)
app.include_router(push_router)
app.include_router(tasks_router)
app.include_router(board_router)
app.include_router(repos_router)
app.include_router(bot_api_router)


@app.get("/", response_class=HTMLResponse, summary="LogicalFire Home Page")
@app.get("/home", response_class=HTMLResponse, summary="LogicalFire Home Page")
async def home_page():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse("<h1>LogicalFire Home Page</h1>")


@app.get("/get", response_class=HTMLResponse, summary="LogicalFire GET Route Explorer & Quickstart")
async def get_page():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse("<h1>LogicalFire GET Page</h1>")


@app.get("/api/info", summary="API Root Overview")
async def api_info():
    return {
        "title": "LogicalFire API",
        "version": "1.0.0",
        "documentation": "/docs",
        "openapi_spec": "/openapi.json",
        "endpoints": {
            "auth": {
                "login_via_github": "/login or /auth/github/login",
                "github_callback": "/auth/github/callback",
                "login_with_token": "POST /auth/github/token",
                "register": "POST /auth/register",
                "login": "POST /auth/login",
                "profile": "GET /auth/me"
            },
            "drafts": {
                "create_plan": "POST /api/drafts/plan",
                "list": "GET /api/drafts",
                "get": "GET /api/drafts/{draft_id}",
                "delete": "DELETE /api/drafts/{draft_id}"
            },
            "push": {
                "push_to_github": "POST /api/push"
            },
            "tasks": {
                "create_or_bulk_parse": "POST /api/tasks"
            },
            "board": {
                "get_kanban": "GET /api/board",
                "claim_card": "POST /api/board/{issue_number}/claim",
                "release_card": "POST /api/board/{issue_number}/release",
                "mark_done": "POST /api/board/{issue_number}/done"
            }
        }
    }


@app.get("/health", summary="Health Check")
async def health_check():
    return {"status": "ok", "service": "logicalfire-api"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)

