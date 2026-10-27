
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
    return " ".join(
        str(header).replace("\ufeff", "").strip().lower().split()
    )


def validate_youtube_analytics_csv(file_bytes: bytes) -> dict:
    """Read, validate, and prepare a video-level analytics CSV."""

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

            numeric_values = pd.to_numeric(
                raw_values,
                errors="coerce",
            )

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
                        f"Column '{source_column}' cannot contain "
                        "negative values."
                    )

            clean_df[field] = numeric_values

        else:
            clean_df[field] = (
                df[source_column]
                .fillna("")
                .astype(str)
                .str.strip()
            )

    # Check required values.
    if clean_df["video_title"].eq("").any():
        raise ValueError(
            "Some rows have a missing video title. Please correct the CSV."
        )

    if not clean_df["views"].notna().all():
        raise ValueError(
            "The Views column has missing values. Please correct the CSV."
        )

    # Identify optional metrics that aren't present.
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

    # Validate whole-number fields before storing them in integer columns.
    for field in ("views", "subscribers"):
        if field in clean_df:
            values = clean_df[field].dropna()

            if ((values % 1) != 0).any():
                raise ValueError(
                    f"Column '{matched_columns[field]}' "
                    "must contain whole numbers."
                )

    # Normalize publication dates to YYYY-MM-DD.
    if "video_publish_time" in clean_df:
        raw_dates = (
            clean_df["video_publish_time"]
            .astype("string")
            .str.strip()
        )

        has_value = raw_dates.notna() & raw_dates.ne("")

        parsed_dates = pd.to_datetime(
            raw_dates,
            errors="coerce",
            utc=True,
        )

        invalid_dates = has_value & parsed_dates.isna()

        if invalid_dates.any():
            raise ValueError(
                f"Column '{matched_columns['video_publish_time']}' "
                f"contains {int(invalid_dates.sum())} invalid date value(s)."
            )

        clean_df["video_publish_time"] = (
            parsed_dates.dt.strftime("%Y-%m-%d")
            .where(parsed_dates.notna(), None)
        )

    # Return a small preview to the API client.
    preview = json.loads(
        clean_df.head(5).to_json(
            orient="records",
            date_format="iso",
        )
    )

    # Prepare every validated row for database persistence.
    records = json.loads(
        clean_df.to_json(
            orient="records",
            date_format="iso",
        )
    )

    # Identify the currency declared by the revenue column, if any.
    revenue_column = matched_columns.get("estimated_revenue", "")
    revenue_header = normalize_header(revenue_column)

    revenue_currency = None

    if "usd" in revenue_header or "$" in revenue_column:
        revenue_currency = "USD"
    elif "inr" in revenue_header or "₹" in revenue_column:
        revenue_currency = "INR"
    elif "eur" in revenue_header or "€" in revenue_column:
        revenue_currency = "EUR"
    elif "gbp" in revenue_header or "£" in revenue_column:
        revenue_currency = "GBP"

    # Normalize each record for our database schema.
    for record in records:
        record["views"] = int(record["views"])

        if record.get("subscribers") is not None:
            record["subscribers"] = int(record["subscribers"])

        record["video_publish_date"] = record.pop(
            "video_publish_time",
            None,
        )

        record["revenue_currency"] = revenue_currency

    # Return both the public preview and the internal database records.
    return {
        "row_count": int(len(clean_df)),
        "original_columns": [str(column) for column in df.columns],
        "matched_columns": matched_columns,
        "available_metrics": list(clean_df.columns),
        "warnings": warnings,
        "preview": preview,
        "_records": records,
    }
