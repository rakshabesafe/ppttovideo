from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import crud, schemas
from app.api.dependencies import get_db
from app.db.models import PresentationJob, JobTask
from app.workers.celery_app import app as celery_app
from app.workers.celery_app_cpu import app as celery_app_cpu
from app.workers.celery_app_gpu import app as celery_app_gpu
import datetime
from typing import Dict, Any

router = APIRouter()

@router.get("/job/{job_id}", response_model=schemas.PresentationJobDashboard)
def get_job_dashboard(job_id: int, db: Session = Depends(get_db)):
    """Get detailed dashboard view of a specific job including all tasks"""
    db_job = db.query(PresentationJob).filter(PresentationJob.id == job_id).first()
    if db_job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Load tasks explicitly to avoid lazy loading issues
    tasks = db.query(JobTask).filter(JobTask.job_id == job_id).order_by(
        JobTask.task_type, JobTask.slide_number.asc().nullslast()
    ).all()
    
    # Convert to dashboard schema
    job_dict = {
        "id": db_job.id,
        "status": db_job.status,
        "s3_pptx_path": db_job.s3_pptx_path,
        "s3_video_path": db_job.s3_video_path,
        "error_message": db_job.error_message,
        "num_slides": db_job.num_slides,
        "current_stage": db_job.current_stage,
        "created_at": db_job.created_at,
        "updated_at": db_job.updated_at,
        "owner_id": db_job.owner_id,
        "voice_clone_id": db_job.voice_clone_id,
        "tasks": tasks
    }
    
    return schemas.PresentationJobDashboard(**job_dict)

@router.get("/workers", response_model=schemas.SystemStatus)
def get_worker_status():
    """Get status of all Celery workers and queue information"""
    try:
        # Get worker statistics from all Celery apps
        workers = []
        
        # Check CPU worker
        try:
            cpu_inspect = celery_app_cpu.control.inspect()
            cpu_active = cpu_inspect.active() or {}
            cpu_reserved = cpu_inspect.reserved() or {}
            cpu_stats = cpu_inspect.stats() or {}
            
            for worker_name, active_tasks in cpu_active.items():
                reserved_tasks = cpu_reserved.get(worker_name, [])
                worker_stats = cpu_stats.get(worker_name, {})
                
                workers.append({
                    "worker_name": worker_name,
                    "status": "online" if worker_stats else "offline",
                    "active_tasks": active_tasks,
                    "queued_tasks": reserved_tasks,
                    "last_heartbeat": datetime.datetime.utcnow() if worker_stats else None
                })
        except Exception as e:
            print(f"Error getting CPU worker status: {e}")
        
        # Check GPU worker
        try:
            gpu_inspect = celery_app_gpu.control.inspect()
            gpu_active = gpu_inspect.active() or {}
            gpu_reserved = gpu_inspect.reserved() or {}
            gpu_stats = gpu_inspect.stats() or {}
            
            for worker_name, active_tasks in gpu_active.items():
                reserved_tasks = gpu_reserved.get(worker_name, [])
                worker_stats = gpu_stats.get(worker_name, {})
                
                workers.append({
                    "worker_name": worker_name,
                    "status": "online" if worker_stats else "offline",
                    "active_tasks": active_tasks,
                    "queued_tasks": reserved_tasks,
                    "last_heartbeat": datetime.datetime.utcnow() if worker_stats else None
                })
        except Exception as e:
            print(f"Error getting GPU worker status: {e}")
        
        # Calculate queue statistics
        total_active = sum(len(w["active_tasks"]) for w in workers)
        total_queued = sum(len(w["queued_tasks"]) for w in workers)
        
        queue_stats = {
            "total_active_tasks": total_active,
            "total_queued_tasks": total_queued,
            "cpu_worker_active": len([w for w in workers if "cpu" in w["worker_name"] and w["status"] == "online"]),
            "gpu_worker_active": len([w for w in workers if "gpu" in w["worker_name"] and w["status"] == "online"])
        }
        
        return schemas.SystemStatus(
            workers=[schemas.WorkerStatus(**w) for w in workers],
            queue_stats=queue_stats,
            active_jobs=total_active,
            total_jobs=total_active + total_queued
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting worker status: {str(e)}")

@router.get("/jobs/active", response_model=list[schemas.PresentationJobDashboard])
def get_active_jobs(db: Session = Depends(get_db)):
    """Get all currently active/processing jobs with their tasks"""
    active_jobs = db.query(PresentationJob).filter(
        PresentationJob.status.in_(["pending", "processing_slides", "synthesizing_audio", "assembling_video"])
    ).order_by(PresentationJob.created_at.desc()).all()
    
    result = []
    for job in active_jobs:
        tasks = db.query(JobTask).filter(JobTask.job_id == job.id).order_by(
            JobTask.task_type, JobTask.slide_number.asc().nullslast()
        ).all()
        
        job_dict = {
            "id": job.id,
            "status": job.status,
            "s3_pptx_path": job.s3_pptx_path,
            "s3_video_path": job.s3_video_path,
            "error_message": job.error_message,
            "num_slides": job.num_slides,
            "current_stage": job.current_stage,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
            "owner_id": job.owner_id,
            "voice_clone_id": job.voice_clone_id,
            "tasks": tasks
        }
        result.append(schemas.PresentationJobDashboard(**job_dict))
    
    return result

@router.get("/system/health")
def get_system_health():
    """Get overall system health status"""
    try:
        # Check database connectivity
        from app.db.session import SessionLocal
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"
    
    # Check worker connectivity
    try:
        cpu_inspect = celery_app_cpu.control.inspect()
        cpu_stats = cpu_inspect.stats() or {}
        cpu_workers_online = len(cpu_stats)
    except Exception:
        cpu_workers_online = 0
    
    try:
        gpu_inspect = celery_app_gpu.control.inspect()
        gpu_stats = gpu_inspect.stats() or {}
        gpu_workers_online = len(gpu_stats)
    except Exception:
        gpu_workers_online = 0
    
    # Overall system status
    overall_status = "healthy" if (
        db_status == "healthy" and 
        cpu_workers_online > 0 and 
        gpu_workers_online > 0
    ) else "degraded"
    
    return {
        "status": overall_status,
        "database": db_status,
        "cpu_workers": cpu_workers_online,
        "gpu_workers": gpu_workers_online,
        "timestamp": datetime.datetime.utcnow()
    }

@router.post("/job/{job_id}/cancel")
def cancel_job(job_id: int, db: Session = Depends(get_db)):
    """Cancel a running job and all its associated tasks"""
    db_job = db.query(PresentationJob).filter(PresentationJob.id == job_id).first()
    if db_job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if db_job.status in ["completed", "failed", "cancelled"]:
        raise HTTPException(status_code=400, detail="Job cannot be cancelled in current state")
    
    # Cancel all associated Celery tasks
    tasks = db.query(JobTask).filter(JobTask.job_id == job_id).all()
    cancelled_tasks = []
    
    for task in tasks:
        if task.celery_task_id and task.status in ["pending", "running"]:
            try:
                celery_app.control.revoke(task.celery_task_id, terminate=True)
                celery_app_cpu.control.revoke(task.celery_task_id, terminate=True)
                celery_app_gpu.control.revoke(task.celery_task_id, terminate=True)
                
                task.status = "cancelled"
                task.completed_at = datetime.datetime.utcnow()
                cancelled_tasks.append(task.celery_task_id)
            except Exception as e:
                print(f"Error cancelling task {task.celery_task_id}: {e}")
    
    # Update job status
    db_job.status = "cancelled"
    db_job.current_stage = "cancelled"
    db_job.updated_at = datetime.datetime.utcnow()
    
    db.commit()
    
    return {
        "message": f"Job {job_id} cancelled successfully",
        "cancelled_tasks": cancelled_tasks
    }