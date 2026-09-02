import os
import re
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from bot import db, groq_client
from bot.models import Draft, User
from api.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/drafts", tags=["Drafts"])


class PlanRequest(BaseModel):
    idea: str
    chat_id: Optional[int] = 0


def sanitize_filename(title: str) -> str:
    cleaned = re.sub(r'[#\*\?\\\/\:\<\>\|\"]', '', title)
    cleaned = re.sub(r'\s+', '-', cleaned.strip()).lower()
    cleaned = re.sub(r'[^a-z0-9\-]', '', cleaned)
    return cleaned if cleaned else "project-plan"


@router.post("/plan", summary="Generate & Draft Idea Plan")
async def plan_idea(
    body: PlanRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Submits a raw project idea, formats it using Groq LLM into structured markdown,
    saves it to local storage and the database as a draft.
    """
    if not body.idea.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idea description cannot be empty."
        )

    try:
        formatted_markdown = await groq_client.format_idea_to_markdown(body.idea, use_reasoning=True)
        
        user_id = current_user.id
        chat_id = body.chat_id or current_user.id

        # Save to database
        draft = db.save_draft(chat_id, user_id, formatted_markdown)

        # Save to file
        lines = formatted_markdown.strip().split("\n")
        first_line = lines[0] if lines else "Project Plan"
        title = first_line.lstrip("#").strip()
        filename = f"{sanitize_filename(title)}.md"
        
        plans_dir = os.environ.get("PLANS_DIR", "")
        if plans_dir:
            os.makedirs(plans_dir, exist_ok=True)
            filepath = os.path.join(plans_dir, filename)
        else:
            filepath = filename

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(formatted_markdown)

        return {
            "status": "success",
            "message": "Idea plan formatted and saved successfully",
            "filename": filename,
            "draft": draft,
            "formatted_markdown": formatted_markdown
        }
    except Exception as e:
        logger.exception("Error formatting idea plan:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to format plan: {str(e)}"
        )


@router.get("", summary="List User Drafts")
async def list_drafts(
    chat_id: Optional[int] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves all pending drafts for the logged in user.
    """
    user_id = current_user.id
    target_chat_id = chat_id if chat_id is not None else user_id
    drafts = db.get_all_user_drafts(target_chat_id, user_id)
    return {
        "status": "success",
        "count": len(drafts),
        "drafts": drafts
    }


@router.get("/{draft_id}", summary="Get Specific Draft")
async def get_draft(
    draft_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves a draft by ID.
    """
    draft = db.get_draft_by_id(draft_id)
    if not draft:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Draft with ID {draft_id} not found."
        )
    return {
        "status": "success",
        "draft": draft
    }


@router.delete("/{draft_id}", summary="Delete Draft")
async def delete_draft(
    draft_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Deletes a draft by ID.
    """
    draft = db.get_draft_by_id(draft_id)
    if not draft:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Draft with ID {draft_id} not found."
        )
    
    deleted = db.delete_draft_by_id(draft_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete draft from database."
        )
        
    return {
        "status": "success",
        "message": f"Draft #{draft_id} deleted successfully."
    }
