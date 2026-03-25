import pandas as pd
import re
from typing import Optional


def _clean_isbn(value: str) -> Optional[str]:
    """Strip Goodreads' ="..." ISBN formatting and return clean string or None."""
    if not value or pd.isna(value):
        return None
    cleaned = re.sub(r'[="\']+', "", str(value)).strip()
    return cleaned if cleaned else None


def _parse_date(value) -> Optional[str]:
    """Parse a date string like '2026/03/04' into 'YYYY-MM-DD', or None."""
    if not value or pd.isna(value):
        return None
    try:
        return pd.to_datetime(str(value)).strftime("%Y-%m-%d")
    except Exception:
        return None


def _safe_int(value, fallback=None) -> Optional[int]:
    try:
        v = int(float(str(value)))
        return v if v != 0 else fallback
    except (ValueError, TypeError):
        return fallback


def parse_csv(file_bytes: bytes) -> list[dict]:
    """
    Parse a Goodreads library export CSV and return a list of cleaned book dicts.
    Bookshelves column is intentionally ignored (genre comes from ISBN lookup).
    """
    import io
    df = pd.read_csv(io.BytesIO(file_bytes))

    # Normalize column names: strip whitespace
    df.columns = [c.strip() for c in df.columns]

    books = []
    for _, row in df.iterrows():
        isbn = _clean_isbn(row.get("ISBN"))
        isbn13 = _clean_isbn(row.get("ISBN13"))

        # Prefer ISBN13 as the lookup key, fall back to ISBN
        lookup_isbn = isbn13 or isbn

        books.append({
            "goodreads_id": _safe_int(row.get("Book Id")),
            "title": str(row.get("Title", "")).strip() or "Unknown",
            "author": str(row.get("Author", "")).strip() or None,
            "additional_authors": str(row.get("Additional Authors", "")).strip() or None,
            "isbn": isbn,
            "isbn13": isbn13,
            "lookup_isbn": lookup_isbn,  # used by genre service, not stored
            "my_rating": _safe_int(row.get("My Rating"), fallback=0),
            "avg_rating": float(row.get("Average Rating")) if row.get("Average Rating") else None,
            "publisher": str(row.get("Publisher", "")).strip() or None,
            "num_pages": _safe_int(row.get("Number of Pages")),
            "year_published": _safe_int(row.get("Year Published")),
            "original_pub_year": _safe_int(row.get("Original Publication Year")),
            "date_read": _parse_date(row.get("Date Read")),
            "date_added": _parse_date(row.get("Date Added")),
            "exclusive_shelf": str(row.get("Exclusive Shelf", "")).strip() or None,
            "my_review": str(row.get("My Review", "")).strip() or None,
            "read_count": _safe_int(row.get("Read Count"), fallback=0),
        })

    return books
