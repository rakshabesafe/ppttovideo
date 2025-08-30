# API Module Agents

## Overview
The API module handles HTTP requests and responses for the Presentation Video Generator application. It provides RESTful endpoints for user management, voice clone operations, and presentation processing.

## Architecture

### FastAPI Application (`main.py`)
- **Purpose**: Main application entry point and route registration
- **Responsibilities**:
  - Initialize FastAPI application
  - Register API routers
  - Serve HTML templates
  - Handle database table creation
- **Dependencies**: SQLAlchemy, Jinja2 templates
- **Testing Strategy**: Integration tests with TestClient

### Dependency Management (`dependencies.py`)
- **Purpose**: Provide dependency injection for database sessions
- **Responsibilities**:
  - Database session management
  - Connection lifecycle handling
  - Transaction management
- **Testing Strategy**: Mock database sessions for unit tests

## API Endpoints

### Users Endpoint (`endpoints/users.py`)
- **Agent Type**: CRUD Resource Handler
- **Responsibilities**:
  - User creation and retrieval
  - Input validation via Pydantic schemas
  - Database operations delegation to CRUD layer
- **Key Functions**:
  - `POST /api/users/` - Create new user
  - `GET /api/users/` - List users with pagination
  - `GET /api/users/{user_id}` - Get specific user
- **Testing Approach**:
  - Unit tests for request/response handling
  - Integration tests with real database
  - Error handling validation
- **Refactoring Opportunities**:
  - Extract business logic to service layer
  - Add comprehensive input validation
  - Implement proper error responses

### Voice Clones Endpoint (`endpoints/voice_clones.py`)
- **Agent Type**: File Upload Handler + CRUD Resource
- **Responsibilities**:
  - Handle WAV file uploads
  - Validate audio file formats
  - Coordinate with MinIO for file storage
  - Voice clone metadata management
- **Key Functions**:
  - `POST /api/voice-clones/` - Upload and create voice clone
  - `GET /api/voice-clones/user/{user_id}` - Get user's voice clones
- **External Dependencies**:
  - MinIO service for file storage
  - File format validation
- **Testing Approach**:
  - Mock MinIO service operations
  - Test file upload validation
  - Error handling for storage failures
- **Refactoring Opportunities**:
  - Separate file validation logic
  - Abstract storage operations
  - Add file size and duration limits

### Presentations Endpoint (`endpoints/presentations.py`)
- **Agent Type**: Workflow Orchestrator + File Handler
- **Responsibilities**:
  - PPTX file upload and validation
  - Job creation and status tracking
  - Celery task dispatch
  - Video download handling
- **Key Functions**:
  - `POST /api/presentations/` - Create presentation job
  - `GET /api/presentations/status/all` - List all jobs
  - `GET /api/presentations/status/{job_id}` - Get job status
  - `GET /api/presentations/download/{job_id}` - Download video
- **External Dependencies**:
  - MinIO service for file operations
  - Celery for task queuing
  - Database for job tracking
- **Workflow Integration**:
  - Triggers CPU worker for presentation decomposition
  - Monitors job status throughout pipeline
  - Handles final video retrieval
- **Testing Approach**:
  - Mock all external services
  - Test complete workflow scenarios
  - Error handling at each stage
- **Refactoring Opportunities**:
  - Extract presentation service class
  - Separate file validation logic  
  - Abstract job status management
  - Add job cancellation capability

## Cross-Cutting Concerns

### Error Handling
- **Current State**: Basic HTTP status codes and messages
- **Improvements Needed**:
  - Standardized error response format
  - Error code classification
  - Detailed error logging
  - Client-friendly error messages

### Input Validation
- **Current State**: Pydantic schemas for basic validation
- **Improvements Needed**:
  - File size and type validation
  - Business rule validation
  - Rate limiting
  - Content security validation

### Authentication & Authorization
- **Current State**: No authentication implemented
- **Future Considerations**:
  - User authentication system
  - Role-based access control
  - API key management
  - Resource ownership validation

## Testing Strategy

### Unit Tests
- **Focus**: Individual endpoint functions
- **Mocking**: All external dependencies (database, MinIO, Celery)
- **Coverage**: Request validation, response formatting, error handling

### Integration Tests  
- **Focus**: Full API workflows
- **Database**: Real database with test transactions
- **External Services**: Mocked but realistic responses
- **Scenarios**: Happy path and error conditions

### Contract Tests
- **Focus**: API specification compliance
- **Tools**: OpenAPI schema validation
- **Coverage**: Request/response schema validation

## Service Dependencies

### Internal Dependencies
- `app.crud` - Database operations
- `app.schemas` - Data validation
- `app.db.models` - Database models
- `app.services.minio_service` - File storage

### External Dependencies
- **Database**: PostgreSQL via SQLAlchemy
- **Message Queue**: Redis via Celery
- **Object Storage**: MinIO S3-compatible storage
- **Template Engine**: Jinja2 for HTML rendering

## Performance Considerations

### Current Bottlenecks
- File upload size limits
- Synchronous database operations
- No caching layer
- No request compression

### Optimization Opportunities
- Implement async database operations
- Add response caching
- Stream large file uploads
- Add request/response compression
- Implement connection pooling

## Security Considerations

### Current Vulnerabilities
- No authentication/authorization
- No input sanitization beyond type checking
- No rate limiting
- No HTTPS enforcement
- File upload without virus scanning

### Security Improvements
- Add authentication middleware
- Implement request validation
- Add rate limiting per endpoint
- File content validation
- CORS configuration
- Request logging and monitoring

## Monitoring & Observability

### Current State
- Basic FastAPI automatic documentation
- No structured logging
- No metrics collection
- No health checks

### Recommended Additions
- Structured logging with correlation IDs
- Prometheus metrics
- Health check endpoints
- Request tracing
- Error monitoring integration