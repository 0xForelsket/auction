from celery import Celery

from app.config import settings

celery_app = Celery(
    "auction_ocr",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_time_limit=600,
    task_soft_time_limit=540,
    task_default_queue="default",
)

celery_app.conf.beat_schedule = {
    "watchdog-stuck-documents": {
        "task": "worker.tasks.watchdog.watchdog_stuck_documents",
        "schedule": 300.0,
    }
}

celery_app.autodiscover_tasks(["worker.tasks"])
