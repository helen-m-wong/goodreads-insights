import asyncio
from fastapi import APIRouter, UploadFile, File, Depends, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db
from app.services.csv_parser import parse_csv
from app.services.genre_service import enrich_genres_for_books

router = APIRouter()


def _upsert_books(books: list[dict], db: Session) -> None:
    """Insert or update books. On conflict (same goodreads_id), update all fields."""
    for book in books:
        db.execute(
            text("""
                INSERT INTO books (
                    goodreads_id, title, author, additional_authors, isbn, isbn13,
                    my_rating, avg_rating, publisher, num_pages, year_published,
                    original_pub_year, date_read, date_added, exclusive_shelf,
                    my_review, read_count
                ) VALUES (
                    :goodreads_id, :title, :author, :additional_authors, :isbn, :isbn13,
                    :my_rating, :avg_rating, :publisher, :num_pages, :year_published,
                    :original_pub_year, :date_read, :date_added, :exclusive_shelf,
                    :my_review, :read_count
                )
                ON CONFLICT (goodreads_id) DO UPDATE SET
                    title             = EXCLUDED.title,
                    author            = EXCLUDED.author,
                    additional_authors = EXCLUDED.additional_authors,
                    isbn              = EXCLUDED.isbn,
                    isbn13            = EXCLUDED.isbn13,
                    my_rating         = EXCLUDED.my_rating,
                    avg_rating        = EXCLUDED.avg_rating,
                    publisher         = EXCLUDED.publisher,
                    num_pages         = EXCLUDED.num_pages,
                    year_published    = EXCLUDED.year_published,
                    original_pub_year = EXCLUDED.original_pub_year,
                    date_read         = EXCLUDED.date_read,
                    date_added        = EXCLUDED.date_added,
                    exclusive_shelf   = EXCLUDED.exclusive_shelf,
                    my_review         = EXCLUDED.my_review,
                    read_count        = EXCLUDED.read_count
            """),
            {k: v for k, v in book.items() if k != "lookup_isbn"},
        )
    db.commit()


def _run_genre_enrichment(books: list[dict], db: Session) -> None:
    """Wrapper to run the async genre enrichment from a sync background task."""
    asyncio.run(enrich_genres_for_books(books, db))
    db.close()


@router.post("/upload")
async def upload_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a .csv")

    contents = await file.read()

    try:
        books = parse_csv(contents)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not parse CSV: {e}")

    _upsert_books(books, db)

    # Kick off genre enrichment in the background so the upload returns immediately
    from app.database import SessionLocal
    bg_db = SessionLocal()
    background_tasks.add_task(_run_genre_enrichment, books, bg_db)

    return {
        "status": "ok",
        "books_processed": len(books),
        "message": "Books imported. Genre enrichment running in background.",
    }
