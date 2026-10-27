from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import UploadBatch, VideoMetric


router = APIRouter(
    prefix="/api/analytics",
    tags=["Analytics"],
)


def serialize_video(video: VideoMetric) -> dict:
    """Convert a video database record into a JSON-friendly dictionary."""
    return {
        "video_id": video.id,
        "video_title": video.video_title,
        "views": video.views,
        "watch_time_hours": video.watch_time_hours,
        "subscribers": video.subscribers,
        "estimated_revenue": video.estimated_revenue,
        "average_view_duration": video.average_view_duration,
        "video_publish_date": (
            video.video_publish_date.isoformat()
            if video.video_publish_date
            else None
        ),
    }


@router.get("/{upload_id}/overview")
def get_analytics_overview(
    upload_id: int,
    db: Session = Depends(get_db),
):
    """Return summary metrics and top-performing videos for one upload."""

    # 1. Confirm that this upload exists.
    upload = db.get(UploadBatch, upload_id)

    if upload is None:
        raise HTTPException(
            status_code=404,
            detail=f"Upload {upload_id} was not found.",
        )

    # 2. Aggregate metrics across all videos in this upload.
    summary_query = select(
        func.count(VideoMetric.id),
        func.coalesce(func.sum(VideoMetric.views), 0),
        func.coalesce(func.sum(VideoMetric.watch_time_hours), 0),
        func.coalesce(func.sum(VideoMetric.subscribers), 0),
        func.coalesce(func.sum(VideoMetric.estimated_revenue), 0),
        func.avg(VideoMetric.views),
        func.avg(VideoMetric.estimated_revenue),
    ).where(VideoMetric.upload_id == upload_id)

    (
        video_count,
        total_views,
        total_watch_time_hours,
        total_subscribers_gained,
        total_estimated_revenue,
        average_views,
        average_revenue,
    ) = db.execute(summary_query).one()

    # 3. Get the five most-viewed videos.
    top_by_views_query = (
        select(VideoMetric)
        .where(VideoMetric.upload_id == upload_id)
        .order_by(VideoMetric.views.desc(), VideoMetric.id.asc())
        .limit(5)
    )

    top_by_views = db.scalars(top_by_views_query).all()

    # 4. Get the five videos with the highest estimated revenue.
    top_by_revenue_query = (
        select(VideoMetric)
        .where(VideoMetric.upload_id == upload_id)
        .order_by(
            VideoMetric.estimated_revenue.desc().nulls_last(),
            VideoMetric.views.desc(),
        )
        .limit(5)
    )

    top_by_revenue = db.scalars(top_by_revenue_query).all()

    # 5. Return a structured response.
    return {
        "upload_id": upload.id,
        "filename": upload.filename,
        "video_count": int(video_count),
        "total_views": int(total_views or 0),
        "total_watch_time_hours": round(
            float(total_watch_time_hours or 0), 2
        ),
        "total_subscribers_gained": int(total_subscribers_gained or 0),
        "total_estimated_revenue": round(
            float(total_estimated_revenue or 0), 2
        ),
        "average_views_per_video": round(
            float(average_views or 0), 2
        ),
        "average_revenue_per_video": round(
            float(average_revenue or 0), 2
        ),
        "top_videos_by_views": [
            serialize_video(video) for video in top_by_views
        ],
        "top_videos_by_revenue": [
            serialize_video(video) for video in top_by_revenue
        ],
    }