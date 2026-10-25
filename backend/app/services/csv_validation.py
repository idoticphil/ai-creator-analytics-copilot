from io import BytesIO
import json

import pandas as pd
from pandas.errors import EmptyDataError, ParserError


# Map common YouTube Analytics CSV headers to standard field names.
COLUMN_ALIASES = {
    "video_title": ("video title", "content", "video", "title"),
    "views": ("views",),
    "watch_time_hours": ("watch time (hours)", "watch time hours"),
    "subscribers": ("subscribers", "subscribers gained"),
    "estimated_revenue": (
        "estimated revenue (usd)",
        "estimated revenue (inr)",
        "estimated revenue",
        "revenue",
    ),
    "average_view_duration": (
        "average view duration",
        "avg view duration",
    ),
    "video_publish_time": (
        "video publish time",
        "publish date",
        "published at",
    ),
}

NUMERIC_FIELDS = {
    "views",
    "watch_time_hours",
    "subscribers",
    "estimated_revenue",
}

REQUIRED_FIELDS = {"video_title", "views"}


def normalize_header(header: str) -> str:
    """Normalize CSV headers for case-insensitive matching."""
    return " ".join(str(header).replace("\ufeff", "").strip().lower().split())


def validate_youtube_analytics_csv(file_bytes: bytes) -> dict:
    """Read, validate, and preview a video-level analytics CSV."""

    if not file_bytes:
        raise ValueError("The uploaded file is empty.")

    try:
        df = pd.read_csv(BytesIO(file_bytes))
    except (EmptyDataError, ParserError, UnicodeDecodeError) as exc:
        raise ValueError(
            "Could not read this CSV. Please export a valid UTF-8 CSV file."
        ) from exc

    # Remove rows that are entirely blank.
    df = df.dropna(how="all").copy()

    if df.empty:
        raise ValueError("The CSV contains no data rows.")

    # Match column names without depending on capitalization.
    normalized_headers = [normalize_header(c) for c in df.columns]

    if len(set(normalized_headers)) != len(normalized_headers):
        raise ValueError(
            "The CSV contains duplicate column names. Please check the export."
        )

    header_lookup = dict(zip(normalized_headers, df.columns))
    matched_columns = {}

    for field, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in header_lookup:
                matched_columns[field] = header_lookup[alias]
                break

    missing = REQUIRED_FIELDS - set(matched_columns)

    if missing:
        raise ValueError(
            "Missing required columns: Video title (or Content) and Views. "
            "Please upload a video-level YouTube Analytics export."
        )

    # Build a clean data frame with consistent field names.
    clean_df = pd.DataFrame(index=df.index)

    for field, source_column in matched_columns.items():
        if field in NUMERIC_FIELDS:
            raw_values = (
                df[source_column]
                .astype("string")
                .str.replace(r"[,₹$€£]", "", regex=True)
                .str.strip()
            )

            numeric_values = pd.to_numeric(raw_values, errors="coerce")

            invalid = (
                df[source_column].notna()
                & raw_values.ne("")
                & numeric_values.isna()
            )

            if invalid.any():
                raise ValueError(
                    f"Column '{source_column}' contains "
                    f"{int(invalid.sum())} non-numeric value(s)."
                )

            if field in {"views", "watch_time_hours"}:
                if (numeric_values.dropna() < 0).any():
                    raise ValueError(
                        f"Column '{source_column}' cannot contain negative values."
                    )

            clean_df[field] = numeric_values

        else:
            clean_df[field] = df[source_column].fillna("").astype(str).str.strip()

    if clean_df["video_title"].eq("").any():
        raise ValueError(
            "Some rows have a missing video title. Please correct the CSV."
        )

    if not clean_df["views"].notna().all():
        raise ValueError(
            "The Views column has missing values. Please correct the CSV."
        )

    warnings = []

    optional_fields = {
        "watch_time_hours",
        "subscribers",
        "estimated_revenue",
        "average_view_duration",
        "video_publish_time",
    }

    for field in sorted(optional_fields - set(matched_columns)):
        warnings.append(
            f"Optional metric '{field}' was not found in the uploaded CSV."
        )

    # Convert preview values into JSON-safe Python data.
    preview = json.loads(
        clean_df.head(5).to_json(orient="records", date_format="iso")
    )

    return {
        "row_count": int(len(clean_df)),
        "original_columns": [str(column) for column in df.columns],
        "matched_columns": matched_columns,
        "available_metrics": list(clean_df.columns),
        "warnings": warnings,
        "preview": preview,
    }