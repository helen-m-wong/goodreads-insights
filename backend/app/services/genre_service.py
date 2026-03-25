import httpx
from sqlalchemy.orm import Session
from sqlalchemy import text

# Only skip genres that are truly meaningless noise
_SKIP_GENRES = {"general", "books", "e-books", "unspecified"}


def _normalize_genres(raw: list[str]) -> list[str]:
    """Title-case, deduplicate, and filter noise from a raw genre list."""
    seen = set()
    result = []
    for g in raw:
        # Google Books returns entries like "Fiction / Fantasy / Epic" — split on /
        for part in g.split("/"):
            name = part.strip().title()
            lower = name.lower()
            if name and lower not in _SKIP_GENRES and lower not in seen:
                seen.add(lower)
                result.append(name)
    return result


async def _fetch_google_books_by_isbn(isbn: str, client: httpx.AsyncClient) -> list[str]:
    try:
        resp = await client.get(
            f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}",
            timeout=8,
        )
        items = resp.json().get("items", [])
        if not items:
            return []
        return items[0].get("volumeInfo", {}).get("categories", [])
    except Exception:
        return []


async def _fetch_google_books_by_title_author(
    title: str, author: str, client: httpx.AsyncClient
) -> list[str]:
    try:
        query = f"intitle:{title}"
        if author:
            query += f"+inauthor:{author}"
        resp = await client.get(
            f"https://www.googleapis.com/books/v1/volumes?q={query}",
            timeout=8,
        )
        items = resp.json().get("items", [])
        if not items:
            return []
        return items[0].get("volumeInfo", {}).get("categories", [])
    except Exception:
        return []


async def _fetch_open_library_by_isbn(isbn: str, client: httpx.AsyncClient) -> list[str]:
    try:
        resp = await client.get(
            f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data",
            timeout=8,
        )
        data = resp.json().get(f"ISBN:{isbn}", {})
        subjects = data.get("subjects", [])
        return [s.get("name", "") for s in subjects if s.get("name")]
    except Exception:
        return []


async def _resolve_genres(book: dict, client: httpx.AsyncClient) -> list[str]:
    """
    Try multiple strategies to find genres for a book, in order of preference.
    Returns a normalized list of genre strings, or [] if none found.
    """
    isbn = book.get("lookup_isbn")
    title = book.get("title", "")
    author = book.get("author", "")

    # 1. Google Books by ISBN
    if isbn:
        raw = await _fetch_google_books_by_isbn(isbn, client)
        if raw:
            return _normalize_genres(raw)

        # 2. Open Library by ISBN (fallback)
        raw = await _fetch_open_library_by_isbn(isbn, client)
        if raw:
            return _normalize_genres(raw)

    # 3. Google Books by title + author (for books without ISBN)
    if title:
        raw = await _fetch_google_books_by_title_author(title, author, client)
        if raw:
            return _normalize_genres(raw)

    # No genres found — will be treated as Uncategorized on the frontend
    return []


async def enrich_genres_for_books(books: list[dict], db: Session) -> None:
    """
    For each book, fetch genres from external APIs and upsert into
    genres + book_genres tables. Idempotent — skips books that already
    have genres (safe to call on re-upload).
    """
    async with httpx.AsyncClient() as client:
        for book in books:
            goodreads_id = book.get("goodreads_id")
            if not goodreads_id:
                continue

            # Look up the book's internal DB id
            row = db.execute(
                text("SELECT id FROM books WHERE goodreads_id = :gid"),
                {"gid": goodreads_id},
            ).fetchone()
            if not row:
                continue
            book_id = row[0]

            # Skip if already enriched
            already_has_genres = db.execute(
                text("SELECT 1 FROM book_genres WHERE book_id = :bid LIMIT 1"),
                {"bid": book_id},
            ).fetchone()
            if already_has_genres:
                continue

            genres = await _resolve_genres(book, client)
            if not genres:
                continue

            # Upsert each genre and link to book
            for genre_name in genres:
                db.execute(
                    text("INSERT INTO genres (name) VALUES (:name) ON CONFLICT (name) DO NOTHING"),
                    {"name": genre_name},
                )
                db.execute(
                    text("""
                        INSERT INTO book_genres (book_id, genre_id)
                        SELECT :book_id, id FROM genres WHERE name = :name
                        ON CONFLICT DO NOTHING
                    """),
                    {"book_id": book_id, "name": genre_name},
                )

            db.commit()
