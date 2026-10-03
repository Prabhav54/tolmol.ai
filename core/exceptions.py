class RAGException(Exception):
    """Base exception for the tolmol.ai platform."""


class ScrapingError(RAGException):
    """Raised when a URL cannot be fetched or parsed into a product."""


class DatabaseConnectionError(RAGException):
    """Raised when PostgreSQL is unreachable."""


class EmbeddingError(RAGException):
    """Raised when the embedding provider fails or is not configured."""


class LLMGenerationError(RAGException):
    """Raised when the text generation provider fails or is not configured."""
