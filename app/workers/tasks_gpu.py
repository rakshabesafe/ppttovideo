from app.workers.celery_app import app as celery_app
from app.db.session import SessionLocal
from app import crud
from app.services.minio_service import minio_service
import torch
from openvoice import se_extractor
from openvoice.api import ToneColorConverter
import librosa
import io
import re

# Load models once when the worker starts
# This is a simplification. In a real scenario, model loading should be more robust.
device = "cuda:0" if torch.cuda.is_available() else "cpu"
tone_color_converter = ToneColorConverter('checkpoints_v2/converter', device=device)
# Load base speaker TTS for English
source_se = torch.load('checkpoints_v2/base_speakers/ses/en_base_se.pth', map_location=device)

@celery_app.task(name="app.workers.tasks_gpu.synthesize_audio")
def synthesize_audio(job_id: int, slide_number: int):
    """
    Generates audio for a single slide's notes using a cloned voice.
    """
    db = SessionLocal()
    try:
        job = crud.get_presentation_job(db, job_id)
        if not job:
            raise Exception(f"Job {job_id} not found.")

        # 1. Get reference audio for voice clone
        voice_clone = job.voice_clone
        ref_audio_path = voice_clone.s3_path
        ref_bucket, ref_object = ref_audio_path.split('/', 2)[1:]

        ref_response = minio_service.client.get_object(ref_bucket, ref_object)
        ref_audio_data = io.BytesIO(ref_response.read())
        ref_response.close()
        ref_response.release_conn()

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

        # 3. Process reference audio and extract tone color
        # For simplicity, we use a temporary file. A better way is in-memory processing.
        with open("temp_ref.wav", "wb") as f:
            f.write(ref_audio_data.getvalue())

        # Trim silence from reference audio
        audio, sr = librosa.load("temp_ref.wav", sr=24000)
        audio_trimmed, _ = librosa.effects.trim(audio, top_db=20)
        librosa.output.write_wav("temp_ref_trimmed.wav", audio_trimmed, sr)

        target_se, audio_name = se_extractor.get_se("temp_ref_trimmed.wav", tone_color_converter, vad=True)

        # 4. Synthesize speech
        # This is a simplified implementation. OpenVoice has more style controls.
        # We can parse the note_text for emotion tags here.
        # For now, we use a default style.
        save_path = f"temp_output_{job_id}_{slide_number}.wav"

        # Handle silence tag
        if note_text == "[SILENCE]":
            # Create 1 second of silence
            silence = torch.zeros(24000)
            librosa.output.write_wav(save_path, silence.numpy(), 24000)
        else:
            tone_color_converter.convert(
                audio_src_path="checkpoints_v2/base_speakers/voice/en_base.wav", # Base voice
                src_se=source_se,
                tgt_se=target_se,
                output_path=save_path,
                message=note_text,
                style="default" # We can make this dynamic based on tags
            )

        # 5. Upload synthesized audio to MinIO
        audio_object_name = f"{job_id}/audio/slide_{slide_number}.wav"
        with open(save_path, "rb") as audio_data:
            minio_service.upload_file(
                bucket_name="presentations",
                object_name=audio_object_name,
                data=audio_data,
                length=os.path.getsize(save_path)
            )

        return f"Audio for slide {slide_number} of job {job_id} created."

    except Exception as e:
        crud.update_job_status(db, job_id, "failed")
        print(f"Error in synthesize_audio for job {job_id}, slide {slide_number}: {e}")
        # Reraise to let Celery know the task failed
        raise
    finally:
        db.close()
