import pytest
from pydantic import ValidationError
import datetime
from app import schemas


class TestUserSchemas:
    def test_user_base_valid(self):
        """Test UserBase schema with valid data"""
        data = {"name": "Test User", "email": "test@example.com"}
        user_base = schemas.UserBase(**data)
        
        assert user_base.name == "Test User"
        assert user_base.email == "test@example.com"
    
    def test_user_base_no_email(self):
        """Test UserBase schema without email (optional field)"""
        data = {"name": "Test User"}
        user_base = schemas.UserBase(**data)
        
        assert user_base.name == "Test User"
        assert user_base.email is None
    
    def test_user_base_missing_name(self):
        """Test UserBase schema missing required name field"""
        data = {"email": "test@example.com"}
        
        with pytest.raises(ValidationError) as exc_info:
            schemas.UserBase(**data)
        
        assert "name" in str(exc_info.value)
    
    def test_user_create_schema(self):
        """Test UserCreate schema"""
        data = {"name": "Test User", "email": "test@example.com"}
        user_create = schemas.UserCreate(**data)
        
        assert isinstance(user_create, schemas.UserBase)
        assert user_create.name == "Test User"
        assert user_create.email == "test@example.com"
    
    def test_user_response_schema(self):
        """Test User response schema"""
        data = {
            "name": "Test User",
            "email": "test@example.com",
            "id": 1,
            "created_at": datetime.datetime.utcnow()
        }
        user = schemas.User(**data)
        
        assert user.name == "Test User"
        assert user.email == "test@example.com"
        assert user.id == 1
        assert isinstance(user.created_at, datetime.datetime)


class TestVoiceCloneSchemas:
    def test_voice_clone_base_valid(self):
        """Test VoiceCloneBase schema with valid data"""
        data = {"name": "Test Voice Clone"}
        voice_clone_base = schemas.VoiceCloneBase(**data)
        
        assert voice_clone_base.name == "Test Voice Clone"
    
    def test_voice_clone_base_missing_name(self):
        """Test VoiceCloneBase schema missing required name field"""
        data = {}
        
        with pytest.raises(ValidationError) as exc_info:
            schemas.VoiceCloneBase(**data)
        
        assert "name" in str(exc_info.value)
    
    def test_voice_clone_create_schema(self):
        """Test VoiceCloneCreate schema"""
        data = {"name": "Test Voice Clone", "owner_id": 1}
        voice_clone_create = schemas.VoiceCloneCreate(**data)
        
        assert isinstance(voice_clone_create, schemas.VoiceCloneBase)
        assert voice_clone_create.name == "Test Voice Clone"
        assert voice_clone_create.owner_id == 1
    
    def test_voice_clone_create_missing_owner_id(self):
        """Test VoiceCloneCreate schema missing required owner_id field"""
        data = {"name": "Test Voice Clone"}
        
        with pytest.raises(ValidationError) as exc_info:
            schemas.VoiceCloneCreate(**data)
        
        assert "owner_id" in str(exc_info.value)
    
    def test_voice_clone_response_schema(self):
        """Test VoiceClone response schema"""
        data = {
            "name": "Test Voice Clone",
            "id": 1,
            "s3_path": "/bucket/voice.wav",
            "created_at": datetime.datetime.utcnow(),
            "owner_id": 1
        }
        voice_clone = schemas.VoiceClone(**data)
        
        assert voice_clone.name == "Test Voice Clone"
        assert voice_clone.id == 1
        assert voice_clone.s3_path == "/bucket/voice.wav"
        assert voice_clone.owner_id == 1
        assert isinstance(voice_clone.created_at, datetime.datetime)


class TestPresentationJobSchemas:
    def test_presentation_job_base_valid(self):
        """Test PresentationJobBase schema"""
        data = {}
        job_base = schemas.PresentationJobBase(**data)
        
        # PresentationJobBase is empty, should instantiate without issues
        assert isinstance(job_base, schemas.PresentationJobBase)
    
    def test_presentation_job_create_schema(self):
        """Test PresentationJobCreate schema"""
        data = {"owner_id": 1, "voice_clone_id": 2}
        job_create = schemas.PresentationJobCreate(**data)
        
        assert isinstance(job_create, schemas.PresentationJobBase)
        assert job_create.owner_id == 1
        assert job_create.voice_clone_id == 2
    
    def test_presentation_job_create_missing_fields(self):
        """Test PresentationJobCreate schema missing required fields"""
        # Missing owner_id
        data = {"voice_clone_id": 2}
        with pytest.raises(ValidationError) as exc_info:
            schemas.PresentationJobCreate(**data)
        assert "owner_id" in str(exc_info.value)
        
        # Missing voice_clone_id
        data = {"owner_id": 1}
        with pytest.raises(ValidationError) as exc_info:
            schemas.PresentationJobCreate(**data)
        assert "voice_clone_id" in str(exc_info.value)
    
    def test_presentation_job_response_schema(self):
        """Test PresentationJob response schema"""
        data = {
            "id": 1,
            "status": "pending",
            "s3_pptx_path": "/bucket/presentation.pptx",
            "s3_video_path": None,
            "created_at": datetime.datetime.utcnow(),
            "updated_at": datetime.datetime.utcnow(),
            "owner_id": 1,
            "voice_clone_id": 2
        }
        job = schemas.PresentationJob(**data)
        
        assert job.id == 1
        assert job.status == "pending"
        assert job.s3_pptx_path == "/bucket/presentation.pptx"
        assert job.s3_video_path is None
        assert job.owner_id == 1
        assert job.voice_clone_id == 2
        assert isinstance(job.created_at, datetime.datetime)
        assert isinstance(job.updated_at, datetime.datetime)
    
    def test_presentation_job_response_with_video_path(self):
        """Test PresentationJob response schema with video path"""
        data = {
            "id": 1,
            "status": "completed",
            "s3_pptx_path": "/bucket/presentation.pptx",
            "s3_video_path": "/bucket/output.mp4",
            "created_at": datetime.datetime.utcnow(),
            "updated_at": datetime.datetime.utcnow(),
            "owner_id": 1,
            "voice_clone_id": 2
        }
        job = schemas.PresentationJob(**data)
        
        assert job.status == "completed"
        assert job.s3_video_path == "/bucket/output.mp4"


class TestSchemaValidation:
    def test_email_format_validation(self):
        """Test email format validation (if implemented)"""
        # Note: Current schema doesn't have email validation
        # This test shows where validation could be added
        data = {"name": "Test User", "email": "invalid-email"}
        
        # Currently this passes because no validation is implemented
        user = schemas.UserBase(**data)
        assert user.email == "invalid-email"
        
        # TODO: Add email validation to schemas
    
    def test_string_type_validation(self):
        """Test string type validation"""
        # Test with non-string name
        with pytest.raises(ValidationError):
            schemas.UserBase(name=123, email="test@example.com")
        
        # Test with non-string s3_path in response
        with pytest.raises(ValidationError):
            schemas.VoiceClone(
                name="Test",
                id=1,
                s3_path=123,  # Should be string
                created_at=datetime.datetime.utcnow(),
                owner_id=1
            )