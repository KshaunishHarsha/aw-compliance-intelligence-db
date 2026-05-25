import logging
from celery_worker import celery_app

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, name="tasks.ping")
def ping(self) -> dict:
    logger.info("ping task received", extra={"task_id": self.request.id})
    return {"status": "pong"}
