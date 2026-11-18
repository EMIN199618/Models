"""Token əsaslı autentifikasiya və rol yoxlaması + Redis rate limiting."""
from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cache.redis_cache import get_cache
from app.config import get_settings
from app.db import get_session
from app.models import User

ROLE_RANK = {"viewer": 0, "analyst": 1, "admin": 2}


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_token() -> str:
    return "mos_" + secrets.token_urlsafe(24)


def current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_session)) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Authorization: Bearer <token> tələb olunur")
    user = db.scalar(select(User).where(User.api_token_hash == hash_token(authorization[7:].strip())))
    if not user:
        raise HTTPException(401, "etibarsız token")
    return user


def require_role(min_role: str) -> Callable[[User], User]:
    def dep(user: User = Depends(current_user)) -> User:
        if ROLE_RANK[user.role] < ROLE_RANK[min_role]:
            raise HTTPException(403, f"bu əməliyyat üçün ən azı '{min_role}' rolu lazımdır")
        return user
    return dep


def rate_limited(bucket: str = "api", per_minute: int | None = None):
    def dep(request: Request, user: User = Depends(current_user)) -> User:
        limit = per_minute or get_settings().rate_limit_per_minute
        ok, remaining = get_cache().rate_limit(f"{bucket}:u{user.id}", limit)
        request.state.rate_remaining = remaining
        if not ok:
            raise HTTPException(429, "sorğu limiti aşıldı, bir dəqiqə sonra yenidən cəhd edin",
                                headers={"Retry-After": "60"})
        return user
    return dep
