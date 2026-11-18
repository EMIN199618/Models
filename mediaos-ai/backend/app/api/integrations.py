"""EnsembleData (Instagram + TikTok) inteqrasiyasının idarəsi — yalnız admin."""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.collectors import ensembledata as ED
from app.collectors.collectors import run_collector
from app.config import get_settings
from app.db import get_session, session_scope
from app.models import AuditLog, CollectorRun, Setting, User
from app.security.auth import require_role

router = APIRouter(prefix="/api/integrations/ensembledata", tags=["integrations"])
_run_lock = threading.Lock()
_state: dict[str, Any] = {"running": False, "last_result": None, "started_at": None}


def _token_source(db: Session) -> str | None:
    row = db.get(Setting, ED.TOKEN_KEY)
    if row and row.value.get("token"):
        return "admin_panel"
    return "environment" if get_settings().ensembledata_token else None


@router.get("")
def status(db: Session = Depends(get_session), _: User = Depends(require_role("admin"))):
    runs = db.scalars(select(CollectorRun).where(CollectorRun.source == "ensembledata")
                      .order_by(CollectorRun.id.desc()).limit(5)).all()
    return {
        "configured": bool(ED.get_token()), "token": ED.mask(ED.get_token()), "token_source": _token_source(db),
        "config": ED.effective_config(db), "running": _state["running"], "started_at": _state["started_at"],
        "last_result": _state["last_result"],
        "runs": [{"started_at": r.started_at, "finished_at": r.finished_at, "fetched": r.fetched, "inserted": r.inserted,
                  "duplicates": r.duplicates, "irrelevant": r.irrelevant, "errors": r.errors, "error": r.error} for r in runs],
    }


class TokenIn(BaseModel):
    token: str = Field(min_length=16, max_length=256)


@router.put("/token")
def set_token(body: TokenIn, db: Session = Depends(get_session), user: User = Depends(require_role("admin"))):
    tok = body.token.strip()
    # Saxlamazdan əvvəl yoxla (bu sorğu unit xərcləmir)
    try:
        usage = ED.EnsembleDataClient(token=tok, max_units=1).used_units_today()
    except ED.AuthError as exc:
        raise HTTPException(400, str(exc)) from exc
    except ED.EnsembleDataError as exc:
        raise HTTPException(502, f"EnsembleData yoxlanıla bilmədi: {exc}") from exc
    row = db.get(Setting, ED.TOKEN_KEY)
    if row:
        row.value, row.updated_by = {"token": tok}, user.id
    else:
        db.add(Setting(key=ED.TOKEN_KEY, value={"token": tok}, updated_by=user.id))
    db.add(AuditLog(user_id=user.id, action="integration.ensembledata.token_set", detail={"token": ED.mask(tok)}))
    return {"configured": True, "token": ED.mask(tok), "used_units_today": usage}


@router.delete("/token", status_code=204)
def delete_token(db: Session = Depends(get_session), user: User = Depends(require_role("admin"))):
    row = db.get(Setting, ED.TOKEN_KEY)
    if row:
        db.delete(row)
    db.add(AuditLog(user_id=user.id, action="integration.ensembledata.token_deleted"))


class ConfigIn(BaseModel):
    tiktok_keywords: list[str] | None = Field(default=None, max_length=30)
    tiktok_hashtags: list[str] | None = Field(default=None, max_length=30)
    tiktok_period_days: str | None = Field(default=None, pattern="^(0|1|7|30|90|180)$")
    tiktok_country: str | None = Field(default=None, max_length=2)
    tiktok_official_accounts: list[str] | None = Field(default=None, max_length=20)
    tiktok_media_accounts: list[str] | None = Field(default=None, max_length=50)
    instagram_official_accounts: list[str] | None = Field(default=None, max_length=20)
    instagram_media_accounts: list[str] | None = Field(default=None, max_length=50)
    instagram_posts_per_account: int | None = Field(default=None, ge=1, le=20)
    instagram_comment_posts: int | None = Field(default=None, ge=0, le=10)
    max_units_per_run: int | None = Field(default=None, ge=1, le=5000)


@router.put("/config")
def set_config(body: ConfigIn, db: Session = Depends(get_session), user: User = Depends(require_role("admin"))):
    upd = {k: ([x.strip() for x in v if x.strip()] if isinstance(v, list) else v)
           for k, v in body.model_dump(exclude_none=True).items()}
    row = db.get(Setting, ED.CONFIG_KEY)
    if row:
        row.value, row.updated_by = {**row.value, **upd}, user.id
    else:
        db.add(Setting(key=ED.CONFIG_KEY, value=upd, updated_by=user.id))
    db.add(AuditLog(user_id=user.id, action="integration.ensembledata.config", detail=upd))
    db.flush()
    return ED.effective_config(db)


def _run(max_units: int | None, user_id: int) -> None:
    try:
        cfg = ED.effective_config()
        if max_units:
            cfg["max_units_per_run"] = max_units
        res = run_collector(ED.SocialCollector(config=cfg))
    except Exception as exc:  # thread-də itməsin
        res = {"error": str(exc)}
    _state.update(running=False, last_result={**res, "finished_at": datetime.now(timezone.utc).isoformat()})
    _run_lock.release()


class RunIn(BaseModel):
    max_units: int | None = Field(default=None, ge=1, le=5000)


@router.post("/run", status_code=202)
def run_now(body: RunIn | None = None, user: User = Depends(require_role("admin"))):
    if not ED.get_token():
        raise HTTPException(400, "Əvvəlcə EnsembleData tokenini daxil edin")
    if not _run_lock.acquire(blocking=False):
        raise HTTPException(409, "Toplama artıq gedir")
    _state.update(running=True, started_at=datetime.now(timezone.utc).isoformat(), last_result=None)
    with session_scope() as db:
        db.add(AuditLog(user_id=user.id, action="integration.ensembledata.run",
                        detail={"max_units": body.max_units if body else None}))
    threading.Thread(target=_run, args=(body.max_units if body else None, user.id), daemon=True).start()
    return {"started": True}


@router.get("/usage")
def usage(_: User = Depends(require_role("admin"))):
    tok = ED.get_token()
    if not tok:
        raise HTTPException(400, "token konfiqurasiya edilməyib")
    try:
        return {"date": datetime.now(timezone.utc).date().isoformat(),
                "used_units": ED.EnsembleDataClient(token=tok, max_units=1).used_units_today()}
    except ED.EnsembleDataError as exc:
        raise HTTPException(502, str(exc)) from exc


class DiscoverIn(BaseModel):
    query: str = Field(min_length=2, max_length=100)


@router.post("/discover")
def discover(body: DiscoverIn, _: User = Depends(require_role("admin"))):
    """Instagram-da hesab axtarışı (4 unit) — rəsmi DGK hesabını və media hesablarını tapmaq üçün."""
    tok = ED.get_token()
    if not tok:
        raise HTTPException(400, "token konfiqurasiya edilməyib")
    try:
        data = ED.EnsembleDataClient(token=tok, max_units=4).get("/instagram/search", {"text": body.query}).get("data") or {}
    except ED.EnsembleDataError as exc:
        raise HTTPException(502, str(exc)) from exc
    return [{"username": u["user"].get("username"), "full_name": u["user"].get("full_name"),
             "is_verified": u["user"].get("is_verified")} for u in data.get("users", [])[:15]]
