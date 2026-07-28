import logging
import httpx
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from core.models import User
from api.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/github", tags=["GitHub Repositories"])


class ActiveRepoRequest(BaseModel):
    repo: str


@router.get("/repos", summary="List User GitHub Repositories")
async def list_user_repos(current_user: User = Depends(get_current_user)):
    """
    Lists repositories that the authenticated user has access to on GitHub.
    """
    if not current_user.access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has not connected their GitHub account."
        )

    url = "https://api.github.com/user/repos"
    params = {
        "sort": "updated",
        "per_page": 100
    }
    headers = {
        "Authorization": f"token {current_user.access_token}",
        "Accept": "application/vnd.github+json"
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url, headers=headers, params=params)
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to fetch repositories from GitHub: {response.text}"
            )
        
        repos = response.json()
        result = []
        for r in repos:
            # We filter for repos where the user has push/admin permissions
            permissions = r.get("permissions", {})
            result.append({
                "id": r.get("id"),
                "name": r.get("name"),
                "full_name": r.get("full_name"),
                "private": r.get("private"),
                "html_url": r.get("html_url"),
                "description": r.get("description"),
                "permissions": permissions
            })
        return {
            "status": "success",
            "repos": result
        }


@router.post("/active_repo", summary="Set Active Repository")
async def set_active_repo(body: ActiveRepoRequest, current_user: User = Depends(get_current_user)):
    """
    Sets the active repository for the authenticated user.
    Verifies that the user has write access to the repository on GitHub.
    """
    if not current_user.access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has not connected their GitHub account."
        )

    repo_fullname = body.repo.strip()
    if "/" not in repo_fullname:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid repository format. Must be 'owner/repo'."
        )

    # Verify user access and permissions on GitHub
    url = f"https://api.github.com/repos/{repo_fullname}"
    headers = {
        "Authorization": f"token {current_user.access_token}",
        "Accept": "application/vnd.github+json"
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url, headers=headers)
        if response.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Repository '{repo_fullname}' not found or you do not have permission to access it."
            )
        elif response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error checking repository access on GitHub: {response.text}"
            )

        repo_data = response.json()
        permissions = repo_data.get("permissions", {})
        
        # Check for push (write) or admin access
        has_write_access = permissions.get("push", False) or permissions.get("admin", False)
        
        if not has_write_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You do not have write (push) access to repository '{repo_fullname}'."
            )

        # Update user's active repo
        current_user.active_repo = repo_fullname
        await current_user.save()

        return {
            "status": "success",
            "message": f"Active repository set successfully to '{repo_fullname}'.",
            "active_repo": repo_fullname
        }
