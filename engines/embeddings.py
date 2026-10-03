from functools import lru_cache
from typing import List, Tuple

from core.config import settings
from core.exceptions import EmbeddingError, LLMGenerationError
from core.logger import get_logger
from engines.llm import gemini_client, hf_client

logger = get_logger(__name__)


def _embed_gemini(texts: List[str], task_type: str) -> List[List[float]]:
    from google.genai import types

    vectors: List[List[float]] = []
    for start in range(0, len(texts), settings.EMBED_BATCH_SIZE):
        batch = texts[start:start + settings.EMBED_BATCH_SIZE]
        result = gemini_client().models.embed_content(
            model=settings.GEMINI_EMBEDDING_MODEL,
            contents=batch,
            config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=settings.EMBEDDING_DIM),
        )
        vectors.extend(list(embedding.values) for embedding in result.embeddings)
    return vectors


def _embed_huggingface(texts: List[str]) -> List[List[float]]:
    client = hf_client()
    vectors = []
    for text in texts:
        output = client.feature_extraction(text, model=settings.HF_EMBEDDING_MODEL)
        vector = output.tolist() if hasattr(output, "tolist") else list(output)
        # Some models return one vector per token; mean-pool them into a sentence vector.
        if vector and isinstance(vector[0], list):
            vector = [sum(column) / len(vector) for column in zip(*vector)]
        vectors.append(vector)
    return vectors


def _embed(texts: List[str], task_type: str) -> List[List[float]]:
    if not texts:
        return []
    try:
        if settings.EMBEDDING_PROVIDER.lower() == "huggingface":
            vectors = _embed_huggingface(texts)
        else:
            vectors = _embed_gemini(texts, task_type)
    except LLMGenerationError as exc:
        raise EmbeddingError(str(exc)) from exc
    except Exception as exc:
        raise EmbeddingError(f"Embedding request failed: {exc}") from exc

    wrong_dim = next((len(vector) for vector in vectors if len(vector) != settings.EMBEDDING_DIM), None)
    if wrong_dim is not None:
        raise EmbeddingError(
            f"Embedding model returned {wrong_dim} dimensions, expected EMBEDDING_DIM={settings.EMBEDDING_DIM}."
        )
    return vectors


def embed_documents(texts: List[str]) -> List[List[float]]:
    return _embed(texts, "RETRIEVAL_DOCUMENT")


@lru_cache(maxsize=512)
def _embed_query_cached(text: str) -> Tuple[float, ...]:
    return tuple(_embed([text], "RETRIEVAL_QUERY")[0])


def embed_query(text: str, use_cache: bool = True) -> List[float]:
    normalized = text.strip().lower()
    if not use_cache:
        return _embed([normalized], "RETRIEVAL_QUERY")[0]
    return list(_embed_query_cached(normalized))
