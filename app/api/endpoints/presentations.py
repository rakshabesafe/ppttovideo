from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from app import crud, schemas
from app.api.dependencies import get_db
from app.services.minio_service import minio_service
from app.workers.celery_app import app as celery_app
import uuid

router = APIRouter()

@router.post("/", response_model=schemas.PresentationJob)
def create_presentation(
    owner_id: int = Form(...),
    voice_clone_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    if not file.content_type == "application/vnd.openxmlformats-officedocument.presentationml.presentation":
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a .pptx file.")

    # Generate a unique name for the file
    object_name = f"{uuid.uuid4()}.pptx"

    # Upload to MinIO's ingest bucket
    s3_path = minio_service.upload_file(
        bucket_name="ingest",
        object_name=object_name,
        data=file.file,
        length=file.size
    )

    # Create DB record for the job
    job_data = schemas.PresentationJobCreate(owner_id=owner_id, voice_clone_id=voice_clone_id)
    db_job = crud.create_presentation_job(db=db, job=job_data, pptx_s3_path=s3_path)

    # Dispatch the first task in the pipeline
    celery_app.send_task("app.workers.tasks_cpu.decompose_presentation", args=[db_job.id])

    return db_job

from minio.error import S3Error
from starlette.responses import StreamingResponse

@router.get("/status/all", response_model=list[schemas.PresentationJob])
def get_all_jobs(db: Session = Depends(get_db)):
    # In a real app, this should be paginated
    return db.query(crud.models.PresentationJob).order_by(crud.models.PresentationJob.created_at.desc()).all()

@router.get("/status/{job_id}", response_model=schemas.PresentationJob)
def get_job_status(job_id: int, db: Session = Depends(get_db)):
    db_job = crud.get_presentation_job(db, job_id=job_id)
    if db_job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return db_job

@router.get("/download/{job_id}")
def download_video(job_id: int, db: Session = Depends(get_db)):
    db_job = crud.get_presentation_job(db, job_id=job_id)
    if db_job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if db_job.status != "completed":
        raise HTTPException(status_code=400, detail="Job is not complete.")
    if not db_job.s3_video_path:
        raise HTTPException(status_code=404, detail="Video file not found.")

    try:
        bucket_name = "output"
        object_name = db_job.s3_video_path.split('/')[-1]

        response = minio_service.client.get_object(bucket_name, object_name)

        return StreamingResponse(response.stream(32*1024), media_type="video/mp4", headers={
            "Content-Disposition": f"attachment; filename={object_name}"
        })

    except S3Error as e:
        raise HTTPException(status_code=500, detail=f"MinIO error: {e}")
