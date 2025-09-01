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

class PresentationJob(PresentationJobBase):
    id: int
    status: str
    s3_pptx_path: str
    s3_video_path: str | None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    owner_id: int
    voice_clone_id: int

    class Config:
        from_attributes = True
