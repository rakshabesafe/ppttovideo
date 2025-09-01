from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db import models
from app.services.minio_service import minio_service
from minio.error import S3Error
import logging

logger = logging.getLogger(__name__)

class CleanupService:
    def __init__(self):
        self.minio_client = minio_service.client

    def cleanup_old_jobs(self, days_old: int = 7, status_filter: List[str] = None) -> dict:
        """
        Clean up jobs older than specified days and their associated files.
        
        Args:
            days_old: Number of days old jobs should be to qualify for cleanup
            status_filter: List of job statuses to cleanup (default: all except 'pending', 'processing_slides', 'synthesizing_audio', 'assembling_video')
        
        Returns:
            dict: Summary of cleanup results
        """
        if status_filter is None:
            # Don't cleanup jobs that might still be processing
            status_filter = ['completed', 'failed']
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        db = SessionLocal()
        cleanup_stats = {
            'jobs_deleted': 0,
            'files_deleted': 0,
            'errors': [],
            'jobs_processed': []
        }
        
        try:
            # Find jobs to cleanup
            jobs_to_cleanup = db.query(models.PresentationJob).filter(
                models.PresentationJob.created_at < cutoff_date,
                models.PresentationJob.status.in_(status_filter)
            ).all()
            
            for job in jobs_to_cleanup:
                try:
                    job_cleanup_result = self._cleanup_single_job(db, job)
                    cleanup_stats['jobs_deleted'] += 1
                    cleanup_stats['files_deleted'] += job_cleanup_result['files_deleted']
                    cleanup_stats['jobs_processed'].append({
                        'job_id': job.id,
                        'status': job.status,
                        'created_at': job.created_at.isoformat(),
                        'files_deleted': job_cleanup_result['files_deleted']
                    })
                    
                except Exception as e:
                    error_msg = f"Error cleaning up job {job.id}: {str(e)}"
                    logger.error(error_msg)
                    cleanup_stats['errors'].append(error_msg)
            
        except Exception as e:
            error_msg = f"Error during cleanup operation: {str(e)}"
            logger.error(error_msg)
            cleanup_stats['errors'].append(error_msg)
        finally:
            db.close()
            
        return cleanup_stats

    def cleanup_specific_jobs(self, job_ids: List[int]) -> dict:
        """
        Clean up specific jobs by their IDs.
        
        Args:
            job_ids: List of job IDs to cleanup
            
        Returns:
            dict: Summary of cleanup results
        """
        db = SessionLocal()
        cleanup_stats = {
            'jobs_deleted': 0,
            'files_deleted': 0,
            'errors': [],
            'jobs_processed': []
        }
        
        try:
            for job_id in job_ids:
                job = db.query(models.PresentationJob).filter(
                    models.PresentationJob.id == job_id
                ).first()
                
                if not job:
                    cleanup_stats['errors'].append(f"Job {job_id} not found")
                    continue
                
                try:
                    job_cleanup_result = self._cleanup_single_job(db, job)
                    cleanup_stats['jobs_deleted'] += 1
                    cleanup_stats['files_deleted'] += job_cleanup_result['files_deleted']
                    cleanup_stats['jobs_processed'].append({
                        'job_id': job.id,
                        'status': job.status,
                        'created_at': job.created_at.isoformat(),
                        'files_deleted': job_cleanup_result['files_deleted']
                    })
                    
                except Exception as e:
                    error_msg = f"Error cleaning up job {job_id}: {str(e)}"
                    logger.error(error_msg)
                    cleanup_stats['errors'].append(error_msg)
        
        except Exception as e:
            error_msg = f"Error during specific job cleanup: {str(e)}"
            logger.error(error_msg)
            cleanup_stats['errors'].append(error_msg)
        finally:
            db.close()
            
        return cleanup_stats

    def _cleanup_single_job(self, db: Session, job: models.PresentationJob) -> dict:
        """
        Clean up a single job and all its associated files.
        
        Args:
            db: Database session
            job: PresentationJob instance to cleanup
            
        Returns:
            dict: Cleanup result for this job
        """
        files_deleted = 0
        
        # Extract UUID from PPT path for finding related files
        # Format: /ingest/{uuid}.pptx
        pptx_uuid = None
        if job.s3_pptx_path:
            pptx_path_parts = job.s3_pptx_path.strip('/').split('/')
            if len(pptx_path_parts) >= 2:
                filename = pptx_path_parts[-1]  # Get filename
                pptx_uuid = filename.split('.')[0]  # Remove extension to get UUID
        
        # 1. Delete original PPTX file
        if job.s3_pptx_path:
            files_deleted += self._delete_s3_file_safe(job.s3_pptx_path)
        
        # 2. Delete final video file
        if job.s3_video_path:
            files_deleted += self._delete_s3_file_safe(job.s3_video_path)
        
        # 3. Delete job-specific files in presentations bucket
        # Audio files: presentations/{job_id}/audio/
        files_deleted += self._delete_s3_prefix_safe('presentations', f'{job.id}/audio/')
        
        # Notes files: presentations/{job_id}/notes/
        files_deleted += self._delete_s3_prefix_safe('presentations', f'{job.id}/notes/')
        
        # 4. Delete UUID-based files if we have the UUID
        if pptx_uuid:
            # Images: presentations/{uuid}/images/
            files_deleted += self._delete_s3_prefix_safe('presentations', f'{pptx_uuid}/images/')
            
            # Any other UUID-based files
            files_deleted += self._delete_s3_prefix_safe('presentations', f'{pptx_uuid}/')
        
        # 5. Delete the job record from database
        db.delete(job)
        db.commit()
        
        return {'files_deleted': files_deleted}

    def _delete_s3_file_safe(self, s3_path: str) -> int:
        """
        Safely delete a single file from S3.
        
        Args:
            s3_path: Full S3 path like "/bucket/object"
            
        Returns:
            int: 1 if file was deleted, 0 if not found or error
        """
        try:
            # Parse S3 path: /bucket/object -> bucket, object
            clean_path = s3_path.strip('/')
            path_parts = clean_path.split('/', 1)
            
            if len(path_parts) != 2:
                logger.warning(f"Invalid S3 path format: {s3_path}")
                return 0
                
            bucket_name, object_name = path_parts
            
            # Check if object exists before trying to delete
            try:
                self.minio_client.stat_object(bucket_name, object_name)
            except S3Error as e:
                if e.code == 'NoSuchKey':
                    logger.info(f"File not found (already deleted?): {s3_path}")
                    return 0
                else:
                    raise
            
            # Delete the file
            self.minio_client.remove_object(bucket_name, object_name)
            logger.info(f"Deleted file: {s3_path}")
            return 1
            
        except Exception as e:
            logger.error(f"Error deleting file {s3_path}: {str(e)}")
            return 0

    def _delete_s3_prefix_safe(self, bucket_name: str, prefix: str) -> int:
        """
        Safely delete all files with a given prefix from S3.
        
        Args:
            bucket_name: S3 bucket name
            prefix: Prefix to match files
            
        Returns:
            int: Number of files deleted
        """
        deleted_count = 0
        
        try:
            # List all objects with the prefix
            objects = self.minio_client.list_objects(bucket_name, prefix=prefix, recursive=True)
            
            for obj in objects:
                try:
                    self.minio_client.remove_object(bucket_name, obj.object_name)
                    deleted_count += 1
                    logger.info(f"Deleted file: /{bucket_name}/{obj.object_name}")
                except Exception as e:
                    logger.error(f"Error deleting /{bucket_name}/{obj.object_name}: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Error listing/deleting objects with prefix {prefix} in {bucket_name}: {str(e)}")
            
        return deleted_count

    def get_cleanup_preview(self, days_old: int = 7, status_filter: List[str] = None) -> dict:
        """
        Preview what would be cleaned up without actually deleting anything.
        
        Args:
            days_old: Number of days old jobs should be to qualify for cleanup
            status_filter: List of job statuses to cleanup
            
        Returns:
            dict: Preview of what would be cleaned up
        """
        if status_filter is None:
            status_filter = ['completed', 'failed']
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        db = SessionLocal()
        try:
            jobs_to_cleanup = db.query(models.PresentationJob).filter(
                models.PresentationJob.created_at < cutoff_date,
                models.PresentationJob.status.in_(status_filter)
            ).all()
            
            preview = {
                'jobs_count': len(jobs_to_cleanup),
                'cutoff_date': cutoff_date.isoformat(),
                'status_filter': status_filter,
                'jobs': []
            }
            
            for job in jobs_to_cleanup:
                job_info = {
                    'id': job.id,
                    'status': job.status,
                    'created_at': job.created_at.isoformat(),
                    'pptx_path': job.s3_pptx_path,
                    'video_path': job.s3_video_path,
                    'owner_id': job.owner_id
                }
                preview['jobs'].append(job_info)
                
            return preview
            
        finally:
            db.close()

# Create singleton instance
cleanup_service = CleanupService()