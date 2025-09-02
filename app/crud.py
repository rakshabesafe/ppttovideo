from sqlalchemy.orm import Session
from .db import models
from . import schemas

# User CRUD
def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def get_user_by_name(db: Session, name: str):
    return db.query(models.User).filter(models.User.name == name).first()

def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.User).offset(skip).limit(limit).all()

def create_user(db: Session, user: schemas.UserCreate):
    db_user = models.User(name=user.name, email=user.email)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# Voice Clone CRUD
def create_voice_clone(db: Session, voice_clone: schemas.VoiceCloneCreate, s3_path: str):
    db_voice_clone = models.VoiceClone(**voice_clone.model_dump(), s3_path=s3_path)
    db.add(db_voice_clone)
    db.commit()
    db.refresh(db_voice_clone)
    return db_voice_clone

def get_voice_clones_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    return db.query(models.VoiceClone).filter(models.VoiceClone.owner_id == user_id).offset(skip).limit(limit).all()

# Presentation Job CRUD
def create_presentation_job(db: Session, job: schemas.PresentationJobCreate, pptx_s3_path: str):
    db_job = models.PresentationJob(
        owner_id=job.owner_id,
        voice_clone_id=job.voice_clone_id,
        s3_pptx_path=pptx_s3_path,
        status="pending"
    )
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    return db_job

def get_presentation_job(db: Session, job_id: int):
    return db.query(models.PresentationJob).filter(models.PresentationJob.id == job_id).first()

def update_job_status(db: Session, job_id: int, status: str, video_path: str = None, error_message: str = None, current_stage: str = None):
    db_job = get_presentation_job(db, job_id)
    if db_job:
        db_job.status = status
        if video_path:
            db_job.s3_video_path = video_path
        if error_message:
            db_job.error_message = error_message
        if current_stage:
            db_job.current_stage = current_stage
        db.commit()
        db.refresh(db_job)
    return db_job

def update_job_slides(db: Session, job_id: int, num_slides: int):
    db_job = get_presentation_job(db, job_id)
    if db_job:
        db_job.num_slides = num_slides
        db.commit()
        db.refresh(db_job)
    return db_job

# JobTask CRUD
def create_job_task(db: Session, job_id: int, task_type: str, slide_number: int = None, celery_task_id: str = None):
    db_task = models.JobTask(
        job_id=job_id,
        task_type=task_type,
        slide_number=slide_number,
        celery_task_id=celery_task_id,
        status="pending"
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task

def update_task_status(db: Session, task_id: int = None, celery_task_id: str = None, status: str = None, 
                      progress_message: str = None, error_message: str = None, set_celery_task_id: str = None):
    import datetime
    
    if task_id:
        db_task = db.query(models.JobTask).filter(models.JobTask.id == task_id).first()
    elif celery_task_id:
        db_task = db.query(models.JobTask).filter(models.JobTask.celery_task_id == celery_task_id).first()
    else:
        return None
    
    if db_task:
        if status:
            db_task.status = status
            if status == "running" and not db_task.started_at:
                db_task.started_at = datetime.datetime.utcnow()
            elif status in ["completed", "failed", "cancelled"]:
                db_task.completed_at = datetime.datetime.utcnow()
        
        if progress_message:
            db_task.progress_message = progress_message
        if error_message:
            db_task.error_message = error_message
        if set_celery_task_id:
            db_task.celery_task_id = set_celery_task_id
            
        db.commit()
        db.refresh(db_task)
    return db_task

def get_job_tasks(db: Session, job_id: int):
    return db.query(models.JobTask).filter(models.JobTask.job_id == job_id).order_by(
        models.JobTask.task_type, models.JobTask.slide_number.asc().nullslast()
    ).all()

def get_presentation_jobs_by_status(db: Session, statuses: list, skip: int = 0, limit: int = 100):
    """Get presentation jobs by status list"""
    return db.query(models.PresentationJob).filter(
        models.PresentationJob.status.in_(statuses)
    ).offset(skip).limit(limit).all()

def get_old_presentation_jobs(db: Session, cutoff_date, statuses: list = None):
    """Get presentation jobs older than cutoff_date"""
    query = db.query(models.PresentationJob).filter(
        models.PresentationJob.created_at < cutoff_date
    )
    
    if statuses:
        query = query.filter(models.PresentationJob.status.in_(statuses))
    
    return query.all()

def delete_presentation_job(db: Session, job_id: int):
    """Delete a presentation job"""
    job = get_presentation_job(db, job_id)
    if job:
        db.delete(job)
        db.commit()
        return True
    return False

def get_all_presentation_jobs(db: Session, skip: int = 0, limit: int = 100):
    """Get all presentation jobs"""
    return db.query(models.PresentationJob).offset(skip).limit(limit).all()

def create_default_voice_clones(db: Session):
    """Create default voice clones using OpenVoice built-in speakers"""
    default_voices = [
        {"name": "English (Default)", "s3_path": "builtin://en-default.pth", "owner_id": 1},
        {"name": "English (US)", "s3_path": "builtin://en-us.pth", "owner_id": 1}, 
        {"name": "English (UK)", "s3_path": "builtin://en-br.pth", "owner_id": 1},
        {"name": "English (Australia)", "s3_path": "builtin://en-au.pth", "owner_id": 1},
        {"name": "English (India)", "s3_path": "builtin://en-india.pth", "owner_id": 1},
        {"name": "Spanish", "s3_path": "builtin://es.pth", "owner_id": 1},
        {"name": "French", "s3_path": "builtin://fr.pth", "owner_id": 1},
        {"name": "Japanese", "s3_path": "builtin://jp.pth", "owner_id": 1},
        {"name": "Korean", "s3_path": "builtin://kr.pth", "owner_id": 1},
        {"name": "Chinese", "s3_path": "builtin://zh.pth", "owner_id": 1},
    ]
    
    for voice_data in default_voices:
        # Check if voice clone already exists
        existing = db.query(models.VoiceClone).filter(models.VoiceClone.name == voice_data["name"]).first()
        if not existing:
            db_voice = models.VoiceClone(**voice_data)
            db.add(db_voice)
    
    db.commit()
    return default_voices
