"""
AI features using Gemini Flash (generative) and HuggingFace (sentiment NLP).
All Gemini results are cached in the DB to minimize API calls.
"""
import hashlib
import json
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.config import settings
from app.services.insights import get_top_books_for_ai, summary_stats, genre_breakdown


def _library_hash(db: Session) -> str:
    """Generate a hash of the current library state to detect changes."""
    row = db.execute(text("""
        SELECT COUNT(*), MAX(date_added::TEXT), MAX(my_rating::TEXT)
        FROM books
    """)).fetchone()
    fingerprint = f"{row[0]}|{row[1]}|{row[2]}"
    return hashlib.md5(fingerprint.encode()).hexdigest()


def _get_cached_summary(db: Session, lib_hash: str) -> dict | None:
    row = db.execute(
        text("SELECT summary_text, recommendations_json FROM reader_summary WHERE library_hash = :h"),
        {"h": lib_hash},
    ).fetchone()
    if row:
        recs = json.loads(row[1]) if row[1] else []
        return {"summary": row[0], "recommendations": recs}
    return None


def _save_to_cache(db: Session, lib_hash: str, summary: str, recommendations: list) -> None:
    db.execute(
        text("""
            INSERT INTO reader_summary (library_hash, summary_text, recommendations_json)
            VALUES (:h, :s, :r)
            ON CONFLICT (library_hash) DO UPDATE
            SET summary_text = EXCLUDED.summary_text,
                recommendations_json = EXCLUDED.recommendations_json
        """),
        {"h": lib_hash, "s": summary, "r": json.dumps(recommendations)},
    )
    db.commit()


def _build_reader_context(db: Session) -> dict:
    """Collect stats to feed into the Gemini prompt."""
    stats = summary_stats(db)
    top_books = get_top_books_for_ai(db, target=10)
    genres = genre_breakdown(db)[:5]  # top 5 genres

    # Longest book
    longest = db.execute(text("""
        SELECT title, author, num_pages FROM books
        WHERE exclusive_shelf = 'read' AND num_pages IS NOT NULL
        ORDER BY num_pages DESC LIMIT 1
    """)).fetchone()

    return {
        "total_books": stats["total_books"],
        "total_pages": stats["total_pages"],
        "avg_rating": stats["avg_rating"],
        "reread_count": stats["reread_count"],
        "top_genres": [g["genre"] for g in genres],
        "top_books": top_books,
        "longest_book": {"title": longest[0], "author": longest[1], "pages": longest[2]} if longest else None,
    }


def _call_gemini(prompt: str) -> str:
    """Call Gemini Flash and return the text response."""
    import google.generativeai as genai
    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)
    return response.text.strip()


def get_reader_summary(db: Session) -> dict:
    """
    Return the whimsical reader personality blurb + 5 book recommendations.
    Served from DB cache if library hasn't changed; generates via Gemini Flash otherwise.
    Returns {"summary": str, "recommendations": list} or error message if no data.
    """
    # Check if there are enough read books to generate a meaningful summary
    total = db.execute(
        text("SELECT COUNT(*) FROM books WHERE exclusive_shelf = 'read'")
    ).scalar()
    if not total:
        return {
            "summary": None,
            "recommendations": [],
            "message": "Upload your Goodreads library to see your reader personality.",
        }

    lib_hash = _library_hash(db)
    cached = _get_cached_summary(db, lib_hash)
    if cached:
        return cached

    if not settings.gemini_api_key:
        return {
            "summary": None,
            "recommendations": [],
            "message": "Add a GEMINI_API_KEY to your .env to enable AI features.",
        }

    ctx = _build_reader_context(db)

    # --- Reader personality blurb ---
    top_books_text = ", ".join(
        f'"{b["title"]}" by {b["author"]}' for b in ctx["top_books"][:5]
    )
    genres_text = ", ".join(ctx["top_genres"]) if ctx["top_genres"] else "a variety of genres"

    blurb_prompt = f"""You are a warm, witty librarian writing a 2-3 sentence personality profile
for a reader. Be playful and specific — reference their actual reading habits.

Reader stats:
- Books read: {ctx['total_books']}
- Pages read: {ctx['total_pages']:,}
- Average rating they give: {ctx['avg_rating'] or 'not rated yet'} / 5
- Re-reads: {ctx['reread_count']}
- Favourite genres: {genres_text}
- Some of their top-rated books: {top_books_text}
{"- Longest book they tackled: " + ctx['longest_book']['title'] + " (" + str(ctx['longest_book']['pages']) + " pages)" if ctx['longest_book'] else ""}

Write only the personality blurb. No preamble, no sign-off."""

    summary = _call_gemini(blurb_prompt)

    # --- Book recommendations ---
    rec_prompt = f"""You are a knowledgeable librarian recommending books to a reader.

Their top-rated books: {top_books_text}
Their favourite genres: {genres_text}

Recommend exactly 5 books they haven't read yet. For each, provide:
- title
- author
- a one-sentence reason why they'll love it

Respond ONLY with a JSON array in this format, no markdown:
[{{"title": "...", "author": "...", "reason": "..."}}]"""

    try:
        rec_text = _call_gemini(rec_prompt)
        # Strip any accidental markdown code fences
        rec_text = rec_text.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        recommendations = json.loads(rec_text)
    except Exception:
        recommendations = []

    _save_to_cache(db, lib_hash, summary, recommendations)
    return {"summary": summary, "recommendations": recommendations}


def get_sentiment_for_reviews(db: Session) -> list[dict]:
    """
    Run HuggingFace sentiment analysis on user reviews.
    Returns list of {date_read, title, sentiment, score} for reviews that exist.
    Runs locally — no API cost.
    """
    rows = db.execute(text("""
        SELECT title, my_review, date_read::TEXT
        FROM books
        WHERE exclusive_shelf = 'read'
          AND my_review IS NOT NULL
          AND my_review != ''
          AND date_read IS NOT NULL
        ORDER BY date_read
    """)).fetchall()

    if not rows:
        return []

    try:
        from transformers import pipeline
        sentiment_pipe = pipeline(
            "sentiment-analysis",
            model="distilbert-base-uncased-finetuned-sst-2-english",
            truncation=True,
            max_length=512,
        )
    except Exception:
        return []

    results = []
    for title, review, date_read in rows:
        try:
            out = sentiment_pipe(review[:512])[0]
            results.append({
                "title": title,
                "date_read": date_read,
                "sentiment": out["label"].lower(),   # "positive" or "negative"
                "score": round(out["score"], 3),
            })
        except Exception:
            continue

    return results
