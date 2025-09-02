from app.workers.celery_app_gpu import app as celery_app
from app.db.session import SessionLocal
from app import crud
from app.services.minio_service import minio_service
import torch
import os
import sys
print(f"Current working directory: {os.getcwd()}")
print(f"Python path: {sys.path}")
from openvoice import se_extractor
from openvoice.api import ToneColorConverter
import librosa
import io
import re
import soundfile as sf

# Import MeloTTS for base TTS synthesis
sys.path.append('/src/melotts')
# Delay import of MeloTTS to handle initialization issues
base_tts = None

# Configurable timeouts via environment variables
TTS_SOFT_TIME_LIMIT = int(os.getenv('TTS_SOFT_TIME_LIMIT', '300'))  # 5 minutes default
TTS_HARD_TIME_LIMIT = int(os.getenv('TTS_HARD_TIME_LIMIT', '360'))  # 6 minutes default

# Load models once when the worker starts
# This is a simplification. In a real scenario, model loading should be more robust.
device = "cuda:0" if torch.cuda.is_available() else "cpu"
tone_color_converter = ToneColorConverter('checkpoints_v2/checkpoints_v2/converter/config.json', device=device)
# Load base speaker TTS for English
source_se = torch.load('checkpoints_v2/checkpoints_v2/base_speakers/ses/en-default.pth', map_location=device)

# MeloTTS will be loaded on demand to avoid initialization issues

def parse_note_text_tags(text):
    """
    Parse special tags from PowerPoint notes for emotion and emphasis control.
    
    Supported tags:
    [EMOTION:happy/sad/excited/calm/angry] - Sets emotional tone
    [SPEED:slow/normal/fast] or [SPEED:0.8] - Controls speech speed (0.5-2.0)
    [PITCH:low/normal/high] - Controls pitch (not fully implemented)
    [PAUSE:2] - Adds pause in seconds
    [EMPHASIS:word] - Emphasizes specific words (capitalization)
    
    Returns:
        tuple: (cleaned_text, emotion, speed, pitch)
    """
    import re
    
    # Default values
    emotion = "neutral"
    speed = 1.0
    pitch = 1.0
    
    # Extract emotion tags
    emotion_match = re.search(r'\[EMOTION:(happy|sad|excited|calm|angry|neutral)\]', text, re.IGNORECASE)
    if emotion_match:
        emotion = emotion_match.group(1).lower()
        text = re.sub(r'\[EMOTION:[^\]]+\]', '', text, flags=re.IGNORECASE)
    
    # Extract speed tags
    speed_match = re.search(r'\[SPEED:(slow|normal|fast|[\d.]+)\]', text, re.IGNORECASE)
    if speed_match:
        speed_val = speed_match.group(1).lower()
        if speed_val == "slow":
            speed = 0.7
        elif speed_val == "fast":
            speed = 1.3
        elif speed_val == "normal":
            speed = 1.0
        else:
            try:
                speed = float(speed_val)
                speed = max(0.5, min(2.0, speed))  # Clamp between 0.5 and 2.0
            except ValueError:
                speed = 1.0
        text = re.sub(r'\[SPEED:[^\]]+\]', '', text, flags=re.IGNORECASE)
    
    # Extract pitch tags (for future implementation)
    pitch_match = re.search(r'\[PITCH:(low|normal|high|[\d.]+)\]', text, re.IGNORECASE)
    if pitch_match:
        pitch_val = pitch_match.group(1).lower()
        if pitch_val == "low":
            pitch = 0.8
        elif pitch_val == "high":
            pitch = 1.2
        elif pitch_val == "normal":
            pitch = 1.0
        else:
            try:
                pitch = float(pitch_val)
                pitch = max(0.5, min(2.0, pitch))
            except ValueError:
                pitch = 1.0
        text = re.sub(r'\[PITCH:[^\]]+\]', '', text, flags=re.IGNORECASE)
    
    # Handle pause tags by converting to commas for natural pauses
    text = re.sub(r'\[PAUSE:(\d+)\]', lambda m: ',' * int(m.group(1)), text, flags=re.IGNORECASE)
    
    # Handle emphasis tags by capitalizing words
    text = re.sub(r'\[EMPHASIS:([^\]]+)\]', lambda m: m.group(1).upper(), text, flags=re.IGNORECASE)
    
    # Clean up extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text, emotion, speed, pitch

@celery_app.task(name="app.workers.tasks_gpu.synthesize_audio", bind=True, soft_time_limit=TTS_SOFT_TIME_LIMIT, time_limit=TTS_HARD_TIME_LIMIT)
def synthesize_audio(self, job_id: int, slide_number: int):
    """
    Generates audio for a single slide's notes using a cloned voice.
    """
    from celery.exceptions import SoftTimeLimitExceeded
    db = SessionLocal()
    try:
        # Update task status to running
        crud.update_task_status(db, celery_task_id=celery_app.current_task.request.id, 
                               status="running", progress_message=f"Starting audio synthesis for slide {slide_number}")
        job = crud.get_presentation_job(db, job_id)
        if not job:
            raise Exception(f"Job {job_id} not found.")

        # 1. Get reference audio or built-in speaker embedding for voice clone
        voice_clone = job.voice_clone
        ref_audio_path = voice_clone.s3_path
        
        # Check if this is a built-in speaker
        if ref_audio_path.startswith("builtin://"):
            # Use built-in speaker embedding
            speaker_name = ref_audio_path.replace("builtin://", "").replace(".pth", "")
            target_se = torch.load(f'checkpoints_v2/checkpoints_v2/base_speakers/ses/{speaker_name}.pth', map_location=device)
            use_builtin_speaker = True
        else:
            # Use uploaded voice clone
            ref_bucket, ref_object = ref_audio_path.split('/', 2)[1:]
            ref_response = minio_service.client.get_object(ref_bucket, ref_object)
            ref_audio_data = io.BytesIO(ref_response.read())
            ref_response.close()
            ref_response.release_conn()
            use_builtin_speaker = False

        # 2. Get note text for the slide
        note_object_name = f"{job_id}/notes/slide_{slide_number}.txt"
        note_response = minio_service.client.get_object("presentations", note_object_name)
        note_text = note_response.read().decode('utf-8')
        note_response.close()
        note_response.release_conn()

        if not note_text.strip():
            # If no notes, create a silent audio clip of 1s as a placeholder
            # This ensures video assembly has an audio track for every slide
            # In a real app, we might want a minimum slide duration instead.
            note_text = "[SILENCE]" # Special tag to handle silence

        # 3. Process reference audio and extract tone color (skip for builtin speakers)
        if not use_builtin_speaker:
            # Determine file format from S3 path
            file_extension = ref_audio_path.split('.')[-1].lower()
            temp_filename = f"temp_ref.{file_extension}"
            
            # For simplicity, we use a temporary file. A better way is in-memory processing.
            with open(temp_filename, "wb") as f:
                f.write(ref_audio_data.getvalue())

            # Trim silence from reference audio (librosa can handle both WAV and MP3)
            audio, sr = librosa.load(temp_filename, sr=24000)
            audio_trimmed, _ = librosa.effects.trim(audio, top_db=20)
            
            # Check if audio is too short after trimming
            min_duration = 3.0  # 3 seconds minimum
            if len(audio_trimmed) < min_duration * sr:
                # Use original audio if trimmed version is too short
                audio_trimmed = audio
            
            sf.write("temp_ref_trimmed.wav", audio_trimmed, sr)

            target_se, audio_name = se_extractor.get_se("temp_ref_trimmed.wav", tone_color_converter, vad=True)

        # 4. Synthesize speech
        # This is a simplified implementation. OpenVoice has more style controls.
        # We can parse the note_text for emotion tags here.
        # For now, we use a default style.
        save_path = f"temp_output_{job_id}_{slide_number}.wav"

        # Handle silence tag or empty text
        if note_text == "[SILENCE]" or not note_text.strip():
            # Create 1 second of silence
            silence = torch.zeros(24000)
            sf.write(save_path, silence.numpy(), 24000)
        else:
            try:
                print(f"Synthesizing speech for: {note_text[:100]}...")
                
                # Parse emotion and emphasis tags from note text
                processed_text, emotion, speed, pitch = parse_note_text_tags(note_text)
                print(f"Processing: '{processed_text}' with emotion='{emotion}', speed={speed}, pitch={pitch}")
                
                # Initialize MeloTTS if not already loaded
                global base_tts
                if base_tts is None:
                    try:
                        print("Initializing MeloTTS for speech synthesis...")
                        
                        # Download required NLTK data
                        try:
                            import nltk
                            print("Downloading required NLTK data...")
                            nltk.download('averaged_perceptron_tagger_eng', quiet=True)
                            nltk.download('averaged_perceptron_tagger', quiet=True)
                            nltk.download('cmudict', quiet=True)
                            print("NLTK data downloaded successfully")
                        except Exception as nltk_error:
                            print(f"NLTK setup warning: {nltk_error}")
                        
                        # Import and initialize MeloTTS
                        from melo.api import TTS
                        model_name = 'EN'
                        base_tts = TTS(language='EN', device=device)
                        base_speaker_ids = base_tts.hps.data.spk2id
                        print(f"MeloTTS initialized successfully with speakers: {list(base_speaker_ids.keys())}")
                    except Exception as init_error:
                        print(f"MeloTTS initialization failed: {init_error}")
                        print("Falling back to placeholder audio generation")
                        base_tts = "FAILED"
                
                # Generate base TTS audio using MeloTTS
                if base_tts is not None and base_tts != "FAILED":
                    try:
                        # Use MeloTTS for base speech synthesis
                        temp_base_audio = f"temp_base_{job_id}_{slide_number}.wav"
                        
                        # Adjust speed and other parameters based on parsed tags
                        tts_speed = speed if speed != 1.0 else 1.0
                        
                        base_tts.tts_to_file(
                            text=processed_text,
                            speaker_id=0,  # Default English speaker
                            output_path=temp_base_audio,
                            speed=tts_speed,
                            quiet=True
                        )
                        
                        print(f"Base TTS audio generated successfully for slide {slide_number}")
                        
                        # Load the generated audio for voice cloning
                        base_audio, sr = librosa.load(temp_base_audio, sr=24000)
                        
                        # Apply voice cloning using OpenVoice
                        if not use_builtin_speaker:
                            try:
                                tone_color_converter.convert(
                                    audio_src_path=temp_base_audio,
                                    src_se=source_se,
                                    tgt_se=target_se,
                                    output_path=save_path,
                                    message=f"Converting voice for slide {slide_number}"
                                )
                                print(f"Voice cloning applied successfully for slide {slide_number}")
                            except Exception as clone_error:
                                print(f"Voice cloning failed: {clone_error}, using base TTS audio")
                                # Copy base audio if cloning fails
                                import shutil
                                shutil.copy2(temp_base_audio, save_path)
                        else:
                            # Use built-in speaker, just copy the base audio
                            import shutil
                            shutil.copy2(temp_base_audio, save_path)
                            
                        # Clean up temporary file
                        if os.path.exists(temp_base_audio):
                            os.remove(temp_base_audio)
                            
                    except Exception as tts_error:
                        print(f"TTS generation failed: {tts_error}")
                        raise tts_error
                        
                else:
                    # Fallback to duration-based silence if MeloTTS fails
                    print("MeloTTS not available, generating silence based on text duration")
                    word_count = len(processed_text.split())
                    # Estimate duration: ~150 words per minute average speaking rate
                    estimated_duration = max(3.0, word_count / 150.0 * 60.0)
                    estimated_duration = min(estimated_duration, 30.0)
                    
                    sample_rate = 24000
                    duration_samples = int(estimated_duration * sample_rate)
                    
                    # Generate silence instead of beeps
                    import numpy as np
                    audio = np.zeros(duration_samples, dtype=np.float32)
                    
                    sf.write(save_path, audio, sample_rate)
                    print(f"Generated {estimated_duration:.1f}s silent audio for slide {slide_number}")
                
            except Exception as e:
                print(f"Error in speech synthesis: {e}")
                print("Falling back to basic silence...")
                # Fallback to basic silence if everything fails
                silence = torch.zeros(24000 * 5)  # 5 seconds of silence as fallback
                sf.write(save_path, silence.numpy(), 24000)

        # 5. Upload synthesized audio to MinIO
        audio_object_name = f"{job_id}/audio/slide_{slide_number}.wav"
        with open(save_path, "rb") as audio_data:
            minio_service.upload_file(
                bucket_name="presentations",
                object_name=audio_object_name,
                data=audio_data,
                length=os.path.getsize(save_path)
            )

        # Mark task as completed
        crud.update_task_status(db, celery_task_id=celery_app.current_task.request.id, 
                               status="completed", progress_message=f"Audio synthesis completed for slide {slide_number}")
        
        return f"Audio for slide {slide_number} of job {job_id} created."

    except SoftTimeLimitExceeded:
        # Handle soft timeout - create a placeholder audio file
        print(f"TTS synthesis timed out for job {job_id}, slide {slide_number}. Creating placeholder audio.")
        try:
            # Create 3 seconds of silence as fallback
            silence = torch.zeros(3 * 24000)  # 3 seconds at 24kHz
            save_path = f"temp_output_{job_id}_{slide_number}.wav"
            sf.write(save_path, silence.numpy(), 24000)
            
            # Upload to S3
            output_s3_path = f"presentations/{job.s3_uuid}/audio/slide_{slide_number}.wav"
            with open(save_path, "rb") as audio_file:
                minio_service.upload_file(audio_file, "output", output_s3_path.lstrip('/'))
            
            crud.update_task_status(db, celery_task_id=self.request.id, 
                                   status="completed", progress_message=f"Audio synthesis timed out - used placeholder audio for slide {slide_number}")
            
            # Clean up
            if os.path.exists(save_path):
                os.remove(save_path)
                
            return f"Timeout fallback audio for slide {slide_number} of job {job_id} created."
        except Exception as fallback_error:
            print(f"Fallback audio creation failed: {fallback_error}")
            raise SoftTimeLimitExceeded("TTS synthesis timed out and fallback failed")
            
    except Exception as e:
        # Mark task as failed
        crud.update_task_status(db, celery_task_id=celery_app.current_task.request.id, 
                               status="failed", error_message=str(e))
        crud.update_job_status(db, job_id, "failed", error_message=f"Audio synthesis failed for slide {slide_number}: {str(e)}")
        print(f"Error in synthesize_audio for job {job_id}, slide {slide_number}: {e}")
        # Reraise to let Celery know the task failed
        raise
    finally:
        db.close()
