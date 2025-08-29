from sqlalchemy.orm import Session
from . import models, schemas

# User CRUD
def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

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
    db_voice_clone = models.VoiceClone(**voice_clone.dict(), s3_path=s3_path)
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

def update_job_status(db: Session, job_id: int, status: str, video_path: str = None):
    db_job = get_presentation_job(db, job_id)
    if db_job:
        db_job.status = status
        if video_path:
            db_job.s3_video_path = video_path
        db.commit()
        db.refresh(db_job)
    return db_job
