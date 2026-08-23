from __future__ import annotations

import math
import re

import jieba

from app.database import SessionLocal
from app.models import Chunk, Document

K1 = 1.5
B = 0.75
DEFAULT_TOP_K = 5

PUNCTUATION_ONLY = re.compile(r"^\W+$")


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

    def search(self, query: str, top_k: int = DEFAULT_TOP_K) -> list[dict]:
        self.ensure_loaded()
        query_tokens = self.tokenize(query)
        scores = {}
        for cid in self.chunk_meta:
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


index = BM25Index()


def build_index() -> BM25Index:
    index.load()
    return index


def search(query: str, top_k: int = DEFAULT_TOP_K) -> list[dict]:
    return index.search(query, top_k)
