from app.workers.celery_app_cpu import app as celery_app
from app.db.session import SessionLocal
from app import crud
from app.services.minio_service import minio_service
from pptx import Presentation
import requests
import io
import os
import tempfile
from celery import chord, group
from moviepy import ImageClip, AudioFileClip, concatenate_videoclips
# Import tasks through celery to avoid direct module imports
# This prevents MoviePy being loaded in GPU worker

@celery_app.task(name="app.workers.tasks_cpu.decompose_presentation")
def decompose_presentation(job_id: int):
    # ... (previous implementation is correct)
    db = SessionLocal()
    try:
        job = crud.get_presentation_job(db, job_id)
        if not job:
            print(f"Job {job_id} not found.")
            return

        crud.update_job_status(db, job_id, "processing_slides")

        pptx_object_name = job.s3_pptx_path.split('/', 2)[-1]
        pptx_bucket_name = job.s3_pptx_path.split('/')[1]

        response = minio_service.client.get_object(pptx_bucket_name, pptx_object_name)
        pptx_data = io.BytesIO(response.read())
        response.close()
        response.release_conn()

        prs = Presentation(pptx_data)
        num_slides = len(prs.slides)
        notes_paths = []
        for i, slide in enumerate(prs.slides):
            slide_number = i + 1
            notes = slide.notes_slide.notes_text_frame.text if slide.has_notes_slide else ""
            note_object_name = f"{job_id}/notes/slide_{slide_number}.txt"
            minio_service.upload_file(
                bucket_name="presentations",
                object_name=note_object_name,
                data=io.BytesIO(notes.encode('utf-8')),
                length=len(notes.encode('utf-8'))
            )
            notes_paths.append(f"/presentations/{note_object_name}")

        libreoffice_url = "http://libreoffice:8100/convert"
        payload = {"bucket_name": pptx_bucket_name, "object_name": pptx_object_name}
        res = requests.post(libreoffice_url, json=payload)
        res.raise_for_status()
        image_paths = res.json().get("image_paths", [])

        if len(image_paths) != num_slides:
            raise Exception(f"Mismatch between number of images ({len(image_paths)}) and slides ({num_slides}).")

        callback = assemble_video.s(job_id=job_id)
        header = group(
            celery_app.send_task('app.workers.tasks_gpu.synthesize_audio', 
                               args=(job_id, i+1)) for i in range(num_slides)
        )
        chord(header)(callback)

        crud.update_job_status(db, job_id, "synthesizing_audio")

    except Exception as e:
        crud.update_job_status(db, job_id, "failed")
        print(f"Error in decompose_presentation for job {job_id}: {e}")
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks_cpu.assemble_video")
def assemble_video(results, job_id: int):
    """
    Assembles the final video from slide images and synthesized audio.
    """
    db = SessionLocal()
    try:
        crud.update_job_status(db, job_id, "assembling_video")

        with tempfile.TemporaryDirectory() as temp_dir:
            # 1. List and download all images and audio for the job
            image_files = minio_service.client.list_objects("presentations", prefix=f"{job_id}/images/")
            audio_files = minio_service.client.list_objects("presentations", prefix=f"{job_id}/audio/")

            image_paths = {}
            audio_paths = {}

            for img in image_files:
                local_path = os.path.join(temp_dir, os.path.basename(img.object_name))
                minio_service.client.fget_object("presentations", img.object_name, local_path)
                # slide-01.png -> 1
                slide_num = int(os.path.splitext(os.path.basename(local_path))[0].split('-')[1])
                image_paths[slide_num] = local_path

            for aud in audio_files:
                local_path = os.path.join(temp_dir, os.path.basename(aud.object_name))
                minio_service.client.fget_object("presentations", aud.object_name, local_path)
                # slide_1.wav -> 1
                slide_num = int(os.path.splitext(os.path.basename(local_path))[0].split('_')[1])
                audio_paths[slide_num] = local_path

            # 2. Create video clips
            clips = []
            for i in sorted(image_paths.keys()):
                image_path = image_paths[i]
                audio_path = audio_paths.get(i)

                if not audio_path:
                    raise Exception(f"Missing audio for slide {i}")

                audio_clip = AudioFileClip(audio_path)
                image_clip = ImageClip(image_path).set_duration(audio_clip.duration)
                image_clip.fps = 24 # Standard fps

                final_clip = image_clip.set_audio(audio_clip)
                clips.append(final_clip)

            # 3. Concatenate and write final video
            final_video = concatenate_videoclips(clips)
            output_filename = f"{job_id}.mp4"
            local_output_path = os.path.join(temp_dir, output_filename)
            final_video.write_videofile(local_output_path, codec='libx264', audio_codec='aac')

            # 4. Upload to MinIO output bucket
            with open(local_output_path, "rb") as f:
                s3_path = minio_service.upload_file(
                    bucket_name="output",
                    object_name=output_filename,
                    data=f,
                    length=os.path.getsize(local_output_path)
                )

            # 5. Update job status in DB
            crud.update_job_status(db, job_id, "completed", video_path=s3_path)

    except Exception as e:
        crud.update_job_status(db, job_id, "failed")
        print(f"Error in assemble_video for job {job_id}: {e}")
    finally:
        db.close()
