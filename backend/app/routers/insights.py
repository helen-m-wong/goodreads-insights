from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import insights as svc

router = APIRouter()


@router.get("/books-per-year")
def books_per_year(db: Session = Depends(get_db)):
    return svc.books_per_year(db)


@router.get("/genres")
def genre_breakdown(db: Session = Depends(get_db)):
    return svc.genre_breakdown(db)


@router.get("/ratings")
def rating_distribution(db: Session = Depends(get_db)):
    return svc.rating_distribution(db)


@router.get("/top-authors")
def top_authors(db: Session = Depends(get_db)):
    return svc.top_authors(db)


@router.get("/reading-pace")
def reading_pace(db: Session = Depends(get_db)):
    return svc.reading_pace(db)


@router.get("/heatmap")
def reading_heatmap(db: Session = Depends(get_db)):
    return svc.reading_heatmap(db)


@router.get("/top-rated")
def top_rated_books(db: Session = Depends(get_db)):
    return svc.top_rated_books(db)


@router.get("/page-extremes")
def page_extremes(db: Session = Depends(get_db)):
    return svc.page_extremes(db)


@router.get("/summary")
def summary_stats(db: Session = Depends(get_db)):
    return svc.summary_stats(db)
