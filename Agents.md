# PPT to Video Generator - AI Agent Reference Documentation

## Application Overview
The PPT to Video Generator is a microservices-based application that converts PowerPoint presentations to narrated videos using AI-powered voice synthesis. The system processes PPTX files by extracting slide notes, converting slides to images, synthesizing audio using voice clones, and assembling the final video.

## Architecture Components

### Services
- **API Service** (`ppt-api`): FastAPI web application and REST API
- **CPU Worker** (`ppt-worker_cpu`): Celery worker for CPU-intensive tasks (video assembly, presentation processing)
- **GPU Worker** (`ppt-worker_gpu`): Celery worker for GPU tasks (voice synthesis using OpenVoice)
- **LibreOffice Service** (`ppt-libreoffice`): Microservice for PowerPoint to PDF/image conversion
- **PostgreSQL** (`ppt-postgres`): Primary database for user data and job tracking
- **Redis** (`ppt-redis`): Message broker for Celery tasks and caching
- **MinIO** (`ppt-minio`): S3-compatible object storage for files

### Port Mapping
- **Web Interface**: http://localhost:18000
- **API Endpoints**: http://localhost:18000/api/*
- **LibreOffice Service**: Internal port 8100 (mapped to 18100 externally)
- **PostgreSQL**: localhost:15432
- **Redis**: localhost:16379  
- **MinIO Console**: localhost:19001, Storage: localhost:19000

## Database Schema

### Users Table
```sql
- id: INTEGER PRIMARY KEY
- name: STRING (indexed)
- email: STRING (unique, indexed, nullable)
- created_at: DATETIME
```

### Voice Clones Table
```sql
- id: INTEGER PRIMARY KEY
- name: STRING (indexed)
- s3_path: STRING (MinIO storage path)
- created_at: DATETIME
- owner_id: INTEGER (foreign key to users.id)
```

### Presentation Jobs Table
```sql
- id: INTEGER PRIMARY KEY
- status: STRING (pending/processing_slides/synthesizing_audio/assembling_video/completed/failed)
- s3_pptx_path: STRING (input file path)
- s3_video_path: STRING (output file path, nullable)
- created_at: DATETIME
- updated_at: DATETIME
- owner_id: INTEGER (foreign key to users.id)
- voice_clone_id: INTEGER (foreign key to voice_clones.id)
```

## API Endpoints

### Users API (`/api/users/`)
- **POST** `/`: Create new user
  - Body: `{"name": "string", "email": "string"}`
  - Returns: User object with ID
- **GET** `/`: List all users (paginated)
- **GET** `/{user_id}`: Get user by ID
- **GET** `/by_name/{user_name}`: Get user by name (used for login)

### Voice Clones API (`/api/voice-clones/`)
- **POST** `/`: Upload voice clone
  - Form data: `name`, `owner_id`, `file` (WAV audio)
  - Stores in MinIO `voice-clones` bucket
- **GET** `/user/{user_id}`: List voice clones for user

### Presentations API (`/api/presentations/`)
- **POST** `/`: Create presentation job
  - Form data: `owner_id`, `voice_clone_id`, `file` (PPTX)
  - Triggers async processing pipeline
- **GET** `/status/all`: List all presentation jobs
- **GET** `/status/{job_id}`: Get specific job status
- **GET** `/download/{job_id}`: Download completed video

## Processing Pipeline

### Step 1: Presentation Decomposition (CPU Worker)
1. **Task**: `app.workers.tasks_cpu.decompose_presentation`
2. **Input**: Job ID
3. **Process**:
   - Downloads PPTX from MinIO `ingest` bucket
   - Extracts slide notes using python-pptx
   - Uploads notes as text files to `presentations` bucket
   - Calls LibreOffice service to convert PPTX → PDF → images
   - Validates slide count matches image count
4. **Output**: Triggers audio synthesis for each slide

### Step 2: Audio Synthesis (GPU Worker)
1. **Task**: `app.workers.tasks_gpu.synthesize_audio`
2. **Input**: Job ID, slide number
3. **Process**:
   - Downloads slide notes from MinIO
   - Downloads voice clone reference audio
   - Uses OpenVoice for voice synthesis
   - Uploads synthesized audio to `presentations` bucket
4. **Output**: Audio file per slide

### Step 3: Video Assembly (CPU Worker)
1. **Task**: `app.workers.tasks_cpu.assemble_video`
2. **Input**: Job ID (triggered after all audio synthesis completes)
3. **Process**:
   - Downloads all slide images and audio files
   - Uses MoviePy to create video clips (image + audio)
   - Concatenates clips into final video
   - Uploads to MinIO `output` bucket
4. **Output**: Final MP4 video file

## MinIO Buckets
- **`ingest`**: Original uploaded PPTX files
- **`voice-clones`**: Reference audio files for voice synthesis
- **`presentations`**: Intermediate files (notes, slide images, synthesized audio)
- **`output`**: Final generated video files

## Environment Variables
```bash
DATABASE_URL=postgresql://user:password@postgres:5432/presentation_gen_db
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
MINIO_URL=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
LIBREOFFICE_HOST=libreoffice
```

## Key File Locations
- **Main API**: `/app/main.py`
- **Database Models**: `/app/db/models.py`
- **API Schemas**: `/app/schemas.py`
- **CRUD Operations**: `/app/crud.py`
- **CPU Worker Tasks**: `/app/workers/tasks_cpu.py`
- **GPU Worker Tasks**: `/app/workers/tasks_gpu.py`
- **LibreOffice Service**: `/app/services/libreoffice_converter.py`
- **MinIO Service**: `/app/services/minio_service.py`
- **Docker Configuration**: `/docker-compose.yml`

## Celery Task Coordination
The system uses Celery for async task processing with task chaining:
1. `decompose_presentation` → triggers multiple `synthesize_audio` tasks
2. All `synthesize_audio` tasks → triggers `assemble_video`
3. Task coordination uses countdown delays (30 seconds) to ensure audio completion

## Common Debugging Steps
1. **Login Issues**: Verify correct port (18000) and user exists in database
2. **Upload Failures**: Check MinIO storage space and bucket permissions  
3. **Job Failures**: Check worker logs, Java installation, and LibreOffice service
4. **Database Issues**: Verify PostgreSQL connection and table creation

## Dependencies
- **OpenVoice**: AI voice synthesis (GPU worker)
- **LibreOffice**: Document conversion with Java Runtime
- **MoviePy**: Video processing and assembly
- **FastAPI**: Web framework and API
- **Celery**: Distributed task processing
- **SQLAlchemy**: Database ORM
- **python-pptx**: PowerPoint file processing

## Status Codes
- **pending**: Job created, not started
- **processing_slides**: Converting PPTX to images
- **synthesizing_audio**: Generating voice audio
- **assembling_video**: Creating final video
- **completed**: Video ready for download
- **failed**: Error in processing pipeline

## Security Notes
- No authentication system (development only)
- Celery workers run with root privileges (security warning)
- MinIO uses default credentials
- File uploads have basic validation only

## Performance Considerations
- GPU worker: Single concurrency (1 process)
- CPU worker: High concurrency (256 processes) 
- Video processing is CPU intensive
- Voice synthesis requires GPU resources
- Large presentation files may timeout

This documentation provides AI agents with comprehensive technical details for debugging, extending, and maintaining the PPT to Video Generator application.