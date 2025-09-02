from celery import Celery
from app.core.config import settings

app = Celery(
    "presentation_worker_gpu",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks_gpu"]
)

app.conf.update(
    task_track_started=True,
    task_routes={
        'app.workers.tasks_gpu.synthesize_audio': {'queue': 'gpu_tasks'},
    },
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_time_limit=600,  # 10 minute hard timeout
    task_soft_time_limit=480,  # 8 minute soft timeout
)