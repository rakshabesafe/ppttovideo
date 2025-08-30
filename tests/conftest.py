import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import tempfile
import os

from app.db.session import Base
from app.main import app
from app.api.dependencies import get_db
from app.services.minio_service import MinioService


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session")
def test_db():
    """Create test database tables"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    # Clean up test.db file
    if os.path.exists("./test.db"):
        os.remove("./test.db")


@pytest.fixture
def db_session(test_db):
    """Create a fresh database session for each test"""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    """Create test client with database dependency override"""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def mock_minio():
    """Mock MinIO service"""
    with patch('app.services.minio_service.minio_service') as mock:
        mock_service = Mock(spec=MinioService)
        mock_service.upload_file.return_value = "/test-bucket/test-file.txt"
        mock_service.client.get_object.return_value = Mock(
            read=Mock(return_value=b"test data"),
            close=Mock(),
            release_conn=Mock()
        )
        mock_service.client.list_objects.return_value = []
        mock_service.client.fget_object = Mock()
        yield mock_service


@pytest.fixture
def mock_celery():
    """Mock Celery app"""
    with patch('app.workers.celery_app.app') as mock:
        mock.send_task = Mock()
        yield mock


@pytest.fixture
def temp_file():
    """Create temporary file for testing"""
    fd, path = tempfile.mkstemp()
    yield path
    os.close(fd)
    os.remove(path)


@pytest.fixture
def sample_user_data():
    """Sample user data for testing"""
    return {
        "name": "Test User",
        "email": "test@example.com"
    }


@pytest.fixture
def sample_voice_clone_data():
    """Sample voice clone data for testing"""
    return {
        "name": "Test Voice Clone",
        "owner_id": 1
    }


@pytest.fixture
def sample_presentation_job_data():
    """Sample presentation job data for testing"""
    return {
        "owner_id": 1,
        "voice_clone_id": 1
    }