from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional
from pydantic import BaseModel
from app.services.cleanup_service import cleanup_service

router = APIRouter()

class CleanupPreviewRequest(BaseModel):
    days_old: int = 7
    status_filter: Optional[List[str]] = None

class CleanupRequest(BaseModel):
    days_old: int = 7
    status_filter: Optional[List[str]] = None

class SpecificJobsCleanupRequest(BaseModel):
    job_ids: List[int]

@router.get("/preview")
async def preview_cleanup(
    days_old: int = Query(7, description="Number of days old to consider for cleanup"),
    status_filter: Optional[str] = Query(None, description="Comma-separated list of statuses to cleanup (e.g., 'completed,failed')")
):
    """
    Preview what jobs and files would be cleaned up without actually deleting them.
    
    Args:
        days_old: Jobs older than this many days will be considered for cleanup
        status_filter: Comma-separated list of job statuses to include in cleanup
    
    Returns:
        dict: Preview of jobs that would be cleaned up
    """
    try:
        # Parse status filter
        statuses = None
        if status_filter:
            statuses = [status.strip() for status in status_filter.split(',')]
        
        preview = cleanup_service.get_cleanup_preview(
            days_old=days_old,
            status_filter=statuses
        )
        
        return {
            "success": True,
            "preview": preview,
            "message": f"Found {preview['jobs_count']} jobs that would be cleaned up"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating cleanup preview: {str(e)}")

@router.post("/execute")
async def execute_cleanup(request: CleanupRequest):
    """
    Execute cleanup of old jobs and their associated files.
    
    Args:
        request: Cleanup configuration including days_old and status_filter
        
    Returns:
        dict: Summary of cleanup results
    """
    try:
        if request.days_old < 1:
            raise HTTPException(status_code=400, detail="days_old must be at least 1")
        
        # Default status filter if not provided
        status_filter = request.status_filter or ['completed', 'failed']
        
        # Execute cleanup
        cleanup_stats = cleanup_service.cleanup_old_jobs(
            days_old=request.days_old,
            status_filter=status_filter
        )
        
        return {
            "success": True,
            "cleanup_stats": cleanup_stats,
            "message": f"Cleanup completed. Deleted {cleanup_stats['jobs_deleted']} jobs and {cleanup_stats['files_deleted']} files."
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error executing cleanup: {str(e)}")

@router.post("/specific-jobs")
async def cleanup_specific_jobs(request: SpecificJobsCleanupRequest):
    """
    Clean up specific jobs by their IDs.
    
    Args:
        request: List of job IDs to cleanup
        
    Returns:
        dict: Summary of cleanup results
    """
    try:
        if not request.job_ids:
            raise HTTPException(status_code=400, detail="job_ids list cannot be empty")
        
        # Execute cleanup
        cleanup_stats = cleanup_service.cleanup_specific_jobs(request.job_ids)
        
        return {
            "success": True,
            "cleanup_stats": cleanup_stats,
            "message": f"Specific job cleanup completed. Deleted {cleanup_stats['jobs_deleted']} jobs and {cleanup_stats['files_deleted']} files."
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error executing specific job cleanup: {str(e)}")

@router.get("/stats")
async def get_cleanup_stats():
    """
    Get statistics about jobs that could be cleaned up.
    
    Returns:
        dict: Statistics about cleanup candidates
    """
    try:
        # Get preview for different time periods
        stats = {
            "7_days": cleanup_service.get_cleanup_preview(days_old=7),
            "30_days": cleanup_service.get_cleanup_preview(days_old=30),
            "90_days": cleanup_service.get_cleanup_preview(days_old=90)
        }
        
        return {
            "success": True,
            "stats": stats,
            "message": "Cleanup statistics retrieved successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving cleanup stats: {str(e)}")

@router.get("/job-statuses")
async def get_available_job_statuses():
    """
    Get list of available job statuses that can be used for filtering.
    
    Returns:
        dict: List of available job statuses
    """
    return {
        "success": True,
        "statuses": [
            "pending",
            "processing_slides", 
            "synthesizing_audio",
            "assembling_video",
            "completed",
            "failed"
        ],
        "recommended_for_cleanup": ["completed", "failed"],
        "message": "Available job statuses retrieved successfully"
    }