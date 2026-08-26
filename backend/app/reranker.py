from __future__ import annotations

import os

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

import numpy as np


class CrossEncoderReranker:
    MODEL_ID = "Xenova/bge-reranker-base"
    MODEL_FILENAME = "onnx/model_quantized.onnx"

    def __init__(self) -> None:
        self.session = None
        self.tokenizer = None
        self.input_names: list[str] = []
        self.output_names: list[str] = []

    def load(self) -> None:
        from huggingface_hub import hf_hub_download
        from onnxruntime import InferenceSession
        from tokenizers import Tokenizer

        model_path = hf_hub_download(repo_id=self.MODEL_ID, filename=self.MODEL_FILENAME)
        tokenizer_path = hf_hub_download(repo_id=self.MODEL_ID, filename="tokenizer.json")
        self.session = InferenceSession(model_path, providers=["CPUExecutionProvider"])
        self.tokenizer = Tokenizer.from_file(tokenizer_path)
        self.input_names = [item.name for item in self.session.get_inputs()]
        self.output_names = [item.name for item in self.session.get_outputs()]

    def score(self, query: str, text: str) -> float:
        encoding = self.tokenizer.encode(query, text)
        feed = {}
        if "input_ids" in self.input_names:
            feed["input_ids"] = np.array([encoding.ids], dtype=np.int64)
        if "attention_mask" in self.input_names:
            feed["attention_mask"] = np.array([encoding.attention_mask], dtype=np.int64)
        if "token_type_ids" in self.input_names:
            feed["token_type_ids"] = np.array([encoding.type_ids], dtype=np.int64)
        outputs = self.session.run(self.output_names, feed)
        return float(outputs[0][0][0])

    def rerank(self, query: str, candidates: list[dict]) -> list[dict]:
        scored = []
        for item in candidates:
            logit = self.score(query, item["content"])
            result = dict(item)
            result["rerank_score"] = logit
            scored.append(result)
        return scored
