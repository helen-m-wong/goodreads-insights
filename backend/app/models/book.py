from sqlalchemy import (
    Column, Integer, SmallInteger, Text, Numeric, Date, DateTime,
    ForeignKey, func
)
from app.database import Base


class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True)
    goodreads_id = Column(Integer, unique=True)
    title = Column(Text, nullable=False)
    author = Column(Text)
    additional_authors = Column(Text)
    isbn = Column(Text)
    isbn13 = Column(Text)
    my_rating = Column(SmallInteger)        # 0 = not rated, 1-5 = user rating
    avg_rating = Column(Numeric(3, 2))
    publisher = Column(Text)
    num_pages = Column(Integer)
    year_published = Column(SmallInteger)
    original_pub_year = Column(SmallInteger)
    date_read = Column(Date)
    date_added = Column(Date)
    exclusive_shelf = Column(Text)          # 'read', 'to-read', 'currently-reading'
    my_review = Column(Text)
    read_count = Column(SmallInteger, default=0)  # populated directly from CSV


class Genre(Base):
    __tablename__ = "genres"

    id = Column(Integer, primary_key=True)
    name = Column(Text, unique=True, nullable=False)


class BookGenre(Base):
    __tablename__ = "book_genres"

    book_id = Column(Integer, ForeignKey("books.id", ondelete="CASCADE"), primary_key=True)
    genre_id = Column(Integer, ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True)


class ReaderSummary(Base):
    __tablename__ = "reader_summary"

    id = Column(Integer, primary_key=True)
    library_hash = Column(Text, unique=True)
    summary_text = Column(Text)
    recommendations_json = Column(Text)     # cached JSON string
    created_at = Column(DateTime, server_default=func.now())
