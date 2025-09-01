# 🎬 PPT to Video Generator

Transform your PowerPoint presentations into engaging narrated videos using AI-powered voice synthesis!

## ✨ Features

- **📊 PowerPoint Integration**: Upload PPTX files and automatically extract slide content
- **🎤 Voice Cloning**: Create custom voice models from audio samples using OpenVoice V2
- **🔊 Default Voice Options**: 10 built-in voices (English, Spanish, French, Japanese, Korean, Chinese) - no upload required!
- **🎵 Multi-Format Support**: Upload WAV or MP3 files for custom voice cloning
- **🤖 AI Narration**: Generate natural-sounding speech from slide notes
- **🎥 Video Generation**: Combine slides with synchronized audio into MP4 videos
- **💾 Persistent Storage**: Host volume mapping for videos and presentations
- **📱 Web Interface**: Easy-to-use browser-based application
- **⚡ Async Processing**: Background job processing with real-time status updates
- **📈 Jobs Dashboard**: Monitor processing status and download completed videos

## Architecture

The application is built with a microservices architecture, orchestrated by Docker Compose for easy local development.

- **`api`**: A FastAPI application that serves the frontend and the backend REST API. The container is named `ppt-api`.
- **`worker_cpu`**: A Celery worker for CPU-intensive tasks like presentation decomposition and video assembly with MoviePy. The container is named `ppt-worker-cpu`.
- **`worker_gpu`**: A Celery worker for GPU-intensive tasks, specifically voice synthesis with OpenVoice V2. The container is named `ppt-worker-gpu`.
- **`libreoffice`**: A dedicated service running a headless LibreOffice instance (wrapped in a Flask API) to convert `.pptx` files to images. The container is named `ppt-libreoffice`.
- **`postgres`**: A PostgreSQL database for storing user, voice clone, and job metadata. The container is named `ppt-postgres`.
- **`redis`**: A Redis instance that acts as the message broker for Celery. The container is named `ppt-redis`.
- **`minio`**: An S3-compatible object storage server for storing all files (presentations, voice samples, images, audio clips, and final videos). The container is named `ppt-minio`.

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- NVIDIA GPU with CUDA support (for voice synthesis)
- 4GB+ available RAM
- 50GB+ free disk space

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd ppttovideo
```

2. **Set up environment variables** (optional)
```bash
# Create .env file with custom settings (optional)
POSTGRES_USER=user
POSTGRES_PASSWORD=password
POSTGRES_DB=presentation_gen_db
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
```

3. **Start the application**
```bash
docker-compose up --build
```
*Note: First run takes 5-10 minutes to download AI models and build containers*

4. **Access the application**
   - **🌐 Main App**: [http://localhost:18000](http://localhost:18000)
   - **📚 API Docs**: [http://localhost:18000/docs](http://localhost:18000/docs)
   - **🗄️ MinIO Console**: [http://localhost:19001](http://localhost:19001)

## 📖 How to Use

### Step 1: Create or Login User
1. Visit http://localhost:18000
2. Click **"Login"** or **"Create User"**
3. Enter your username

### Step 2: Select Voice  
**Option A: Use Default Voices (Recommended)**
- Default voices are automatically available including:
  - English (Default, US, UK, Australia, India)
  - Spanish, French, Japanese, Korean, Chinese
- No upload required - ready to use immediately!

**Option B: Upload Custom Voice Sample**
1. In **"Manage Voice Clones"** section
2. Enter a name for your voice clone
3. Upload a clear audio file (WAV or MP3, 10-30 seconds)
4. Click **"Upload Voice Clone"**

### Step 3: Generate Video
1. Upload your PowerPoint (.pptx) file
2. Select a voice clone
3. Click **"Generate Video"**
4. Monitor progress in Jobs Dashboard

### Step 4: Download Result
- Processing takes 2-10 minutes
- Click **"Download"** when status shows **"completed"**

## 🏗️ System Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Web Browser   │◄──►│   FastAPI App    │◄──►│   PostgreSQL    │
│  (localhost:    │    │  (localhost:     │    │  (User Data &   │
│   18000)        │    │   18000/api)     │    │   Job Status)   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│     MinIO       │◄──►│     Redis        │◄──►│ Celery Workers  │
│  (File Storage) │    │  (Message Queue) │    │ (CPU + GPU)     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
                                                         ▼
                               ┌──────────────────┐
                               │  LibreOffice     │
                               │  (PPTX→Images)   │
                               └──────────────────┘
```

### Service Details
- **`ppt-api`**: FastAPI web server and REST API endpoints
- **`ppt-worker-cpu`**: Video processing and presentation decomposition  
- **`ppt-worker-gpu`**: AI voice synthesis using OpenVoice V2
- **`ppt-libreoffice`**: PowerPoint to image conversion service
- **`ppt-postgres`**: Database for users, jobs, and metadata
- **`ppt-redis`**: Task queue and message broker
- **`ppt-minio`**: File storage (presentations, audio, videos)

## 🔧 Configuration

### Port Mapping
- **Main Application**: 18000
- **PostgreSQL**: 15432  
- **Redis**: 16379
- **MinIO Storage**: 19000
- **MinIO Console**: 19001
- **LibreOffice Service**: 18100

### Volume Mapping (Configurable via .env)
- **Generated Videos**: `/MWC/data/ppt/output` (host) → MinIO output bucket
- **Slide Storage**: `/MWC/data/ppt/slides` (host) → MinIO presentations bucket
- **Environment Variables**: `PPT_OUTPUT_VOLUME` and `PPT_SLIDES_VOLUME` in `.env`

### Storage Buckets
- `ingest`: Uploaded PPTX files
- `voice-clones`: Voice reference audio files
- `presentations`: Intermediate processing files
- `output`: Final generated videos

## 🐛 Troubleshooting

### Common Issues

**❌ Application won't load**
- Verify Docker is running: `docker ps`
- Check all services: `docker-compose ps`
- Use correct URL: http://localhost:18000 (not 8000)

**❌ Login fails**
- Ensure correct port: 18000
- Check existing users: 
  ```bash
  docker-compose exec postgres psql -U user -d presentation_gen_db -c "SELECT * FROM users;"
  ```

**❌ Voice upload fails**
- Check disk space: `df -h`  
- Verify WAV format, < 50MB
- Clean up space: `docker system prune -f`

**❌ Job fails immediately**
- View logs: `docker-compose logs worker_cpu worker_gpu`
- Verify PPTX has slide notes
- Check LibreOffice service: `docker-compose logs libreoffice`

**❌ Out of storage**
- Clean Docker: `docker system prune -f`
- Check MinIO console: http://localhost:19001
- Free up host disk space

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service  
docker-compose logs api
docker-compose logs worker_cpu
docker-compose logs worker_gpu
```

### Database Access
```bash
# Connect to database
docker-compose exec postgres psql -U user -d presentation_gen_db

# View data
SELECT * FROM users;
SELECT id, status, created_at FROM presentation_jobs ORDER BY created_at DESC;
```

## 📋 Requirements

### System Requirements
- **OS**: Linux, macOS, or Windows with WSL2
- **Memory**: 8GB RAM minimum, 16GB recommended  
- **GPU**: NVIDIA GPU with CUDA (for voice synthesis)
- **Storage**: 50GB available space
- **Network**: Internet access for AI model downloads

### File Requirements
- **PowerPoint**: .pptx format only
- **Voice Samples**: .wav or .mp3 format, 16-44kHz sample rate
- **Slide Notes**: Required in PowerPoint Notes section

## 🎯 Best Practices

### PowerPoint Preparation
1. ✅ Add detailed speaker notes to each slide
2. ✅ Keep under 50 slides for optimal performance
3. ✅ Use standard fonts and layouts
4. ❌ Avoid complex animations or embedded media

### Voice Clone Creation
1. ✅ Use clear, high-quality recordings
2. ✅ Record 10-30 seconds of natural speech
3. ✅ Minimize background noise
4. ✅ Speak at normal pace and volume

## 🔒 Security Notice

⚠️ **Development Use Only** - This application is designed for development and testing.

- No user authentication or authorization
- Default credentials for all services
- Files stored without encryption
- Services run with elevated privileges

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature-name`
3. Test changes thoroughly  
4. Submit pull request

## 📄 License

This project is licensed under the MIT License.

## 🆕 Recent Updates

### v2.1.0 - Enhanced Voice & Storage Features
- ✅ **Default Voice Library**: 10 built-in professional voices available instantly
  - English variants: Default, US, UK, Australia, India  
  - International: Spanish, French, Japanese, Korean, Chinese
- ✅ **MP3 Support**: Upload both WAV and MP3 files for voice cloning
- ✅ **Volume Mapping**: Persistent storage on host filesystem
- ✅ **Improved Error Handling**: Better audio processing and task coordination
- ✅ **Enhanced Documentation**: Comprehensive guides for users and developers

### v2.0.0 - Core System Fixes
- ✅ **Task Routing**: Fixed CPU/GPU worker communication
- ✅ **Docker Issues**: Resolved Java runtime and build problems
- ✅ **User Authentication**: Added proper login functionality
- ✅ **Storage Management**: Disk space optimization and cleanup

---

**🎬 Start creating amazing narrated videos from your presentations! ✨**
