from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.api.analytics import router as analytics_router
from app import models
from app.api.uploads import router as uploads_router
from app.database import Base, engine, get_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create the initial database tables if they don't exist.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="AI Creator Analytics Copilot",
    description="Analyze YouTube analytics and generate evidence-based insights.",
    version="0.2.0",
    lifespan=lifespan,
)

app.include_router(uploads_router)
app.include_router(analytics_router)

@app.get("/")
def root():
    return {
        "message": "Welcome to AI Creator Analytics Copilot",
        "status": "running",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
    }


@app.get("/health/db")
def database_health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))

    return {
        "status": "healthy",
        "database": "connected",
    }