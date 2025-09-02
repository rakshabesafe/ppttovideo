from pydantic import BaseModel
import datetime

# Base Models
class UserBase(BaseModel):
    name: str
    email: str | None = None

class VoiceCloneBase(BaseModel):
    name: str

class PresentationJobBase(BaseModel):
    pass

# Schemas for Creation (what the API receives)
class UserCreate(UserBase):
    pass

class VoiceCloneCreate(VoiceCloneBase):
    owner_id: int

class PresentationJobCreate(PresentationJobBase):
    owner_id: int
    voice_clone_id: int

# Schemas for Reading (what the API sends back)
class User(UserBase):
    id: int
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class VoiceClone(VoiceCloneBase):
    id: int
    s3_path: str
    created_at: datetime.datetime
    owner_id: int

    class Config:
        from_attributes = True

# Schemas for JobTask
class JobTaskBase(BaseModel):
    task_type: str
    slide_number: int | None = None

class JobTask(JobTaskBase):
    id: int
    job_id: int
    celery_task_id: str | None
    status: str
    progress_message: str | None
    error_message: str | None
    started_at: datetime.datetime | None
    completed_at: datetime.datetime | None
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class PresentationJob(PresentationJobBase):
    id: int
    status: str
    s3_pptx_path: str
    s3_video_path: str | None
    error_message: str | None
    num_slides: int | None
    current_stage: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    owner_id: int
    voice_clone_id: int

    class Config:
        from_attributes = True

# Detailed dashboard schema
class PresentationJobDashboard(PresentationJob):
    tasks: list[JobTask] = []

    class Config:
        from_attributes = True

# Worker status schema
class WorkerStatus(BaseModel):
    worker_name: str
    status: str  # online, offline
    active_tasks: list[dict]
    queued_tasks: list[dict]
    last_heartbeat: datetime.datetime | None

# System status schema
class SystemStatus(BaseModel):
    workers: list[WorkerStatus]
    queue_stats: dict
    active_jobs: int
    total_jobs: int
