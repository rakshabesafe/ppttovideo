from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from app.db.session import engine, SessionLocal
from app.db import models
from app.api.endpoints import users, voice_clones, presentations, cleanup, dashboard
from app import crud

# This will create the tables in the database
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Presentation Video Generator API")

@app.on_event("startup")
async def startup_event():
    """Initialize default data on startup"""
    db = SessionLocal()
    try:
        # Create default system user
        existing_user = crud.get_user_by_name(db, "System")
        if not existing_user:
            from app.schemas import UserCreate
            user_data = UserCreate(name="System", email="system@localhost")
            crud.create_user(db, user_data)
        
        # Create default voice clones
        crud.create_default_voice_clones(db)
    finally:
        db.close()

templates = Jinja2Templates(directory="/templates")

# Include API routers
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(voice_clones.router, prefix="/api/voice-clones", tags=["voice-clones"])
app.include_router(presentations.router, prefix="/api/presentations", tags=["presentations"])
app.include_router(cleanup.router, prefix="/api/cleanup", tags=["cleanup"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])


@app.get("/")
def read_root(request: Request):
    """Serve the main HTML page."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/dashboard")
def dashboard(request: Request):
    """Serve the operational dashboard page."""
    return templates.TemplateResponse("dashboard.html", {"request": request})
