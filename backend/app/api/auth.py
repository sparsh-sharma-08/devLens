"""
DevLens AI — Authentication Router
Supports three auth methods:
  1. GitHub OAuth  → GET /auth/github/login → /auth/github/callback
  2. Google OAuth  → GET /auth/google/login → /auth/google/callback
  3. Email/Password → POST /auth/signup  +  POST /auth/login

All paths issue the same JWT pair on success and redirect to / call the same
frontend callback flow, so the frontend stays provider-agnostic.
"""
import urllib.parse
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx
import bcrypt
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import select

from app.auth.jwt import (
    ACCESS_TOKEN_TYPE,
    REFRESH_TOKEN_TYPE,
    create_access_token,
    create_refresh_token,
    verify_token,
)
from app.config import get_settings
from app.database import get_db_context
from app.models import User

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

# ── Password hashing ─────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    pwd_bytes = plain.encode("utf-8")
    if len(pwd_bytes) > 72:
        pwd_bytes = pwd_bytes[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    pwd_bytes = plain.encode("utf-8")
    if len(pwd_bytes) > 72:
        pwd_bytes = pwd_bytes[:72]
    return bcrypt.checkpw(pwd_bytes, hashed.encode("utf-8"))


# ── Shared helpers ────────────────────────────────────────────────────────────

def _frontend_redirect(user_id: uuid.UUID, username: str, avatar_url: Optional[str]) -> RedirectResponse:
    """Build the frontend /auth/callback redirect with JWT tokens in query params."""
    access_token = create_access_token(user_id, username)
    refresh_token = create_refresh_token(user_id)
    params = urllib.parse.urlencode({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user_id": str(user_id),
        "username": username,
        "avatar_url": avatar_url or "",
    })
    return RedirectResponse(f"{settings.frontend_url}/auth/callback?{params}")


# ── Request / Response schemas ────────────────────────────────────────────────

class UserOut(BaseModel):
    id: uuid.UUID
    username: str
    avatar_url: Optional[str]
    email: Optional[str]
    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: UserOut


class RefreshRequest(BaseModel):
    refresh_token: str


class SignupRequest(BaseModel):
    username: str
    email: str
    password: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Username must be at least 2 characters")
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username may only contain letters, numbers, hyphens, and underscores")
        return v


class LoginRequest(BaseModel):
    email: str
    password: str


# ═════════════════════════════════════════════════════════════════════════════
# 1. GITHUB OAUTH
# ═════════════════════════════════════════════════════════════════════════════

GITHUB_AUTH_URL  = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL  = "https://api.github.com/user"


@router.get("/github/login", summary="Redirect to GitHub OAuth")
async def github_login():
    if not settings.github_client_id:
        raise HTTPException(503, "GitHub OAuth not configured — set GITHUB_CLIENT_ID in .env")
    params = urllib.parse.urlencode({
        "client_id": settings.github_client_id,
        "redirect_uri": f"{settings.api_base_url}/v1/auth/github/callback",
        "scope": "user:email read:user",
    })
    return RedirectResponse(f"{GITHUB_AUTH_URL}?{params}")


@router.get("/github/callback", summary="GitHub OAuth callback")
async def github_callback(code: str = Query(...)):
    """Exchange GitHub code → upsert user → issue DevLens JWT → redirect to frontend."""
    async with httpx.AsyncClient() as client:
        # Exchange code for access token
        token_resp = await client.post(
            GITHUB_TOKEN_URL,
            headers={"Accept": "application/json"},
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
                "redirect_uri": f"{settings.api_base_url}/v1/auth/github/callback",
            },
        )
        token_data = token_resp.json()
        gh_token = token_data.get("access_token")
        if not gh_token:
            raise HTTPException(400, f"GitHub token error: {token_data}")

        # Fetch user profile
        user_resp = await client.get(
            GITHUB_USER_URL,
            headers={"Authorization": f"token {gh_token}", "Accept": "application/json"},
        )
        gh_user = user_resp.json()

    github_id  = str(gh_user["id"])
    username   = gh_user.get("login", "")
    avatar_url = gh_user.get("avatar_url")
    email      = gh_user.get("email")  # may be None if user hides email

    async with get_db_context() as db:
        result = await db.execute(select(User).where(User.github_id == github_id))
        user = result.scalar_one_or_none()

        if user is None:
            # Check if email is already taken by an email/password account
            if email:
                dup = await db.execute(select(User).where(User.email == email, User.github_id.is_(None)))
                dup_user = dup.scalar_one_or_none()
                if dup_user:
                    # Link GitHub to the existing email account
                    dup_user.github_id = github_id
                    dup_user.avatar_url = dup_user.avatar_url or avatar_url
                    dup_user.last_login_at = datetime.now(timezone.utc)
                    await db.flush()
                    user = dup_user
            if user is None:
                user = User(
                    github_id=github_id,
                    username=username,
                    avatar_url=avatar_url,
                    email=email,
                    last_login_at=datetime.now(timezone.utc),
                )
                db.add(user)
                await db.flush()
        else:
            user.username      = username
            user.avatar_url    = user.avatar_url or avatar_url
            user.email         = user.email or email
            user.last_login_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(user)
        user_id, uname, av = user.id, user.username, user.avatar_url

    return _frontend_redirect(user_id, uname, av)


# ═════════════════════════════════════════════════════════════════════════════
# 2. GOOGLE OAUTH
# ═════════════════════════════════════════════════════════════════════════════

GOOGLE_AUTH_URL   = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL  = "https://oauth2.googleapis.com/token"
GOOGLE_USER_URL   = "https://www.googleapis.com/oauth2/v3/userinfo"


@router.get("/google/login", summary="Redirect to Google OAuth")
async def google_login():
    if not settings.google_client_id:
        raise HTTPException(503, "Google OAuth not configured — set GOOGLE_CLIENT_ID in .env")
    params = urllib.parse.urlencode({
        "client_id": settings.google_client_id,
        "redirect_uri": f"{settings.api_base_url}/v1/auth/google/callback",
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    })
    return RedirectResponse(f"{GOOGLE_AUTH_URL}?{params}")


@router.get("/google/callback", summary="Google OAuth callback")
async def google_callback(code: str = Query(...)):
    """Exchange Google code → upsert user → issue DevLens JWT → redirect to frontend."""
    async with httpx.AsyncClient() as client:
        # Exchange code for tokens
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": f"{settings.api_base_url}/v1/auth/google/callback",
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code != 200:
            raise HTTPException(400, f"Google token exchange failed: {token_resp.text}")

        google_token = token_resp.json().get("access_token")

        # Fetch user info
        user_resp = await client.get(
            GOOGLE_USER_URL,
            headers={"Authorization": f"Bearer {google_token}"},
        )
        g_user = user_resp.json()

    google_id  = g_user.get("sub")
    email      = g_user.get("email")
    username   = (g_user.get("name") or email or "user").replace(" ", "").lower()
    avatar_url = g_user.get("picture")

    if not google_id:
        raise HTTPException(400, "Could not retrieve Google user info")

    async with get_db_context() as db:
        result = await db.execute(select(User).where(User.google_id == google_id))
        user = result.scalar_one_or_none()

        if user is None:
            # Check if email already registered (email/password or GitHub account)
            if email:
                dup = await db.execute(select(User).where(User.email == email, User.google_id.is_(None)))
                dup_user = dup.scalar_one_or_none()
                if dup_user:
                    dup_user.google_id     = google_id
                    dup_user.avatar_url    = dup_user.avatar_url or avatar_url
                    dup_user.last_login_at = datetime.now(timezone.utc)
                    await db.flush()
                    user = dup_user
            if user is None:
                user = User(
                    google_id=google_id,
                    username=username,
                    email=email,
                    avatar_url=avatar_url,
                    last_login_at=datetime.now(timezone.utc),
                )
                db.add(user)
                await db.flush()
        else:
            user.avatar_url    = user.avatar_url or avatar_url
            user.email         = user.email or email
            user.last_login_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(user)
        user_id, uname, av = user.id, user.username, user.avatar_url

    return _frontend_redirect(user_id, uname, av)


# ═════════════════════════════════════════════════════════════════════════════
# 3. EMAIL / PASSWORD
# ═════════════════════════════════════════════════════════════════════════════

@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED,
             summary="Sign up with email and password")
async def signup(body: SignupRequest):
    """
    Create a new email/password account.
    Returns a JWT pair directly (no redirect needed — pure JSON API call from the frontend).
    """
    async with get_db_context() as db:
        # Check for duplicate email
        result = await db.execute(select(User).where(User.email == body.email))
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=409,
                detail="An account with this email already exists. Try logging in instead.",
            )

        # Check for duplicate username
        result2 = await db.execute(select(User).where(User.username == body.username))
        if result2.scalar_one_or_none():
            raise HTTPException(
                status_code=409,
                detail="This username is already taken. Please choose another.",
            )

        user = User(
            username=body.username,
            email=body.email,
            password_hash=hash_password(body.password),
            last_login_at=datetime.now(timezone.utc),
        )
        db.add(user)
        await db.flush()
        await db.commit()
        await db.refresh(user)

        user_out = UserOut(
            id=user.id,
            username=user.username,
            avatar_url=user.avatar_url,
            email=user.email,
        )
        access_token  = create_access_token(user.id, user.username)
        refresh_token = create_refresh_token(user.id)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token, user=user_out)


@router.post("/login", response_model=TokenResponse, summary="Log in with email and password")
async def login(body: LoginRequest):
    """
    Authenticate an email/password user.
    Returns a JWT pair directly.
    """
    async with get_db_context() as db:
        result = await db.execute(select(User).where(User.email == body.email))
        user = result.scalar_one_or_none()

        # Constant-time failure — don't reveal whether email exists
        if not user or not user.password_hash or not verify_password(body.password, user.password_hash):
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password.",
            )

        user.last_login_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(user)

        user_out = UserOut(
            id=user.id,
            username=user.username,
            avatar_url=user.avatar_url,
            email=user.email,
        )
        access_token  = create_access_token(user.id, user.username)
        refresh_token = create_refresh_token(user.id)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token, user=user_out)


# ═════════════════════════════════════════════════════════════════════════════
# 4. TOKEN MANAGEMENT
# ═════════════════════════════════════════════════════════════════════════════

@router.post("/refresh", response_model=dict, summary="Refresh access token")
async def refresh_token(body: RefreshRequest):
    payload = verify_token(body.refresh_token, REFRESH_TOKEN_TYPE)
    if not payload:
        raise HTTPException(401, "Invalid or expired refresh token")

    user_id = uuid.UUID(payload["sub"])
    async with get_db_context() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(401, "User not found")

    return {"access_token": create_access_token(user_id, user.username)}


@router.post("/logout", status_code=204, summary="Log out (client-side token disposal)")
async def logout():
    """
    V1 stateless logout — client discards tokens.
    Full jti blocklist revocation is a V2 enhancement.
    """
    return None
