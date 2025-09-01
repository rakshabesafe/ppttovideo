# 📚 PPT to Video Generator - API Documentation

## Base URL
- **Production**: `http://localhost:18000`
- **API Base Path**: `/api`

## Authentication
Currently, no authentication is required for API access. This is for development use only.

---

## 👥 Users API

### Get User by Name
```http
GET /api/users/by_name/{username}
```

**Parameters:**
- `username` (path): Username to look up

**Response:**
```json
{
  "id": 1,
  "name": "john_doe",
  "email": "john@example.com",
  "created_at": "2025-09-01T10:00:00"
}
```

### Create User
```http
POST /api/users/
```

**Request Body:**
```json
{
  "name": "john_doe",
  "email": "john@example.com"
}
```

**Response:**
```json
{
  "id": 1,
  "name": "john_doe", 
  "email": "john@example.com",
  "created_at": "2025-09-01T10:00:00"
}
```

---

## 🎤 Voice Clones API

### Get User's Voice Clones
```http
GET /api/voice-clones/user/{user_id}
```

**Parameters:**
- `user_id` (path): User ID

**Response:**
```json
[
  {
    "id": 1,
    "name": "My Voice",
    "s3_path": "/voice-clones/sample.wav",
    "created_at": "2025-09-01T10:00:00",
    "owner_id": 1
  }
]
```

### Upload Voice Clone
```http
POST /api/voice-clones/
```

**Request:** Multipart form data
- `name` (string): Voice clone name
- `owner_id` (integer): Owner user ID
- `audio_file` (file): WAV or MP3 audio file

**Response:**
```json
{
  "id": 2,
  "name": "Custom Voice",
  "s3_path": "/voice-clones/custom.wav",
  "created_at": "2025-09-01T10:00:00",
  "owner_id": 1
}
```

---

## 🎬 Presentations API

### Create Presentation Job
```http
POST /api/presentations/
```

**Request:** Multipart form data
- `owner_id` (integer): User ID
- `voice_clone_id` (integer): Voice clone ID
- `pptx_file` (file): PowerPoint presentation file (.pptx)

**Response:**
```json
{
  "id": 1,
  "status": "pending",
  "s3_pptx_path": "/ingest/presentation.pptx",
  "s3_video_path": null,
  "created_at": "2025-09-01T10:00:00",
  "updated_at": "2025-09-01T10:00:00",
  "owner_id": 1,
  "voice_clone_id": 1
}
```

### Get Job Status
```http
GET /api/presentations/status/{job_id}
```

**Parameters:**
- `job_id` (path): Presentation job ID

**Response:**
```json
{
  "id": 1,
  "status": "completed",
  "s3_pptx_path": "/ingest/presentation.pptx",
  "s3_video_path": "/output/1.mp4",
  "created_at": "2025-09-01T10:00:00",
  "updated_at": "2025-09-01T10:05:00",
  "owner_id": 1,
  "voice_clone_id": 1
}
```

**Job Statuses:**
- `pending`: Job queued for processing
- `processing_slides`: Extracting slide content
- `synthesizing_audio`: Generating voice narration
- `assembling_video`: Creating final video
- `completed`: Video ready for download
- `failed`: Processing failed

### Get All Job Statuses
```http
GET /api/presentations/status/all
```

**Response:**
```json
[
  {
    "id": 1,
    "status": "completed",
    "created_at": "2025-09-01T10:00:00",
    "owner_id": 1
  },
  {
    "id": 2,
    "status": "pending",
    "created_at": "2025-09-01T10:30:00",
    "owner_id": 1
  }
]
```

### Download Video
```http
GET /api/presentations/download/{job_id}
```

**Parameters:**
- `job_id` (path): Presentation job ID

**Response:** Binary video file (MP4)

---

## 🧹 Cleanup API - **NEW**

### Preview Cleanup
```http
GET /api/cleanup/preview?days_old={days}&status_filter={statuses}
```

**Parameters:**
- `days_old` (query, optional): Jobs older than N days (default: 7)
- `status_filter` (query, optional): Comma-separated statuses (default: "completed,failed")

**Response:**
```json
{
  "success": true,
  "preview": {
    "jobs_count": 5,
    "cutoff_date": "2025-08-25T10:00:00",
    "status_filter": ["completed", "failed"],
    "jobs": [
      {
        "id": 1,
        "status": "failed",
        "created_at": "2025-08-20T10:00:00",
        "pptx_path": "/ingest/old.pptx",
        "video_path": null,
        "owner_id": 1
      }
    ]
  },
  "message": "Found 5 jobs that would be cleaned up"
}
```

### Execute Cleanup
```http
POST /api/cleanup/execute
```

**Request Body:**
```json
{
  "days_old": 30,
  "status_filter": ["failed", "completed"]
}
```

**Response:**
```json
{
  "success": true,
  "cleanup_stats": {
    "jobs_deleted": 3,
    "files_deleted": 21,
    "errors": [],
    "jobs_processed": [
      {
        "job_id": 1,
        "status": "failed",
        "created_at": "2025-08-20T10:00:00",
        "files_deleted": 7
      }
    ]
  },
  "message": "Cleanup completed. Deleted 3 jobs and 21 files."
}
```

### Cleanup Specific Jobs
```http
POST /api/cleanup/specific-jobs
```

**Request Body:**
```json
{
  "job_ids": [1, 2, 3, 4, 5]
}
```

**Response:**
```json
{
  "success": true,
  "cleanup_stats": {
    "jobs_deleted": 5,
    "files_deleted": 35,
    "errors": [],
    "jobs_processed": [
      {
        "job_id": 1,
        "status": "failed",
        "created_at": "2025-08-20T10:00:00",
        "files_deleted": 7
      }
    ]
  },
  "message": "Specific job cleanup completed. Deleted 5 jobs and 35 files."
}
```

### Get Cleanup Statistics
```http
GET /api/cleanup/stats
```

**Response:**
```json
{
  "success": true,
  "stats": {
    "7_days": {
      "jobs_count": 2,
      "cutoff_date": "2025-08-25T10:00:00",
      "status_filter": ["completed", "failed"],
      "jobs": []
    },
    "30_days": {
      "jobs_count": 8,
      "cutoff_date": "2025-08-02T10:00:00", 
      "status_filter": ["completed", "failed"],
      "jobs": []
    },
    "90_days": {
      "jobs_count": 15,
      "cutoff_date": "2025-06-03T10:00:00",
      "status_filter": ["completed", "failed"],
      "jobs": []
    }
  },
  "message": "Cleanup statistics retrieved successfully"
}
```

### Get Available Job Statuses
```http
GET /api/cleanup/job-statuses
```

**Response:**
```json
{
  "success": true,
  "statuses": [
    "pending",
    "processing_slides",
    "synthesizing_audio", 
    "assembling_video",
    "completed",
    "failed"
  ],
  "recommended_for_cleanup": ["completed", "failed"],
  "message": "Available job statuses retrieved successfully"
}
```

---

## 🔧 CLI Tools - **NEW**

### Cleanup Jobs CLI

```bash
# Preview cleanup (jobs older than 7 days)
docker exec ppt-api python -m app.cli.cleanup_jobs --preview --days 7

# Execute cleanup with confirmation prompt
docker exec ppt-api python -m app.cli.cleanup_jobs --execute --days 30 --status failed

# Cleanup specific jobs by ID
docker exec ppt-api python -m app.cli.cleanup_jobs --specific-jobs 1,2,3,4,5

# View cleanup statistics
docker exec ppt-api python -m app.cli.cleanup_jobs --stats

# JSON output format
docker exec ppt-api python -m app.cli.cleanup_jobs --stats --format json

# Verbose output
docker exec ppt-api python -m app.cli.cleanup_jobs --preview --days 7 --verbose
```

**CLI Options:**
- `--preview`: Preview what would be cleaned (no deletion)
- `--execute`: Execute cleanup with confirmation
- `--specific-jobs`: Comma-separated job IDs to clean
- `--stats`: Show cleanup statistics for different time periods
- `--days N`: Clean jobs older than N days (default: 7)
- `--status STATUS`: Filter by job status (default: "completed,failed")
- `--format FORMAT`: Output format: text or json (default: text)
- `--verbose`: Show detailed information

---

## 📊 Error Responses

### Standard Error Format
```json
{
  "detail": "Error description",
  "error_code": "ERROR_CODE",
  "timestamp": "2025-09-01T10:00:00"
}
```

### Common HTTP Status Codes
- **200**: Success
- **400**: Bad Request (invalid parameters)
- **404**: Not Found (job/user doesn't exist)
- **500**: Internal Server Error (processing failed)

---

## 🗂️ File Storage Structure

### MinIO Buckets
- **`ingest`**: Uploaded PPTX files
  - Format: `/ingest/{uuid}.pptx`
- **`voice-clones`**: Voice reference audio files
  - Format: `/voice-clones/{uuid}.wav`
- **`presentations`**: Intermediate processing files
  - Images: `/presentations/{uuid}/images/slide-1.png`
  - Audio: `/presentations/{job_id}/audio/slide_1.wav`
  - Notes: `/presentations/{job_id}/notes/slide_1.txt`
- **`output`**: Final generated videos
  - Format: `/output/{job_id}.mp4`

### File Cleanup Process
When cleaning up a job, the following files are removed:
1. Original PPTX file from `ingest` bucket
2. Generated slide images from `presentations` bucket
3. Synthesized audio files from `presentations` bucket
4. Extracted notes files from `presentations` bucket
5. Final video file from `output` bucket
6. Job record from PostgreSQL database

---

## 🛠️ Development & Testing

### Using the API with curl

```bash
# Create a user
curl -X POST "http://localhost:18000/api/users/" \
  -H "Content-Type: application/json" \
  -d '{"name": "test_user", "email": "test@example.com"}'

# Upload voice clone
curl -X POST "http://localhost:18000/api/voice-clones/" \
  -F "name=My Voice" \
  -F "owner_id=1" \
  -F "audio_file=@voice_sample.wav"

# Create presentation job
curl -X POST "http://localhost:18000/api/presentations/" \
  -F "owner_id=1" \
  -F "voice_clone_id=1" \
  -F "pptx_file=@presentation.pptx"

# Check job status
curl "http://localhost:18000/api/presentations/status/1"

# Preview cleanup
curl "http://localhost:18000/api/cleanup/preview?days_old=0"

# Execute cleanup
curl -X POST "http://localhost:18000/api/cleanup/execute" \
  -H "Content-Type: application/json" \
  -d '{"days_old": 7, "status_filter": ["failed"]}'
```

### Interactive API Documentation
Visit [http://localhost:18000/docs](http://localhost:18000/docs) for interactive Swagger documentation.

---

## 🔄 Rate Limits & Best Practices

### Recommendations
- **File Sizes**: Keep PPTX files under 100MB
- **Voice Samples**: 10-30 seconds, clear audio quality
- **Concurrent Jobs**: Limit to 5 simultaneous processing jobs
- **Cleanup Frequency**: Run cleanup weekly or when storage is low
- **Status Polling**: Check job status every 10-30 seconds

### Storage Management
- Monitor disk usage via MinIO console: [http://localhost:19001](http://localhost:19001)
- Use cleanup API regularly to manage storage
- Set up automated cleanup via cron jobs using CLI tools

---

## 🆕 Recent API Changes

### v2.2.0 - Cleanup Management
- ✅ Added complete cleanup API with preview, execute, and statistics endpoints
- ✅ Added CLI tools for automation and batch operations
- ✅ Added job-specific cleanup functionality
- ✅ Enhanced error handling and response formats

### v2.1.0 - Enhanced Features  
- ✅ Added default voice clones (no upload required)
- ✅ Added MP3 support for voice cloning
- ✅ Improved error responses and status tracking

### v2.0.0 - Core API
- ✅ Initial API implementation with users, voice clones, and presentations
- ✅ Job status tracking and video download functionality

---

**📚 For more detailed examples and integration guides, see the main README.md file.**