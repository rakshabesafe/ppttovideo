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

### Step 2: Audio Synthesis (GPU Worker) - Modular Architecture
1. **Task**: `app.workers.tasks_gpu.synthesize_audio`
2. **Input**: Job ID, slide number
3. **Process**: Multi-layer modular architecture with fallback protection
   - **Data Loading**: `AudioSynthesisService.load_job_data()` validates job and voice data
   - **Text Processing**: `TextProcessor.parse_note_text_tags()` handles emotion/speed tags
   - **TTS Synthesis**: Layered approach with multiple fallbacks:
     - Primary: `TTSProcessor.synthesize_with_custom_voice()` (OpenVoice cloning)
     - Fallback 1: `TTSProcessor.synthesize_with_builtin_voice()` (MeloTTS only)
     - Fallback 2: `TTSProcessor.synthesize_base_only()` (base TTS)
     - Fallback 3: `TTSProcessor.create_silence()` (silence audio)
   - **Error Handling**: Custom exceptions (`TTSException`, `MeloTTSException`, `OpenVoiceException`)
   - **Timeout Protection**: Configurable soft/hard timeouts with graceful degradation
   - **File Upload**: `AudioSynthesisService.upload_audio_file()` handles MinIO storage
4. **Output**: High-quality audio file per slide with guaranteed completion

### Step 3: Video Assembly (CPU Worker) - Enhanced Dependency Tracking
1. **Task**: `app.workers.tasks_cpu.assemble_video_with_deps`
2. **Input**: Job ID, list of audio task IDs (proper dependency tracking)
3. **Process**:
   - **Dependency Verification**: Waits for all audio synthesis tasks to complete
   - **Resource Collection**: Downloads all slide images and audio files from MinIO
   - **Video Generation**: Uses MoviePy to create synchronized video clips
   - **Assembly**: Concatenates clips into final video with proper timing
   - **Storage**: Uploads to MinIO `output` bucket with metadata
4. **Output**: Final MP4 video file with guaranteed audio synchronization

## MinIO Buckets
- **`ingest`**: Original uploaded PPTX files
- **`voice-clones`**: Reference audio files for voice synthesis
- **`presentations`**: Intermediate files (notes, slide images, synthesized audio)
- **`output`**: Final generated video files

## Environment Variables
```bash
# Database & Service Configuration
DATABASE_URL=postgresql://user:password@postgres:5432/presentation_gen_db
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
MINIO_URL=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
LIBREOFFICE_HOST=libreoffice

# TTS Timeout Configuration (New in v2.3.0)
TTS_SOFT_TIME_LIMIT=300    # Soft timeout - triggers fallback audio (5 minutes)
TTS_HARD_TIME_LIMIT=360    # Hard timeout - kills hung tasks (6 minutes)

# GPU Configuration  
GPU_RUNTIME=nvidia         # or 'runc' for CPU-only mode
GPU_COUNT=1               # Number of GPUs to use
NVIDIA_VISIBLE_DEVICES=all # GPU device visibility
```

## Key File Locations

### Core Application
- **Main API**: `/app/main.py`
- **Database Models**: `/app/db/models.py` (includes new `JobTask` model for task tracking)
- **API Schemas**: `/app/schemas.py`
- **CRUD Operations**: `/app/crud.py`

### Worker System (Enhanced in v2.3.0)
- **CPU Worker Tasks**: `/app/workers/tasks_cpu.py` (enhanced dependency tracking)
- **GPU Worker Tasks**: `/app/workers/tasks_gpu.py` (modular architecture)
- **TTS Service Layer**: `/app/services/tts_service.py` (new modular TTS components)

### Service Layer
- **LibreOffice Service**: `/app/services/libreoffice_converter.py`
- **MinIO Service**: `/app/services/minio_service.py`

### Testing & Debugging (New in v2.3.0)
- **TTS Isolated Tests**: `/test_tts_isolated.py`
- **TTS Component Tests**: `/tests/test_tts_components.py`
- **Integration Test Runner**: `/test_tts_components_runner.py`

### Configuration
- **Docker Configuration**: `/docker-compose.yml`
- **Environment Template**: `/.env.example`

## Celery Task Coordination (Enhanced in v2.3.0)

### Task Flow
1. **`decompose_presentation`** → triggers multiple **`synthesize_audio`** tasks
2. All **`synthesize_audio`** tasks → triggers **`assemble_video_with_deps`**
3. **Enhanced Dependency Tracking**: Proper task ID tracking instead of hardcoded delays

### Task State Management
- **`JobTask` Model**: Tracks individual task status, progress, and errors
- **Granular Status Updates**: Real-time progress monitoring per task
- **Error Isolation**: Individual task failures don't crash entire job
- **Timeout Handling**: Configurable soft/hard timeouts with fallback mechanisms

### Coordination Improvements
- **Dependency Lists**: Video assembly waits for specific audio task completions
- **Progress Tracking**: Detailed progress messages for user feedback  
- **Failure Recovery**: Multi-layer fallbacks ensure pipeline completion

## Common Debugging Steps (Updated for v2.3.0)

### General Issues
1. **Login Issues**: Verify correct port (18000) and user exists in database
2. **Upload Failures**: Check MinIO storage space and bucket permissions  
3. **Database Issues**: Verify PostgreSQL connection and table creation

### TTS-Specific Debugging (New)
4. **TTS Hangs/Timeouts**: 
   - Check timeout configuration in `.env`
   - Verify BERT model pre-caching: `docker exec ppt-worker_gpu python -c "from transformers import BertTokenizer; print('BERT OK')"`
   - Run isolated TTS tests: `docker exec ppt-worker_gpu python test_tts_isolated.py`

5. **Audio Synthesis Failures**:
   - Check GPU worker logs: `docker-compose logs worker_gpu`
   - Test TTS components: `docker exec ppt-worker_gpu python test_tts_components_runner.py`
   - Monitor fallback behavior: `docker logs ppt-worker_gpu | grep -E "(fallback|timeout|TTS)"`

6. **Job Stuck in Processing**:
   - Check `JobTask` table: `SELECT * FROM job_tasks WHERE status='running' ORDER BY started_at;`
   - Verify task dependencies: Look for orphaned or hung tasks
   - Review worker concurrency settings

### Performance Issues
7. **Slow Processing**: Check GPU availability and worker resource allocation
8. **Memory Issues**: Monitor Docker container resource usage
9. **Storage Full**: Use cleanup APIs to remove old jobs and temporary files

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

## TTS Modular Architecture (New in v2.3.0)

### Core TTS Components

#### `TTSProcessor` (Main Orchestrator)
```python
class TTSProcessor:
    def initialize()                               # Lazy model loading
    def is_ready()                                # Check initialization status
    def synthesize_with_builtin_voice()           # Built-in speaker synthesis
    def synthesize_with_custom_voice()            # Custom voice cloning
    def synthesize_base_only()                    # Fallback base TTS
    def create_silence()                          # Ultimate fallback
```

#### `MeloTTSEngine` (Base TTS)
```python
class MeloTTSEngine:
    def initialize()                              # Load MeloTTS models
    def synthesize_to_file()                      # Pure TTS synthesis
    def is_ready()                               # Check model availability
```

#### `OpenVoiceCloner` (Voice Cloning)
```python
class OpenVoiceCloner:
    def initialize()                              # Load OpenVoice models
    def extract_speaker_embedding()               # Voice analysis
    def clone_voice()                            # Apply voice conversion
    def is_ready()                               # Check model availability
```

#### `TextProcessor` (Text Preprocessing)
```python
class TextProcessor:
    @staticmethod
    def parse_note_text_tags()                    # Parse emotion/speed tags
    def clean_text_for_tts()                     # Text sanitization
```

### Custom Exception Hierarchy
- **`TTSException`**: Base exception for all TTS errors
- **`MeloTTSException`**: MeloTTS-specific errors (model loading, synthesis)
- **`OpenVoiceException`**: OpenVoice-specific errors (cloning, embedding)

### Testing Framework
- **`test_tts_isolated.py`**: Isolated component testing with timeout simulation
- **`tests/test_tts_components.py`**: Unit tests for each modular component
- **`test_tts_components_runner.py`**: Integration tests for Docker environment

This modular approach enables:
- **Independent Testing**: Each component can be tested in isolation
- **Graceful Degradation**: Multiple fallback layers ensure reliability
- **Better Error Handling**: Precise error identification and recovery
- **Maintainable Code**: Clear separation of concerns and responsibilities

---

This documentation provides AI agents with comprehensive technical details for debugging, extending, and maintaining the PPT to Video Generator application.