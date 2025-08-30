import pytest
import datetime
from app.db.models import User, VoiceClone, PresentationJob


class TestUser:
    def test_user_creation(self, db_session):
        """Test User model creation"""
        user = User(name="Test User", email="test@example.com")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        assert user.id is not None
        assert user.name == "Test User"
        assert user.email == "test@example.com"
        assert isinstance(user.created_at, datetime.datetime)
    
    def test_user_unique_email(self, db_session):
        """Test that user email is unique"""
        user1 = User(name="User 1", email="test@example.com")
        user2 = User(name="User 2", email="test@example.com")
        
        db_session.add(user1)
        db_session.commit()
        
        db_session.add(user2)
        with pytest.raises(Exception):  # SQLite will raise IntegrityError
            db_session.commit()
    
    def test_user_relationships(self, db_session):
        """Test User model relationships"""
        user = User(name="Test User", email="test@example.com")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        # Test that relationships are accessible
        assert hasattr(user, 'voice_clones')
        assert hasattr(user, 'presentations')
        assert user.voice_clones == []
        assert user.presentations == []


class TestVoiceClone:
    def test_voice_clone_creation(self, db_session):
        """Test VoiceClone model creation"""
        user = User(name="Test User", email="test@example.com")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        voice_clone = VoiceClone(
            name="Test Voice",
            s3_path="/bucket/voice.wav",
            owner_id=user.id
        )
        db_session.add(voice_clone)
        db_session.commit()
        db_session.refresh(voice_clone)
        
        assert voice_clone.id is not None
        assert voice_clone.name == "Test Voice"
        assert voice_clone.s3_path == "/bucket/voice.wav"
        assert voice_clone.owner_id == user.id
        assert isinstance(voice_clone.created_at, datetime.datetime)
    
    def test_voice_clone_owner_relationship(self, db_session):
        """Test VoiceClone owner relationship"""
        user = User(name="Test User", email="test@example.com")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        voice_clone = VoiceClone(
            name="Test Voice",
            s3_path="/bucket/voice.wav",
            owner_id=user.id
        )
        db_session.add(voice_clone)
        db_session.commit()
        db_session.refresh(voice_clone)
        
        # Test relationship
        assert voice_clone.owner == user
        assert voice_clone in user.voice_clones


class TestPresentationJob:
    def test_presentation_job_creation(self, db_session):
        """Test PresentationJob model creation"""
        user = User(name="Test User", email="test@example.com")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        voice_clone = VoiceClone(
            name="Test Voice",
            s3_path="/bucket/voice.wav",
            owner_id=user.id
        )
        db_session.add(voice_clone)
        db_session.commit()
        db_session.refresh(voice_clone)
        
        job = PresentationJob(
            s3_pptx_path="/bucket/presentation.pptx",
            owner_id=user.id,
            voice_clone_id=voice_clone.id
        )
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)
        
        assert job.id is not None
        assert job.status == "pending"  # Default status
        assert job.s3_pptx_path == "/bucket/presentation.pptx"
        assert job.s3_video_path is None
        assert job.owner_id == user.id
        assert job.voice_clone_id == voice_clone.id
        assert isinstance(job.created_at, datetime.datetime)
        assert isinstance(job.updated_at, datetime.datetime)
    
    def test_presentation_job_relationships(self, db_session):
        """Test PresentationJob relationships"""
        user = User(name="Test User", email="test@example.com")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        voice_clone = VoiceClone(
            name="Test Voice",
            s3_path="/bucket/voice.wav",
            owner_id=user.id
        )
        db_session.add(voice_clone)
        db_session.commit()
        db_session.refresh(voice_clone)
        
        job = PresentationJob(
            s3_pptx_path="/bucket/presentation.pptx",
            owner_id=user.id,
            voice_clone_id=voice_clone.id
        )
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)
        
        # Test relationships
        assert job.owner == user
        assert job.voice_clone == voice_clone
        assert job in user.presentations
    
    def test_presentation_job_status_update(self, db_session):
        """Test PresentationJob status and path updates"""
        user = User(name="Test User", email="test@example.com")
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        
        voice_clone = VoiceClone(
            name="Test Voice",
            s3_path="/bucket/voice.wav",
            owner_id=user.id
        )
        db_session.add(voice_clone)
        db_session.commit()
        db_session.refresh(voice_clone)
        
        job = PresentationJob(
            s3_pptx_path="/bucket/presentation.pptx",
            owner_id=user.id,
            voice_clone_id=voice_clone.id
        )
        db_session.add(job)
        db_session.commit()
        
        # Update status
        job.status = "processing"
        job.s3_video_path = "/bucket/output.mp4"
        db_session.commit()
        db_session.refresh(job)
        
        assert job.status == "processing"
        assert job.s3_video_path == "/bucket/output.mp4"
        # updated_at should be automatically updated (in real PostgreSQL)
        assert isinstance(job.updated_at, datetime.datetime)