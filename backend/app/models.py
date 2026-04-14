from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from .database import Base

# NOTE: The search_vector (TSVECTOR) column is NOT defined here because it is
# a PostgreSQL-specific type and would crash on SQLite.
# For PostgreSQL deployments, main.py adds it via raw SQL after table creation.
# For SQLite deployments, search falls back to LIKE queries.


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
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
