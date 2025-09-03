import pytest
import os
import io
from minio import Minio
from app.workers.tasks_cpu import assemble_video
from app.core.config import settings

# This is an integration test and requires the Docker environment to be running.
# It connects to the MinIO service specified in the docker-compose file.

# --- Test Setup ---

@pytest.fixture(scope="module")
def minio_client():
    """Provides a Minio client configured for the test environment."""
    # These settings should match the ones in your .env file or docker-compose defaults
    client = Minio(
        "localhost:19000",
        access_key="minioadmin",
        secret_key="minioadmin",
        secure=False
    )
    return client

@pytest.fixture(scope="module")
def setup_minio_buckets(minio_client):
    """Ensure the necessary buckets exist before tests run."""
    buckets = ["presentations", "output"]
    for bucket in buckets:
        if not minio_client.bucket_exists(bucket):
            minio_client.make_bucket(bucket)
    yield
    # No cleanup of buckets themselves, just their content

def create_dummy_image_data():
    """Creates a dummy PNG image in memory."""
    from PIL import Image
    img = Image.new('RGB', (100, 100), color = 'red')
    byte_arr = io.BytesIO()
    img.save(byte_arr, format='PNG')
    return byte_arr.getvalue()

def create_dummy_audio_data():
    """Creates a dummy WAV audio file in memory."""
    import wave
    import struct

    sample_rate = 44100.0  # hertz
    duration = 1.0       # seconds
    frequency = 440.0    # hertz

    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for i in range(int(duration * sample_rate)):
            value = int(32767.0 * 0.5 * (2**0.5) * (i / sample_rate * frequency * 2 * 3.14159))
            data = struct.pack('<h', value)
            wf.writeframesraw(data)
    return buffer.getvalue()

# --- Integration Test ---

@pytest.mark.integration
def test_assemble_video_integration(minio_client, setup_minio_buckets):
    """
    Tests the assemble_video task by interacting with a live MinIO service.

    Steps:
    1. Creates dummy image and audio files.
    2. Uploads them to the 'presentations' bucket in MinIO.
    3. Calls the assemble_video function with the paths to the uploaded files.
    4. Verifies that the final video is created and uploaded to the 'output' bucket.
    5. Cleans up all created files in MinIO.
    """
    job_id = 999  # A test job ID
    job_uuid = "test-integration-job"
    num_slides = 2

    image_data = create_dummy_image_data()
    audio_data = create_dummy_audio_data()

    uploaded_objects = []

    try:
        # 1. Upload dummy files to MinIO
        image_s3_paths = []
        for i in range(1, num_slides + 1):
            # Upload image
            image_obj_name = f"{job_uuid}/images/slide-{i}.png"
            minio_client.put_object(
                "presentations", image_obj_name, io.BytesIO(image_data), len(image_data), content_type="image/png"
            )
            uploaded_objects.append(("presentations", image_obj_name))
            image_s3_paths.append(f"presentations/{image_obj_name}")

            # Upload audio
            audio_obj_name = f"{job_uuid}/audio/slide_{i}.wav"
            minio_client.put_object(
                "presentations", audio_obj_name, io.BytesIO(audio_data), len(audio_data), content_type="audio/wav"
            )
            uploaded_objects.append(("presentations", audio_obj_name))

        # 2. Call the task function directly
        # We patch the DB functions since we are only testing the MinIO interaction
        with patch('app.workers.tasks_cpu.SessionLocal'), patch('app.workers.tasks_cpu.crud') as mock_crud:
            assemble_video(image_s3_paths, job_id)

        # 3. Verify the output video exists in MinIO
        video_output_name = f"{job_id}.mp4"
        uploaded_objects.append(("output", video_output_name))

        video_stat = minio_client.stat_object("output", video_output_name)
        assert video_stat.size > 0
        assert video_stat.content_type == "video/mp4"

        print(f"Successfully verified video '{video_output_name}' was created in MinIO.")

    finally:
        # 4. Cleanup all objects created during the test
        print("Cleaning up test objects from MinIO...")
        for bucket, obj_name in uploaded_objects:
            try:
                minio_client.remove_object(bucket, obj_name)
                print(f"Removed {bucket}/{obj_name}")
            except Exception as e:
                print(f"Error cleaning up {bucket}/{obj_name}: {e}")
