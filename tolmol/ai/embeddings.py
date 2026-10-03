import time
from functools import lru_cache
from typing import List, Tuple

from tolmol.ai.llm import gemini_client
from tolmol.config import settings
from tolmol.errors import ProviderError
from tolmol.logger import get_logger

logger = get_logger(__name__)


def _embed(texts: List[str], task_type: str, retries: int) -> List[List[float]]:
    from google.genai import errors, types

    vectors: List[List[float]] = []
    for start in range(0, len(texts), settings.EMBED_BATCH_SIZE):
        batch = texts[start:start + settings.EMBED_BATCH_SIZE]
        for attempt in range(retries + 1):
            try:
                result = gemini_client().models.embed_content(
                    model=settings.GEMINI_EMBEDDING_MODEL,
                    contents=batch,
                    config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=settings.EMBEDDING_DIM),
                )
                break
            except errors.ClientError as exc:
                # The free tier counts every text in a batch against a per-minute quota.
                if exc.code != 429 or attempt == retries:
                    raise ProviderError(f"Embedding request failed: {exc}") from exc
                wait = 20 * (attempt + 1)
                logger.warning(f"Embedding quota hit; retrying in {wait}s ({attempt + 1}/{retries}).")
                time.sleep(wait)
            except ProviderError:
                raise
            except Exception as exc:
                raise ProviderError(f"Embedding request failed: {exc}") from exc
        vectors.extend(list(embedding.values) for embedding in result.embeddings)
    return vectors


def embed_documents(texts: List[str], retries: int = 1) -> List[List[float]]:
    return _embed(texts, "RETRIEVAL_DOCUMENT", retries) if texts else []


@lru_cache(maxsize=512)
def _embed_query_cached(text: str) -> Tuple[float, ...]:
    return tuple(_embed([text], "RETRIEVAL_QUERY", retries=0)[0])


def embed_query(text: str) -> List[float]:
    return list(_embed_query_cached(text.strip().lower()))
