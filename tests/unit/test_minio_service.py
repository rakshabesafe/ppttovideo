import pytest
import io
from unittest.mock import Mock, patch, MagicMock
from app.services.minio_service import MinioService


class TestMinioService:
    @pytest.fixture
    def mock_minio_client(self):
        """Mock Minio client"""
        with patch('app.services.minio_service.Minio') as mock_minio:
            client = Mock()
            mock_minio.return_value = client
            yield client
    
    @pytest.fixture
    def minio_service(self, mock_minio_client):
        """Create MinioService instance with mocked client"""
        with patch('app.core.config.settings') as mock_settings:
            mock_settings.MINIO_URL = "localhost:9000"
            mock_settings.MINIO_ACCESS_KEY = "minioadmin"
            mock_settings.MINIO_SECRET_KEY = "minioadmin"
            
            service = MinioService()
            return service
    
    def test_minio_service_initialization(self, mock_minio_client):
        """Test MinioService initialization"""
        with patch('app.core.config.settings') as mock_settings:
            mock_settings.MINIO_URL = "localhost:9000"
            mock_settings.MINIO_ACCESS_KEY = "test_access"
            mock_settings.MINIO_SECRET_KEY = "test_secret"
            
            service = MinioService()
            
            # Verify Minio client was initialized with correct parameters
            from app.services.minio_service import Minio
            Minio.assert_called_once_with(
                "localhost:9000",
                access_key="test_access",
                secret_key="test_secret",
                secure=False
            )
    
    def test_upload_file_success(self, minio_service, mock_minio_client):
        """Test successful file upload"""
        # Setup test data
        bucket_name = "test-bucket"
        object_name = "test-file.txt"
        test_data = b"test file content"
        data_stream = io.BytesIO(test_data)
        
        # Mock successful upload
        mock_minio_client.put_object.return_value = None
        
        # Execute upload
        result = minio_service.upload_file(bucket_name, object_name, data_stream, len(test_data))
        
        # Verify client was called correctly
        mock_minio_client.put_object.assert_called_once_with(
            bucket_name,
            object_name,
            data_stream,
            length=len(test_data)
        )
        
        # Verify return value
        expected_path = f"/{bucket_name}/{object_name}"
        assert result == expected_path
    
    def test_upload_file_with_different_parameters(self, minio_service, mock_minio_client):
        """Test file upload with different parameters"""
        bucket_name = "presentations"
        object_name = "folder/subfolder/presentation.pptx"
        test_data = b"presentation data"
        data_stream = io.BytesIO(test_data)
        
        mock_minio_client.put_object.return_value = None
        
        result = minio_service.upload_file(bucket_name, object_name, data_stream, len(test_data))
        
        mock_minio_client.put_object.assert_called_once_with(
            bucket_name,
            object_name,
            data_stream,
            length=len(test_data)
        )
        
        assert result == f"/{bucket_name}/{object_name}"
    
    def test_upload_file_client_exception(self, minio_service, mock_minio_client):
        """Test file upload when client raises exception"""
        from minio.error import S3Error
        
        bucket_name = "test-bucket"
        object_name = "test-file.txt"
        test_data = b"test file content"
        data_stream = io.BytesIO(test_data)
        
        # Mock client to raise exception
        mock_minio_client.put_object.side_effect = S3Error(
            "BucketNotFound",
            "The specified bucket does not exist",
            resource="test-bucket",
            request_id="123",
            host_id="456"
        )
        
        # Verify exception is propagated
        with pytest.raises(S3Error):
            minio_service.upload_file(bucket_name, object_name, data_stream, len(test_data))
    
    def test_singleton_behavior(self):
        """Test that minio_service is a singleton-like instance"""
        from app.services.minio_service import minio_service
        
        # The module-level minio_service should be an instance
        assert isinstance(minio_service, MinioService)
        
        # Verify it has the expected client attribute
        assert hasattr(minio_service, 'client')
    
    def test_upload_file_empty_content(self, minio_service, mock_minio_client):
        """Test uploading empty file"""
        bucket_name = "test-bucket"
        object_name = "empty-file.txt"
        data_stream = io.BytesIO(b"")
        
        mock_minio_client.put_object.return_value = None
        
        result = minio_service.upload_file(bucket_name, object_name, data_stream, 0)
        
        mock_minio_client.put_object.assert_called_once_with(
            bucket_name,
            object_name,
            data_stream,
            length=0
        )
        
        assert result == f"/{bucket_name}/{object_name}"
    
    def test_upload_file_large_content(self, minio_service, mock_minio_client):
        """Test uploading large file"""
        bucket_name = "test-bucket"
        object_name = "large-file.dat"
        large_data = b"x" * (10 * 1024 * 1024)  # 10MB
        data_stream = io.BytesIO(large_data)
        
        mock_minio_client.put_object.return_value = None
        
        result = minio_service.upload_file(bucket_name, object_name, data_stream, len(large_data))
        
        mock_minio_client.put_object.assert_called_once_with(
            bucket_name,
            object_name,
            data_stream,
            length=len(large_data)
        )
        
        assert result == f"/{bucket_name}/{object_name}"


class TestMinioServiceIntegration:
    """Integration-style tests that test the actual module imports"""
    
    def test_minio_service_module_import(self):
        """Test that minio_service can be imported"""
        from app.services.minio_service import minio_service, MinioService
        
        assert minio_service is not None
        assert isinstance(minio_service, MinioService)
    
    def test_minio_service_methods_exist(self):
        """Test that minio_service has expected methods"""
        from app.services.minio_service import minio_service
        
        assert hasattr(minio_service, 'upload_file')
        assert hasattr(minio_service, 'client')
        assert callable(minio_service.upload_file)