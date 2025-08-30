import pytest
import io
import json
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock
from app.main import app
from app import crud, schemas


class TestUsersEndpoint:
    """Test the users API endpoints"""
    
    def test_create_user_success(self, client, db_session, sample_user_data):
        """Test successful user creation"""
        response = client.post("/api/users/", json=sample_user_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == sample_user_data["name"]
        assert data["email"] == sample_user_data["email"]
        assert "id" in data
        assert "created_at" in data
    
    def test_create_user_missing_name(self, client, db_session):
        """Test user creation with missing name"""
        user_data = {"email": "test@example.com"}
        
        response = client.post("/api/users/", json=user_data)
        
        assert response.status_code == 422  # Validation error
    
    def test_get_users(self, client, db_session, sample_user_data):
        """Test getting list of users"""
        # Create a user first
        client.post("/api/users/", json=sample_user_data)
        
        response = client.get("/api/users/")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["name"] == sample_user_data["name"]
    
    def test_get_user_by_id(self, client, db_session, sample_user_data):
        """Test getting user by ID"""
        # Create a user first
        create_response = client.post("/api/users/", json=sample_user_data)
        user_id = create_response.json()["id"]
        
        response = client.get(f"/api/users/{user_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == user_id
        assert data["name"] == sample_user_data["name"]
    
    def test_get_user_not_found(self, client, db_session):
        """Test getting non-existent user"""
        response = client.get("/api/users/999")
        
        assert response.status_code == 404


class TestVoiceClonesEndpoint:
    """Test the voice clones API endpoints"""
    
    @pytest.fixture
    def user_id(self, client, db_session, sample_user_data):
        """Create a user and return its ID"""
        response = client.post("/api/users/", json=sample_user_data)
        return response.json()["id"]
    
    @patch('app.api.endpoints.voice_clones.minio_service')
    def test_create_voice_clone_success(self, mock_minio, client, db_session, user_id):
        """Test successful voice clone creation"""
        # Mock MinIO upload
        mock_minio.upload_file.return_value = "/voice-clones/test-voice.wav"
        
        # Create test WAV file data
        wav_data = b"RIFF" + b"\x00" * 44  # Minimal WAV header
        
        response = client.post(
            "/api/voice-clones/",
            data={"name": "Test Voice Clone", "owner_id": user_id},
            files={"file": ("test.wav", io.BytesIO(wav_data), "audio/wav")}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Voice Clone"
        assert data["owner_id"] == user_id
        assert data["s3_path"] == "/voice-clones/test-voice.wav"
        assert "id" in data
    
    def test_create_voice_clone_invalid_file_type(self, client, db_session, user_id):
        """Test voice clone creation with invalid file type"""
        response = client.post(
            "/api/voice-clones/",
            data={"name": "Test Voice Clone", "owner_id": user_id},
            files={"file": ("test.txt", io.BytesIO(b"text data"), "text/plain")}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "Invalid file type" in data["detail"]
    
    def test_create_voice_clone_missing_name(self, client, db_session, user_id):
        """Test voice clone creation with missing name"""
        wav_data = b"RIFF" + b"\x00" * 44
        
        response = client.post(
            "/api/voice-clones/",
            data={"owner_id": user_id},  # Missing name
            files={"file": ("test.wav", io.BytesIO(wav_data), "audio/wav")}
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_get_voice_clones_by_user(self, client, db_session, user_id):
        """Test getting voice clones by user"""
        # Create a voice clone first
        with patch('app.api.endpoints.voice_clones.minio_service') as mock_minio:
            mock_minio.upload_file.return_value = "/voice-clones/test-voice.wav"
            wav_data = b"RIFF" + b"\x00" * 44
            
            client.post(
                "/api/voice-clones/",
                data={"name": "Test Voice Clone", "owner_id": user_id},
                files={"file": ("test.wav", io.BytesIO(wav_data), "audio/wav")}
            )
        
        response = client.get(f"/api/voice-clones/user/{user_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["name"] == "Test Voice Clone"
        assert data[0]["owner_id"] == user_id


class TestPresentationsEndpoint:
    """Test the presentations API endpoints"""
    
    @pytest.fixture
    def user_and_voice_clone(self, client, db_session, sample_user_data):
        """Create user and voice clone for testing"""
        # Create user
        user_response = client.post("/api/users/", json=sample_user_data)
        user_id = user_response.json()["id"]
        
        # Create voice clone
        with patch('app.api.endpoints.voice_clones.minio_service') as mock_minio:
            mock_minio.upload_file.return_value = "/voice-clones/test-voice.wav"
            wav_data = b"RIFF" + b"\x00" * 44
            
            voice_response = client.post(
                "/api/voice-clones/",
                data={"name": "Test Voice", "owner_id": user_id},
                files={"file": ("test.wav", io.BytesIO(wav_data), "audio/wav")}
            )
        
        voice_clone_id = voice_response.json()["id"]
        return user_id, voice_clone_id
    
    @patch('app.api.endpoints.presentations.celery_app')
    @patch('app.api.endpoints.presentations.minio_service')
    def test_create_presentation_success(self, mock_minio, mock_celery, client, db_session, user_and_voice_clone):
        """Test successful presentation creation"""
        user_id, voice_clone_id = user_and_voice_clone
        
        # Mock MinIO upload
        mock_minio.upload_file.return_value = "/ingest/test-presentation.pptx"
        
        # Mock Celery task dispatch
        mock_celery.send_task.return_value = None
        
        # Create test PPTX file data
        pptx_data = b"PK" + b"\x00" * 100  # Minimal PPTX-like data
        
        response = client.post(
            "/api/presentations/",
            data={"owner_id": user_id, "voice_clone_id": voice_clone_id},
            files={"file": ("test.pptx", io.BytesIO(pptx_data), 
                          "application/vnd.openxmlformats-officedocument.presentationml.presentation")}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["owner_id"] == user_id
        assert data["voice_clone_id"] == voice_clone_id
        assert data["status"] == "pending"
        assert data["s3_pptx_path"] == "/ingest/test-presentation.pptx"
        
        # Verify Celery task was dispatched
        mock_celery.send_task.assert_called_once()
        assert "decompose_presentation" in mock_celery.send_task.call_args[0][0]
    
    def test_create_presentation_invalid_file_type(self, client, db_session, user_and_voice_clone):
        """Test presentation creation with invalid file type"""
        user_id, voice_clone_id = user_and_voice_clone
        
        response = client.post(
            "/api/presentations/",
            data={"owner_id": user_id, "voice_clone_id": voice_clone_id},
            files={"file": ("test.pdf", io.BytesIO(b"pdf data"), "application/pdf")}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "Invalid file type" in data["detail"]
        assert ".pptx" in data["detail"]
    
    def test_create_presentation_missing_fields(self, client, db_session):
        """Test presentation creation with missing required fields"""
        pptx_data = b"PK" + b"\x00" * 100
        
        # Missing owner_id
        response = client.post(
            "/api/presentations/",
            data={"voice_clone_id": 1},
            files={"file": ("test.pptx", io.BytesIO(pptx_data),
                          "application/vnd.openxmlformats-officedocument.presentationml.presentation")}
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_get_all_jobs(self, client, db_session, user_and_voice_clone):
        """Test getting all presentation jobs"""
        user_id, voice_clone_id = user_and_voice_clone
        
        # Create a presentation job first
        with patch('app.api.endpoints.presentations.celery_app') as mock_celery, \
             patch('app.api.endpoints.presentations.minio_service') as mock_minio:
            
            mock_minio.upload_file.return_value = "/ingest/test-presentation.pptx"
            mock_celery.send_task.return_value = None
            
            pptx_data = b"PK" + b"\x00" * 100
            client.post(
                "/api/presentations/",
                data={"owner_id": user_id, "voice_clone_id": voice_clone_id},
                files={"file": ("test.pptx", io.BytesIO(pptx_data),
                              "application/vnd.openxmlformats-officedocument.presentationml.presentation")}
            )
        
        response = client.get("/api/presentations/status/all")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["status"] == "pending"
    
    def test_get_job_status(self, client, db_session, user_and_voice_clone):
        """Test getting specific job status"""
        user_id, voice_clone_id = user_and_voice_clone
        
        # Create a presentation job first
        with patch('app.api.endpoints.presentations.celery_app') as mock_celery, \
             patch('app.api.endpoints.presentations.minio_service') as mock_minio:
            
            mock_minio.upload_file.return_value = "/ingest/test-presentation.pptx"
            mock_celery.send_task.return_value = None
            
            pptx_data = b"PK" + b"\x00" * 100
            create_response = client.post(
                "/api/presentations/",
                data={"owner_id": user_id, "voice_clone_id": voice_clone_id},
                files={"file": ("test.pptx", io.BytesIO(pptx_data),
                              "application/vnd.openxmlformats-officedocument.presentationml.presentation")}
            )
        
        job_id = create_response.json()["id"]
        
        response = client.get(f"/api/presentations/status/{job_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == job_id
        assert data["status"] == "pending"
    
    def test_get_job_status_not_found(self, client, db_session):
        """Test getting status of non-existent job"""
        response = client.get("/api/presentations/status/999")
        
        assert response.status_code == 404
        data = response.json()
        assert "Job not found" in data["detail"]
    
    @patch('app.api.endpoints.presentations.minio_service')
    def test_download_video_success(self, mock_minio, client, db_session, user_and_voice_clone):
        """Test successful video download"""
        user_id, voice_clone_id = user_and_voice_clone
        
        # Create and complete a presentation job
        job_data = schemas.PresentationJobCreate(
            owner_id=user_id,
            voice_clone_id=voice_clone_id
        )
        job = crud.create_presentation_job(db_session, job_data, "/ingest/test.pptx")
        crud.update_job_status(db_session, job.id, "completed", "/output/video.mp4")
        
        # Mock MinIO response
        mock_stream = Mock()
        mock_stream.stream.return_value = iter([b"video data chunk 1", b"video data chunk 2"])
        mock_minio.client.get_object.return_value = mock_stream
        
        response = client.get(f"/api/presentations/download/{job.id}")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "video/mp4"
        assert "attachment" in response.headers["content-disposition"]
    
    def test_download_video_job_not_found(self, client, db_session):
        """Test download for non-existent job"""
        response = client.get("/api/presentations/download/999")
        
        assert response.status_code == 404
        data = response.json()
        assert "Job not found" in data["detail"]
    
    def test_download_video_job_not_completed(self, client, db_session, user_and_voice_clone):
        """Test download for incomplete job"""
        user_id, voice_clone_id = user_and_voice_clone
        
        # Create job but don't complete it
        job_data = schemas.PresentationJobCreate(
            owner_id=user_id,
            voice_clone_id=voice_clone_id
        )
        job = crud.create_presentation_job(db_session, job_data, "/ingest/test.pptx")
        # Leave status as "pending"
        
        response = client.get(f"/api/presentations/download/{job.id}")
        
        assert response.status_code == 400
        data = response.json()
        assert "Job is not complete" in data["detail"]
    
    def test_download_video_no_video_path(self, client, db_session, user_and_voice_clone):
        """Test download when job is completed but has no video path"""
        user_id, voice_clone_id = user_and_voice_clone
        
        # Create job and mark completed but without video path
        job_data = schemas.PresentationJobCreate(
            owner_id=user_id,
            voice_clone_id=voice_clone_id
        )
        job = crud.create_presentation_job(db_session, job_data, "/ingest/test.pptx")
        crud.update_job_status(db_session, job.id, "completed")  # No video_path
        
        response = client.get(f"/api/presentations/download/{job.id}")
        
        assert response.status_code == 404
        data = response.json()
        assert "Video file not found" in data["detail"]
    
    @patch('app.api.endpoints.presentations.minio_service')
    def test_download_video_minio_error(self, mock_minio, client, db_session, user_and_voice_clone):
        """Test download with MinIO error"""
        from minio.error import S3Error
        
        user_id, voice_clone_id = user_and_voice_clone
        
        # Create completed job
        job_data = schemas.PresentationJobCreate(
            owner_id=user_id,
            voice_clone_id=voice_clone_id
        )
        job = crud.create_presentation_job(db_session, job_data, "/ingest/test.pptx")
        crud.update_job_status(db_session, job.id, "completed", "/output/video.mp4")
        
        # Mock MinIO to raise error
        mock_minio.client.get_object.side_effect = S3Error(
            "NoSuchKey",
            "The specified key does not exist",
            resource="video.mp4",
            request_id="123",
            host_id="456"
        )
        
        response = client.get(f"/api/presentations/download/{job.id}")
        
        assert response.status_code == 500
        data = response.json()
        assert "MinIO error" in data["detail"]


class TestMainApplication:
    """Test the main FastAPI application"""
    
    def test_root_endpoint(self, client):
        """Test the root endpoint serves HTML template"""
        response = client.get("/")
        
        assert response.status_code == 200
        # Note: This will fail if template doesn't exist, which is expected in test environment
        # In real tests, you'd mock the template rendering
    
    def test_api_docs_available(self, client):
        """Test that API documentation is available"""
        response = client.get("/docs")
        
        assert response.status_code == 200
    
    def test_openapi_schema_available(self, client):
        """Test that OpenAPI schema is available"""
        response = client.get("/openapi.json")
        
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert data["info"]["title"] == "Presentation Video Generator API"