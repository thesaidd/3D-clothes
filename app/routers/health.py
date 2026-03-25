import logging
import time

import redis as redis_lib
from fastapi import APIRouter

from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health", summary="Sistem sağlık kontrolü")
async def health_check():
    """
    API, Redis ve Celery worker bağlantılarını kontrol eder.

    Durum değerleri: `ok` | `error`
    """
    checks: dict = {}

    # ── Redis bağlantı testi ─────────────────────────────────────
    try:
        r = redis_lib.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        latency_ms = _ping_latency(r)
        r.close()
        checks["redis"] = {"status": "ok", "latency_ms": latency_ms}
    except Exception as exc:
        logger.warning(f"Redis bağlantı hatası: {exc}")
        checks["redis"] = {"status": "error", "detail": str(exc)}

    # ── Celery worker kontrolü ───────────────────────────────────
    try:
        from app.worker.celery_app import celery
        inspect = celery.control.inspect(timeout=2.0)
        active = inspect.active()
        worker_count = len(active) if active else 0
        checks["celery"] = {
            "status": "ok" if worker_count > 0 else "no_workers",
            "active_workers": worker_count,
        }
    except Exception as exc:
        logger.warning(f"Celery inspect hatası: {exc}")
        checks["celery"] = {"status": "error", "detail": str(exc)}

    overall = "ok" if all(v.get("status") == "ok" for v in checks.values()) else "degraded"

    return {
        "status": overall,
        "version": settings.APP_VERSION,
        "checks": checks,
    }


def _ping_latency(r: redis_lib.Redis) -> float:
    """Redis'e PING atıp ms cinsinden gecikmeyi döner."""
    start = time.perf_counter()
    r.ping()
    return round((time.perf_counter() - start) * 1000, 2)
