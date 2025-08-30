import pytest
import json
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from flask import Flask
import io


class TestLibreOfficeConverter:
    """Test the LibreOffice converter Flask service"""
    
    @pytest.fixture
    def app(self):
        """Create test Flask app"""
        with patch.dict('os.environ', {
            'MINIO_URL': 'localhost:9000',
            'MINIO_ACCESS_KEY': 'test_access',
            'MINIO_SECRET_KEY': 'test_secret'
        }):
            # Import after setting environment variables
            from app.services.libreoffice_converter import app as flask_app
            flask_app.config['TESTING'] = True
            return flask_app
    
    @pytest.fixture
    def client(self, app):
        """Create test client"""
        return app.test_client()
    
    @pytest.fixture
    def mock_minio_client(self):
        """Mock MinIO client"""
        with patch('app.services.libreoffice_converter.minio_client') as mock:
            yield mock
    
    @pytest.fixture
    def mock_subprocess(self):
        """Mock subprocess module"""
        with patch('app.services.libreoffice_converter.subprocess') as mock:
            mock.run.return_value = None
            yield mock
    
    @pytest.fixture
    def mock_temp_dir(self):
        """Mock temporary directory with file operations"""
        with patch('tempfile.TemporaryDirectory') as mock_temp:
            temp_dir = "/tmp/test_dir"
            mock_temp.return_value.__enter__.return_value = temp_dir
            mock_temp.return_value.__exit__.return_value = None
            
            with patch('os.path.exists') as mock_exists, \
                 patch('os.makedirs') as mock_makedirs, \
                 patch('os.listdir') as mock_listdir:
                
                # Mock file system operations
                mock_exists.return_value = True
                mock_listdir.return_value = ["slide-01.png", "slide-02.png", "slide-03.png"]
                
                yield {
                    'temp_dir': temp_dir,
                    'makedirs': mock_makedirs,
                    'listdir': mock_listdir,
                    'exists': mock_exists
                }
    
    def test_convert_success(self, client, mock_minio_client, mock_subprocess, mock_temp_dir):
        """Test successful conversion"""
        # Setup request data
        request_data = {
            "bucket_name": "ingest",
            "object_name": "test-presentation.pptx"
        }
        
        # Mock MinIO operations
        mock_minio_client.fget_object.return_value = None
        mock_minio_client.fput_object.return_value = None
        
        # Make request
        response = client.post('/convert', 
                             data=json.dumps(request_data),
                             content_type='application/json')
        
        # Verify response
        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert "image_paths" in response_data
        assert len(response_data["image_paths"]) == 3
        
        # Verify expected image paths
        expected_paths = [
            "/presentations/test-presentation/images/slide-01.png",
            "/presentations/test-presentation/images/slide-02.png", 
            "/presentations/test-presentation/images/slide-03.png"
        ]
        assert response_data["image_paths"] == expected_paths
        
        # Verify MinIO calls
        mock_minio_client.fget_object.assert_called_once()
        assert mock_minio_client.fput_object.call_count == 3
        
        # Verify subprocess calls
        assert mock_subprocess.run.call_count == 2  # PDF conversion + image conversion
    
    def test_convert_missing_bucket_name(self, client):
        """Test conversion with missing bucket_name"""
        request_data = {"object_name": "test.pptx"}
        
        response = client.post('/convert',
                             data=json.dumps(request_data),
                             content_type='application/json')
        
        assert response.status_code == 400
        response_data = json.loads(response.data)
        assert "error" in response_data
        assert "Missing bucket_name or object_name" in response_data["error"]
    
    def test_convert_missing_object_name(self, client):
        """Test conversion with missing object_name"""
        request_data = {"bucket_name": "ingest"}
        
        response = client.post('/convert',
                             data=json.dumps(request_data),
                             content_type='application/json')
        
        assert response.status_code == 400
        response_data = json.loads(response.data)
        assert "error" in response_data
        assert "Missing bucket_name or object_name" in response_data["error"]
    
    def test_convert_invalid_json(self, client):
        """Test conversion with invalid JSON"""
        response = client.post('/convert',
                             data="invalid json",
                             content_type='application/json')
        
        assert response.status_code == 400
    
    def test_convert_no_json(self, client):
        """Test conversion with no JSON data"""
        response = client.post('/convert')
        
        assert response.status_code == 400
        response_data = json.loads(response.data)
        assert "error" in response_data
    
    def test_convert_minio_error(self, client, mock_minio_client, mock_temp_dir):
        """Test conversion with MinIO error"""
        from minio.error import S3Error
        
        request_data = {
            "bucket_name": "ingest",
            "object_name": "test-presentation.pptx"
        }
        
        # Mock MinIO to raise error
        mock_minio_client.fget_object.side_effect = S3Error(
            "NoSuchBucket",
            "The specified bucket does not exist",
            resource="ingest",
            request_id="123",
            host_id="456"
        )
        
        response = client.post('/convert',
                             data=json.dumps(request_data),
                             content_type='application/json')
        
        assert response.status_code == 500
        response_data = json.loads(response.data)
        assert "error" in response_data
        assert "MinIO error" in response_data["error"]
    
    def test_convert_subprocess_error(self, client, mock_minio_client, mock_subprocess, mock_temp_dir):
        """Test conversion with subprocess error"""
        import subprocess
        
        request_data = {
            "bucket_name": "ingest", 
            "object_name": "test-presentation.pptx"
        }
        
        # Mock subprocess to raise error
        mock_subprocess.run.side_effect = subprocess.CalledProcessError(1, "libreoffice")
        
        response = client.post('/convert',
                             data=json.dumps(request_data),
                             content_type='application/json')
        
        assert response.status_code == 500
        response_data = json.loads(response.data)
        assert "error" in response_data
        assert "Conversion command failed" in response_data["error"]
    
    def test_convert_pdf_not_created(self, client, mock_minio_client, mock_subprocess, mock_temp_dir):
        """Test conversion when PDF creation fails"""
        request_data = {
            "bucket_name": "ingest",
            "object_name": "test-presentation.pptx"
        }
        
        # Mock that PDF file doesn't exist after conversion
        mock_temp_dir['exists'].return_value = False
        
        response = client.post('/convert',
                             data=json.dumps(request_data),
                             content_type='application/json')
        
        assert response.status_code == 500
        response_data = json.loads(response.data)
        assert "error" in response_data
        assert "PDF conversion failed" in response_data["error"]
    
    def test_convert_no_images_generated(self, client, mock_minio_client, mock_subprocess, mock_temp_dir):
        """Test conversion when no images are generated"""
        request_data = {
            "bucket_name": "ingest",
            "object_name": "test-presentation.pptx"
        }
        
        # Mock empty image directory
        mock_temp_dir['listdir'].return_value = []
        
        response = client.post('/convert',
                             data=json.dumps(request_data),
                             content_type='application/json')
        
        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert "image_paths" in response_data
        assert len(response_data["image_paths"]) == 0
    
    def test_convert_mixed_files_in_directory(self, client, mock_minio_client, mock_subprocess, mock_temp_dir):
        """Test conversion with mixed file types in image directory"""
        request_data = {
            "bucket_name": "ingest",
            "object_name": "test-presentation.pptx"
        }
        
        # Mock directory with mixed file types
        mock_temp_dir['listdir'].return_value = [
            "slide-01.png", 
            "slide-02.png", 
            "readme.txt",  # Should be ignored
            "slide-03.png",
            "temp.pdf"     # Should be ignored
        ]
        
        response = client.post('/convert',
                             data=json.dumps(request_data),
                             content_type='application/json')
        
        assert response.status_code == 200
        response_data = json.loads(response.data)
        assert "image_paths" in response_data
        assert len(response_data["image_paths"]) == 3  # Only PNG files
        
        # Verify only PNG files are processed
        for path in response_data["image_paths"]:
            assert path.endswith(".png")
    
    def test_job_id_extraction(self, client, mock_minio_client, mock_subprocess, mock_temp_dir):
        """Test that job ID is correctly extracted from object name"""
        request_data = {
            "bucket_name": "ingest",
            "object_name": "folder/subfolder/my-presentation.pptx"
        }
        
        response = client.post('/convert',
                             data=json.dumps(request_data),
                             content_type='application/json')
        
        assert response.status_code == 200
        response_data = json.loads(response.data)
        
        # Verify job ID is extracted correctly (should be "my-presentation")
        for path in response_data["image_paths"]:
            assert "/presentations/my-presentation/images/" in path


class TestLibreOfficeConverterConfiguration:
    """Test configuration aspects of the LibreOffice converter"""
    
    def test_environment_variable_defaults(self):
        """Test default environment variable values"""
        with patch.dict('os.environ', {}, clear=True):
            # Clear all environment variables
            from app.services import libreoffice_converter
            
            # Reload the module to test defaults
            import importlib
            importlib.reload(libreoffice_converter)
            
            assert libreoffice_converter.MINIO_URL == "minio:9000"
            assert libreoffice_converter.MINIO_ACCESS_KEY == "minioadmin"
            assert libreoffice_converter.MINIO_SECRET_KEY == "minioadmin"
    
    def test_environment_variable_override(self):
        """Test environment variable override"""
        test_env = {
            'MINIO_URL': 'custom:9000',
            'MINIO_ACCESS_KEY': 'custom_access',
            'MINIO_SECRET_KEY': 'custom_secret'
        }
        
        with patch.dict('os.environ', test_env, clear=True):
            from app.services import libreoffice_converter
            import importlib
            importlib.reload(libreoffice_converter)
            
            assert libreoffice_converter.MINIO_URL == "custom:9000"
            assert libreoffice_converter.MINIO_ACCESS_KEY == "custom_access"
            assert libreoffice_converter.MINIO_SECRET_KEY == "custom_secret"