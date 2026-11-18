"""Worker / Scheduler: kollektorları dövri işlədir, yaddaş saxlanma müddətini tətbiq edir.

    python -m app.worker                 # sonsuz dövr
    python -m app.worker --once          # bir dəfə (cron üçün)

Lentlər: MEDIAOS_COLLECTOR_FEEDS='["https://.../rss|Mənbə adı|media"]'
"""
from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime, timezone

from app.collectors.collectors import RssCollector, run_collector
from app.config import get_settings
from app.db import init_db, session_scope
from app.memory.service import purge_expired

log = logging.getLogger("mediaos.worker")


def collectors():
    out = []
    for spec in get_settings().collector_feeds:
        url, name, kind = (spec.split("|") + ["", "media"])[:3]
        out.append(RssCollector(url, name or url, kind or "media"))
    return out


def tick() -> dict:
    results = {c.name: run_collector(c) for c in collectors()}
    return results


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    init_db()
    last_purge = None
    while True:
        started = time.monotonic()
        log.info("collector tick: %s", tick())
        today = datetime.now(timezone.utc).date()
        if last_purge != today:
            with session_scope() as db:
                log.info("retention purge: %s", purge_expired(db))
            last_purge = today
        if args.once:
            break
        time.sleep(max(5, get_settings().collector_interval_s - (time.monotonic() - started)))


if __name__ == "__main__":
    main()
