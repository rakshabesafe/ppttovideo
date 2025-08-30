# Presentation Video Generator

This project is an AI-powered tool to generate videos from PowerPoint presentations. It uses a cloned voice to read the speaker notes from each slide and synchronizes the audio with the corresponding slide image to create a final video file.

## Features (MVP)

- **Web-Based Interface**: A simple, single-page web UI to manage the video generation process.
- **User Management**: Basic user creation to keep resources organized.
- **Voice Cloning**: Upload a `.wav` file to create a reusable voice clone for your presentations.
- **PPTX to Video**: Upload a `.pptx` file, select a voice clone, and start the generation process.
- **Asynchronous Processing**: Uses Celery and Redis to manage long-running video generation tasks in the background.
- **Jobs Dashboard**: View the status of all your presentation jobs (`pending`, `processing`, `completed`, `failed`) and download the final video.

## Architecture

The application is built with a microservices architecture, orchestrated by Docker Compose for easy local development.

- **`api`**: A FastAPI application that serves the frontend and the backend REST API. The container is named `ppt-api`.
- **`worker_cpu`**: A Celery worker for CPU-intensive tasks like presentation decomposition and video assembly with MoviePy. The container is named `ppt-worker-cpu`.
- **`worker_gpu`**: A Celery worker for GPU-intensive tasks, specifically voice synthesis with OpenVoice V2. The container is named `ppt-worker-gpu`.
- **`libreoffice`**: A dedicated service running a headless LibreOffice instance (wrapped in a Flask API) to convert `.pptx` files to images. The container is named `ppt-libreoffice`.
- **`postgres`**: A PostgreSQL database for storing user, voice clone, and job metadata. The container is named `ppt-postgres`.
- **`redis`**: A Redis instance that acts as the message broker for Celery. The container is named `ppt-redis`.
- **`minio`**: An S3-compatible object storage server for storing all files (presentations, voice samples, images, audio clips, and final videos). The container is named `ppt-minio`.

## How to Run Locally

1.  **Prerequisites**:
    -   [Docker](https://www.docker.com/get-started)
    -   [Docker Compose](https://docs.docker.com/compose/install/)
    -   If using a GPU for voice synthesis, you need an NVIDIA GPU with the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) installed.

2.  **Clone the repository**:
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

3.  **Set up environment variables**:
    The application uses a `.env` file for configuration. A sample is provided below. Create a file named `.env` in the root of the project with the following content:
    ```env
    # .env
    POSTGRES_USER=user
    POSTGRES_PASSWORD=password
    POSTGRES_DB=presentation_gen_db

    MINIO_ROOT_USER=minioadmin
    MINIO_ROOT_PASSWORD=minioadmin
    ```

4.  **Build and run the services**:
    ```bash
    docker-compose up --build
    ```
    This command will build the Docker images for all the custom services and start all the containers. The `--build` flag is only necessary the first time or when you make changes to the Dockerfiles or application dependencies.

5.  **Access the application**:
    -   **Web Interface**: Open your browser and navigate to [http://localhost:18000](http://localhost:18000).
    -   **API Docs**: The FastAPI documentation is available at [http://localhost:18000/docs](http://localhost:18000/docs).
    -   **MinIO Console**: You can access the MinIO dashboard at [http://localhost:19001](http://localhost:19001) using the credentials from your `.env` file.
    -   **Database**: The PostgreSQL database is exposed on `localhost:15432`.
    -   **Redis**: The Redis server is exposed on `localhost:16379`.
