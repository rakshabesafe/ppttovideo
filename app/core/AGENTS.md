# Core Module Agents

## Overview
The Core module contains foundational components that support the entire application. This includes configuration management, constants, utilities, and cross-cutting concerns that are used throughout the system.

## Module Components

### Configuration Management (`config.py`)
- **Agent Type**: Settings and Environment Manager
- **Purpose**: Centralize application configuration and environment variable handling
- **Framework**: Pydantic Settings for validation and type safety

#### Current Implementation Analysis
```python
# Current minimal configuration
# Likely contains basic settings like database URLs, API keys, etc.
```

#### Recommended Enhanced Configuration
```python
from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import Optional, List
import os
from pathlib import Path

class DatabaseSettings(BaseSettings):
    """Database configuration settings"""
    host: str = Field(default="postgres", env="POSTGRES_HOST")
    port: int = Field(default=5432, env="POSTGRES_PORT")
    user: str = Field(env="POSTGRES_USER")
    password: str = Field(env="POSTGRES_PASSWORD")
    database: str = Field(env="POSTGRES_DB")
    
    # Advanced settings
    pool_size: int = Field(default=10, env="DB_POOL_SIZE")
    max_overflow: int = Field(default=20, env="DB_MAX_OVERFLOW")
    pool_timeout: int = Field(default=30, env="DB_POOL_TIMEOUT")
    pool_recycle: int = Field(default=3600, env="DB_POOL_RECYCLE")
    echo: bool = Field(default=False, env="DB_ECHO")
    
    @property
    def url(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
    
    @property
    def async_url(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

class MinIOSettings(BaseSettings):
    """MinIO/S3 storage configuration"""
    url: str = Field(default="minio:9000", env="MINIO_URL")
    access_key: str = Field(env="MINIO_ACCESS_KEY")
    secret_key: str = Field(env="MINIO_SECRET_KEY")
    secure: bool = Field(default=False, env="MINIO_SECURE")
    
    # Bucket configuration
    ingest_bucket: str = Field(default="ingest", env="MINIO_INGEST_BUCKET")
    presentations_bucket: str = Field(default="presentations", env="MINIO_PRESENTATIONS_BUCKET")
    voice_clones_bucket: str = Field(default="voice-clones", env="MINIO_VOICE_CLONES_BUCKET")
    output_bucket: str = Field(default="output", env="MINIO_OUTPUT_BUCKET")
    
    @validator('url')
    def validate_url(cls, v):
        if not v or ':' not in v:
            raise ValueError('MinIO URL must include port (e.g., localhost:9000)')
        return v

class CelerySettings(BaseSettings):
    """Celery task queue configuration"""
    broker_url: str = Field(default="redis://redis:6379/0", env="CELERY_BROKER_URL")
    result_backend: str = Field(default="redis://redis:6379/0", env="CELERY_RESULT_BACKEND")
    task_serializer: str = Field(default="json")
    accept_content: List[str] = Field(default=["json"])
    result_serializer: str = Field(default="json")
    timezone: str = Field(default="UTC")
    enable_utc: bool = Field(default=True)
    
    # Worker configuration
    worker_concurrency: int = Field(default=4, env="CELERY_WORKER_CONCURRENCY")
    worker_prefetch_multiplier: int = Field(default=1, env="CELERY_WORKER_PREFETCH_MULTIPLIER")
    task_acks_late: bool = Field(default=True)
    worker_disable_rate_limits: bool = Field(default=False)

class AISettings(BaseSettings):
    """AI/ML model configuration"""
    models_path: Path = Field(default=Path("/app/models"), env="AI_MODELS_PATH")
    openvoice_checkpoint_path: Path = Field(default=Path("/app/checkpoints_v2"), env="OPENVOICE_CHECKPOINT_PATH")
    
    # GPU configuration
    device: str = Field(default="auto", env="AI_DEVICE")  # auto, cpu, cuda:0, etc.
    gpu_memory_fraction: float = Field(default=0.8, env="GPU_MEMORY_FRACTION")
    
    # Audio processing
    sample_rate: int = Field(default=24000, env="AUDIO_SAMPLE_RATE")
    audio_format: str = Field(default="wav", env="AUDIO_FORMAT")
    max_audio_duration: int = Field(default=300, env="MAX_AUDIO_DURATION_SECONDS")  # 5 minutes
    
    @validator('device')
    def validate_device(cls, v):
        if v not in ['auto', 'cpu'] and not v.startswith('cuda:'):
            raise ValueError('Device must be "auto", "cpu", or "cuda:N"')
        return v

class SecuritySettings(BaseSettings):
    """Security and authentication settings"""
    secret_key: str = Field(env="SECRET_KEY")
    algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    
    # File upload limits
    max_file_size: int = Field(default=100 * 1024 * 1024, env="MAX_FILE_SIZE")  # 100MB
    allowed_voice_formats: List[str] = Field(default=["wav", "mp3"], env="ALLOWED_VOICE_FORMATS")
    allowed_presentation_formats: List[str] = Field(default=["pptx"], env="ALLOWED_PRESENTATION_FORMATS")
    
    # CORS configuration
    cors_origins: List[str] = Field(default=["*"], env="CORS_ORIGINS")
    cors_allow_credentials: bool = Field(default=True, env="CORS_ALLOW_CREDENTIALS")

class LibreOfficeSettings(BaseSettings):
    """LibreOffice service configuration"""
    url: str = Field(default="http://libreoffice:8100", env="LIBREOFFICE_URL")
    timeout: int = Field(default=300, env="LIBREOFFICE_TIMEOUT")  # 5 minutes
    retry_attempts: int = Field(default=3, env="LIBREOFFICE_RETRY_ATTEMPTS")
    retry_delay: int = Field(default=5, env="LIBREOFFICE_RETRY_DELAY")

class MonitoringSettings(BaseSettings):
    """Monitoring and observability configuration"""
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(default="json", env="LOG_FORMAT")  # json or text
    
    # Metrics
    enable_metrics: bool = Field(default=True, env="ENABLE_METRICS")
    metrics_port: int = Field(default=9090, env="METRICS_PORT")
    
    # Health checks
    health_check_interval: int = Field(default=30, env="HEALTH_CHECK_INTERVAL")
    
    @validator('log_level')
    def validate_log_level(cls, v):
        allowed_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in allowed_levels:
            raise ValueError(f'Log level must be one of: {allowed_levels}')
        return v.upper()

class AppSettings(BaseSettings):
    """Main application settings"""
    # Application metadata
    app_name: str = Field(default="Presentation Video Generator", env="APP_NAME")
    version: str = Field(default="1.0.0", env="APP_VERSION")
    environment: str = Field(default="development", env="ENVIRONMENT")
    debug: bool = Field(default=False, env="DEBUG")
    
    # Server configuration
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    workers: int = Field(default=1, env="WORKERS")
    
    # Component settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    minio: MinIOSettings = Field(default_factory=MinIOSettings)
    celery: CelerySettings = Field(default_factory=CelerySettings)
    ai: AISettings = Field(default_factory=AISettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    libreoffice: LibreOfficeSettings = Field(default_factory=LibreOfficeSettings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    @validator('environment')
    def validate_environment(cls, v):
        allowed_envs = ['development', 'testing', 'staging', 'production']
        if v not in allowed_envs:
            raise ValueError(f'Environment must be one of: {allowed_envs}')
        return v
    
    def is_production(self) -> bool:
        return self.environment == "production"
    
    def is_development(self) -> bool:
        return self.environment == "development"
    
    def is_testing(self) -> bool:
        return self.environment == "testing"

# Global settings instance
settings = AppSettings()

# Environment-specific configurations
class DevelopmentSettings(AppSettings):
    debug: bool = True
    database: DatabaseSettings = Field(default_factory=lambda: DatabaseSettings(echo=True))
    monitoring: MonitoringSettings = Field(default_factory=lambda: MonitoringSettings(log_level="DEBUG"))

class TestingSettings(AppSettings):
    environment: str = "testing"
    database: DatabaseSettings = Field(default_factory=lambda: DatabaseSettings(
        host="localhost",
        database="test_db"
    ))
    minio: MinIOSettings = Field(default_factory=lambda: MinIOSettings(
        url="localhost:9000",
        access_key="test",
        secret_key="test"
    ))

class ProductionSettings(AppSettings):
    debug: bool = False
    environment: str = "production"
    security: SecuritySettings = Field(default_factory=lambda: SecuritySettings(
        cors_origins=["https://yourdomain.com"]
    ))
    monitoring: MonitoringSettings = Field(default_factory=lambda: MonitoringSettings(
        log_level="INFO"
    ))

# Factory function for different environments
def get_settings(environment: Optional[str] = None) -> AppSettings:
    env = environment or os.getenv("ENVIRONMENT", "development")
    
    if env == "testing":
        return TestingSettings()
    elif env == "production":
        return ProductionSettings()
    elif env == "development":
        return DevelopmentSettings()
    else:
        return AppSettings()
```

## Utility Modules (Recommended Additions)

### Logging Configuration (`logging_config.py`)
```python
import logging
import sys
from datetime import datetime
from typing import Dict, Any
import json
from pythonjsonlogger import jsonlogger

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional context"""
    
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]):
        super().add_fields(log_record, record, message_dict)
        
        # Add timestamp
        log_record['timestamp'] = datetime.utcnow().isoformat()
        
        # Add application context
        log_record['service'] = 'presentation-generator'
        log_record['environment'] = settings.environment
        
        # Add request context if available
        if hasattr(record, 'request_id'):
            log_record['request_id'] = record.request_id
        
        if hasattr(record, 'user_id'):
            log_record['user_id'] = record.user_id

def setup_logging(settings: AppSettings) -> None:
    """Configure application logging"""
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.monitoring.log_level)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    
    if settings.monitoring.log_format == "json":
        formatter = CustomJsonFormatter(
            '%(levelname)s %(name)s %(message)s'
        )
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    
    # Configure specific loggers
    loggers_config = {
        'uvicorn': {'level': 'INFO'},
        'sqlalchemy.engine': {'level': 'WARNING'},
        'celery': {'level': 'INFO'},
        'app': {'level': settings.monitoring.log_level}
    }
    
    for logger_name, config in loggers_config.items():
        logger = logging.getLogger(logger_name)
        logger.setLevel(config['level'])

# Context manager for request logging
import contextvars
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar('request_id')
user_id_var: contextvars.ContextVar[int] = contextvars.ContextVar('user_id')

class ContextualLogger:
    def __init__(self, logger: logging.Logger):
        self.logger = logger
    
    def _add_context(self, extra: Dict[str, Any]) -> Dict[str, Any]:
        """Add contextual information to log record"""
        context = extra or {}
        
        try:
            context['request_id'] = request_id_var.get()
        except LookupError:
            pass
        
        try:
            context['user_id'] = user_id_var.get()
        except LookupError:
            pass
        
        return context
    
    def info(self, message: str, **kwargs):
        extra = self._add_context(kwargs.get('extra', {}))
        self.logger.info(message, extra=extra)
    
    def error(self, message: str, **kwargs):
        extra = self._add_context(kwargs.get('extra', {}))
        self.logger.error(message, extra=extra)
    
    def warning(self, message: str, **kwargs):
        extra = self._add_context(kwargs.get('extra', {}))
        self.logger.warning(message, extra=extra)

def get_logger(name: str) -> ContextualLogger:
    """Get a contextual logger instance"""
    return ContextualLogger(logging.getLogger(name))
```

### Exception Handling (`exceptions.py`)
```python
from typing import Optional, Dict, Any

class PresentationGeneratorException(Exception):
    """Base exception for the application"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

class ConfigurationError(PresentationGeneratorException):
    """Configuration-related errors"""
    pass

class ValidationError(PresentationGeneratorException):
    """Input validation errors"""
    pass

class StorageError(PresentationGeneratorException):
    """File storage operations errors"""
    pass

class ProcessingError(PresentationGeneratorException):
    """Presentation processing errors"""
    pass

class ConversionError(ProcessingError):
    """Document conversion errors"""
    pass

class SynthesisError(ProcessingError):
    """Voice synthesis errors"""
    pass

class VideoGenerationError(ProcessingError):
    """Video generation errors"""
    pass

class ExternalServiceError(PresentationGeneratorException):
    """External service communication errors"""
    pass

# Error handlers for different contexts
class ErrorHandler:
    """Centralized error handling logic"""
    
    def __init__(self, logger):
        self.logger = logger
    
    def handle_storage_error(self, error: Exception, context: Dict[str, Any]) -> StorageError:
        """Handle and standardize storage errors"""
        self.logger.error(f"Storage operation failed: {str(error)}", extra=context)
        return StorageError(
            message="File storage operation failed",
            details={"original_error": str(error), **context}
        )
    
    def handle_processing_error(self, error: Exception, job_id: int, stage: str) -> ProcessingError:
        """Handle and standardize processing errors"""
        context = {"job_id": job_id, "stage": stage}
        self.logger.error(f"Processing failed at {stage}: {str(error)}", extra=context)
        return ProcessingError(
            message=f"Processing failed during {stage}",
            details={"original_error": str(error), **context}
        )
```

### Constants and Enums (`constants.py`)
```python
from enum import Enum

class JobStatus(str, Enum):
    """Presentation job status constants"""
    PENDING = "pending"
    PROCESSING_SLIDES = "processing_slides"
    SYNTHESIZING_AUDIO = "synthesizing_audio"
    ASSEMBLING_VIDEO = "assembling_video"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class FileType(str, Enum):
    """Supported file types"""
    PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    WAV = "audio/wav"
    MP3 = "audio/mpeg"
    MP4 = "video/mp4"

class BucketName(str, Enum):
    """MinIO bucket names"""
    INGEST = "ingest"
    PRESENTATIONS = "presentations"
    VOICE_CLONES = "voice-clones"
    OUTPUT = "output"

# Application constants
DEFAULT_VIDEO_FPS = 24
DEFAULT_AUDIO_SAMPLE_RATE = 24000
MAX_SLIDES_PER_PRESENTATION = 100
MAX_AUDIO_DURATION_SECONDS = 300  # 5 minutes
DEFAULT_SILENCE_DURATION_SECONDS = 1

# File size limits (in bytes)
MAX_PRESENTATION_FILE_SIZE = 100 * 1024 * 1024  # 100MB
MAX_VOICE_CLONE_FILE_SIZE = 50 * 1024 * 1024    # 50MB

# Task timeout constants (in seconds)
PRESENTATION_PROCESSING_TIMEOUT = 1800  # 30 minutes
AUDIO_SYNTHESIS_TIMEOUT = 600          # 10 minutes
VIDEO_ASSEMBLY_TIMEOUT = 1200          # 20 minutes

# API rate limits
API_RATE_LIMIT_PER_MINUTE = 60
FILE_UPLOAD_RATE_LIMIT_PER_HOUR = 10
```

### Health Checks (`health.py`)
```python
import asyncio
from typing import Dict, Any, List
import httpx
from sqlalchemy import text
from app.db.session import engine
from app.services.minio_service import minio_service

class HealthChecker:
    """Centralized health checking for all system components"""
    
    def __init__(self, settings):
        self.settings = settings
    
    async def check_database(self) -> Dict[str, Any]:
        """Check database connectivity and basic functionality"""
        try:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1")).fetchone()
                return {
                    "status": "healthy",
                    "response_time_ms": 0,  # Could be measured
                    "details": {"connection": "ok", "query_result": result[0] if result else None}
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "details": {"connection": "failed"}
            }
    
    async def check_minio(self) -> Dict[str, Any]:
        """Check MinIO connectivity"""
        try:
            # List buckets to verify connectivity
            buckets = minio_service.client.list_buckets()
            return {
                "status": "healthy",
                "details": {
                    "connection": "ok",
                    "buckets_count": len(buckets)
                }
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "details": {"connection": "failed"}
            }
    
    async def check_redis(self) -> Dict[str, Any]:
        """Check Redis connectivity"""
        try:
            import redis
            r = redis.from_url(self.settings.celery.broker_url)
            r.ping()
            return {
                "status": "healthy",
                "details": {"connection": "ok"}
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "details": {"connection": "failed"}
            }
    
    async def check_libreoffice(self) -> Dict[str, Any]:
        """Check LibreOffice service availability"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.settings.libreoffice.url}/health")
                if response.status_code == 200:
                    return {
                        "status": "healthy",
                        "details": {"connection": "ok", "status_code": response.status_code}
                    }
                else:
                    return {
                        "status": "unhealthy",
                        "details": {"connection": "failed", "status_code": response.status_code}
                    }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "details": {"connection": "failed"}
            }
    
    async def get_system_health(self) -> Dict[str, Any]:
        """Get comprehensive system health status"""
        checks = [
            ("database", self.check_database()),
            ("minio", self.check_minio()),
            ("redis", self.check_redis()),
            ("libreoffice", self.check_libreoffice())
        ]
        
        results = {}
        overall_healthy = True
        
        for name, check_coro in checks:
            result = await check_coro
            results[name] = result
            if result["status"] != "healthy":
                overall_healthy = False
        
        return {
            "status": "healthy" if overall_healthy else "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "services": results
        }

health_checker = HealthChecker(settings)
```

## Testing Strategy for Core Module

### Configuration Testing
```python
def test_settings_validation():
    """Test that settings validation works correctly"""
    # Test valid settings
    valid_settings = AppSettings(
        database__host="localhost",
        database__user="test",
        database__password="test",
        database__database="test",
        minio__access_key="test",
        minio__secret_key="test",
        security__secret_key="test-secret"
    )
    assert valid_settings.database.host == "localhost"
    
    # Test invalid settings
    with pytest.raises(ValidationError):
        AppSettings(
            database__host="localhost",
            # Missing required fields
        )

def test_environment_specific_settings():
    """Test that environment-specific settings work"""
    test_settings = get_settings("testing")
    assert test_settings.environment == "testing"
    assert test_settings.database.database == "test_db"
    
    prod_settings = get_settings("production")
    assert prod_settings.environment == "production"
    assert not prod_settings.debug
```

### Logging Testing
```python
def test_contextual_logging(caplog):
    """Test contextual logging functionality"""
    logger = get_logger("test")
    
    # Set context
    request_id_var.set("test-request-123")
    user_id_var.set(42)
    
    logger.info("Test message")
    
    # Verify context was included
    assert "test-request-123" in caplog.text
    assert "42" in caplog.text

def test_json_logging_format():
    """Test JSON logging format"""
    settings = AppSettings()
    settings.monitoring.log_format = "json"
    
    setup_logging(settings)
    
    logger = logging.getLogger("test")
    with caplog.at_level(logging.INFO):
        logger.info("Test message")
    
    # Verify JSON format
    log_record = json.loads(caplog.records[0].getMessage())
    assert log_record["service"] == "presentation-generator"
```

### Exception Handling Testing
```python
def test_exception_hierarchy():
    """Test custom exception hierarchy"""
    base_error = PresentationGeneratorException("Base error")
    assert isinstance(base_error, Exception)
    
    storage_error = StorageError("Storage failed", {"bucket": "test"})
    assert isinstance(storage_error, PresentationGeneratorException)
    assert storage_error.details["bucket"] == "test"

def test_error_handler():
    """Test centralized error handling"""
    logger = Mock()
    handler = ErrorHandler(logger)
    
    original_error = Exception("Original error")
    handled_error = handler.handle_storage_error(original_error, {"context": "test"})
    
    assert isinstance(handled_error, StorageError)
    assert "Original error" in str(handled_error.details["original_error"])
    logger.error.assert_called_once()
```

### Health Check Testing
```python
@pytest.mark.asyncio
async def test_database_health_check():
    """Test database health check"""
    checker = HealthChecker(settings)
    
    result = await checker.check_database()
    
    assert result["status"] in ["healthy", "unhealthy"]
    assert "details" in result

@pytest.mark.asyncio
async def test_system_health_comprehensive():
    """Test comprehensive system health check"""
    checker = HealthChecker(settings)
    
    with patch.object(checker, 'check_database', return_value={"status": "healthy"}):
        with patch.object(checker, 'check_minio', return_value={"status": "healthy"}):
            result = await checker.get_system_health()
            
            assert result["status"] == "healthy"
            assert "services" in result
            assert len(result["services"]) >= 2
```

## Integration with Application

### Dependency Injection Integration
```python
# In main FastAPI application
from fastapi import Depends
from app.core.config import get_settings, AppSettings

def get_settings_dependency() -> AppSettings:
    return get_settings()

# Use in endpoints
@app.get("/health")
async def health_check(settings: AppSettings = Depends(get_settings_dependency)):
    checker = HealthChecker(settings)
    return await checker.get_system_health()
```

### Configuration Management Best Practices
1. **Environment Parity**: Same configuration structure across all environments
2. **Security**: Sensitive values in environment variables, not in code
3. **Validation**: Comprehensive validation of all configuration values
4. **Documentation**: Clear documentation of all configuration options
5. **Testing**: Test configuration in different environments

## Performance and Security Considerations

### Performance
- Lazy loading of expensive configuration values
- Caching of computed configuration properties
- Minimal overhead for logging and exception handling

### Security
- Secrets never logged or exposed in error messages
- Configuration validation prevents misconfiguration vulnerabilities
- Structured logging prevents log injection attacks

This comprehensive core module provides a solid foundation for the entire application with proper configuration management, logging, error handling, and monitoring capabilities.