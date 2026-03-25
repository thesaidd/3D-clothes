import logging

from celery import Celery
from celery.signals import worker_ready, worker_shutdown

from app.config import settings

logger = logging.getLogger(__name__)

celery = Celery(
    "vtryon_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.worker.tasks",  # Task modülleri buraya eklenir
    ],
)

celery.conf.update(
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Güvenilirlik
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Zaman aşımı
    task_time_limit=600,        # 10 dakika hard limit
    task_soft_time_limit=540,   # 9 dakika soft limit (temiz kapanış için)
    # Sonuç saklama süresi (saniye)
    result_expires=3600,        # 1 saat
    # Worker health
    worker_send_task_events=True,
    task_send_sent_event=True,
)


@worker_ready.connect
def on_worker_ready(sender, **kwargs):
    logger.info("✅ Celery worker hazır ve Redis'e bağlı.")


@worker_shutdown.connect
def on_worker_shutdown(sender, **kwargs):
    logger.info("🛑 Celery worker kapatılıyor...")
