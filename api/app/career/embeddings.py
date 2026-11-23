"""Gemini text embeddings used by the public opportunity index."""
import json
import math
import os
import re
from functools import lru_cache
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class EmbeddingUnavailable(Exception):
    pass


def normalize(values, dimensions):
    if not isinstance(values, list) or len(values) != dimensions:
        raise EmbeddingUnavailable("임베딩 차원이 일치하지 않아요.")
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in values):
        raise EmbeddingUnavailable("임베딩 값이 유효하지 않아요.")
    length = math.sqrt(sum(value * value for value in values))
    if length == 0:
        raise EmbeddingUnavailable("빈 임베딩 벡터예요.")
    return [value / length for value in values]


class GeminiEmbeddings:
    def __init__(self, api_key, model="gemini-embedding-001", dimensions=768):
        if not re.fullmatch(r"gemini-embedding-[a-z0-9.-]+", model) or not 128 <= dimensions <= 3072:
            raise ValueError("임베딩 모델 또는 차원을 확인하세요.")
        self.api_key, self.model, self.dimensions = api_key, model, dimensions

    def embed(self, texts, *, query=False):
        requests = [{
            "model": "models/" + self.model,
            "content": {"parts": [{"text": text}]},
            "taskType": "RETRIEVAL_QUERY" if query else "RETRIEVAL_DOCUMENT",
            "outputDimensionality": self.dimensions,
        } for text in texts]
        if self.model.startswith("gemini-embedding-2"):
            for item, text in zip(requests, texts):
                item.pop("taskType")
                item["content"]["parts"][0]["text"] = (
                    "task: search result | query: " + text if query else "title: none | text: " + text)
        body = json.dumps({"requests": requests}, ensure_ascii=False).encode()
        request = Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:batchEmbedContents",
            data=body, headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key})
        try:
            with urlopen(request, timeout=8) as response:
                data = json.load(response)
            embeddings = data["embeddings"]
            if len(embeddings) != len(texts):
                raise EmbeddingUnavailable("임베딩 응답 개수가 달라요.")
            return [normalize(item["values"], self.dimensions) for item in embeddings]
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError, TypeError):
            raise EmbeddingUnavailable("임베딩 서비스를 사용할 수 없어요.") from None

    @lru_cache(maxsize=128)
    def query(self, text):
        return self.embed([text], query=True)[0]


def configured_embeddings():
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    return GeminiEmbeddings(key, os.environ.get("CAREER_EMBEDDING_MODEL", "gemini-embedding-001"),
                            int(os.environ.get("CAREER_EMBEDDING_DIMENSIONS", "768")))

