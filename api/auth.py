import json
import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
import httpx
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr

from core.models import User

logger = logging.getLogger(__name__)

# Config
GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
GITHUB_REDIRECT_URI = os.environ.get("GITHUB_REDIRECT_URI", "")
TELEGRAM_BOT_USERNAME = os.environ.get("TELEGRAM_BOT_USERNAME", "")

JWT_SECRET = os.environ.get("JWT_SECRET", "super-secret-jwt-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24 * 7  # 7 days

router = APIRouter(tags=["Authentication"])
security = HTTPBearer(auto_error=False)


def render_oauth_success_html(user: dict, jwt_token: str, is_telegram: bool) -> str:
    username = user.get("username") or "Developer"
    avatar_url = user.get("avatar_url") or "https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png"
    user_json = json.dumps(user)
    bot_username = TELEGRAM_BOT_USERNAME.lstrip("@")
    telegram_url = f"https://t.me/{bot_username}" if bot_username else "tg://open"

    telegram_badge = """
      <div class="status-pill telegram">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"/>
        </svg>
        Telegram Linked
      </div>
    """ if is_telegram else """
      <div class="status-pill github">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/>
        </svg>
        GitHub Verified
      </div>
    """

    action_buttons = f"""
      <a href="{telegram_url}" class="btn btn-telegram">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"/>
        </svg>
        Return to Telegram
      </a>
      <a href="/" class="btn btn-secondary">Open Web Dashboard</a>
    """ if is_telegram else """
      <a href="/" class="btn btn-primary">Go to Web Dashboard</a>
      <a href="/docs" class="btn btn-secondary">API Documentation</a>
    """

    title_text = "Telegram Account Linked!" if is_telegram else "Authentication Successful!"
    subtitle_text = (
        f"Your Telegram account has been linked to <strong>@{username}</strong>. You can now return to your bot chat to run commands."
        if is_telegram else
        f"Welcome back, <strong>@{username}</strong>! Your session is authenticated and ready to go."
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>LogicalFire - {title_text}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@500;600;700;800&family=Inter:wght@400;500;600&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg-primary: #080b11;
      --bg-card: rgba(22, 28, 46, 0.75);
      --border-color: rgba(255, 255, 255, 0.08);
      --flame-gradient: linear-gradient(135deg, #ff3b00 0%, #ff7300 50%, #ffa200 100%);
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --text-dim: #64748b;
      --green-accent: #00e676;
      --telegram-blue: #0088cc;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background-color: var(--bg-primary);
      background-image: 
        radial-gradient(circle at 50% 20%, rgba(255, 69, 0, 0.14) 0%, transparent 60%),
        radial-gradient(circle at 80% 80%, rgba(0, 136, 204, 0.1) 0%, transparent 50%);
      color: var(--text-main);
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 24px;
    }}
    .container {{
      background: var(--bg-card);
      backdrop-filter: blur(18px);
      -webkit-backdrop-filter: blur(18px);
      border: 1px solid var(--border-color);
      box-shadow: 0 24px 60px rgba(0, 0, 0, 0.6), 0 0 35px rgba(255, 69, 0, 0.12);
      border-radius: 24px;
      width: 100%;
      max-width: 460px;
      padding: 40px 32px;
      text-align: center;
      animation: fadeIn 0.4s cubic-bezier(0.16, 1, 0.3, 1);
    }}
    @keyframes fadeIn {{
      from {{ opacity: 0; transform: translateY(16px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}
    .icon-badge {{
      width: 72px;
      height: 72px;
      background: rgba(0, 230, 118, 0.12);
      border: 2px solid rgba(0, 230, 118, 0.4);
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      margin: 0 auto 20px;
      box-shadow: 0 0 30px rgba(0, 230, 118, 0.25);
    }}
    .icon-badge svg {{
      width: 36px;
      height: 36px;
      fill: none;
      stroke: var(--green-accent);
      stroke-width: 2.5;
      stroke-linecap: round;
      stroke-linejoin: round;
    }}
    h1 {{
      font-family: 'Outfit', sans-serif;
      font-size: 24px;
      font-weight: 700;
      letter-spacing: -0.4px;
      margin-bottom: 8px;
    }}
    .subtitle {{
      color: var(--text-muted);
      font-size: 14px;
      line-height: 1.55;
      margin-bottom: 24px;
    }}
    .user-card {{
      background: rgba(15, 20, 32, 0.85);
      border: 1px solid rgba(255, 255, 255, 0.06);
      border-radius: 16px;
      padding: 14px 18px;
      display: flex;
      align-items: center;
      gap: 14px;
      margin-bottom: 26px;
      text-align: left;
    }}
    .avatar {{
      width: 48px;
      height: 48px;
      border-radius: 50%;
      border: 2px solid rgba(255, 255, 255, 0.15);
      object-fit: cover;
      background: #1e293b;
    }}
    .user-meta {{
      flex: 1;
      overflow: hidden;
    }}
    .user-meta .username {{
      font-weight: 600;
      font-size: 15px;
      color: #fff;
    }}
    .user-meta .repo-info {{
      color: var(--text-dim);
      font-size: 12px;
      font-family: 'Fira Code', monospace;
      margin-top: 2px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .status-pill {{
      display: inline-flex;
      align-items: center;
      gap: 5px;
      font-size: 11px;
      font-weight: 600;
      padding: 4px 8px;
      border-radius: 20px;
    }}
    .status-pill.telegram {{
      background: rgba(0, 136, 204, 0.15);
      color: #38bdf8;
      border: 1px solid rgba(0, 136, 204, 0.3);
    }}
    .status-pill.github {{
      background: rgba(0, 230, 118, 0.15);
      color: var(--green-accent);
      border: 1px solid rgba(0, 230, 118, 0.3);
    }}
    .btn-stack {{
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}
    .btn {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      width: 100%;
      padding: 13px 18px;
      border-radius: 12px;
      font-weight: 600;
      font-size: 14px;
      text-decoration: none;
      transition: all 0.2s ease;
      cursor: pointer;
      border: none;
    }}
    .btn-telegram {{
      background: linear-gradient(135deg, #0088cc 0%, #0099e6 100%);
      color: #fff;
      box-shadow: 0 4px 16px rgba(0, 136, 204, 0.35);
    }}
    .btn-telegram:hover {{
      transform: translateY(-2px);
      box-shadow: 0 6px 22px rgba(0, 136, 204, 0.5);
    }}
    .btn-primary {{
      background: var(--flame-gradient);
      color: #fff;
      box-shadow: 0 4px 16px rgba(255, 69, 0, 0.35);
    }}
    .btn-primary:hover {{
      transform: translateY(-2px);
      box-shadow: 0 6px 22px rgba(255, 69, 0, 0.5);
    }}
    .btn-secondary {{
      background: rgba(255, 255, 255, 0.05);
      color: var(--text-main);
      border: 1px solid rgba(255, 255, 255, 0.08);
    }}
    .btn-secondary:hover {{
      background: rgba(255, 255, 255, 0.1);
      transform: translateY(-2px);
    }}
    .btn-close {{
      background: transparent;
      color: var(--text-dim);
      border: none;
      font-size: 12px;
      margin-top: 4px;
      text-decoration: underline;
      cursor: pointer;
    }}
    .btn-close:hover {{
      color: var(--text-muted);
    }}
    .footer-text {{
      margin-top: 20px;
      font-size: 12px;
      color: var(--text-dim);
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="icon-badge">
      <svg viewBox="0 0 24 24">
        <polyline points="20 6 9 17 4 12"></polyline>
      </svg>
    </div>

    <h1>{title_text}</h1>
    <p class="subtitle">{subtitle_text}</p>

    <div class="user-card">
      <img src="{avatar_url}" alt="{username}" class="avatar" onerror="this.src='https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png'">
      <div class="user-meta">
        <div class="username">@{username}</div>
        <div class="repo-info">Active Repo: {user.get("active_repo") or "Not configured"}</div>
      </div>
      {telegram_badge}
    </div>

    <div class="btn-stack">
      {action_buttons}
      <button onclick="window.close()" class="btn-close">You can close this tab</button>
    </div>

    <p class="footer-text">LogicalFire AI Platform &middot; Token stored in session</p>
  </div>

  <script>
    try {{
      const token = "{jwt_token}";
      if (token) {{
        localStorage.setItem("access_token", token);
        localStorage.setItem("token", token);
        localStorage.setItem("user", JSON.stringify({user_json}));
      }}
    }} catch (e) {{
      console.warn("Storage exception:", e);
    }}
  </script>
</body>
</html>"""


def render_oauth_error_html(error_message: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>LogicalFire - Authentication Error</title>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@600;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    body {{
      background-color: #080b11;
      color: #f8fafc;
      font-family: 'Inter', sans-serif;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px;
      margin: 0;
    }}
    .card {{
      background: rgba(22, 28, 46, 0.85);
      border: 1px solid rgba(255, 69, 0, 0.3);
      border-radius: 20px;
      max-width: 440px;
      width: 100%;
      padding: 36px 28px;
      text-align: center;
      box-shadow: 0 20px 50px rgba(0, 0, 0, 0.6);
    }}
    .icon {{
      width: 64px;
      height: 64px;
      background: rgba(239, 68, 68, 0.15);
      border: 2px solid rgba(239, 68, 68, 0.35);
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      margin: 0 auto 18px;
    }}
    h1 {{
      font-family: 'Outfit', sans-serif;
      font-size: 22px;
      margin-bottom: 10px;
    }}
    p {{
      color: #94a3b8;
      font-size: 14px;
      line-height: 1.5;
      margin-bottom: 24px;
    }}
    .error-box {{
      background: rgba(15, 20, 32, 0.8);
      border: 1px solid rgba(255, 255, 255, 0.05);
      border-radius: 10px;
      padding: 12px;
      font-family: monospace;
      font-size: 12px;
      color: #f87171;
      margin-bottom: 24px;
      word-break: break-word;
    }}
    .btn {{
      display: inline-block;
      width: 100%;
      padding: 12px 18px;
      border-radius: 10px;
      font-weight: 600;
      font-size: 14px;
      text-decoration: none;
      background: linear-gradient(135deg, #ff3b00 0%, #ff7300 100%);
      color: #fff;
    }}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="15" y1="9" x2="9" y2="15"></line>
        <line x1="9" y1="9" x2="15" y2="15"></line>
      </svg>
    </div>
    <h1>Authentication Failed</h1>
    <p>We could not complete the GitHub OAuth handshake.</p>
    <div class="error-box">{error_message}</div>
    <a href="/auth/github/login" class="btn">Try Again</a>
  </div>
</body>
</html>"""


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
async def github_oauth_callback(request: Request, code: str, state: Optional[str] = None):
    """
    Callback endpoint for GitHub OAuth.
    Exchanges authorization code for access token and logs in/registers user.
    Returns a responsive, styled HTML confirmation page for browsers.
    """
    is_json_request = "application/json" in request.headers.get("accept", "") and "text/html" not in request.headers.get("accept", "")

    if not GITHUB_CLIENT_ID or not GITHUB_CLIENT_SECRET:
        error_msg = "GitHub OAuth credentials (CLIENT_ID / CLIENT_SECRET) are not configured."
        if is_json_request:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_msg)
        return HTMLResponse(content=render_oauth_error_html(error_msg), status_code=500)

    token_url = "https://github.com/login/oauth/access_token"
    payload = {
        "client_id": GITHUB_CLIENT_ID,
        "client_secret": GITHUB_CLIENT_SECRET,
        "code": code
    }
    headers = {"Accept": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 1. Exchange code for access_token
            token_resp = await client.post(token_url, json=payload, headers=headers)
            if token_resp.status_code != 200:
                err = f"Failed to exchange code for GitHub token: {token_resp.text}"
                if is_json_request:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err)
                return HTMLResponse(content=render_oauth_error_html(err), status_code=400)
            
            token_data = token_resp.json()
            github_access_token = token_data.get("access_token")
            if not github_access_token:
                error_desc = token_data.get("error_description", "No access_token returned by GitHub")
                if is_json_request:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"GitHub OAuth error: {error_desc}")
                return HTMLResponse(content=render_oauth_error_html(f"GitHub OAuth error: {error_desc}"), status_code=400)

            # 2. Fetch user profile from GitHub
            user_resp = await client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"token {github_access_token}",
                    "Accept": "application/vnd.github+json"
                }
            )
            if user_resp.status_code != 200:
                err = "Failed to fetch GitHub user profile"
                if is_json_request:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err)
                return HTMLResponse(content=render_oauth_error_html(err), status_code=400)
            
            gh_user = user_resp.json()
            github_id = gh_user.get("id")
            username = gh_user.get("login")
            email = gh_user.get("email")
            avatar_url = gh_user.get("avatar_url")

            # Fetch email if private
            if not email:
                try:
                    emails_resp = await client.get(
                        "https://api.github.com/user/emails",
                        headers={"Authorization": f"token {github_access_token}"}
                    )
                    if emails_resp.status_code == 200:
                        emails = emails_resp.json()
                        primary_email = next((e["email"] for e in emails if e.get("primary")), None)
                        if primary_email:
                            email = primary_email
                except Exception as ex:
                    logger.warning(f"Could not fetch user private email: {ex}")

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
            is_telegram = False
            if state and state.startswith("telegram_"):
                is_telegram = True
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

            user_dict = {
                "id": user.id,
                "github_id": user.github_id,
                "username": user.username,
                "email": user.email,
                "avatar_url": user.avatar_url,
                "telegram_id": user.telegram_id,
                "active_repo": user.active_repo,
                "role": user.role
            }

            if is_json_request:
                return {
                    "status": "success",
                    "message": "GitHub OAuth login successful",
                    "access_token": jwt_token,
                    "token_type": "bearer",
                    "user": user_dict
                }

            html_content = render_oauth_success_html(user=user_dict, jwt_token=jwt_token, is_telegram=is_telegram)
            return HTMLResponse(content=html_content)

    except Exception as e:
        logger.exception("Unexpected error in GitHub OAuth callback:")
        if is_json_request:
            raise HTTPException(status_code=500, detail=str(e))
        return HTMLResponse(content=render_oauth_error_html(str(e)), status_code=500)


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
