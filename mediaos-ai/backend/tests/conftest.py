import os

os.environ.setdefault("MEDIAOS_ENV", "test")
os.environ.setdefault("MEDIAOS_DATABASE_URL", "postgresql+psycopg://mediaos:mediaos@localhost:5432/mediaos_test")
os.environ.setdefault("MEDIAOS_REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("MEDIAOS_LLM_PROVIDER", "local")

import pytest  # noqa: E402
import redis  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.cache.redis_cache import RedisCache, set_cache  # noqa: E402

TOKENS = {"admin": "mos_dev_admin_token", "analyst": "mos_dev_analyst_token", "viewer": "mos_dev_viewer_token",
          "analyst2": "mos_dev_analyst2_token"}


@pytest.fixture(scope="session", autouse=True)
def seeded():
    redis.Redis.from_url(os.environ["MEDIAOS_REDIS_URL"]).flushdb()
    set_cache(None)
    from scripts.seed import seed
    return seed(reset=True)


@pytest.fixture(scope="session")
def client(seeded):
    from app.api.main import app
    with TestClient(app) as c:
        yield c


def auth(role: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKENS[role]}"}


@pytest.fixture
def redis_down():
    """Redis-i əlçatmaz edir (mövcud olmayan port) və testdən sonra bərpa edir."""
    down = RedisCache("redis://localhost:6390/0")
    set_cache(down)
    yield down
    set_cache(None)
