from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path

import jieba
import numpy as np

from app.database import SessionLocal
from app.models import Chunk, Document
from app.reranker import CrossEncoderReranker

K1 = 1.5
B = 0.75
DEFAULT_TOP_K = 5
RRF_K = 60
HYBRID_CANDIDATES = 20
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
ROLE_PERMISSIONS = {
    "employee": {"全员"},
    "department": {"全员", "部门"},
    "admin": {"全员", "部门", "管理员"},
}

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

PUNCTUATION_ONLY = re.compile(r"^\W+$")
CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "embeddings"


class BM25Index:
    def __init__(self) -> None:
        self.loaded = False
        self.chunk_count = 0
        self.avgdl = 0.0
        self.chunk_len = {}
        self.chunk_meta = {}
        self.doc_freq = {}
        self.term_tf = {}

    def tokenize(self, text: str) -> list[str]:
        tokens = []
        for token in jieba.cut(text.lower()):
            token = token.strip()
            if not token or PUNCTUATION_ONLY.match(token):
                continue
            tokens.append(token)
        return tokens

    def load(self) -> None:
        db = SessionLocal()
        try:
            rows = (
                db.query(Chunk, Document)
                .join(Document, Chunk.document_id == Document.id)
                .all()
            )
        finally:
            db.close()

        self.chunk_count = 0
        total_len = 0
        self.chunk_len = {}
        self.chunk_meta = {}
        self.doc_freq = {}
        self.term_tf = {}

        for chunk, doc in rows:
            cid = chunk.id
            tokens = self.tokenize(chunk.content)
            tf = {}
            for token in tokens:
                tf[token] = tf.get(token, 0) + 1

            self.chunk_count += 1
            total_len += len(tokens)
            self.chunk_len[cid] = len(tokens)
            self.chunk_meta[cid] = {
                "chunk_id": cid,
                "doc_id": doc.doc_id,
                "title": doc.title,
                "category": doc.category,
                "permission": doc.permission,
                "heading": chunk.heading,
                "content": chunk.content,
                "char_count": chunk.char_count,
            }
            for token, count in tf.items():
                self.doc_freq[token] = self.doc_freq.get(token, 0) + 1
                self.term_tf.setdefault(token, {})[cid] = count

        self.avgdl = total_len / self.chunk_count if self.chunk_count else 0.0
        self.loaded = True

    def ensure_loaded(self) -> None:
        if not self.loaded:
            self.load()

    def _score_chunk(self, cid: int, query_tokens: list[str]) -> float:
        length = self.chunk_len.get(cid, 0)
        score = 0.0
        for token in query_tokens:
            posting = self.term_tf.get(token)
            if posting is None or cid not in posting:
                continue
            tf = posting[cid]
            df = self.doc_freq.get(token, 0)
            idf = math.log(1 + (self.chunk_count - df + 0.5) / (df + 0.5))
            if self.avgdl:
                denom = tf + K1 * (1 - B + B * length / self.avgdl)
            else:
                denom = tf + K1
            score += idf * (tf * (K1 + 1)) / denom
        return score

    def search(self, query: str, top_k: int = DEFAULT_TOP_K, role: str = "employee") -> list[dict]:
        self.ensure_loaded()
        allowed = ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS["employee"])
        query_tokens = self.tokenize(query)
        scores = {}
        for cid in self.chunk_meta:
            if self.chunk_meta[cid]["permission"] not in allowed:
                continue
            score = self._score_chunk(cid, query_tokens)
            if score > 0:
                scores[cid] = score
        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:top_k]
        results = []
        for cid, score in ranked:
            result = dict(self.chunk_meta[cid])
            result["score"] = round(score, 4)
            results.append(result)
        return results


class VectorIndex:
    def __init__(self) -> None:
        self.loaded = False
        self.chunk_ids: list[int] = []
        self.matrix: np.ndarray | None = None
        self._model = None

    def _get_model(self):
        if self._model is None:
            from fastembed import TextEmbedding

            self._model = TextEmbedding(model_name=EMBEDDING_MODEL)
        return self._model

    def _collect_chunks(self) -> list[tuple[int, str]]:
        db = SessionLocal()
        try:
            rows = db.query(Chunk.id, Chunk.content).all()
        finally:
            db.close()
        return [(cid, content) for cid, content in rows]

    def load(self) -> None:
        chunks = self._collect_chunks()
        ids = [cid for cid, _ in chunks]
        cache_path = CACHE_DIR / "chunks.npy"
        ids_path = CACHE_DIR / "chunk_ids.json"

        if cache_path.exists() and ids_path.exists():
            cached_ids = json.loads(ids_path.read_text(encoding="utf-8"))
            if cached_ids == ids:
                self.chunk_ids = ids
                self.matrix = np.load(cache_path)
                self.loaded = True
                return

        model = self._get_model()
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        contents = [content for _, content in chunks]
        if contents:
            embeddings = list(model.embed(contents))
            self.matrix = np.asarray(embeddings, dtype=np.float32)
        else:
            self.matrix = None
        self.chunk_ids = ids
        if self.matrix is not None:
            np.save(cache_path, self.matrix)
        ids_path.write_text(json.dumps(ids), encoding="utf-8")
        self.loaded = True

    def search(self, query: str, top_k: int = DEFAULT_TOP_K) -> list[dict]:
        if not self.loaded or self.matrix is None or self.matrix.shape[0] == 0:
            return []
        model = self._get_model()
        query_vec = np.asarray(list(model.query_embed(query)), dtype=np.float32)[0]
        q_norm = np.linalg.norm(query_vec)
        if q_norm == 0:
            return []
        norms = np.linalg.norm(self.matrix, axis=1)
        scores = (self.matrix @ query_vec) / (norms * q_norm + 1e-9)
        order = np.argsort(-scores)[:top_k]
        results = []
        for pos in order:
            results.append(
                {
                    "chunk_id": int(self.chunk_ids[pos]),
                    "score": float(scores[pos]),
                }
            )
        return results


class HybridIndex:
    def __init__(self) -> None:
        self.bm25 = BM25Index()
        self.vector = VectorIndex()
        self.vector_enabled = False
        self.reranker = CrossEncoderReranker()
        self.rerank_enabled = False
        self.loaded = False

    def load(self) -> None:
        self.bm25.load()
        try:
            self.vector.load()
            self.vector_enabled = True
        except Exception as exc:
            print(f"[hybrid] vector search disabled: {exc}")
            self.vector_enabled = False
        try:
            self.reranker.load()
            self.rerank_enabled = True
        except Exception as exc:
            print(f"[hybrid] reranker disabled: {exc}")
            self.rerank_enabled = False
        self.loaded = True

    def ensure_loaded(self) -> None:
        if not self.loaded:
            self.load()

    def _rrf_merge(self, bm25_hits: list[dict], vec_hits: list[dict], top_k: int) -> list[dict]:
        scores = {}
        for rank, item in enumerate(bm25_hits):
            cid = item["chunk_id"]
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (RRF_K + rank + 1)
        for rank, item in enumerate(vec_hits):
            cid = item["chunk_id"]
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (RRF_K + rank + 1)
        ranked = sorted(scores.items(), key=lambda pair: pair[1], reverse=True)[:top_k]
        results = []
        for cid, score in ranked:
            meta = self.bm25.chunk_meta.get(cid)
            if meta is None:
                continue
            result = dict(meta)
            result["score"] = round(score, 6)
            results.append(result)
        return results

    def _fuse_scores(self, items: list[dict]) -> list[dict]:
        if not items:
            return items
        rrf_scores = [item["score"] for item in items]
        rerank_scores = [item["rerank_score"] for item in items]
        rrf_min, rrf_max = min(rrf_scores), max(rrf_scores)
        rr_min, rr_max = min(rerank_scores), max(rerank_scores)

        def normalize(value: float, low: float, high: float) -> float:
            if high > low:
                return (value - low) / (high - low)
            return 1.0

        for item, rrf_score, rr_score in zip(items, rrf_scores, rerank_scores):
            item["score"] = round(
                0.5 * normalize(rrf_score, rrf_min, rrf_max)
                + 0.5 * normalize(rr_score, rr_min, rr_max),
                6,
            )
        items.sort(key=lambda item: item["score"], reverse=True)
        return items

    def search(self, query: str, top_k: int = DEFAULT_TOP_K, role: str = "employee") -> list[dict]:
        self.ensure_loaded()
        allowed = ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS["employee"])
        bm25_hits = self.bm25.search(query, top_k=HYBRID_CANDIDATES, role=role)
        if not self.vector_enabled:
            return bm25_hits[:top_k]
        vec_hits = self.vector.search(query, top_k=HYBRID_CANDIDATES)
        vec_hits = [
            hit for hit in vec_hits
            if self.bm25.chunk_meta.get(hit["chunk_id"], {}).get("permission") in allowed
        ]
        merged = self._rrf_merge(bm25_hits, vec_hits, HYBRID_CANDIDATES)
        if self.rerank_enabled and merged:
            merged = self.reranker.rerank(query, merged)
            merged = self._fuse_scores(merged)
        merged = [item for item in merged if item["permission"] in allowed]
        return merged[:top_k]


index = HybridIndex()


def build_index() -> HybridIndex:
    index.load()
    return index


def search(query: str, top_k: int = DEFAULT_TOP_K, role: str = "employee") -> list[dict]:
    return index.search(query, top_k, role=role)
