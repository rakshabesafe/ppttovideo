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

def update_job_status(db: Session, job_id: int, status: str, video_path: str = None):
    db_job = get_presentation_job(db, job_id)
    if db_job:
        db_job.status = status
        if video_path:
            db_job.s3_video_path = video_path
        db.commit()
        db.refresh(db_job)
    return db_job

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
