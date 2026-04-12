from sqlalchemy import Column, Integer, String, Text, DateTime, Index, Float
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.sql import func
from .database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    content = Column(Text, default="")
    url = Column(String(1000), unique=True, nullable=False)
    category = Column(String(200), default="")
    document_type = Column(String(100), default="regulation")
    published_date = Column(String(50), default="")
    source_id = Column(String(200), default="")
    # PostgreSQL full-text search vector (populated via trigger)
    search_vector = Column(TSVECTOR)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        # GIN index on search_vector for fast FTS
        Index("idx_documents_search_vector", "search_vector", postgresql_using="gin"),
        # Trigram index on title for autocomplete / fuzzy title matching
        Index(
            "idx_documents_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
    )
