# Agent Development Guidelines for Presentation Video Generator

This document provides guidelines for AI agents working on this project.

## Architecture Overview

The application is built on a microservices architecture orchestrated with Docker Compose for development and designed for Kubernetes in production.

- **FastAPI**: Serves the web application and API. API routes are prefixed with `/api/`. The root `/` serves the frontend.
- **Celery**: Manages asynchronous background tasks. There are two types of workers:
    - `worker_cpu`: For general, CPU-bound tasks like file processing and video assembly (MoviePy). Listens to the `cpu_tasks` queue.
    - `worker_gpu`: For ML-intensive, GPU-bound tasks, specifically voice synthesis with OpenVoice V2. Listens to the `gpu_tasks` queue.
- **PostgreSQL**: The primary database for storing job and user metadata. Models are defined in `app/db/models.py`.
- **Redis**: Acts as the message broker for Celery.
- **MinIO**: S3-compatible object storage for all files. Buckets used: `ingest`, `output`, `voice-clones`, `presentations`.
- **LibreOffice Service**: A dedicated container running a Flask API that wraps a headless LibreOffice instance for `.pptx` to image conversion.

## Development Workflow

1.  **Run the environment**: Use `docker-compose up --build` to start all services.
2.  **Modify code**: The `app` directory is mounted as a volume in the `api` and worker containers.
    - Changes to Python files in `app/` will be reflected automatically in the API container thanks to Uvicorn's reload feature.
    - Celery workers do **not** auto-reload. You must restart the specific worker container after making changes to its tasks (e.g., `docker-compose restart worker_cpu`).
3.  **Adding a new API Endpoint**:
    - Add the endpoint function to the appropriate file in `app/api/endpoints/`.
    - If it involves new data, add schemas to `app/schemas.py`.
    - Add any new database logic to `app/crud.py`.
4.  **Adding a new Celery Task**:
    - Decide if it's a CPU or GPU task.
    - Add the task function to `app/workers/tasks_cpu.py` or `app/workers/tasks_gpu.py`.
    - Ensure the `@celery_app.task(...)` decorator is used.
    - Call the task from your application code using `celery_app.send_task("task.name", args=[...])`.

## Frontend Notes

The frontend is a simple, single-page application located in `templates/index.html`. It uses vanilla JavaScript with the `fetch` API to communicate with the backend. There is no build step. All logic is contained within the `<script>` tag in the HTML file.

## Potential Future Improvements

- **Authentication**: Implement a proper user authentication system (e.g., using JWT) to replace the current simple user creation.
- **Database Migrations**: Add `alembic` to manage database schema changes gracefully. Currently, changes require a manual database reset.
- **Error Handling & Retries**: Implement more robust error handling in Celery tasks, including automatic retries for transient failures.
- **Frontend Framework**: For more complex features, migrate the frontend to a modern JavaScript framework like Vue.js or React.
- **Configuration**: Make video generation settings (e.g., resolution, format) configurable in the API and UI.
- **Real-time Updates**: Replace the frontend's polling mechanism with WebSockets for real-time job status updates.
- **Testing**: Add a comprehensive suite of unit and integration tests for the API and Celery tasks.
