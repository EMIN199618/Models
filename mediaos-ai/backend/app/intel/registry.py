"""DGK struktur/rəhbərlik reyestri və açar söz lüğətinin bazaya yüklənməsi.

Yalnız ƏLAVƏ edir: mövcud açar söz, şəxs, vəzifə və ya bölmə silinmir və üzərinə yazılmır
(admin paneldə edilmiş düzəlişlər qorunur). Təkrar işlədilə bilər.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.intel.lexicon import BUILTIN, REGISTRY, name_variants
from app.models import AuditLog, Checkpoint, Keyword, OrgUnit, Person, Position

COMPILED = datetime(2026, 11, 18, tzinfo=timezone.utc)


def _dt(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc) if s else None


def seed_registry(db: Session) -> dict[str, int]:
    st = {"keywords": 0, "units": 0, "persons": 0, "positions": 0, "checkpoints": 0}
    existing = {(k.term, k.level) for k in db.scalars(select(Keyword))}
    for term, level, cat, lang in BUILTIN:
        if (term, level) not in existing:
            db.add(Keyword(term=term, level=level, category=cat, lang=lang, builtin=True))
            st["keywords"] += 1
    reg: dict[str, Any] = json.loads(REGISTRY.read_text(encoding="utf-8"))
    units = {u.slug: u for u in db.scalars(select(OrgUnit))}
    for u in reg["units"]:
        if u["slug"] not in units:
            obj = OrgUnit(slug=u["slug"], name=u["name"], kind=u["kind"],
                          source_url=None if u["source"] == "user" else u["source"],
                          variants={"source_note": "istifadəçi siyahısı" if u["source"] == "user" else "rəsmi səhifə (axtarış indeksi)"},
                          last_checked=COMPILED)
            db.add(obj)
            units[u["slug"]] = obj
            st["units"] += 1
    db.flush()
    persons = {p.full_name: p for p in db.scalars(select(Person))}
    for p in reg["people"]:
        parts = p["name"].split()
        surname, given = parts[0], parts[1]
        patr = " ".join(parts[2:]) or None
        per = persons.get(p["name"])
        if per is None:
            per = Person(full_name=p["name"], surname=surname, given_name=given, patronymic=patr,
                         variants=name_variants(given, surname), last_checked=COMPILED)
            db.add(per)
            db.flush()
            persons[p["name"]] = per
            st["persons"] += 1
        have = {(x.title, x.unit_id) for x in db.scalars(select(Position).where(Position.person_id == per.id))}
        for pos in p["positions"]:
            unit = units.get(pos["unit"])
            key = (pos["title"], unit.id if unit else None)
            if key in have:
                continue
            db.add(Position(person_id=per.id, unit_id=unit.id if unit else None, title=pos["title"],
                            start_date=_dt(pos.get("start")), end_date=_dt(pos.get("end")), status=pos["status"],
                            source_url=pos.get("source"), source_type=pos.get("source_type", "media"),
                            note=pos.get("note"), last_checked=COMPILED))
            st["positions"] += 1
    cps = {c.name for c in db.scalars(select(Checkpoint))}
    for c in reg["checkpoints"]:
        if c["name"] not in cps:
            unit = units.get(c["unit"]) if c.get("unit") else None
            db.add(Checkpoint(name=c["name"], variants=c.get("variants", []), unit_id=unit.id if unit else None,
                              unit_inferred=bool(c.get("unit_inferred", True)), source=c.get("source"),
                              last_checked=COMPILED))
            st["checkpoints"] += 1
    if any(st.values()):
        db.add(AuditLog(action="registry.seed", detail=st))
    return st
