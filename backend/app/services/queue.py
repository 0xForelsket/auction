from celery import Celery

from app.config import settings

celery_client = Celery(
    "auction_ocr_client",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)


def enqueue_preprocess(document_id: str) -> None:
    celery_client.send_task("worker.tasks.preprocess", args=[document_id])
