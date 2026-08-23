from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    doc_id = Column(String, unique=True, index=True)
    title = Column(String, default="")
    filename = Column(String, default="")
    category = Column(String, default="")
    source = Column(String, default="")
    method = Column(String, default="")
    update_date = Column(String, default="")
    permission = Column(String, default="")
    owner = Column(String, default="")
    status = Column(String, default="")
    remark = Column(String, default="")
    source_url = Column(String, default="")
    license = Column(String, default="")
    file_path = Column(String, default="")
    imported_at = Column(DateTime, default=datetime.utcnow)

    chunks = relationship(
        "Chunk", back_populates="document", cascade="all, delete-orphan"
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True)
    document_id = Column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    chunk_index = Column(Integer, default=0)
    heading = Column(String, default="")
    content = Column(Text, default="")
    char_count = Column(Integer, default=0)

    document = relationship("Document", back_populates="chunks")


class ChatLog(Base):
    __tablename__ = "chat_logs"

    id = Column(Integer, primary_key=True)
    question = Column(Text, default="")
    answer = Column(Text, default="")
    refused = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
