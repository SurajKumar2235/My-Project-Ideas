import sqlite3
import os
import contextlib
from datetime import datetime, timezone
from typing import Optional, List
from bot.models import Draft, Lock

DB_PATH = os.environ.get("DB_PATH", "bot.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@contextlib.contextmanager
def db_session():
    """
    Context manager that yields a connection, commits transactions on success,
    rolls back on error, and ensures the connection is closed.
    """
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    with db_session() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS drafts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS locks (
                issue_number INTEGER PRIMARY KEY,
                repo TEXT NOT NULL,
                locked_by_user_id INTEGER,
                locked_by_username TEXT,
                locked_at TIMESTAMP,
                status TEXT DEFAULT 'todo'
            )
        """)

def save_draft(chat_id: int, user_id: int, content: str) -> Draft:
    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO drafts (chat_id, user_id, content, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (chat_id, user_id, content, datetime.now(timezone.utc).isoformat())
        )
    return get_latest_draft(chat_id, user_id)

def get_latest_draft(chat_id: int, user_id: int) -> Optional[Draft]:
    with db_session() as conn:
        cur = conn.execute(
            "SELECT id, chat_id, user_id, content, created_at FROM drafts WHERE chat_id = ? AND user_id = ? ORDER BY created_at DESC LIMIT 1",
            (chat_id, user_id)
        )
        row = cur.fetchone()
        if not row:
            return None
        
        created_at_val = row["created_at"]
        if isinstance(created_at_val, str):
            try:
                # Remove timezone suffix if present or parse properly
                # python-fromisoformat can handle iso strings
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
    with db_session() as conn:
        cur = conn.execute(
            "DELETE FROM drafts WHERE id = ?",
            (draft_id,)
        )
        return cur.rowcount > 0

def get_draft_by_id(draft_id: int) -> Optional[Draft]:
    with db_session() as conn:
        cur = conn.execute(
            "SELECT id, chat_id, user_id, content, created_at FROM drafts WHERE id = ?",
            (draft_id,)
        )
        row = cur.fetchone()
        if not row:
            return None
        
        created_at_val = row["created_at"]
        if isinstance(created_at_val, str):
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
    with db_session() as conn:
        cur = conn.execute(
            "SELECT id, chat_id, user_id, content, created_at FROM drafts WHERE chat_id = ? AND user_id = ? ORDER BY created_at ASC",
            (chat_id, user_id)
        )
        rows = cur.fetchall()
        drafts = []
        for row in rows:
            created_at_val = row["created_at"]
            if isinstance(created_at_val, str):
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
    with db_session() as conn:
        locked_at_val = lock.locked_at.isoformat() if lock.locked_at else None
        conn.execute(
            """
            INSERT OR REPLACE INTO locks (issue_number, repo, locked_by_user_id, locked_by_username, locked_at, status)
            VALUES (?, ?, ?, ?, ?, ?)
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
    with db_session() as conn:
        cur = conn.execute(
            "SELECT issue_number, repo, locked_by_user_id, locked_by_username, locked_at, status FROM locks WHERE issue_number = ?",
            (issue_number,)
        )
        row = cur.fetchone()
        if not row:
            return None
        
        locked_at_val = row["locked_at"]
        locked_at = None
        if locked_at_val:
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
    with db_session() as conn:
        cur = conn.execute(
            "SELECT issue_number, repo, locked_by_user_id, locked_by_username, locked_at, status FROM locks"
        )
        rows = cur.fetchall()
        locks = []
        for row in rows:
            locked_at_val = row["locked_at"]
            locked_at = None
            if locked_at_val:
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
    with db_session() as conn:
        now_str = datetime.now(timezone.utc).isoformat()
        cur = conn.execute(
            """
            UPDATE locks
            SET locked_by_user_id = ?, locked_by_username = ?, locked_at = ?, status = 'doing'
            WHERE issue_number = ? AND (locked_by_user_id IS NULL OR status = 'todo')
            """,
            (user_id, username, now_str, issue_number)
        )
        return cur.rowcount > 0

def release_lock_in_db(issue_number: int, user_id: int) -> bool:
    """
    Attempts to release a lock.
    Returns True if successfully released, False otherwise.
    Only allows release if the lock is held by user_id or is status 'doing'.
    """
    with db_session() as conn:
        cur = conn.execute(
            """
            UPDATE locks
            SET locked_by_user_id = NULL, locked_by_username = NULL, locked_at = NULL, status = 'todo'
            WHERE issue_number = ? AND locked_by_user_id = ?
            """,
            (issue_number, user_id)
        )
        return cur.rowcount > 0

def force_release_lock_in_db(issue_number: int) -> bool:
    """
    Forces a lock release (useful for stale locks or admin commands).
    """
    with db_session() as conn:
        cur = conn.execute(
            """
            UPDATE locks
            SET locked_by_user_id = NULL, locked_by_username = NULL, locked_at = NULL, status = 'todo'
            WHERE issue_number = ?
            """,
            (issue_number,)
        )
        return cur.rowcount > 0

def mark_lock_done_in_db(issue_number: int, user_id: int) -> bool:
    """
    Marks a lock as done.
    Only allows if the lock is currently claimed by the user_id.
    """
    with db_session() as conn:
        cur = conn.execute(
            """
            UPDATE locks
            SET status = 'done'
            WHERE issue_number = ? AND locked_by_user_id = ?
            """,
            (issue_number, user_id)
        )
        return cur.rowcount > 0
