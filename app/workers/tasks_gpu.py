"""
Refactored GPU worker tasks using modular TTS components

This version separates concerns into distinct, testable components:
- Data retrieval and validation
- TTS processing (MeloTTS + OpenVoice) 
- File upload and cleanup
- Error handling and timeouts
"""

from app.workers.celery_app_gpu import app as celery_app
from app.db.session import SessionLocal
from app import crud
from app.services.minio_service import minio_service
from app.services.tts_service import TTSProcessor, TTSException, MeloTTSException, OpenVoiceException
import torch
import os
import sys
import io
import time
import tempfile
from typing import Tuple, Optional

print(f"Current working directory: {os.getcwd()}")
print(f"Python path: {sys.path}")

# Configurable timeouts via environment variables
TTS_SOFT_TIME_LIMIT = int(os.getenv('TTS_SOFT_TIME_LIMIT', '300'))  # 5 minutes default
TTS_HARD_TIME_LIMIT = int(os.getenv('TTS_HARD_TIME_LIMIT', '360'))  # 6 minutes default

# Initialize TTS processor (models loaded lazily)
device = "cuda:0" if torch.cuda.is_available() else "cpu"
tts_processor = TTSProcessor(device=device)


class AudioSynthesisData:
    """Data class for audio synthesis job information"""
    
    def __init__(self, job_id: int, slide_number: int):
        self.job_id = job_id
        self.slide_number = slide_number
        self.job = None
        self.voice_clone = None
        self.note_text = ""
        self.use_builtin_speaker = False
        self.speaker_name = ""
        self.reference_audio_data = None
        self.reference_file_extension = ""


class AudioSynthesisService:
    """Service class that handles the complete audio synthesis pipeline"""
    
    def __init__(self, tts_processor: TTSProcessor, minio_service):
        self.tts_processor = tts_processor
        self.minio_service = minio_service
    
    def load_job_data(self, db, job_id: int, slide_number: int) -> AudioSynthesisData:
        """
        Load and validate job data from database and storage
        
        Args:
            db: Database session
            job_id: Presentation job ID
            slide_number: Slide number to process
            
        Returns:
            AudioSynthesisData object with loaded information
            
        Raises:
            Exception: If job data cannot be loaded
        """
        data = AudioSynthesisData(job_id, slide_number)
        
        # Load job from database
        data.job = crud.get_presentation_job(db, job_id)
        if not data.job:
            raise Exception(f"Job {job_id} not found.")
        
        data.voice_clone = data.job.voice_clone
        
        # Determine voice type and load voice data
        ref_audio_path = data.voice_clone.s3_path
        
        if ref_audio_path.startswith("builtin://"):
            # Built-in speaker
            data.use_builtin_speaker = True
            data.speaker_name = ref_audio_path.replace("builtin://", "").replace(".pth", "")
            print(f"Using built-in speaker: {data.speaker_name}")
        else:
            # Custom voice clone
            data.use_builtin_speaker = False
            ref_bucket, ref_object = ref_audio_path.split('/', 2)[1:]
            
            try:
                ref_response = self.minio_service.client.get_object(ref_bucket, ref_object)
                data.reference_audio_data = ref_response.read()
                data.reference_file_extension = ref_audio_path.split('.')[-1].lower()
                ref_response.close()
                ref_response.release_conn()
                print(f"Loaded custom voice reference audio ({len(data.reference_audio_data)} bytes)")
            except Exception as e:
                raise Exception(f"Failed to load reference audio: {e}")
        
        # Load note text
        try:
            note_object_name = f"{job_id}/notes/slide_{slide_number}.txt"
            note_response = self.minio_service.client.get_object("presentations", note_object_name)
            data.note_text = note_response.read().decode('utf-8')
            note_response.close()
            note_response.release_conn()
            
            if not data.note_text.strip():
                data.note_text = "[SILENCE]"  # Use silence for empty notes
                
        except Exception as e:
            print(f"Warning: Could not load notes for slide {slide_number}: {e}")
            data.note_text = "[SILENCE]"
        
        return data
    
    def synthesize_audio(self, data: AudioSynthesisData) -> str:
        """
        Synthesize audio using the appropriate TTS method
        
        Args:
            data: AudioSynthesisData with job information
            
        Returns:
            Path to generated audio file
            
        Raises:
            TTSException: If synthesis fails
        """
        output_filename = f"temp_output_{data.job_id}_{data.slide_number}.wav"
        
        try:
            print(f"Synthesizing audio for slide {data.slide_number}: '{data.note_text[:100]}...'")
            
            # Ensure TTS processor is initialized
            if not self.tts_processor.is_ready():
                print("Initializing TTS processor...")
                self.tts_processor.initialize()
            
            if data.use_builtin_speaker:
                # Use built-in speaker with voice cloning
                print(f"Using built-in speaker: {data.speaker_name}")
                return self.tts_processor.synthesize_with_builtin_voice(
                    text=data.note_text,
                    speaker_name=data.speaker_name,
                    output_path=output_filename
                )
            else:
                # Use custom voice cloning
                print("Using custom voice cloning")
                return self.tts_processor.synthesize_with_custom_voice(
                    text=data.note_text,
                    reference_audio_data=data.reference_audio_data,
                    file_extension=data.reference_file_extension,
                    output_path=output_filename
                )
                
        except (MeloTTSException, OpenVoiceException) as e:
            print(f"TTS component error: {e}")
            # Fallback to base TTS without voice cloning
            try:
                print("Falling back to base TTS synthesis...")
                return self.tts_processor.synthesize_base_only(
                    text=data.note_text,
                    output_path=output_filename
                )
            except Exception as fallback_error:
                print(f"Fallback TTS also failed: {fallback_error}")
                # Last resort: create silence
                return self.tts_processor.create_silence(output_filename, duration_seconds=3.0)
        
        except Exception as e:
            raise TTSException(f"Audio synthesis failed: {e}")
    
    def upload_audio_file(self, data: AudioSynthesisData, audio_file_path: str) -> str:
        """
        Upload generated audio file to storage
        
        Args:
            data: AudioSynthesisData with job information  
            audio_file_path: Path to generated audio file
            
        Returns:
            S3 path of uploaded file
            
        Raises:
            Exception: If upload fails
        """
        try:
            # Extract UUID from s3_pptx_path (e.g., "/ingest/uuid.pptx" -> "uuid")
            import os.path
            pptx_filename = os.path.basename(data.job.s3_pptx_path)
            job_uuid = os.path.splitext(pptx_filename)[0]  # Remove .pptx extension
            
            output_s3_path = f"{job_uuid}/audio/slide_{data.slide_number}.wav"
            
            with open(audio_file_path, "rb") as audio_file:
                self.minio_service.upload_file(
                    bucket_name="presentations",
                    object_name=output_s3_path,
                    data=audio_file,
                    length=os.path.getsize(audio_file_path)
                )
            
            print(f"Audio uploaded to: {output_s3_path}")
            return output_s3_path
            
        except Exception as e:
            raise Exception(f"Audio upload failed: {e}")
    
    def cleanup_temp_files(self, *file_paths: str) -> None:
        """Clean up temporary files"""
        for file_path in file_paths:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    print(f"Cleaned up: {file_path}")
                except Exception as e:
                    print(f"Warning: Could not clean up {file_path}: {e}")


# Initialize service
audio_service = AudioSynthesisService(tts_processor, minio_service)


@celery_app.task(name="app.workers.tasks_gpu.synthesize_audio", bind=True, 
                soft_time_limit=TTS_SOFT_TIME_LIMIT, time_limit=TTS_HARD_TIME_LIMIT)
def synthesize_audio(self, job_id: int, slide_number: int):
    """
    Generates audio for a single slide's notes using a cloned voice.
    
    This refactored version uses modular components for:
    - Data loading and validation
    - TTS processing (MeloTTS + OpenVoice)
    - File upload and cleanup
    - Comprehensive error handling
    """
    from celery.exceptions import SoftTimeLimitExceeded
    
    db = SessionLocal()
    temp_files = []
    
    try:
        # Update task status
        crud.update_task_status(
            db, 
            celery_task_id=self.request.id, 
            status="running", 
            progress_message=f"Starting audio synthesis for slide {slide_number}"
        )
        
        # Load job data
        print(f"Loading data for job {job_id}, slide {slide_number}")
        data = audio_service.load_job_data(db, job_id, slide_number)
        
        # Synthesize audio
        print(f"Starting TTS synthesis...")
        audio_file_path = audio_service.synthesize_audio(data)
        temp_files.append(audio_file_path)
        
        # Upload audio file
        print(f"Uploading audio file...")
        output_s3_path = audio_service.upload_audio_file(data, audio_file_path)
        
        # Update task completion
        crud.update_task_status(
            db, 
            celery_task_id=self.request.id, 
            status="completed", 
            progress_message=f"Audio synthesis completed for slide {slide_number}"
        )
        
        print(f"Audio synthesis completed for job {job_id}, slide {slide_number}")
        return f"Audio for slide {slide_number} of job {job_id} created at {output_s3_path}"
    
    except SoftTimeLimitExceeded:
        # Handle soft timeout - create a placeholder audio file
        print(f"TTS synthesis timed out for job {job_id}, slide {slide_number}. Creating placeholder audio.")
        try:
            # Create 3 seconds of silence as fallback
            fallback_path = f"temp_fallback_{job_id}_{slide_number}.wav"
            tts_processor.create_silence(fallback_path, duration_seconds=3.0)
            temp_files.append(fallback_path)
            
            # Upload fallback audio
            data = AudioSynthesisData(job_id, slide_number)
            data.job = crud.get_presentation_job(db, job_id)
            if data.job:
                output_s3_path = audio_service.upload_audio_file(data, fallback_path)
            
            crud.update_task_status(
                db, 
                celery_task_id=self.request.id, 
                status="completed", 
                progress_message=f"Audio synthesis timed out - used placeholder audio for slide {slide_number}"
            )
            
            return f"Timeout fallback audio for slide {slide_number} of job {job_id} created."
            
        except Exception as fallback_error:
            print(f"Fallback audio creation failed: {fallback_error}")
            raise SoftTimeLimitExceeded("TTS synthesis timed out and fallback failed")
    
    except TTSException as tts_error:
        # Handle TTS-specific errors
        error_msg = f"TTS error for slide {slide_number}: {tts_error}"
        print(error_msg)
        
        crud.update_task_status(
            db, 
            celery_task_id=self.request.id, 
            status="failed", 
            error_message=str(tts_error)
        )
        
        # Don't fail the job for individual slide errors - create silence instead
        try:
            fallback_path = f"temp_silence_{job_id}_{slide_number}.wav"
            tts_processor.create_silence(fallback_path, duration_seconds=2.0)
            temp_files.append(fallback_path)
            
            data = AudioSynthesisData(job_id, slide_number)
            data.job = crud.get_presentation_job(db, job_id)
            if data.job:
                output_s3_path = audio_service.upload_audio_file(data, fallback_path)
            
            return f"Fallback silence audio created for slide {slide_number} due to TTS error"
            
        except Exception:
            raise tts_error  # Re-raise original error if fallback also fails
    
    except Exception as e:
        # Handle general errors
        error_msg = f"Audio synthesis failed for job {job_id}, slide {slide_number}: {e}"
        print(error_msg)
        
        crud.update_task_status(
            db, 
            celery_task_id=self.request.id, 
            status="failed", 
            error_message=str(e)
        )
        
        crud.update_job_status(
            db, 
            job_id, 
            "failed", 
            error_message=f"Audio synthesis failed for slide {slide_number}: {str(e)}"
        )
        
        raise
    
    finally:
        # Cleanup
        audio_service.cleanup_temp_files(*temp_files)
        db.close()