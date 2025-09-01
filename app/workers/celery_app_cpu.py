from celery import Celery
from app.core.config import settings

app = Celery(
    "presentation_worker_cpu",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks_cpu"]
)

app.conf.update(
    task_track_started=True,
    task_routes={
        'app.workers.tasks_cpu.decompose_presentation': {'queue': 'cpu_tasks'},
        'app.workers.tasks_cpu.assemble_video': {'queue': 'cpu_tasks'},
        'app.workers.tasks_gpu.synthesize_audio': {'queue': 'gpu_tasks'},
    },
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)