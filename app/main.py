from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from app.db.session import engine
from app.db import models
from app.api.endpoints import users, voice_clones, presentations

# This will create the tables in the database
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Presentation Video Generator API")

templates = Jinja2Templates(directory="/templates")

# Include API routers
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(voice_clones.router, prefix="/api/voice-clones", tags=["voice-clones"])
app.include_router(presentations.router, prefix="/api/presentations", tags=["presentations"])


@app.get("/")
def read_root(request: Request):
    """Serve the main HTML page."""
    return templates.TemplateResponse("index.html", {"request": request})
