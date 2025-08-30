import pytest
from app import crud, schemas
from app.db.models import User, VoiceClone, PresentationJob


class TestUserCRUD:
    def test_create_user(self, db_session, sample_user_data):
        """Test user creation"""
        user_create = schemas.UserCreate(**sample_user_data)
        user = crud.create_user(db_session, user_create)
        
        assert user.name == sample_user_data["name"]
        assert user.email == sample_user_data["email"]
        assert user.id is not None
        assert user.created_at is not None
    
    def test_get_user(self, db_session, sample_user_data):
        """Test getting user by ID"""
        user_create = schemas.UserCreate(**sample_user_data)
        created_user = crud.create_user(db_session, user_create)
        
        retrieved_user = crud.get_user(db_session, created_user.id)
        
        assert retrieved_user is not None
        assert retrieved_user.id == created_user.id
        assert retrieved_user.name == sample_user_data["name"]
    
    def test_get_user_by_email(self, db_session, sample_user_data):
        """Test getting user by email"""
        user_create = schemas.UserCreate(**sample_user_data)
        created_user = crud.create_user(db_session, user_create)
        
        retrieved_user = crud.get_user_by_email(db_session, sample_user_data["email"])
        
        assert retrieved_user is not None
        assert retrieved_user.id == created_user.id
        assert retrieved_user.email == sample_user_data["email"]
    
    def test_get_users(self, db_session):
        """Test getting multiple users with pagination"""
        # Create multiple users
        for i in range(5):
            user_data = {"name": f"User {i}", "email": f"user{i}@example.com"}
            user_create = schemas.UserCreate(**user_data)
            crud.create_user(db_session, user_create)
        
        # Test default pagination
        users = crud.get_users(db_session)
        assert len(users) == 5
        
        # Test with limit
        users = crud.get_users(db_session, limit=2)
        assert len(users) == 2
        
        # Test with skip and limit
        users = crud.get_users(db_session, skip=2, limit=2)
        assert len(users) == 2


class TestVoiceCloneCRUD:
    def test_create_voice_clone(self, db_session, sample_user_data, sample_voice_clone_data):
        """Test voice clone creation"""
        # Create user first
        user_create = schemas.UserCreate(**sample_user_data)
        user = crud.create_user(db_session, user_create)
        
        # Create voice clone
        voice_clone_data = {**sample_voice_clone_data, "owner_id": user.id}
        voice_clone_create = schemas.VoiceCloneCreate(**voice_clone_data)
        s3_path = "/test-bucket/voice-clone.wav"
        
        voice_clone = crud.create_voice_clone(db_session, voice_clone_create, s3_path)
        
        assert voice_clone.name == sample_voice_clone_data["name"]
        assert voice_clone.owner_id == user.id
        assert voice_clone.s3_path == s3_path
        assert voice_clone.id is not None
    
    def test_get_voice_clones_by_user(self, db_session, sample_user_data, sample_voice_clone_data):
        """Test getting voice clones by user"""
        # Create user
        user_create = schemas.UserCreate(**sample_user_data)
        user = crud.create_user(db_session, user_create)
        
        # Create multiple voice clones
        for i in range(3):
            voice_clone_data = {
                "name": f"Voice Clone {i}",
                "owner_id": user.id
            }
            voice_clone_create = schemas.VoiceCloneCreate(**voice_clone_data)
            crud.create_voice_clone(db_session, voice_clone_create, f"/bucket/voice{i}.wav")
        
        voice_clones = crud.get_voice_clones_by_user(db_session, user.id)
        assert len(voice_clones) == 3
        
        # Test pagination
        voice_clones = crud.get_voice_clones_by_user(db_session, user.id, limit=2)
        assert len(voice_clones) == 2


class TestPresentationJobCRUD:
    def test_create_presentation_job(self, db_session, sample_user_data, sample_voice_clone_data):
        """Test presentation job creation"""
        # Create user and voice clone
        user_create = schemas.UserCreate(**sample_user_data)
        user = crud.create_user(db_session, user_create)
        
        voice_clone_data = {**sample_voice_clone_data, "owner_id": user.id}
        voice_clone_create = schemas.VoiceCloneCreate(**voice_clone_data)
        voice_clone = crud.create_voice_clone(db_session, voice_clone_create, "/bucket/voice.wav")
        
        # Create presentation job
        job_data = schemas.PresentationJobCreate(
            owner_id=user.id,
            voice_clone_id=voice_clone.id
        )
        pptx_s3_path = "/bucket/presentation.pptx"
        
        job = crud.create_presentation_job(db_session, job_data, pptx_s3_path)
        
        assert job.owner_id == user.id
        assert job.voice_clone_id == voice_clone.id
        assert job.s3_pptx_path == pptx_s3_path
        assert job.status == "pending"
        assert job.id is not None
    
    def test_get_presentation_job(self, db_session, sample_user_data, sample_voice_clone_data):
        """Test getting presentation job by ID"""
        # Setup prerequisites
        user_create = schemas.UserCreate(**sample_user_data)
        user = crud.create_user(db_session, user_create)
        
        voice_clone_data = {**sample_voice_clone_data, "owner_id": user.id}
        voice_clone_create = schemas.VoiceCloneCreate(**voice_clone_data)
        voice_clone = crud.create_voice_clone(db_session, voice_clone_create, "/bucket/voice.wav")
        
        job_data = schemas.PresentationJobCreate(
            owner_id=user.id,
            voice_clone_id=voice_clone.id
        )
        created_job = crud.create_presentation_job(db_session, job_data, "/bucket/presentation.pptx")
        
        # Test retrieval
        retrieved_job = crud.get_presentation_job(db_session, created_job.id)
        
        assert retrieved_job is not None
        assert retrieved_job.id == created_job.id
        assert retrieved_job.status == "pending"
    
    def test_update_job_status(self, db_session, sample_user_data, sample_voice_clone_data):
        """Test updating job status"""
        # Setup prerequisites
        user_create = schemas.UserCreate(**sample_user_data)
        user = crud.create_user(db_session, user_create)
        
        voice_clone_data = {**sample_voice_clone_data, "owner_id": user.id}
        voice_clone_create = schemas.VoiceCloneCreate(**voice_clone_data)
        voice_clone = crud.create_voice_clone(db_session, voice_clone_create, "/bucket/voice.wav")
        
        job_data = schemas.PresentationJobCreate(
            owner_id=user.id,
            voice_clone_id=voice_clone.id
        )
        job = crud.create_presentation_job(db_session, job_data, "/bucket/presentation.pptx")
        
        # Update status
        updated_job = crud.update_job_status(db_session, job.id, "processing")
        
        assert updated_job.status == "processing"
        assert updated_job.s3_video_path is None
        
        # Update with video path
        video_path = "/bucket/output.mp4"
        updated_job = crud.update_job_status(db_session, job.id, "completed", video_path)
        
        assert updated_job.status == "completed"
        assert updated_job.s3_video_path == video_path
    
    def test_update_job_status_nonexistent(self, db_session):
        """Test updating status of non-existent job"""
        result = crud.update_job_status(db_session, 999, "processing")
        assert result is None