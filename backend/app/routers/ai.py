from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import ai_service

router = APIRouter()


@router.get("/reader-summary")
def reader_summary(db: Session = Depends(get_db)):
    """
    Returns the whimsical reader personality blurb + book recommendations.
    Cached in DB — regenerated only when the library changes.
    """
    return ai_service.get_reader_summary(db)


@router.get("/sentiment")
def review_sentiment(db: Session = Depends(get_db)):
    """
    HuggingFace sentiment analysis on the user's Goodreads reviews.
    Returns sentiment (positive/negative) and score per review.
    """
    return ai_service.get_sentiment_for_reviews(db)
