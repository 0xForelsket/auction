from worker.celery_app import celery_app


@celery_app.task
def validate(document_id: str):
    return {"status": "skipped", "document_id": document_id}
