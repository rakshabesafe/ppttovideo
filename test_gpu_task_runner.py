import time
from celery import Celery
from celery.result import AsyncResult

# --- Configuration ---
# This script assumes the Docker environment is running.
# It connects to the Redis instance used by Celery.

CELERY_BROKER_URL = 'redis://localhost:16379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:16379/0'

# Name of the GPU task to trigger
TASK_NAME = 'app.workers.tasks_gpu.synthesize_audio'

# --- Prerequisite Setup ---
# Before running this script, you must ensure the following data exists:
#
# 1. A Presentation Job in the Database:
#    - You need a job_id for a job that has already been created through the UI
#      or API. Let's assume the job_id is 1.
#
# 2. Slide Notes in MinIO:
#    - The GPU task needs the notes for the slide it's going to process.
#    - For job_id=1 and slide_number=1, a file must exist in the 'presentations'
#      bucket with the object name: '1/notes/slide_1.txt'
#    - You can create this manually in the MinIO console (http://localhost:19001).
#
# 3. A Voice Clone in the Database:
#    - The job (e.g., job_id=1) must be associated with a voice clone. This happens
#      automatically when you create a job through the UI.
#
# --- Script ---

def main(job_id: int, slide_number: int):
    """
    Sends a task to the GPU worker and waits for the result.

    Args:
        job_id: The ID of the presentation job to process.
        slide_number: The slide number to generate audio for.
    """
    print("--- GPU Task Runner ---")
    print("Connecting to Celery...")

    # Initialize a Celery app to send tasks
    celery_app = Celery(
        'task_runner',
        broker=CELERY_BROKER_URL,
        backend=CELERY_RESULT_BACKEND
    )

    print(f"Sending task '{TASK_NAME}' for job_id={job_id}, slide_number={slide_number}...")

    # Send the task to the 'gpu_tasks' queue
    async_result = celery_app.send_task(
        TASK_NAME,
        args=[job_id, slide_number],
        queue='gpu_tasks'
    )

    task_id = async_result.id
    print(f"Task sent with ID: {task_id}")

    print("Waiting for result (checking every 5 seconds)...")

    start_time = time.time()
    while not async_result.ready():
        time.sleep(5)
        elapsed = time.time() - start_time
        print(f"[{int(elapsed)}s] Current task status: {async_result.status}")
        if elapsed > 300: # 5 minute timeout
            print("Timeout reached. Exiting.")
            return

    print("\n--- Task Finished ---")
    if async_result.successful():
        print(f"Status: SUCCESS")
        print(f"Result: {async_result.result}")
    else:
        print(f"Status: FAILED")
        print(f"Error: {async_result.traceback}")

if __name__ == '__main__':
    # --- IMPORTANT: Set these values before running ---
    # You must have a job with this ID in your database.
    # The job must have notes for the specified slide in MinIO.
    TEST_JOB_ID = 1
    TEST_SLIDE_NUMBER = 1

    print("NOTE: Please ensure the prerequisite data is set up before running.")
    print(f"Prerequisites: Job ID {TEST_JOB_ID} must exist and have notes for slide {TEST_SLIDE_NUMBER}.")

    try:
        main(TEST_JOB_ID, TEST_SLIDE_NUMBER)
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        print("Please ensure the Docker containers (especially Redis and the GPU worker) are running.")
