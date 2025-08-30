# Database Module Agents

## Overview
The Database module handles data persistence, schema definitions, and database connectivity for the Presentation Video Generator application. It provides a clean abstraction layer between the application logic and the PostgreSQL database.

## Module Components

### Database Session Management (`session.py`)
- **Agent Type**: Connection Pool Manager
- **Purpose**: Configure SQLAlchemy engine and session management
- **Responsibilities**:
  - Database connection string construction
  - SQLAlchemy engine configuration
  - Session factory creation
  - Base class definition for ORM models

#### Current Implementation
```python
# Simple but functional approach
SQLALCHEMY_DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@postgres:5432/{POSTGRES_DB}"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
```

#### Strengths
- ✅ Clean separation of concerns
- ✅ Standard SQLAlchemy patterns
- ✅ Environment-based configuration
- ✅ Easy to test with SQLite

#### Improvements for Production
```python
# Enhanced session management
class DatabaseConfig:
    def __init__(self):
        self.url = self._build_database_url()
        self.engine_options = {
            'pool_size': 10,
            'max_overflow': 20,
            'pool_pre_ping': True,
            'pool_recycle': 3600,
            'echo': os.getenv('DATABASE_DEBUG', 'false').lower() == 'true'
        }
    
    def _build_database_url(self) -> str:
        # Enhanced with SSL and connection options
        base_url = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
        if os.getenv('DATABASE_SSL', 'false').lower() == 'true':
            base_url += "?sslmode=require"
        return base_url

class DatabaseManager:
    def __init__(self, config: DatabaseConfig):
        self.engine = create_engine(config.url, **config.engine_options)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
    
    def get_session(self):
        """Dependency injection-friendly session factory"""
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    def init_db(self):
        """Initialize database tables"""
        Base.metadata.create_all(bind=self.engine)
    
    def health_check(self) -> bool:
        """Database health check for monitoring"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                return True
        except Exception:
            return False
```

### Data Models (`models.py`)
- **Agent Type**: Domain Entity Definitions
- **Purpose**: Define database schema and relationships
- **ORM Framework**: SQLAlchemy declarative models

#### Current Models Analysis

##### User Model
```python
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
```

**Strengths:**
- ✅ Simple and clean
- ✅ Proper indexing on searchable fields
- ✅ Relationship definitions

**Improvements Needed:**
```python
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)  # Length constraint
    email = Column(String(255), unique=True, index=True, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, 
                       onupdate=datetime.datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)  # Soft delete support
    
    # Enhanced relationships with lazy loading options
    voice_clones = relationship("VoiceClone", back_populates="owner", 
                               lazy="dynamic", cascade="all, delete-orphan")
    presentations = relationship("PresentationJob", back_populates="owner",
                               lazy="dynamic", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, name='{self.name}', email='{self.email}')>"
    
    @validates('email')
    def validate_email(self, key, address):
        if address and '@' not in address:
            raise ValueError("Invalid email format")
        return address
```

##### VoiceClone Model
```python
class VoiceClone(Base):
    __tablename__ = "voice_clones"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    s3_path = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    owner_id = Column(Integer, ForeignKey("users.id"))
```

**Improvements:**
```python
class VoiceClone(Base):
    __tablename__ = "voice_clones"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    s3_path = Column(String(1000), nullable=False, unique=True)  # Longer path, unique constraint
    file_size = Column(BigInteger, nullable=True)  # Track file size
    duration_seconds = Column(Float, nullable=True)  # Track audio duration
    sample_rate = Column(Integer, nullable=True)  # Track audio properties
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow,
                       onupdate=datetime.datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Foreign key with proper constraints
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), 
                     nullable=False, index=True)
    
    # Relationship with back reference
    owner = relationship("User", back_populates="voice_clones")
    
    # Table constraints
    __table_args__ = (
        CheckConstraint('file_size > 0', name='positive_file_size'),
        CheckConstraint('duration_seconds > 0', name='positive_duration'),
        Index('idx_owner_name', 'owner_id', 'name'),  # Composite index for user queries
    )
    
    def __repr__(self):
        return f"<VoiceClone(id={self.id}, name='{self.name}', owner_id={self.owner_id})>"
```

##### PresentationJob Model
```python
class PresentationJob(Base):
    __tablename__ = "presentation_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    status = Column(Enum(JobStatus), default=JobStatus.PENDING, nullable=False, index=True)
    s3_pptx_path = Column(String(1000), nullable=False)
    s3_video_path = Column(String(1000), nullable=True)
    
    # Enhanced metadata
    slides_count = Column(Integer, nullable=True)
    video_duration_seconds = Column(Float, nullable=True)
    file_size_bytes = Column(BigInteger, nullable=True)
    processing_time_seconds = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)  # Store error details
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow,
                       onupdate=datetime.datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Foreign keys with proper constraints
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), 
                     nullable=False, index=True)
    voice_clone_id = Column(Integer, ForeignKey("voice_clones.id", ondelete="RESTRICT"),
                           nullable=False, index=True)
    
    # Relationships
    owner = relationship("User", back_populates="presentations")
    voice_clone = relationship("VoiceClone")
    
    # Table constraints and indexes
    __table_args__ = (
        Index('idx_owner_status', 'owner_id', 'status'),
        Index('idx_created_at', 'created_at'),
        CheckConstraint("completed_at IS NULL OR completed_at >= started_at", 
                       name="valid_completion_time"),
    )

# Enhanced status enum
class JobStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING_SLIDES = "processing_slides"
    SYNTHESIZING_AUDIO = "synthesizing_audio"
    ASSEMBLING_VIDEO = "assembling_video"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

### Model Relationships and Constraints

#### Relationship Patterns
```python
# One-to-Many with cascade delete
class User(Base):
    voice_clones = relationship("VoiceClone", back_populates="owner", 
                               cascade="all, delete-orphan")
    presentations = relationship("PresentationJob", back_populates="owner",
                               cascade="all, delete-orphan")

# Many-to-One with foreign key constraints
class VoiceClone(Base):
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    owner = relationship("User", back_populates="voice_clones")

class PresentationJob(Base):
    # User can be deleted, jobs should be deleted too
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    # Voice clone should not be deleted if jobs depend on it
    voice_clone_id = Column(Integer, ForeignKey("voice_clones.id", ondelete="RESTRICT"))
```

## Testing Strategy

### Unit Testing Models
```python
def test_user_creation(db_session):
    """Test basic user creation"""
    user = User(name="Test User", email="test@example.com")
    db_session.add(user)
    db_session.commit()
    
    assert user.id is not None
    assert user.created_at is not None
    assert user.is_active is True

def test_user_email_validation(db_session):
    """Test email validation"""
    user = User(name="Test User", email="invalid-email")
    db_session.add(user)
    
    with pytest.raises(ValueError, match="Invalid email format"):
        db_session.commit()

def test_cascade_delete_voice_clones(db_session):
    """Test that deleting user cascades to voice clones"""
    user = User(name="Test User")
    db_session.add(user)
    db_session.commit()
    
    voice_clone = VoiceClone(name="Test Voice", s3_path="/test.wav", owner_id=user.id)
    db_session.add(voice_clone)
    db_session.commit()
    
    db_session.delete(user)
    db_session.commit()
    
    # Voice clone should be deleted due to cascade
    assert db_session.query(VoiceClone).filter_by(id=voice_clone.id).first() is None
```

### Integration Testing
```python
@pytest.fixture
def test_database_url():
    return "sqlite:///./test.db"

@pytest.fixture
def test_engine(test_database_url):
    engine = create_engine(test_database_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db_session(test_engine):
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = TestingSessionLocal()
    yield session
    session.close()
```

### Performance Testing
```python
def test_query_performance(db_session):
    """Test that queries use proper indexes"""
    # Create test data
    users = [User(name=f"User {i}", email=f"user{i}@example.com") for i in range(1000)]
    db_session.add_all(users)
    db_session.commit()
    
    # Test indexed query performance
    start_time = time.time()
    user = db_session.query(User).filter(User.email == "user500@example.com").first()
    query_time = time.time() - start_time
    
    assert user is not None
    assert query_time < 0.1  # Should be fast with index
```

## Database Migration Strategy

### Alembic Integration
```python
# alembic/env.py configuration
from app.db.models import Base
from app.db.session import engine

target_metadata = Base.metadata

def run_migrations():
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
```

### Migration Best Practices
1. **Incremental Changes**: Small, reversible migrations
2. **Data Preservation**: Ensure data integrity during schema changes
3. **Index Management**: Add indexes concurrently in production
4. **Rollback Strategy**: Test rollback procedures
5. **Environment Parity**: Same migrations across all environments

## Performance Optimization

### Query Optimization
```python
# Eager loading to prevent N+1 queries
def get_users_with_voice_clones(db: Session):
    return db.query(User).options(joinedload(User.voice_clones)).all()

# Pagination for large datasets
def get_presentation_jobs(db: Session, skip: int = 0, limit: int = 100):
    return db.query(PresentationJob)\
             .options(joinedload(PresentationJob.owner))\
             .order_by(PresentationJob.created_at.desc())\
             .offset(skip)\
             .limit(limit)\
             .all()
```

### Database Indexes
```sql
-- Performance-critical indexes
CREATE INDEX CONCURRENTLY idx_presentation_jobs_owner_status ON presentation_jobs(owner_id, status);
CREATE INDEX CONCURRENTLY idx_presentation_jobs_created_at ON presentation_jobs(created_at DESC);
CREATE INDEX CONCURRENTLY idx_voice_clones_owner_name ON voice_clones(owner_id, name);
CREATE INDEX CONCURRENTLY idx_users_email ON users(email) WHERE email IS NOT NULL;
```

### Connection Pool Configuration
```python
# Production-ready configuration
engine = create_engine(
    DATABASE_URL,
    pool_size=20,          # Number of permanent connections
    max_overflow=30,       # Additional connections when needed
    pool_pre_ping=True,    # Validate connections before use
    pool_recycle=3600,     # Recycle connections every hour
    connect_args={
        "options": "-c timezone=utc",  # Set timezone
        "connect_timeout": 10,          # Connection timeout
        "application_name": "presentation-generator"
    }
)
```

## Data Integrity and Constraints

### Model Validation
```python
from sqlalchemy.orm import validates
from sqlalchemy import CheckConstraint

class VoiceClone(Base):
    @validates('s3_path')
    def validate_s3_path(self, key, path):
        if not path.startswith('/'):
            raise ValueError("S3 path must start with '/'")
        if not path.endswith('.wav'):
            raise ValueError("Voice clone must be a WAV file")
        return path
    
    @validates('duration_seconds')
    def validate_duration(self, key, duration):
        if duration is not None and duration <= 0:
            raise ValueError("Duration must be positive")
        if duration is not None and duration > 300:  # 5 minutes max
            raise ValueError("Voice clone too long (max 5 minutes)")
        return duration

# Database-level constraints
class PresentationJob(Base):
    __table_args__ = (
        CheckConstraint('slides_count > 0', name='positive_slides_count'),
        CheckConstraint('video_duration_seconds > 0', name='positive_video_duration'),
        CheckConstraint("status != 'completed' OR s3_video_path IS NOT NULL", 
                       name='completed_jobs_have_video'),
    )
```

## Security Considerations

### SQL Injection Prevention
- ✅ Using SQLAlchemy ORM prevents direct SQL injection
- ✅ Parameterized queries for raw SQL
- ✅ Input validation at model level

### Data Access Control
```python
# Row-level security patterns
def get_user_voice_clones(db: Session, user_id: int):
    """Only return voice clones owned by the user"""
    return db.query(VoiceClone).filter(VoiceClone.owner_id == user_id).all()

def get_user_presentation_jobs(db: Session, user_id: int):
    """Only return jobs owned by the user"""
    return db.query(PresentationJob).filter(PresentationJob.owner_id == user_id).all()
```

### Sensitive Data Handling
```python
# Example: Hashed sensitive fields
from werkzeug.security import generate_password_hash

class User(Base):
    password_hash = Column(String(128), nullable=True)  # If authentication added
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
```

## Monitoring and Observability

### Database Health Monitoring
```python
def get_database_metrics(db: Session):
    """Collect database metrics for monitoring"""
    return {
        'total_users': db.query(User).count(),
        'active_users': db.query(User).filter(User.is_active == True).count(),
        'total_voice_clones': db.query(VoiceClone).count(),
        'pending_jobs': db.query(PresentationJob).filter(
            PresentationJob.status == JobStatus.PENDING
        ).count(),
        'failed_jobs_today': db.query(PresentationJob).filter(
            PresentationJob.status == JobStatus.FAILED,
            PresentationJob.created_at >= datetime.date.today()
        ).count()
    }
```

### Logging Database Operations
```python
import logging

db_logger = logging.getLogger('database')

def log_job_status_change(job_id: int, old_status: str, new_status: str):
    db_logger.info(f"Job {job_id} status changed: {old_status} -> {new_status}")

def log_slow_query(query_time: float, query: str):
    if query_time > 1.0:  # Log queries taking more than 1 second
        db_logger.warning(f"Slow query ({query_time:.2f}s): {query}")
```

## Future Enhancements

### Audit Logging
- Track all data modifications
- User action logging
- Change history for critical entities

### Read Replicas
- Separate read/write database connections
- Query routing based on operation type
- Load balancing for read queries

### Data Archival
- Archive completed jobs after retention period
- Compress historical data
- Implement soft delete patterns

### Advanced Features
- Full-text search capabilities
- Database-level encryption for sensitive fields
- Automated backup and recovery procedures
- Multi-tenant data isolation