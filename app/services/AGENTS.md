# Services Module Agents

## Overview
The Services module provides abstraction layers for external service integrations. These services handle file storage, document conversion, and other infrastructure operations that support the main application workflow.

## Service Agents

### MinIO Service (`minio_service.py`)
- **Agent Type**: Object Storage Abstraction
- **Purpose**: Provide S3-compatible object storage operations
- **External Service**: MinIO (S3-compatible storage)

#### Responsibilities
- File upload operations to various buckets
- Connection management with MinIO server
- Path generation for stored objects
- Error handling for storage operations

#### Current Implementation
```python
class MinioService:
    def __init__(self):
        # Hardcoded configuration from settings
        self.client = Minio(...)
    
    def upload_file(self, bucket_name, object_name, data, length):
        # Single operation exposed
```

#### Architecture Issues
1. **Singleton Pattern**: Module-level instance makes testing difficult
2. **Limited Interface**: Only exposes upload functionality
3. **No Error Abstraction**: Raw MinIO exceptions propagate
4. **Configuration Coupling**: Direct dependency on settings module

#### Testing Challenges
- Mocking requires patching at import time
- Configuration cannot be injected for tests
- No interface for easy substitution
- Complex setup for integration tests

#### Refactoring Recommendations
```python
# Improved architecture for testability
class MinioService:
    def __init__(self, client: Minio):
        self.client = client
    
    @classmethod
    def from_config(cls, url: str, access_key: str, secret_key: str) -> 'MinioService':
        client = Minio(url, access_key=access_key, secret_key=secret_key, secure=False)
        return cls(client)
    
    def upload_file(self, bucket_name: str, object_name: str, data: BinaryIO, length: int) -> str:
        try:
            self.client.put_object(bucket_name, object_name, data, length=length)
            return f"/{bucket_name}/{object_name}"
        except S3Error as e:
            raise StorageError(f"Upload failed: {e}") from e
    
    def download_file(self, bucket_name: str, object_name: str) -> BinaryIO:
        # Additional operations for completeness
    
    def delete_file(self, bucket_name: str, object_name: str) -> bool:
        # Cleanup operations
    
    def list_objects(self, bucket_name: str, prefix: str = "") -> List[str]:
        # Object listing for cleanup/management

# Dependency injection factory
def get_minio_service() -> MinioService:
    return MinioService.from_config(
        url=settings.MINIO_URL,
        access_key=settings.MINIO_ACCESS_KEY, 
        secret_key=settings.MINIO_SECRET_KEY
    )
```

#### Enhanced Error Handling
```python
class StorageError(Exception):
    """Base exception for storage operations"""
    pass

class UploadError(StorageError):
    """Failed to upload file"""
    pass

class DownloadError(StorageError):
    """Failed to download file"""
    pass

class BucketError(StorageError):
    """Bucket operation failed"""
    pass
```

#### Testing Strategy
```python
# Unit tests with mocked client
def test_upload_file_success():
    mock_client = Mock()
    service = MinioService(mock_client)
    result = service.upload_file("bucket", "file.txt", BytesIO(b"data"), 4)
    assert result == "/bucket/file.txt"
    mock_client.put_object.assert_called_once()

# Integration tests with test MinIO instance
@pytest.fixture
def test_minio_service():
    return MinioService.from_config("localhost:9000", "test", "test")
```

### LibreOffice Converter (`libreoffice_converter.py`)
- **Agent Type**: Document Conversion Service + HTTP API
- **Purpose**: Convert PPTX presentations to image sequences
- **Technology**: Flask application with LibreOffice headless + pdftoppm

#### Current Architecture
```python
# Flask app with embedded business logic
app = Flask(__name__)

@app.route('/convert', methods=['POST'])
def convert():
    # All conversion logic embedded in route handler
    # Direct subprocess calls
    # Mixed HTTP handling with business logic
```

#### Responsibilities
1. **HTTP API**: Expose conversion endpoint
2. **File Management**: Download from MinIO, process locally, upload results
3. **Process Orchestration**: LibreOffice → PDF → Images pipeline
4. **Error Handling**: Convert processing errors to HTTP responses

#### Architecture Issues
1. **Mixed Concerns**: HTTP handling mixed with business logic
2. **Testability**: Difficult to unit test subprocess operations
3. **Error Handling**: Basic error responses, no structured error handling
4. **Resource Management**: No explicit cleanup of temporary files
5. **Configuration**: Hardcoded environment variable access

#### Testing Challenges
- Flask app testing requires full HTTP setup
- Subprocess mocking is complex and brittle
- File system operations are hard to isolate
- No separation between HTTP layer and business logic

#### Refactoring for Testability
```python
# Separate business logic from HTTP handling
class PresentationConverter:
    def __init__(self, minio_service: MinioService, 
                 temp_dir_factory: Callable[[], ContextManager[str]] = tempfile.TemporaryDirectory):
        self.minio = minio_service
        self.temp_dir_factory = temp_dir_factory
    
    def convert_to_images(self, bucket_name: str, object_name: str) -> List[str]:
        """Pure business logic - easily testable"""
        with self.temp_dir_factory() as temp_dir:
            return self._execute_conversion(bucket_name, object_name, temp_dir)
    
    def _execute_conversion(self, bucket_name: str, object_name: str, temp_dir: str) -> List[str]:
        # Download PPTX
        local_pptx = self._download_presentation(bucket_name, object_name, temp_dir)
        
        # Convert to PDF
        pdf_path = self._convert_to_pdf(local_pptx, temp_dir)
        
        # Convert to images
        image_paths = self._convert_to_images(pdf_path, temp_dir)
        
        # Upload images
        return self._upload_images(image_paths, object_name)
    
    def _download_presentation(self, bucket_name: str, object_name: str, temp_dir: str) -> str:
        """Isolated download operation"""
        local_path = os.path.join(temp_dir, os.path.basename(object_name))
        data = self.minio.download_file(bucket_name, object_name)
        with open(local_path, 'wb') as f:
            f.write(data.read())
        return local_path
    
    def _convert_to_pdf(self, pptx_path: str, temp_dir: str) -> str:
        """Isolated PDF conversion"""
        try:
            subprocess.run([
                "libreoffice", "--headless", "--convert-to", "pdf", 
                "--outdir", temp_dir, pptx_path
            ], check=True, capture_output=True, text=True)
            
            base_name = os.path.splitext(os.path.basename(pptx_path))[0]
            pdf_path = os.path.join(temp_dir, f"{base_name}.pdf")
            
            if not os.path.exists(pdf_path):
                raise ConversionError("PDF conversion failed - output file not created")
                
            return pdf_path
        except subprocess.CalledProcessError as e:
            raise ConversionError(f"LibreOffice conversion failed: {e.stderr}")
    
    def _convert_to_images(self, pdf_path: str, temp_dir: str) -> List[str]:
        """Isolated image conversion"""
        image_dir = os.path.join(temp_dir, "images")
        os.makedirs(image_dir)
        
        try:
            subprocess.run([
                "pdftoppm", pdf_path, os.path.join(image_dir, "slide"), "-png"
            ], check=True, capture_output=True, text=True)
            
            image_files = [f for f in os.listdir(image_dir) if f.endswith('.png')]
            if not image_files:
                raise ConversionError("Image conversion failed - no images generated")
            
            return [os.path.join(image_dir, f) for f in sorted(image_files)]
        except subprocess.CalledProcessError as e:
            raise ConversionError(f"Image conversion failed: {e.stderr}")
    
    def _upload_images(self, image_paths: List[str], original_name: str) -> List[str]:
        """Upload images to storage"""
        job_id = os.path.splitext(os.path.basename(original_name))[0]
        uploaded_paths = []
        
        for image_path in image_paths:
            image_name = os.path.basename(image_path)
            s3_object_name = f"{job_id}/images/{image_name}"
            
            with open(image_path, 'rb') as f:
                path = self.minio.upload_file("presentations", s3_object_name, f, 
                                            os.path.getsize(image_path))
                uploaded_paths.append(path)
        
        return uploaded_paths

# Simplified Flask app
converter = PresentationConverter(get_minio_service())

@app.route('/convert', methods=['POST'])
def convert():
    data = request.get_json()
    if not data or 'bucket_name' not in data or 'object_name' not in data:
        return jsonify({"error": "Missing required fields"}), 400
    
    try:
        image_paths = converter.convert_to_images(data['bucket_name'], data['object_name'])
        return jsonify({"image_paths": image_paths}), 200
    except ConversionError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500
```

#### Error Handling
```python
class ConversionError(Exception):
    """Base class for conversion errors"""
    pass

class LibreOfficeError(ConversionError):
    """LibreOffice processing failed"""
    pass

class ImageConversionError(ConversionError):
    """PDF to image conversion failed"""
    pass
```

#### Testing Strategy
```python
# Unit tests for business logic
def test_convert_to_images_success():
    mock_minio = Mock()
    mock_temp_dir = Mock()
    converter = PresentationConverter(mock_minio, lambda: mock_temp_dir)
    
    with patch('subprocess.run') as mock_subprocess:
        mock_subprocess.return_value = None  # Success
        result = converter.convert_to_images("bucket", "test.pptx")
        assert isinstance(result, list)

# Integration tests for Flask app
def test_convert_endpoint_success():
    with app.test_client() as client:
        with patch.object(converter, 'convert_to_images') as mock_convert:
            mock_convert.return_value = ["/path1.png", "/path2.png"]
            
            response = client.post('/convert', json={
                "bucket_name": "test", 
                "object_name": "test.pptx"
            })
            
            assert response.status_code == 200
            assert len(response.json["image_paths"]) == 2
```

## Missing Services (Opportunities for Extraction)

### Presentation Processing Service
- **Purpose**: Coordinate presentation workflow
- **Responsibilities**:
  - Job orchestration
  - Status tracking
  - Error handling coordination
  - Resource cleanup

### Voice Synthesis Service  
- **Purpose**: Abstract AI model operations
- **Responsibilities**:
  - Model loading and management
  - Audio processing pipeline
  - Voice clone parameter management
  - Quality validation

### Video Assembly Service
- **Purpose**: Handle video creation operations
- **Responsibilities**:
  - MoviePy abstraction
  - Video parameter configuration
  - Progress tracking
  - Format optimization

## Cross-Service Patterns

### Configuration Management
```python
@dataclass
class ServiceConfig:
    minio_url: str
    minio_access_key: str
    minio_secret_key: str
    libreoffice_url: str
    
    @classmethod
    def from_env(cls) -> 'ServiceConfig':
        return cls(
            minio_url=os.getenv('MINIO_URL', 'localhost:9000'),
            minio_access_key=os.getenv('MINIO_ACCESS_KEY', 'minioadmin'),
            minio_secret_key=os.getenv('MINIO_SECRET_KEY', 'minioadmin'),
            libreoffice_url=os.getenv('LIBREOFFICE_URL', 'http://libreoffice:8100')
        )
```

### Dependency Injection
```python
# Service registry for dependency injection
class ServiceRegistry:
    def __init__(self, config: ServiceConfig):
        self.config = config
        self._minio_service = None
        self._presentation_converter = None
    
    def get_minio_service(self) -> MinioService:
        if self._minio_service is None:
            self._minio_service = MinioService.from_config(
                self.config.minio_url,
                self.config.minio_access_key,
                self.config.minio_secret_key
            )
        return self._minio_service
    
    def get_presentation_converter(self) -> PresentationConverter:
        if self._presentation_converter is None:
            self._presentation_converter = PresentationConverter(
                self.get_minio_service()
            )
        return self._presentation_converter
```

### Testing Utilities
```python
# Test service factory
class TestServiceRegistry(ServiceRegistry):
    def __init__(self):
        config = ServiceConfig(
            minio_url="test-minio:9000",
            minio_access_key="test",
            minio_secret_key="test",
            libreoffice_url="http://test-libreoffice:8100"
        )
        super().__init__(config)
    
    def get_minio_service(self) -> MinioService:
        # Return mocked service for tests
        return Mock(spec=MinioService)
```

## Testing Strategy Summary

### Unit Tests
- **Focus**: Individual service methods with mocked dependencies
- **Coverage**: Business logic, error handling, edge cases
- **Speed**: Fast execution with minimal setup

### Integration Tests  
- **Focus**: Service interactions with real/containerized external services
- **Coverage**: Configuration, network operations, error scenarios
- **Environment**: Docker containers for MinIO, LibreOffice

### Contract Tests
- **Focus**: Service interface compliance
- **Coverage**: API contracts, response formats
- **Tools**: Schema validation, API testing frameworks

## Performance and Scalability

### Current Bottlenecks
1. **Synchronous Operations**: All file operations are blocking
2. **Memory Usage**: Large files loaded entirely into memory
3. **No Caching**: Repeated operations for same inputs
4. **Single Instance**: No load balancing or redundancy

### Optimization Opportunities
1. **Async Operations**: Convert to async/await pattern
2. **Streaming**: Handle large files with streaming I/O
3. **Caching Layer**: Cache frequently accessed files and results
4. **Connection Pooling**: Reuse connections to external services
5. **Batch Operations**: Process multiple files simultaneously