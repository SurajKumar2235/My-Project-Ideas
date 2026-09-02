import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from bot import db, locking
from client import github_client
from bot.models import User
from api.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/board", tags=["Kanban Board"])


@router.get("", summary="Get Kanban Board")
async def get_kanban_board(
    current_user: User = Depends(get_current_user)
):
    """
    Returns open GitHub issues categorized into 'todo', 'doing', and 'done' columns,
    along with lock information (who claimed each issue).
    """
    try:
        gh_issues = await github_client.list_github_issues()
    except Exception as e:
        logger.exception("Error listing GitHub issues:")
        gh_issues = []

    db_locks = db.get_all_locks()
    locks_by_issue: Dict[int, Any] = {l.issue_number: l for l in db_locks}

    board = {
        "todo": [],
        "doing": [],
        "done": []
    }

    for issue in gh_issues:
        issue_number = issue.get("number")
        title = issue.get("title")
        html_url = issue.get("html_url")
        
        lock = locks_by_issue.get(issue_number)
        status_name = lock.status if lock else "todo"
        
        # Determine status label override if present on GitHub
        labels = [lbl.get("name") for lbl in issue.get("labels", []) if isinstance(lbl, dict)]
        if "status:doing" in labels:
            status_name = "doing"
        elif "status:done" in labels:
            status_name = "done"

        card_info = {
            "issue_number": issue_number,
            "title": title,
            "html_url": html_url,
            "status": status_name,
            "locked_by_user_id": lock.locked_by_user_id if lock else None,
            "locked_by_username": lock.locked_by_username if lock else None,
            "locked_at": lock.locked_at if lock else None,
            "is_claimed_by_me": (lock.locked_by_user_id == current_user.id) if (lock and lock.locked_by_user_id) else False
        }

        if status_name in board:
            board[status_name].append(card_info)
        else:
            board["todo"].append(card_info)

    return {
        "status": "success",
        "board": board,
        "counts": {
            "todo": len(board["todo"]),
            "doing": len(board["doing"]),
            "done": len(board["done"])
        }
    }


@router.post("/{issue_number}/claim", summary="Claim a Card")
async def claim_card(
    issue_number: int,
    current_user: User = Depends(get_current_user)
):
    """
    Claims an issue card for the logged in user, moving it to 'doing' status.
    """
    user_id = current_user.id
    username = current_user.username

    res = await locking.claim_card(issue_number, user_id, username)
    if res == "claimed":
        return {
            "status": "success",
            "message": f"Successfully claimed issue #{issue_number}",
            "claim_result": res,
            "claimed_by": username
        }
    elif res == "already_claimed_by_you":
        return {
            "status": "success",
            "message": f"Issue #{issue_number} is already claimed by you",
            "claim_result": res
        }
    elif res == "already_claimed_by_other":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Issue #{issue_number} is already claimed by another user."
        )
    elif res == "already_done":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Issue #{issue_number} is already marked as done."
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to claim issue #{issue_number}: {res}"
        )


@router.post("/{issue_number}/release", summary="Release a Card")
async def release_card(
    issue_number: int,
    is_admin: Optional[bool] = False,
    current_user: User = Depends(get_current_user)
):
    """
    Releases a claimed card back to 'todo' status.
    """
    user_id = current_user.id
    res = await locking.release_card(issue_number, user_id, is_admin=is_admin)

    if res == "released":
        return {
            "status": "success",
            "message": f"Successfully released issue #{issue_number} back to TODO"
        }
    elif res == "not_claimed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Issue #{issue_number} is not currently claimed."
        )
    elif res == "unauthorized":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not own the claim for issue #{issue_number}."
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to release issue #{issue_number}: {res}"
        )


@router.post("/{issue_number}/done", summary="Mark Card Done")
async def mark_card_done(
    issue_number: int,
    current_user: User = Depends(get_current_user)
):
    """
    Marks a claimed card as completed ('done').
    """
    user_id = current_user.id
    res = await locking.mark_card_done(issue_number, user_id)

    if res == "marked_done":
        return {
            "status": "success",
            "message": f"Successfully marked issue #{issue_number} as DONE"
        }
    elif res == "not_claimed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Issue #{issue_number} is not currently claimed."
        )
    elif res == "unauthorized":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not own the claim for issue #{issue_number}."
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to mark issue #{issue_number} done: {res}"
        )
