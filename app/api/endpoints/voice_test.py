from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.api.dependencies import get_db
from app import crud
from pydantic import BaseModel
import os
import tempfile
import time
from typing import Optional
from fastapi.responses import FileResponse
from celery import Celery
import asyncio
from app.services.minio_service import minio_service

router = APIRouter()

class VoiceTestRequest(BaseModel):
    text: str
    voice_clone_id: int

@router.post("/test-voice")
async def test_voice_synthesis(request: VoiceTestRequest, db: Session = Depends(get_db)):
    """
    Test voice synthesis with custom text by creating a temporary note and using the GPU worker
    """
    try:
        print(f"Voice test request: text='{request.text[:50]}...', voice_id={request.voice_clone_id}")
        
        # Get voice clone details
        voice_clone = crud.get_voice_clone(db, request.voice_clone_id)
        if not voice_clone:
            raise HTTPException(status_code=404, detail="Voice clone not found")
        
        print(f"Using voice: {voice_clone.name} ({voice_clone.s3_path})")
        
        # Create a temporary "job" for testing - we'll use a fake job ID
        test_job_id = 999999  # Use a high number to avoid conflicts
        test_slide_number = 1
        
        # Upload the test text as a temporary note
        timestamp = int(time.time())
        note_object_name = f"{test_job_id}/notes/slide_{test_slide_number}.txt"
        
        try:
            # Upload test text to MinIO as a note
            from io import BytesIO
            note_data = BytesIO(request.text.encode('utf-8'))
            
            minio_service.upload_file(
                bucket_name="presentations",
                object_name=note_object_name,
                data=note_data,
                length=len(request.text.encode('utf-8'))
            )
            print(f"Uploaded test note to: {note_object_name}")
            
            # Create a temporary job entry in the database
            from app.db.models import PresentationJob
            test_job = PresentationJob(
                id=test_job_id,
                s3_pptx_path=f"/test/test_{timestamp}.pptx",  # Fake path
                voice_clone_id=request.voice_clone_id,
                voice_clone=voice_clone,
                owner_id=1,  # System user
                status="testing"
            )
            
            # Check if test job already exists, if so delete it first
            existing_job = crud.get_presentation_job(db, test_job_id)
            if existing_job:
                db.delete(existing_job)
                db.commit()
            
            db.add(test_job)
            db.commit()
            db.refresh(test_job)
            
            # Import and call the GPU synthesis task directly
            from app.workers.tasks_gpu import synthesize_audio
            
            print("Calling GPU worker for voice synthesis...")
            result = synthesize_audio.delay(test_job_id, test_slide_number)
            
            # Wait for result (with timeout)
            try:
                task_result = result.get(timeout=120)  # 2 minute timeout
                print(f"Synthesis completed: {task_result}")
                
                # Get the generated audio file from MinIO
                audio_object_name = f"{timestamp}/audio/slide_{test_slide_number}.wav"  # This should match the pattern in the task
                
                # Try to find the actual audio file path
                try:
                    # The audio should be stored with the UUID pattern, let's try to find it
                    test_uuid = f"test_{timestamp}"
                    audio_path_attempt = f"{test_uuid}/audio/slide_{test_slide_number}.wav"
                    
                    print(f"Trying to retrieve audio from: {audio_path_attempt}")
                    audio_response = minio_service.client.get_object("presentations", audio_path_attempt)
                    audio_data = audio_response.read()
                    audio_response.close()
                    audio_response.release_conn()
                    
                    # Save to temporary file for response
                    output_filename = f"test_voice_{timestamp}.wav"
                    output_path = f"/tmp/{output_filename}"
                    
                    with open(output_path, "wb") as f:
                        f.write(audio_data)
                    
                    print(f"Audio file created: {output_path}")
                    
                    # Return the audio file
                    return FileResponse(
                        path=output_path,
                        media_type="audio/wav",
                        filename=output_filename,
                        headers={"Content-Disposition": f"attachment; filename={output_filename}"}
                    )
                    
                except Exception as audio_error:
                    print(f"Could not retrieve audio file: {audio_error}")
                    raise HTTPException(status_code=500, detail=f"Audio generated but could not retrieve: {audio_error}")
                
            except Exception as task_error:
                print(f"Synthesis task failed: {task_error}")
                raise HTTPException(status_code=500, detail=f"Synthesis failed: {task_error}")
                
        finally:
            # Cleanup: Remove temporary job and note
            try:
                existing_job = crud.get_presentation_job(db, test_job_id)
                if existing_job:
                    db.delete(existing_job)
                    db.commit()
                    
                # Clean up the temporary note
                try:
                    minio_service.client.remove_object("presentations", note_object_name)
                except:
                    pass  # Ignore cleanup errors
                    
            except Exception as cleanup_error:
                print(f"Cleanup error (ignoring): {cleanup_error}")
        
    except Exception as e:
        print(f"Voice test error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/voices")
async def get_available_voices(db: Session = Depends(get_db)):
    """Get list of available voices for testing"""
    try:
        voice_clones = crud.get_voice_clones(db)
        return [
            {
                "id": vc.id,
                "name": vc.name,
                "type": "builtin" if vc.s3_path.startswith("builtin://") else "custom",
                "s3_path": vc.s3_path
            }
            for vc in voice_clones
        ]
    except Exception as e:
        print(f"Error getting voices: {e}")
        raise HTTPException(status_code=500, detail=str(e))