"""DGK Structure & Management və açar söz idarəetməsi.

Prinsip: şəxslər üzrə reputasiya balı və profil YOXDUR. Rəhbər üzrə yalnız onun DGK kontekstində çəkildiyi
materialların siyahısı, mövzu/sentiment bölgüsü və hər materialın öz (hadisəyə əsaslanan) risk qiymətləndirməsi göstərilir.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.intel.lexicon import invalidate
from app.models import (AuditLog, Checkpoint, EntityMention, Keyword, NewsAnalysis, NewsItem, OrgUnit, Person,
                        Position, User)
from app.security.auth import current_user, require_role

router = APIRouter(prefix="/api", tags=["structure"])
ORDER = {"təsdiqlənmiş": 0, "yoxlanmalıdır": 1, "keçmiş rəhbər": 2}


def _d(x: datetime | None) -> str | None:
    return x.date().isoformat() if x else None


def _news_brief(n: NewsItem) -> dict[str, Any]:
    a = n.analysis
    return {"id": n.id, "title": n.title, "url": n.url, "source": n.source.name, "platform": n.platform or "web",
            "published_at": n.published_at.isoformat(), "content_type": n.content_type, "is_synthetic": n.is_synthetic,
            "sentiment": a.sentiment if a else None, "risk_level": a.risk_level if a else None,
            "risk_status": a.risk_status if a else None, "category": a.category if a else None,
            "thumb": next((m.get("thumb") or m.get("url") for m in (n.media or []) if m.get("type") == "image"), None)}


@router.get("/structure")
def structure(db: Session = Depends(get_session), _: User = Depends(current_user)):
    units = db.scalars(select(OrgUnit).order_by(OrgUnit.kind, OrgUnit.name)).all()
    pos = db.scalars(select(Position)).all()
    persons = {p.id: p for p in db.scalars(select(Person))}
    unit_news = dict(db.execute(select(EntityMention.entity_id, func.count(func.distinct(EntityMention.news_id)))
                                .join(NewsItem, NewsItem.id == EntityMention.news_id)
                                .where(EntityMention.entity_type == "unit", NewsItem.status == "relevant")
                                .group_by(EntityMention.entity_id)).all())
    by_unit: dict[int | None, list[Position]] = {}
    for p in pos:
        by_unit.setdefault(p.unit_id, []).append(p)
    out = []
    for u in units:
        ps = sorted(by_unit.get(u.id, []), key=lambda p: (ORDER.get(p.status, 3), -(p.start_date.timestamp() if p.start_date else 0)))
        out.append({"id": u.id, "slug": u.slug, "name": u.name, "kind": u.kind, "source_url": u.source_url,
                    "source_note": (u.variants or {}).get("source_note"), "last_checked": _d(u.last_checked),
                    "news_count": unit_news.get(u.id, 0),
                    "leaders": [{"person_id": p.person_id, "name": persons[p.person_id].full_name, "title": p.title,
                                 "status": p.status, "start": _d(p.start_date), "end": _d(p.end_date),
                                 "source_url": p.source_url, "source_type": p.source_type, "note": p.note,
                                 "last_checked": _d(p.last_checked)} for p in ps]})
    stats = Counter(p.status for p in pos)
    return {"units": out, "position_status": dict(stats), "people": len(persons),
            "method_note": "customs.gov.az bu mühitdən birbaşa açılmır; məlumat axtarış indeksindəki rəsmi səhifələr və media "
                           "xəbərləri əsasında toplanıb. 'təsdiqlənmiş' yalnız rəsmi şəxs səhifəsində vəzifə ilə göstərilənlərdir."}


@router.get("/persons/{pid}")
def person(pid: int, db: Session = Depends(get_session), _: User = Depends(current_user)):
    p = db.get(Person, pid)
    if not p:
        raise HTTPException(404, "şəxs tapılmadı")
    positions = db.scalars(select(Position).where(Position.person_id == pid)
                           .order_by(Position.start_date.desc().nulls_last())).all()
    ments = db.scalars(select(EntityMention).where(EntityMention.entity_type == "person", EntityMention.entity_id == pid,
                                                   EntityMention.context_confirmed.is_(True))).all()
    news = {m.news_id: m for m in ments}
    items = db.scalars(select(NewsItem).where(NewsItem.id.in_(list(news)), NewsItem.status == "relevant")
                       .order_by(NewsItem.published_at.desc())).all() if news else []
    pos_by_id = {x.id: x for x in positions}
    mats = []
    for n in items:
        m = news[n.id]
        pz = pos_by_id.get(m.position_id) if m.position_id else None
        mats.append({**_news_brief(n), "matched_text": m.matched_text,
                     "position_at_publication": pz.title if pz else "xəbər tarixində vəzifə məlum deyil"})
    return {
        "id": p.id, "full_name": p.full_name, "variants": p.variants, "last_checked": _d(p.last_checked),
        "positions": [{"title": x.title, "unit": x.unit.name if x.unit else None, "status": x.status,
                       "start": _d(x.start_date), "end": _d(x.end_date), "source_url": x.source_url,
                       "source_type": x.source_type, "note": x.note} for x in positions],
        "materials": mats,
        "topics": dict(Counter(m["category"] for m in mats if m["category"])),
        "sentiment": dict(Counter(m["sentiment"] for m in mats if m["sentiment"])),
        "note": "Şəxs üzrə reputasiya balı hesablanmır. Risk yalnız hər materialın öz hadisəsi və sübutları üzrə göstərilir.",
    }


@router.get("/checkpoints")
def checkpoints(db: Session = Depends(get_session), _: User = Depends(current_user)):
    cnt = dict(db.execute(select(EntityMention.entity_id, func.count(func.distinct(EntityMention.news_id)))
                          .where(EntityMention.entity_type == "checkpoint").group_by(EntityMention.entity_id)).all())
    units = {u.id: u.name for u in db.scalars(select(OrgUnit))}
    return [{"id": c.id, "name": c.name, "variants": c.variants, "unit": units.get(c.unit_id),
             "unit_inferred": c.unit_inferred, "active": c.active, "source": c.source, "news_count": cnt.get(c.id, 0),
             "last_checked": _d(c.last_checked)} for c in db.scalars(select(Checkpoint).order_by(Checkpoint.name))]


# ------------------------------------------------------------------ açar söz idarəetməsi
@router.get("/keywords")
def keywords(db: Session = Depends(get_session), _: User = Depends(require_role("analyst"))):
    """Hər açar söz üçün: neçə materialda tapılıb, neçəsi qəbul/rədd edilib (effektivlik və yanlış pozitiv izləmə)."""
    rows = db.execute(select(NewsAnalysis.matched_keywords, NewsItem.status).join(NewsItem)).all()
    hits: Counter = Counter()
    acc: Counter = Counter()
    rej: Counter = Counter()
    for kws, status in rows:
        for k in kws or []:
            hits[k] += 1
            acc[k] += status == "relevant"
            rej[k] += status == "irrelevant"
    return [{"id": k.id, "term": k.term, "level": k.level, "category": k.category, "lang": k.lang, "variants": k.variants,
             "active": k.active, "builtin": k.builtin, "note": k.note, "updated_at": k.updated_at,
             "hits": hits.get(k.term, 0), "accepted": acc.get(k.term, 0), "rejected": rej.get(k.term, 0)}
            for k in db.scalars(select(Keyword).order_by(Keyword.level, Keyword.term))]


class KeywordIn(BaseModel):
    term: str = Field(min_length=2, max_length=256)
    level: Literal["L1", "L2", "L3", "EX"]
    category: str = Field(min_length=2, max_length=32)
    lang: Literal["az", "ru", "en", "tr", "xx"] = "az"
    variants: list[str] = Field(default_factory=list, max_length=30)
    active: bool = True
    note: str | None = Field(default=None, max_length=500)


@router.post("/keywords", status_code=201)
def add_keyword(body: KeywordIn, db: Session = Depends(get_session), user: User = Depends(require_role("admin"))):
    k = Keyword(**body.model_dump(), created_by=user.id)
    db.add(k)
    db.flush()
    db.add(AuditLog(user_id=user.id, action="keyword.create", target=f"keyword:{k.id}", detail=body.model_dump()))
    invalidate()
    return {"id": k.id}


class KeywordPatch(BaseModel):
    level: Literal["L1", "L2", "L3", "EX"] | None = None
    variants: list[str] | None = Field(default=None, max_length=30)
    active: bool | None = None
    note: str | None = Field(default=None, max_length=500)


@router.patch("/keywords/{kid}")
def patch_keyword(kid: int, body: KeywordPatch, db: Session = Depends(get_session), user: User = Depends(require_role("admin"))):
    """Redaktə və aktiv/deaktiv. Açar söz silinmir (tarixçə və statistika qorunur)."""
    k = db.get(Keyword, kid)
    if not k:
        raise HTTPException(404, "açar söz tapılmadı")
    before = {"level": k.level, "variants": k.variants, "active": k.active, "note": k.note}
    for f, v in body.model_dump(exclude_none=True).items():
        setattr(k, f, v)
    db.add(AuditLog(user_id=user.id, action="keyword.update", target=f"keyword:{k.id}",
                    detail={"before": before, "after": body.model_dump(exclude_none=True)}))
    invalidate()
    return {"id": k.id, "active": k.active, "level": k.level}


@router.get("/keywords/{kid}/audit")
def keyword_audit(kid: int, db: Session = Depends(get_session), _: User = Depends(require_role("analyst"))):
    rows = db.scalars(select(AuditLog).where(AuditLog.target == f"keyword:{kid}").order_by(AuditLog.id.desc())).all()
    return [{"action": r.action, "detail": r.detail, "user_id": r.user_id, "at": r.created_at} for r in rows]


@router.post("/keywords/test")
def keyword_test(body: dict, _: User = Depends(require_role("analyst"))):
    """Mətni lüğətə qarşı yoxlamaq (bazaya yazmır): hansı sözlər, varlıqlar, səviyyə və qərar."""
    from app.intel.lexicon import match
    text = str(body.get("text", ""))[:5000]
    if len(text) < 5:
        raise HTTPException(422, "mətn çox qısadır")
    m = match(text, text, str(body.get("source_kind", "media")))
    return {k: v for k, v in m.as_dict().items() if k not in ("keyword_ids",)}
