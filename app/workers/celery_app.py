from celery import Celery
from app.core.config import settings

app = Celery(
    "presentation_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks_cpu", "app.workers.tasks_gpu"]
)

app.conf.update(
    task_track_started=True,
)
