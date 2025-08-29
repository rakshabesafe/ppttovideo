import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.session import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    voice_clones = relationship("VoiceClone", back_populates="owner")
    presentations = relationship("PresentationJob", back_populates="owner")

class VoiceClone(Base):
    __tablename__ = "voice_clones"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    s3_path = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    owner_id = Column(Integer, ForeignKey("users.id"))

    owner = relationship("User", back_populates="voice_clones")

class PresentationJob(Base):
    __tablename__ = "presentation_jobs"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(String, default="pending")
    s3_pptx_path = Column(String, nullable=False)
    s3_video_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    owner_id = Column(Integer, ForeignKey("users.id"))
    voice_clone_id = Column(Integer, ForeignKey("voice_clones.id"))

    owner = relationship("User", back_populates="presentations")
    voice_clone = relationship("VoiceClone")
