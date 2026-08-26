from pydantic import BaseModel


class ChatRequest(BaseModel):
    question: str
    role: str = "employee"


class Citation(BaseModel):
    doc_id: str
    title: str
    heading: str
    content: str
    permission: str
    score: float


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    refused: bool


class DocumentItem(BaseModel):
    doc_id: str
    title: str
    category: str
    permission: str
    owner: str
    status: str
    filename: str
    chunk_count: int


class UploadResult(BaseModel):
    doc_id: str
    title: str
    chunk_count: int


class DeleteResult(BaseModel):
    deleted: bool


class ReindexResult(BaseModel):
    documents: int
    chunks: int


class Stats(BaseModel):
    documents: int
    chunks: int
    question_count: int
    categories: dict[str, int]
