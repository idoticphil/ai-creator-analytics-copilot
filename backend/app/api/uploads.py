from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import UploadBatch, VideoMetric
from app.services.csv_validation import validate_youtube_analytics_csv


router = APIRouter(prefix="/api/uploads", tags=["CSV Upload"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@router.post("/csv", status_code=201)
async def upload_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    filename = file.filename or ""

    if not filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=415,
            detail="Please upload a .csv file.",
        )

    try:
        content = await file.read(MAX_UPLOAD_BYTES + 1)
    finally:
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

    # These records are internal; do not expose them in the API response.
    records = result.pop("_records")

    try:
        batch = UploadBatch(
            filename=filename,
            row_count=len(records),
        )

        db.add(batch)
        db.flush()

        video_rows = []

        for row_number, record in enumerate(records, start=1):
            publish_date = None

            if record.get("video_publish_date"):
                publish_date = date.fromisoformat(
                    record["video_publish_date"]
                )

            video_rows.append(
                VideoMetric(
                    upload_id=batch.id,
                    source_row_number=row_number,
                    video_title=record["video_title"],
                    views=record["views"],
                    watch_time_hours=record.get("watch_time_hours"),
                    subscribers=record.get("subscribers"),
                    estimated_revenue=record.get("estimated_revenue"),
                    revenue_currency=record.get("revenue_currency"),
                    average_view_duration=record.get(
                        "average_view_duration"
                    ),
                    video_publish_date=publish_date,
                )
            )

        db.add_all(video_rows)
        db.commit()
        db.refresh(batch)

    except (SQLAlchemyError, ValueError) as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not save the validated CSV to the database.",
        ) from exc

    return {
        "filename": filename,
        "status": "saved",
        "upload_id": batch.id,
        "uploaded_at": batch.uploaded_at.isoformat(),
        **result,
    }


@router.get("/{upload_id}")
def get_upload(
    upload_id: int,
    db: Session = Depends(get_db),
):
    batch = db.get(UploadBatch, upload_id)

    if batch is None:
        raise HTTPException(status_code=404, detail="Upload not found.")

    saved_count = db.scalar(
        select(func.count(VideoMetric.id)).where(
            VideoMetric.upload_id == upload_id
        )
    ) or 0

    return {
        "upload_id": batch.id,
        "filename": batch.filename,
        "uploaded_at": batch.uploaded_at.isoformat(),
        "row_count": batch.row_count,
        "saved_video_count": saved_count,
    }


@router.get("/{upload_id}/videos")
def get_upload_videos(
    upload_id: int,
    db: Session = Depends(get_db),
):
    batch = db.get(UploadBatch, upload_id)

    if batch is None:
        raise HTTPException(status_code=404, detail="Upload not found.")

    videos = db.scalars(
        select(VideoMetric)
        .where(VideoMetric.upload_id == upload_id)
        .order_by(VideoMetric.source_row_number)
        .limit(100)
    ).all()

    return {
        "upload_id": upload_id,
        "count": len(videos),
        "videos": [
            {
                "id": video.id,
                "source_row_number": video.source_row_number,
                "video_title": video.video_title,
                "views": video.views,
                "watch_time_hours": video.watch_time_hours,
                "subscribers": video.subscribers,
                "estimated_revenue": video.estimated_revenue,
                "revenue_currency": video.revenue_currency,
                "average_view_duration": video.average_view_duration,
                "video_publish_date": (
                    video.video_publish_date.isoformat()
                    if video.video_publish_date
                    else None
                ),
            }
            for video in videos
        ],
    }