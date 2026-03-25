"""
SQL query functions for each insight endpoint.
Written using raw SQL via SQLAlchemy text() so the SQL concepts are explicit and readable.
"""
from sqlalchemy.orm import Session
from sqlalchemy import text


def books_per_year(db: Session) -> list[dict]:
    """COUNT books read per year, ordered chronologically."""
    rows = db.execute(text("""
        SELECT
            EXTRACT(YEAR FROM date_read)::INTEGER AS year,
            COUNT(*) AS count
        FROM books
        WHERE date_read IS NOT NULL
          AND exclusive_shelf = 'read'
        GROUP BY year
        ORDER BY year
    """)).fetchall()
    return [{"year": r[0], "count": r[1]} for r in rows]


def genre_breakdown(db: Session) -> list[dict]:
    """COUNT books per genre via many-to-many join."""
    rows = db.execute(text("""
        SELECT
            g.name AS genre,
            COUNT(DISTINCT bg.book_id) AS count
        FROM genres g
        JOIN book_genres bg ON bg.genre_id = g.id
        JOIN books b ON b.id = bg.book_id
        WHERE b.exclusive_shelf = 'read'
        GROUP BY g.name
        ORDER BY count DESC
    """)).fetchall()
    return [{"genre": r[0], "count": r[1]} for r in rows]


def rating_distribution(db: Session) -> list[dict]:
    """Distribution of user ratings (1–5) for read books."""
    rows = db.execute(text("""
        SELECT
            my_rating AS rating,
            COUNT(*) AS count
        FROM books
        WHERE exclusive_shelf = 'read'
          AND my_rating > 0
        GROUP BY my_rating
        ORDER BY my_rating
    """)).fetchall()
    return [{"rating": r[0], "count": r[1]} for r in rows]


def top_authors(db: Session, limit: int = 10) -> list[dict]:
    """Top authors by number of books read."""
    rows = db.execute(text("""
        SELECT
            author,
            COUNT(*) AS count
        FROM books
        WHERE exclusive_shelf = 'read'
          AND author IS NOT NULL
        GROUP BY author
        ORDER BY count DESC, author
        LIMIT :limit
    """), {"limit": limit}).fetchall()
    return [{"author": r[0], "count": r[1]} for r in rows]


def reading_pace(db: Session) -> list[dict]:
    """Total pages read per month, across all years."""
    rows = db.execute(text("""
        SELECT
            EXTRACT(YEAR FROM date_read)::INTEGER  AS year,
            EXTRACT(MONTH FROM date_read)::INTEGER AS month,
            SUM(num_pages) AS pages,
            COUNT(*) AS books
        FROM books
        WHERE date_read IS NOT NULL
          AND exclusive_shelf = 'read'
          AND num_pages IS NOT NULL
        GROUP BY year, month
        ORDER BY year, month
    """)).fetchall()
    return [{"year": r[0], "month": r[1], "pages": r[2], "books": r[3]} for r in rows]


def reading_heatmap(db: Session) -> list[dict]:
    """Books finished per calendar day (for a GitHub-style heatmap)."""
    rows = db.execute(text("""
        SELECT
            date_read::TEXT AS date,
            COUNT(*) AS count
        FROM books
        WHERE date_read IS NOT NULL
          AND exclusive_shelf = 'read'
        GROUP BY date_read
        ORDER BY date_read
    """)).fetchall()
    return [{"date": r[0], "count": r[1]} for r in rows]


def top_rated_books(db: Session, limit: int = 20) -> list[dict]:
    """Books with the highest user ratings, ordered by rating then date read."""
    rows = db.execute(text("""
        SELECT
            id, title, author, my_rating, date_read::TEXT, num_pages, isbn13
        FROM books
        WHERE exclusive_shelf = 'read'
          AND my_rating > 0
        ORDER BY my_rating DESC, date_read DESC NULLS LAST
        LIMIT :limit
    """), {"limit": limit}).fetchall()
    return [
        {
            "id": r[0], "title": r[1], "author": r[2],
            "my_rating": r[3], "date_read": r[4],
            "num_pages": r[5], "isbn13": r[6],
        }
        for r in rows
    ]


def page_extremes(db: Session) -> dict:
    """Longest and shortest books read (by page count)."""
    row = db.execute(text("""
        SELECT
            MIN(num_pages) AS min_pages,
            MAX(num_pages) AS max_pages
        FROM books
        WHERE exclusive_shelf = 'read'
          AND num_pages IS NOT NULL
    """)).fetchone()

    shortest = db.execute(text("""
        SELECT title, author, num_pages FROM books
        WHERE exclusive_shelf = 'read'
          AND num_pages = (
              SELECT MIN(num_pages) FROM books
              WHERE exclusive_shelf = 'read' AND num_pages IS NOT NULL
          )
        LIMIT 1
    """)).fetchone()

    longest = db.execute(text("""
        SELECT title, author, num_pages FROM books
        WHERE exclusive_shelf = 'read'
          AND num_pages = (
              SELECT MAX(num_pages) FROM books
              WHERE exclusive_shelf = 'read' AND num_pages IS NOT NULL
          )
        LIMIT 1
    """)).fetchone()

    return {
        "shortest": {"title": shortest[0], "author": shortest[1], "pages": shortest[2]} if shortest else None,
        "longest":  {"title": longest[0],  "author": longest[1],  "pages": longest[2]} if longest else None,
    }


def summary_stats(db: Session) -> dict:
    """Aggregate stats: total books, total pages, avg rating, re-reads."""
    row = db.execute(text("""
        SELECT
            COUNT(*)                                        AS total_books,
            COALESCE(SUM(num_pages), 0)                    AS total_pages,
            ROUND(AVG(NULLIF(my_rating, 0))::NUMERIC, 2)   AS avg_rating,
            COUNT(*) FILTER (WHERE read_count > 1)         AS reread_count
        FROM books
        WHERE exclusive_shelf = 'read'
    """)).fetchone()

    to_read = db.execute(text("""
        SELECT COUNT(*) FROM books WHERE exclusive_shelf = 'to-read'
    """)).scalar()

    return {
        "total_books": row[0],
        "total_pages": row[1],
        "avg_rating": float(row[2]) if row[2] else None,
        "reread_count": row[3],
        "to_read_count": to_read,
    }


def get_top_books_for_ai(db: Session, target: int = 10) -> list[dict]:
    """
    Return top-rated books for use as AI recommendation context.
    Waterfall: 5-star → 4-star → 3-star → most recently read.
    Ensures we always have something useful to send to Gemini.
    """
    for min_rating in [5, 4, 3]:
        rows = db.execute(text("""
            SELECT title, author, my_rating
            FROM books
            WHERE exclusive_shelf = 'read'
              AND my_rating >= :min_rating
            ORDER BY my_rating DESC, date_read DESC NULLS LAST
            LIMIT :limit
        """), {"min_rating": min_rating, "limit": target}).fetchall()
        if rows:
            return [{"title": r[0], "author": r[1], "rating": r[2]} for r in rows]

    # No rated books — fall back to most recently read
    rows = db.execute(text("""
        SELECT title, author, my_rating
        FROM books
        WHERE exclusive_shelf = 'read'
        ORDER BY date_read DESC NULLS LAST
        LIMIT :limit
    """), {"limit": target}).fetchall()
    return [{"title": r[0], "author": r[1], "rating": r[2]} for r in rows]
