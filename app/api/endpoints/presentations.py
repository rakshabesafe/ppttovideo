import os
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

        # Get file information first to determine content length
        try:
            file_stat = minio_service.client.stat_object(bucket_name, object_name)
            file_size = file_stat.size
        except S3Error:
            file_size = None

        # Get file data - load entire file to avoid streaming issues in some browsers
        response = minio_service.client.get_object(bucket_name, object_name)
        video_data = response.read()
        response.close()
        response.release_conn()
        
        # Prepare headers with proper content length and caching
        headers = {
            "Content-Disposition": f"inline; filename={object_name}",
            "Accept-Ranges": "bytes", 
            "Cache-Control": "no-cache",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Headers": "Range, Content-Range, Content-Length",
            "Content-Length": str(len(video_data))
        }

        # Return the entire file as response instead of streaming
        from fastapi.responses import Response
        return Response(
            content=video_data,
            media_type="video/mp4",
            headers=headers
        )

    except S3Error as e:
        raise HTTPException(status_code=500, detail=f"MinIO error: {e}")


@router.get("/download/audio/{job_id}/{slide_number}")
def download_slide_audio(job_id: int, slide_number: int, db: Session = Depends(get_db)):
    db_job = crud.get_presentation_job(db, job_id=job_id)
    if db_job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    # Construct the object name from the s3_pptx_path
    pptx_filename = os.path.basename(db_job.s3_pptx_path)
    job_uuid = os.path.splitext(pptx_filename)[0]
    
    object_name = f"{job_uuid}/audio/slide_{slide_number}.wav"
    bucket_name = "presentations"

    try:
        # Get file data
        response = minio_service.client.get_object(bucket_name, object_name)
        audio_data = response.read()
        response.close()
        response.release_conn()

        headers = {
            "Content-Disposition": f"attachment; filename=slide_{slide_number}.wav",
            "Content-Length": str(len(audio_data)),
            "Access-Control-Allow-Origin": "*",
        }

        from fastapi.responses import Response
        return Response(
            content=audio_data,
            media_type="audio/wav",
            headers=headers
        )

    except S3Error as e:
        if e.code == "NoSuchKey":
            raise HTTPException(status_code=404, detail=f"Audio for slide {slide_number} not found.")
        else:
            raise HTTPException(status_code=500, detail=f"MinIO error: {e}")


@router.get("/progress/{job_id}")
def get_job_progress(job_id: int, db: Session = Depends(get_db)):
    """Get detailed progress information for a job including individual task status"""
    db_job = crud.get_presentation_job(db, job_id=job_id)
    if db_job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Get all tasks for this job
    from app.db.models import JobTask
    tasks = db.query(JobTask).filter(JobTask.job_id == job_id).order_by(JobTask.created_at).all()
    
    # Build detailed progress response
    progress_info = {
        "job_id": job_id,
        "status": db_job.status,
        "current_stage": db_job.current_stage,
        "num_slides": db_job.num_slides,
        "error_message": db_job.error_message,
        "created_at": db_job.created_at,
        "updated_at": db_job.updated_at,
        "tasks": []
    }
    
    for task in tasks:
        task_info = {
            "id": task.id,
            "task_type": task.task_type,
            "slide_number": task.slide_number,
            "status": task.status,
            "progress_message": task.progress_message,
            "error_message": task.error_message,
            "started_at": task.started_at,
            "completed_at": task.completed_at
        }
        progress_info["tasks"].append(task_info)
    
    # Generate overall progress description
    if db_job.status == "completed":
        progress_info["overall_progress"] = "✅ Video generation completed successfully!"
    elif db_job.status == "failed":
        progress_info["overall_progress"] = f"❌ Job failed: {db_job.error_message}"
    else:
        # Generate dynamic progress based on tasks
        total_tasks = len(tasks)
        completed_tasks = len([t for t in tasks if t.status == "completed"])
        
        if db_job.current_stage == "pending":
            progress_info["overall_progress"] = "🔄 Job queued and waiting to start..."
        elif db_job.current_stage == "processing_slides":
            progress_info["overall_progress"] = "📊 Converting PowerPoint slides to images..."
        elif db_job.current_stage == "synthesizing_audio":
            audio_tasks = [t for t in tasks if t.task_type == "audio_synthesis"]
            completed_audio = len([t for t in audio_tasks if t.status == "completed"])
            
            if audio_tasks:
                progress_info["overall_progress"] = f"🎵 Synthesizing audio: {completed_audio}/{len(audio_tasks)} slides completed"
                # Add individual slide progress
                for task in audio_tasks:
                    if task.status == "completed":
                        progress_info["overall_progress"] += f"\n  ✅ Slide {task.slide_number}: Audio generated"
                    elif task.status == "running":
                        progress_info["overall_progress"] += f"\n  🔄 Slide {task.slide_number}: {task.progress_message or 'Processing...'}"
                    else:
                        progress_info["overall_progress"] += f"\n  ⏳ Slide {task.slide_number}: Queued"
            else:
                progress_info["overall_progress"] = "🎵 Starting audio synthesis..."
        elif db_job.current_stage == "assembling_video":
            progress_info["overall_progress"] = "🎬 Assembling final video from slides and audio..."
        else:
            progress_info["overall_progress"] = f"🔄 Processing ({completed_tasks}/{total_tasks} tasks completed)"
    
    return progress_info
