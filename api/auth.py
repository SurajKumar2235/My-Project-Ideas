import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
import httpx
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr

from core.models import User

logger = logging.getLogger(__name__)

# Config
GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
GITHUB_REDIRECT_URI = os.environ.get("GITHUB_REDIRECT_URI", "")

JWT_SECRET = os.environ.get("JWT_SECRET", "super-secret-jwt-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24 * 7  # 7 days

router = APIRouter(tags=["Authentication"])
security = HTTPBearer(auto_error=False)


class RegisterRequest(BaseModel):
    username: str
    email: Optional[EmailStr] = None
    avatar_url: Optional[str] = None


class LoginRequest(BaseModel):
    username: str


class GitHubTokenRequest(BaseModel):
    access_token: str


def create_jwt_token(user: User) -> str:
    expiration = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "github_id": user.github_id,
        "exp": expiration
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token"
        )


async def get_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security),
    token: Optional[str] = Query(None)
) -> User:
    jwt_token = None
    if auth and auth.credentials:
        jwt_token = auth.credentials
    elif token:
        jwt_token = token

    if not jwt_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a Bearer token."
        )

    payload = decode_jwt_token(jwt_token)
    user_id = int(payload.get("sub"))
    user = await User.get_or_none(id=user_id)
    if not user:
        username = payload.get("username")
        if username:
            user = await User.get_or_none(username=username)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User associated with token not found"
        )

    return user


@router.get("/login", summary="GitHub OAuth Login (Redirect)")
@router.get("/auth/github/login", summary="Initiate GitHub OAuth Login")
async def github_oauth_login(redirect_uri: Optional[str] = None, state: Optional[str] = None):
    """
    Redirects the user to GitHub OAuth authorization URL.
    """
    if not GITHUB_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GITHUB_CLIENT_ID is not configured on the server."
        )

    callback_uri = redirect_uri or GITHUB_REDIRECT_URI
    scope = "read:user user:email repo"
    print(f"GitHub OAuth Login initiated. Redirect URI: {callback_uri}, State: {state}")
    github_auth_url = (
        f"https://github.com/login/oauth/authorize?"
        f"client_id={GITHUB_CLIENT_ID}"
        f"&scope={scope}"
    )
    if callback_uri:
        github_auth_url += f"&redirect_uri={callback_uri}"
    if state:
        github_auth_url += f"&state={state}"
    print(f"Redirecting to GitHub OAuth URL: {github_auth_url}")
    return RedirectResponse(url=github_auth_url)


@router.get("/auth/github/callback", summary="GitHub OAuth Callback")
async def github_oauth_callback(code: str, state: Optional[str] = None):
    """
    Callback endpoint for GitHub OAuth.
    Exchanges authorization code for access token and logs in/registers user.
    """
    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub OAuth credentials (CLIENT_ID / CLIENT_SECRET) are not configured."
        )

    token_url = "https://github.com/login/oauth/access_token"
    payload = {
        "client_id": GITHUB_CLIENT_ID,
        "client_secret": GITHUB_CLIENT_SECRET,
        "code": code
    }
    headers = {"Accept": "application/json"}

    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1. Exchange code for access_token
        token_resp = await client.post(token_url, json=payload, headers=headers)
        if token_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to exchange code for GitHub token: {token_resp.text}"
            )
        
        token_data = token_resp.json()
        github_access_token = token_data.get("access_token")
        if not github_access_token:
            error_desc = token_data.get("error_description", "No access_token returned by GitHub")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"GitHub OAuth error: {error_desc}"
            )

        # 2. Fetch user profile from GitHub
        user_resp = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"token {github_access_token}",
                "Accept": "application/vnd.github+json"
            }
        )
        if user_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to fetch GitHub user profile"
            )
        
        gh_user = user_resp.json()
        github_id = gh_user.get("id")
        username = gh_user.get("login")
        email = gh_user.get("email")
        avatar_url = gh_user.get("avatar_url")

        # Fetch email if private
        if not email:
            emails_resp = await client.get(
                "https://api.github.com/user/emails",
                headers={"Authorization": f"token {github_access_token}"}
            )
            if emails_resp.status_code == 200:
                emails = emails_resp.json()
                primary_email = next((e["email"] for e in emails if e.get("primary")), None)
                if primary_email:
                    email = primary_email

        # 3. Create or update user in database via Tortoise ORM
        user = await User.get_or_none(github_id=github_id)
        if user:
            user.username = username
            user.email = email
            user.avatar_url = avatar_url
            user.access_token = github_access_token
            await user.save()
        else:
            user = await User.create(
                github_id=github_id,
                username=username,
                email=email,
                avatar_url=avatar_url,
                access_token=github_access_token
            )

        # 4. Handle Telegram linkage state
        if state and state.startswith("telegram_"):
            try:
                parts = state.split("_")
                if len(parts) >= 3:
                    telegram_id = int(parts[1])
                    chat_id = int(parts[2])
                    
                    # Ensure no other user record holds this telegram_id
                    existing_tg_user = await User.get_or_none(telegram_id=telegram_id)
                    if existing_tg_user and existing_tg_user.id != user.id:
                        existing_tg_user.telegram_id = None
                        await existing_tg_user.save()

                    # Update user with Telegram ID
                    user.telegram_id = telegram_id
                    await user.save()

                    # Notify Telegram bot
                    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")
                    if telegram_token:
                        bot_url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
                        notification_payload = {
                            "chat_id": chat_id,
                            "text": (
                                f"🎉 *GitHub OAuth Successful!*\n\n"
                                f"Your Telegram account has been linked to GitHub user *{username}*.\n"
                                "You can now use commands like `/repo` to select a repository."
                            ),
                            "parse_mode": "Markdown"
                        }
                        await client.post(bot_url, json=notification_payload)
            except Exception as e:
                logger.error(f"Error handling Telegram state callback: {e}")

        # 5. Issue JWT access token
        jwt_token = create_jwt_token(user)

        return {
            "status": "success",
            "message": "GitHub OAuth login successful",
            "access_token": jwt_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "github_id": user.github_id,
                "username": user.username,
                "email": user.email,
                "avatar_url": user.avatar_url,
                "telegram_id": user.telegram_id,
                "active_repo": user.active_repo,
                "role": user.role
            }
        }


@router.post("/auth/github/token", summary="Login via existing GitHub Access Token")
async def github_token_login(body: GitHubTokenRequest):
    """
    Authenticate using an existing GitHub OAuth access token.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        user_resp = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"token {body.access_token}",
                "Accept": "application/vnd.github+json"
            }
        )
        if user_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid GitHub access token"
            )
        
        gh_user = user_resp.json()
        github_id = gh_user.get("id")
        username = gh_user.get("login")
        email = gh_user.get("email")
        avatar_url = gh_user.get("avatar_url")

        user = await User.get_or_none(github_id=github_id)
        if user:
            user.username = username
            user.email = email
            user.avatar_url = avatar_url
            user.access_token = body.access_token
            await user.save()
        else:
            user = await User.create(
                github_id=github_id,
                username=username,
                email=email,
                avatar_url=avatar_url,
                access_token=body.access_token
            )

        jwt_token = create_jwt_token(user)

        return {
            "status": "success",
            "access_token": jwt_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "github_id": user.github_id,
                "username": user.username,
                "email": user.email,
                "avatar_url": user.avatar_url,
                "telegram_id": user.telegram_id,
                "active_repo": user.active_repo,
                "role": user.role
            }
        }


@router.post("/auth/register", summary="Register user")
async def register_user(body: RegisterRequest):
    """
    Manually create/register a user in the system.
    """
    existing_user = await User.get_or_none(username=body.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User with username '{body.username}' already exists."
        )

    user = await User.create(username=body.username, email=body.email, avatar_url=body.avatar_url)
    jwt_token = create_jwt_token(user)

    return {
        "status": "success",
        "message": "User registered successfully",
        "access_token": jwt_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "github_id": user.github_id,
            "username": user.username,
            "email": user.email,
            "avatar_url": user.avatar_url,
            "role": user.role
        }
    }


@router.post("/auth/login", summary="Login user")
async def login_user(body: LoginRequest):
    """
    Login an existing user by username.
    """
    user = await User.get_or_none(username=body.username)
    if not user:
        user = await User.create(username=body.username)

    jwt_token = create_jwt_token(user)

    return {
        "status": "success",
        "message": "Login successful",
        "access_token": jwt_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "github_id": user.github_id,
            "username": user.username,
            "email": user.email,
            "avatar_url": user.avatar_url,
            "role": user.role
        }
    }


@router.get("/auth/me", summary="Get Current User Profile")
async def get_me(current_user: User = Depends(get_current_user)):
    """
    Returns profile information of the currently authenticated user.
    """
    return {
        "status": "success",
        "user": {
            "id": current_user.id,
            "github_id": current_user.github_id,
            "username": current_user.username,
            "email": current_user.email,
            "avatar_url": current_user.avatar_url,
            "telegram_id": current_user.telegram_id,
            "active_repo": current_user.active_repo,
            "role": current_user.role
        }
    }
