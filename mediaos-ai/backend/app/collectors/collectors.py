"""Xəbər toplayıcıları. Hər toplayıcı `RawNews` siyahısı qaytarır; emal pipeline-da olur."""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from app.db import session_scope
from app.models import CollectorRun
from app.pipeline.process import RawNews, process_batch

log = logging.getLogger(__name__)


class JsonFileCollector:
    """JSON faylından (və ya qovluqdan) xəbər oxuyur. Format: [{source_name, source_kind, title, body, published_at, url}]"""

    def __init__(self, path: str | Path, synthetic: bool = False):
        self.path, self.synthetic = Path(path), synthetic
        self.name = f"file:{self.path.name}"

    def fetch(self) -> list[RawNews]:
        files = sorted(self.path.glob("*.json")) if self.path.is_dir() else [self.path]
        out = []
        for f in files:
            for r in json.loads(f.read_text(encoding="utf-8")):
                out.append(RawNews(
                    source_name=r["source_name"], source_kind=r["source_kind"], title=r["title"], body=r["body"],
                    published_at=datetime.fromisoformat(r["published_at"]), url=r.get("url"),
                    is_synthetic=self.synthetic or r.get("synthetic", False),
                ))
        return out


class RssCollector:
    """RSS/Atom lentindən oxuyur (MEDIAOS_COLLECTOR_FEEDS). Mənbə növü URL-ə görə verilir."""

    def __init__(self, url: str, source_name: str, source_kind: str = "media"):
        self.url, self.source_name, self.source_kind = url, source_name, source_kind
        self.name = f"rss:{source_name}"

    def fetch(self) -> list[RawNews]:
        import feedparser
        feed = feedparser.parse(self.url)
        if feed.bozo and not feed.entries:
            raise RuntimeError(f"RSS oxunmadı: {feed.bozo_exception}")
        out = []
        for e in feed.entries:
            tm = e.get("published_parsed") or e.get("updated_parsed")
            pub = datetime.fromtimestamp(time.mktime(tm), tz=timezone.utc) if tm else datetime.now(timezone.utc)
            out.append(RawNews(source_name=self.source_name, source_kind=self.source_kind, title=e.get("title", ""),
                               body=e.get("summary", "") or e.get("description", ""), published_at=pub, url=e.get("link")))
        return out


def run_collector(collector) -> dict:
    started = datetime.now(timezone.utc)
    run = {"source": collector.name, "started_at": started}
    try:
        items = collector.fetch()
    except Exception as exc:
        log.error("collector %s xətası: %s", collector.name, exc)
        with session_scope() as db:
            db.add(CollectorRun(**run, finished_at=datetime.now(timezone.utc), errors=1, error=str(exc)[:500]))
        return {"error": str(exc)}
    with session_scope() as db:
        st = process_batch(db, items)
        newest = max((i.published_at for i in items), default=None)
        lag = (started - (newest if newest.tzinfo else newest.replace(tzinfo=timezone.utc))).total_seconds() if newest else None
        db.add(CollectorRun(**run, finished_at=datetime.now(timezone.utc), fetched=st.fetched,
                            inserted=st.relevant + st.review, duplicates=st.duplicates + st.near_duplicates,
                            irrelevant=st.irrelevant, errors=len(st.errors), max_ingest_lag_s=lag))
    return st.as_dict()
