import os
import logging
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from bot import db, github_client

load_dotenv()

LOCK_TIMEOUT_HOURS = int(os.environ.get("LOCK_TIMEOUT_HOURS", "24"))
logger = logging.getLogger(__name__)

async def claim_card(issue_number: int, user_id: int, username: str) -> str:
    """
    Attempts to claim a card.
    Returns:
      - 'claimed': successfully claimed now.
      - 'already_claimed_by_you': user already had this card claimed.
      - 'already_claimed_by_other': another user has already claimed the card.
    """
    lock = db.get_lock(issue_number)
    
    # If the lock doesn't exist, create it as 'todo' first so it can be claimed
    if not lock:
        db.save_lock(db.Lock(
            issue_number=issue_number,
            repo=github_client.GITHUB_PROJECT,
            status="todo"
        ))
        lock = db.get_lock(issue_number)

    if lock.status == "doing":
        if lock.locked_by_user_id == user_id:
            return "already_claimed_by_you"
        else:
            return "already_claimed_by_other"
    
    if lock.status == "done":
        return "already_done"

    # Attempt atomic claim in DB
    success = db.claim_lock_in_db(issue_number, user_id, username)
    if not success:
        # Re-check in case database changed under us
        lock = db.get_lock(issue_number)
        if lock and lock.locked_by_user_id == user_id:
            return "already_claimed_by_you"
        return "already_claimed_by_other"

    # Sync to GitHub
    try:
        await github_client.assign_and_relabel_issue(issue_number, username, "status:doing")
    except Exception as e:
        logger.error(f"Failed to sync claim to GitHub for issue #{issue_number}: {e}")
        # Note: We keep the local lock even if GitHub fails to make the app resilient,
        # but let the caller know it succeeded locally.
        
    return "claimed"

async def release_card(issue_number: int, user_id: int, is_admin: bool = False) -> str:
    """
    Attempts to release a claimed card back to 'todo'.
    Returns:
      - 'released': successfully released.
      - 'not_claimed': the card was not currently claimed.
      - 'unauthorized': user is not the owner of the lock and not an admin.
    """
    lock = db.get_lock(issue_number)
    if not lock or lock.status != "doing":
        return "not_claimed"

    if not is_admin and lock.locked_by_user_id != user_id:
        return "unauthorized"

    # Release in DB
    if is_admin:
        success = db.force_release_lock_in_db(issue_number)
    else:
        success = db.release_lock_in_db(issue_number, user_id)

    if not success:
        return "not_released"

    # Sync to GitHub
    try:
        await github_client.assign_and_relabel_issue(issue_number, None, "status:todo")
    except Exception as e:
        logger.error(f"Failed to sync release to GitHub for issue #{issue_number}: {e}")

    return "released"

async def mark_card_done(issue_number: int, user_id: int) -> str:
    """
    Marks a claimed card as done.
    Returns:
      - 'marked_done': successfully marked done.
      - 'not_claimed': the card was not currently claimed.
      - 'unauthorized': user is not the owner of the lock.
    """
    lock = db.get_lock(issue_number)
    if not lock or lock.status != "doing":
        return "not_claimed"

    if lock.locked_by_user_id != user_id:
        return "unauthorized"

    # Update in DB
    success = db.mark_lock_done_in_db(issue_number, user_id)
    if not success:
        return "not_updated"

    # Sync to GitHub (keep assignee for credit, but set status:done)
    try:
        await github_client.assign_and_relabel_issue(issue_number, lock.locked_by_username, "status:done")
    except Exception as e:
        logger.error(f"Failed to sync mark-done to GitHub for issue #{issue_number}: {e}")

    return "marked_done"

async def expire_stale_locks() -> list[tuple[int, str]]:
    """
    Finds and releases locks that have expired.
    Returns a list of tuples containing (issue_number, username) of released locks.
    """
    locks = db.get_all_locks()
    now = datetime.now(timezone.utc)
    expired_issues = []
    
    timeout_limit = now - timedelta(hours=LOCK_TIMEOUT_HOURS)

    for lock in locks:
        if lock.status == "doing" and lock.locked_at:
            if lock.locked_at < timeout_limit:
                logger.info(f"Lock on issue #{lock.issue_number} is stale (locked at {lock.locked_at}). Expiring.")
                success = db.force_release_lock_in_db(lock.issue_number)
                if success:
                    try:
                        await github_client.assign_and_relabel_issue(lock.issue_number, None, "status:todo")
                        expired_issues.append((lock.issue_number, lock.locked_by_username or "Unknown"))
                    except Exception as e:
                        logger.error(f"Failed to sync stale release for issue #{lock.issue_number} to GitHub: {e}")
                        
    return expired_issues
