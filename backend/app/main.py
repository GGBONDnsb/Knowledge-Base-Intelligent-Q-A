from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from sqlalchemy import func

from app import retrieval
from app.agent_api import router as agent_router
from app.agent_data import ensure_demo_data
from app.auth import ensure_demo_accounts
from app.auth_api import router as auth_router
from app.config import DEEPSEEK_API_KEY
from app.database import SessionLocal, init_db
from app.documents_api import router as documents_router
from app.llm import build_messages, call_deepseek
from app.models import ChatLog, Chunk, Document
from app.schemas import ChatRequest, ChatResponse, Citation, Stats


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        ensure_demo_data(db)
        ensure_demo_accounts(db)
    finally:
        db.close()
    retrieval.build_index()
    yield


app = FastAPI(title="企业智能知识库问答系统", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(agent_router)


def _log_chat(question: str, answer: str, refused: bool) -> None:
    db = SessionLocal()
    try:
        db.add(ChatLog(question=question, answer=answer, refused=int(refused)))
        db.commit()
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
def chat(payload: ChatRequest):
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="问题不能为空")
    if not DEEPSEEK_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="未配置 DEEPSEEK_API_KEY，请在 backend/.env 中填写",
        )

    chunks = retrieval.search(question, top_k=5, role=payload.role)
    if not chunks:
        _log_chat(question, "", True)
        return ChatResponse(
            answer="知识库中没有找到相关内容。",
            citations=[],
            refused=True,
        )

    try:
        answer = call_deepseek(build_messages(question, chunks))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"模型调用失败: {exc}") from exc

    citations = [
        Citation(
            doc_id=item["doc_id"],
            title=item["title"],
            heading=item["heading"],
            content=item["content"],
            permission=item["permission"],
            score=item["score"],
        )
        for item in chunks
    ]
    _log_chat(question, answer, False)
    return ChatResponse(answer=answer, citations=citations, refused=False)


@app.get("/api/stats", response_model=Stats)
def stats():
    db = SessionLocal()
    try:
        documents = db.query(Document).count()
        chunks = db.query(Chunk).count()
        question_count = db.query(ChatLog).count()
        categories = dict(
            db.query(Document.category, func.count())
            .group_by(Document.category)
            .all()
        )
    finally:
        db.close()
    return Stats(
        documents=documents,
        chunks=chunks,
        question_count=question_count,
        categories=categories,
    )
