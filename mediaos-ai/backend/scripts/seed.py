"""Nümunə (SİNTETİK) məlumatla bazanı doldurur və test istifadəçiləri yaradır.

    python -m scripts.seed            # sxem + istifadəçilər + sənədlər + xəbərlər
    python -m scripts.seed --reset    # əvvəlcə MediaOS cədvəllərini silir (yalnız dev/test!)

Bütün nümunə xəbərlər `is_synthetic=true` ilə işarələnir və mənbə adlarında "(nümunə)" var.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.db import drop_db, init_db, session_scope
from app.models import User
from app.pipeline.process import RawNews, process_batch
from app.rag.ingest import FrontMatterDirectoryLoader, ingest_documents
from app.security.auth import hash_token

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "data" / "samples"
# Dev tokenləri sabitdir ki, testlər və nümunə əmrlər işləsin. Production-da istifadə etməyin.
DEV_USERS = [
    ("admin", "Admin", "admin", "mos_dev_admin_token"),
    ("analyst", "Analitik", "analyst", "mos_dev_analyst_token"),
    ("viewer", "Müşahidəçi", "viewer", "mos_dev_viewer_token"),
    ("analyst2", "Analitik 2", "analyst", "mos_dev_analyst2_token"),
]


def load_sample_news(now: datetime | None = None) -> list[tuple[str, RawNews, dict]]:
    now = now or datetime.now(timezone.utc)
    out = []
    for r in json.loads((SAMPLES / "news.json").read_text(encoding="utf-8")):
        pub = (now - timedelta(days=r["days_ago"])).replace(hour=9, minute=0, second=0, microsecond=0) \
            + timedelta(minutes=int(r["key"][1:]) * 7)
        if pub > now:
            pub = now - timedelta(minutes=5)
        out.append((r["key"], RawNews(source_name=r["source_name"], source_kind=r["source_kind"], title=r["title"],
                                      body=r["body"], published_at=pub, url=f"https://example.invalid/{r['key']}",
                                      is_synthetic=True), r["gold"]))
    return out


def seed(reset: bool = False) -> dict:
    if reset:
        assert get_settings().env != "prod", "prod mühitində reset qadağandır"
        drop_db()
    init_db()
    with session_scope() as db:
        for username, name, role, token in DEV_USERS:
            if not db.scalar(select(User).where(User.username == username)):
                db.add(User(username=username, display_name=name, role=role, api_token_hash=hash_token(token)))
    with session_scope() as db:
        doc_stats = ingest_documents(db, list(FrontMatterDirectoryLoader(SAMPLES / "docs").lazy_load()))
    with session_scope() as db:
        news = load_sample_news()
        st = process_batch(db, [n for _, n, _ in news])
    return {"documents": doc_stats, "news": st.as_dict()}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true")
    print(json.dumps(seed(ap.parse_args().reset), ensure_ascii=False, indent=2))
