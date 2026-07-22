import psycopg2
from psycopg2.extras import RealDictCursor
import os
import contextlib
from datetime import datetime, timezone
from typing import Optional, List
from bot.models import Draft, Lock

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/bot")

def get_connection():
    return psycopg2.connect(DATABASE_URL)

@contextlib.contextmanager
def db_session():
    """
    Context manager that yields a database cursor, commits transactions on success,
    rolls back on error, and ensures the cursor and connection are closed.
    """
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

def init_db():
    with db_session() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS drafts (
                id SERIAL PRIMARY KEY,
                chat_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS locks (
                issue_number INTEGER PRIMARY KEY,
                repo TEXT NOT NULL,
                locked_by_user_id BIGINT,
                locked_by_username TEXT,
                locked_at TIMESTAMP WITH TIME ZONE,
                status TEXT DEFAULT 'todo'
            )
        """)

def save_draft(chat_id: int, user_id: int, content: str) -> Draft:
    with db_session() as cur:
        cur.execute(
            """
            INSERT INTO drafts (chat_id, user_id, content, created_at)
            VALUES (%s, %s, %s, %s)
            """,
            (chat_id, user_id, content, datetime.now(timezone.utc))
        )
    return get_latest_draft(chat_id, user_id)

def get_latest_draft(chat_id: int, user_id: int) -> Optional[Draft]:
    with db_session() as cur:
        cur.execute(
            "SELECT id, chat_id, user_id, content, created_at FROM drafts WHERE chat_id = %s AND user_id = %s ORDER BY created_at DESC LIMIT 1",
            (chat_id, user_id)
        )
        row = cur.fetchone()
        if not row:
            return None
        
        created_at_val = row["created_at"]
        if isinstance(created_at_val, datetime):
            created_at = created_at_val
        elif isinstance(created_at_val, str):
            try:
                created_at = datetime.fromisoformat(created_at_val)
            except ValueError:
                created_at = datetime.now(timezone.utc)
        else:
            created_at = datetime.now(timezone.utc)
            
        return Draft(
            id=row["id"],
            chat_id=row["chat_id"],
            user_id=row["user_id"],
            content=row["content"],
            created_at=created_at
        )

def delete_draft_by_id(draft_id: int) -> bool:
    with db_session() as cur:
        cur.execute(
            "DELETE FROM drafts WHERE id = %s",
            (draft_id,)
        )
        return cur.rowcount > 0

def get_draft_by_id(draft_id: int) -> Optional[Draft]:
    with db_session() as cur:
        cur.execute(
            "SELECT id, chat_id, user_id, content, created_at FROM drafts WHERE id = %s",
            (draft_id,)
        )
        row = cur.fetchone()
        if not row:
            return None
        
        created_at_val = row["created_at"]
        if isinstance(created_at_val, datetime):
            created_at = created_at_val
        elif isinstance(created_at_val, str):
            try:
                created_at = datetime.fromisoformat(created_at_val)
            except ValueError:
                created_at = datetime.now(timezone.utc)
        else:
            created_at = datetime.now(timezone.utc)
            
        return Draft(
            id=row["id"],
            chat_id=row["chat_id"],
            user_id=row["user_id"],
            content=row["content"],
            created_at=created_at
        )

def get_all_user_drafts(chat_id: int, user_id: int) -> list[Draft]:
    with db_session() as cur:
        cur.execute(
            "SELECT id, chat_id, user_id, content, created_at FROM drafts WHERE chat_id = %s AND user_id = %s ORDER BY created_at ASC",
            (chat_id, user_id)
        )
        rows = cur.fetchall()
        drafts = []
        for row in rows:
            created_at_val = row["created_at"]
            if isinstance(created_at_val, datetime):
                created_at = created_at_val
            elif isinstance(created_at_val, str):
                try:
                    created_at = datetime.fromisoformat(created_at_val)
                except ValueError:
                    created_at = datetime.now(timezone.utc)
            else:
                created_at = datetime.now(timezone.utc)
                
            drafts.append(Draft(
                id=row["id"],
                chat_id=row["chat_id"],
                user_id=row["user_id"],
                content=row["content"],
                created_at=created_at
            ))
        return drafts

def save_lock(lock: Lock) -> None:
    with db_session() as cur:
        locked_at_val = lock.locked_at if lock.locked_at else None
        cur.execute(
            """
            INSERT INTO locks (issue_number, repo, locked_by_user_id, locked_by_username, locked_at, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (issue_number)
            DO UPDATE SET
                repo = EXCLUDED.repo,
                locked_by_user_id = EXCLUDED.locked_by_user_id,
                locked_by_username = EXCLUDED.locked_by_username,
                locked_at = EXCLUDED.locked_at,
                status = EXCLUDED.status
            """,
            (
                lock.issue_number,
                lock.repo,
                lock.locked_by_user_id,
                lock.locked_by_username,
                locked_at_val,
                lock.status
            )
        )

def get_lock(issue_number: int) -> Optional[Lock]:
    with db_session() as cur:
        cur.execute(
            "SELECT issue_number, repo, locked_by_user_id, locked_by_username, locked_at, status FROM locks WHERE issue_number = %s",
            (issue_number,)
        )
        row = cur.fetchone()
        if not row:
            return None
        
        locked_at_val = row["locked_at"]
        locked_at = None
        if locked_at_val:
            if isinstance(locked_at_val, datetime):
                locked_at = locked_at_val
            elif isinstance(locked_at_val, str):
                try:
                    locked_at = datetime.fromisoformat(locked_at_val)
                except ValueError:
                    pass
                
        return Lock(
            issue_number=row["issue_number"],
            repo=row["repo"],
            locked_by_user_id=row["locked_by_user_id"],
            locked_by_username=row["locked_by_username"],
            locked_at=locked_at,
            status=row["status"]
        )

def get_all_locks() -> List[Lock]:
    with db_session() as cur:
        cur.execute(
            "SELECT issue_number, repo, locked_by_user_id, locked_by_username, locked_at, status FROM locks"
        )
        rows = cur.fetchall()
        locks = []
        for row in rows:
            locked_at_val = row["locked_at"]
            locked_at = None
            if locked_at_val:
                if isinstance(locked_at_val, datetime):
                    locked_at = locked_at_val
                elif isinstance(locked_at_val, str):
                    try:
                        locked_at = datetime.fromisoformat(locked_at_val)
                    except ValueError:
                        pass
            locks.append(
                Lock(
                    issue_number=row["issue_number"],
                    repo=row["repo"],
                    locked_by_user_id=row["locked_by_user_id"],
                    locked_by_username=row["locked_by_username"],
                    locked_at=locked_at,
                    status=row["status"]
                )
            )
        return locks

def claim_lock_in_db(issue_number: int, user_id: int, username: str) -> bool:
    """
    Attempts to atomically claim a lock.
    Returns True if successfully claimed, False otherwise.
    """
    with db_session() as cur:
        now = datetime.now(timezone.utc)
        cur.execute(
            """
            UPDATE locks
            SET locked_by_user_id = %s, locked_by_username = %s, locked_at = %s, status = 'doing'
            WHERE issue_number = %s AND (locked_by_user_id IS NULL OR status = 'todo')
            """,
            (user_id, username, now, issue_number)
        )
        return cur.rowcount > 0

def release_lock_in_db(issue_number: int, user_id: int) -> bool:
    """
    Attempts to release a lock.
    Returns True if successfully released, False otherwise.
    Only allows release if the lock is held by user_id or is status 'doing'.
    """
    with db_session() as cur:
        cur.execute(
            """
            UPDATE locks
            SET locked_by_user_id = NULL, locked_by_username = NULL, locked_at = NULL, status = 'todo'
            WHERE issue_number = %s AND locked_by_user_id = %s
            """,
            (issue_number, user_id)
        )
        return cur.rowcount > 0

def force_release_lock_in_db(issue_number: int) -> bool:
    """
    Forces a lock release (useful for stale locks or admin commands).
    """
    with db_session() as cur:
        cur.execute(
            """
            UPDATE locks
            SET locked_by_user_id = NULL, locked_by_username = NULL, locked_at = NULL, status = 'todo'
            WHERE issue_number = %s
            """,
            (issue_number,)
        )
        return cur.rowcount > 0

def mark_lock_done_in_db(issue_number: int, user_id: int) -> bool:
    """
    Marks a lock as done.
    Only allows if the lock is currently claimed by the user_id.
    """
    with db_session() as cur:
        cur.execute(
            """
            UPDATE locks
            SET status = 'done'
            WHERE issue_number = %s AND locked_by_user_id = %s
            """,
            (issue_number, user_id)
        )
        return cur.rowcount > 0
