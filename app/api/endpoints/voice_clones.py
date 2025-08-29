from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from app import crud, schemas
from app.api.dependencies import get_db
from app.services.minio_service import minio_service
import uuid

router = APIRouter()

@router.post("/", response_model=schemas.VoiceClone)
def create_voice_clone(
    name: str = Form(...),
    owner_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    if not file.content_type == "audio/wav":
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a .wav file.")

    # Generate a unique name for the file to avoid collisions
    file_extension = ".wav"
    object_name = f"{uuid.uuid4()}{file_extension}"

    # Upload to MinIO
    s3_path = minio_service.upload_file(
        bucket_name="voice-clones",
        object_name=object_name,
        data=file.file,
        length=file.size
    )

    # Create DB record
    voice_clone_data = schemas.VoiceCloneCreate(name=name, owner_id=owner_id)
    return crud.create_voice_clone(db=db, voice_clone=voice_clone_data, s3_path=s3_path)

@router.get("/user/{user_id}", response_model=list[schemas.VoiceClone])
def get_voice_clones_for_user(user_id: int, db: Session = Depends(get_db)):
    return crud.get_voice_clones_by_user(db=db, user_id=user_id)
