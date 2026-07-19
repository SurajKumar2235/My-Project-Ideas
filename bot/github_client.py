import os
import httpx
import logging
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "")

# Parse owner and repo
if "/" in GITHUB_REPO:
    GITHUB_OWNER, GITHUB_PROJECT = GITHUB_REPO.split("/", 1)
else:
    GITHUB_OWNER = os.environ.get("GITHUB_OWNER", "surajkumar2235")
    GITHUB_PROJECT = GITHUB_REPO

logger = logging.getLogger(__name__)

def get_headers():
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    return headers

async def create_github_issue(title: str, body: str) -> dict:
    """
    Creates a new GitHub issue and labels it as 'status:todo'.
    """
    if not GITHUB_PROJECT:
        raise ValueError("GITHUB_REPO environment variable is not configured.")

    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_PROJECT}/issues"
    payload = {
        "title": title,
        "body": body,
        "labels": ["status:todo"]
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, headers=get_headers(), json=payload)
        response.raise_for_status()
        return response.json()

async def list_github_issues() -> list[dict]:
    """
    Lists open issues in the GitHub repository.
    """
    if not GITHUB_PROJECT:
        return []

    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_PROJECT}/issues"
    params = {
        "state": "open",
        "per_page": 100
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url, headers=get_headers(), params=params)
        if response.status_code == 404:
            logger.warning("Repository not found or token lacks permissions.")
            return []
        response.raise_for_status()
        return response.json()

async def assign_and_relabel_issue(issue_number: int, github_username: str | None, status_label: str) -> dict:
    """
    Updates the status label and assigns the issue to the given GitHub username.
    First tries to update both assignee and labels. If assignee update fails
    (e.g., user is not a collaborator), falls back to updating labels only.
    """
    if not GITHUB_PROJECT:
        raise ValueError("GITHUB_REPO environment variable is not configured.")

    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_PROJECT}/issues/{issue_number}"
    
    # 1. Fetch current issue to retrieve existing non-status labels
    async with httpx.AsyncClient(timeout=10.0) as client:
        get_resp = await client.get(url, headers=get_headers())
        get_resp.raise_for_status()
        issue_data = get_resp.json()
        
        current_labels = [label["name"] for label in issue_data.get("labels", [])]
        
        # Filter out existing status labels: 'status:todo', 'status:doing', 'status:done'
        filtered_labels = [l for l in current_labels if not l.startswith("status:")]
        filtered_labels.append(status_label)

        # 2. Attempt patching with both labels and assignees
        payload = {
            "labels": filtered_labels
        }
        if github_username:
            payload["assignees"] = [github_username]
            
        patch_resp = await client.patch(url, headers=get_headers(), json=payload)
        
        if patch_resp.status_code == 422 and github_username:
            logger.warning(
                f"Failed to assign user '{github_username}' to issue #{issue_number}. "
                "Retrying without assignee modification."
            )
            # Fallback to updating labels only
            payload.pop("assignees", None)
            patch_resp = await client.patch(url, headers=get_headers(), json=payload)
            
        patch_resp.raise_for_status()
        return patch_resp.json()
