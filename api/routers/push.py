import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from bot import db
from client import github_client
from bot.models import User
from api.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/push", tags=["Push to GitHub"])


class PushRequest(BaseModel):
    draft_id: Optional[int] = None
    chat_id: Optional[int] = None


@router.post("", summary="Push Draft to GitHub Issue")
async def push_draft_to_github(
    body: PushRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Pushes a draft to GitHub as a TODO issue and initializes a lock in database.
    If draft_id is not specified, pushes the latest draft for the current user.
    """
    user_id = current_user.id
    target_chat_id = body.chat_id if body.chat_id is not None else user_id

    draft = None
    if body.draft_id:
        draft = db.get_draft_by_id(body.draft_id)
        if not draft:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Draft #{body.draft_id} not found."
            )
    else:
        draft = db.get_latest_draft(target_chat_id, user_id)
        if not draft:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No pending drafts found. Use /api/drafts/plan first to generate a draft."
            )

    content = draft.content.strip()
    lines = content.split("\n")
    first_line = lines[0] if lines else "Untitled Idea"
    title = first_line.lstrip("#").strip()
    body_text = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""

    try:
        # Create GitHub issue
        issue = await github_client.create_github_issue(title, body_text)
        issue_number = issue.get("number")
        html_url = issue.get("html_url")

        # Save initial lock entry
        db.save_lock(db.Lock(
            issue_number=issue_number,
            repo=github_client.GITHUB_PROJECT,
            status="todo"
        ))

        # Delete draft
        db.delete_draft_by_id(draft.id)

        return {
            "status": "success",
            "message": "Draft successfully pushed to GitHub Issue",
            "issue_number": issue_number,
            "html_url": html_url,
            "title": title,
            "issue_status": "todo"
        }
    except Exception as e:
        logger.exception("Error pushing draft to GitHub:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to push to GitHub: {str(e)}"
        )
