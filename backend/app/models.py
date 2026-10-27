from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UploadBatch(Base):
    __tablename__ = "upload_batches"

    id: Mapped[int] = mapped_column(primary_key=True)

    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    row_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    videos: Mapped[list["VideoMetric"]] = relationship(
        back_populates="upload",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class VideoMetric(Base):
    __tablename__ = "video_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)

    upload_id: Mapped[int] = mapped_column(
        ForeignKey("upload_batches.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    source_row_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    video_title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    views: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    watch_time_hours: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    subscribers: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    estimated_revenue: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    revenue_currency: Mapped[str | None] = mapped_column(
        String(3),
        nullable=True,
    )

    average_view_duration: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    video_publish_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    upload: Mapped["UploadBatch"] = relationship(
        back_populates="videos",
    )