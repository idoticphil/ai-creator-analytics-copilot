from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.csv_validation import validate_youtube_analytics_csv


router = APIRouter(
    prefix="/api/uploads",
    tags=["CSV Upload"],
)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/csv")
async def upload_csv(file: UploadFile = File(...)):
    """Validate an uploaded YouTube Analytics CSV."""

    filename = file.filename or ""

    if not filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=415,
            detail="Please upload a file with the .csv extension.",
        )

    # Read one byte beyond the limit so oversized files can be detected.
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    await file.close()

    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail="The file is too large. Maximum size is 10 MB.",
        )

    if not content:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty.",
        )

    try:
        result = validate_youtube_analytics_csv(content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "filename": filename,
        "status": "validated",
        **result,
    }