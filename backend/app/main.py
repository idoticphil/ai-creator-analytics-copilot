from fastapi import FastAPI

from app.api.uploads import router as uploads_router


app = FastAPI(
    title="AI Creator Analytics Copilot",
    description="Analyze YouTube analytics and generate evidence-based insights.",
    version="0.1.0",
)

app.include_router(uploads_router)


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