class RAGException(Exception):
    """Base exception for the Hybrid RAG platform."""
    pass

class ScrapingError(RAGException):
    """Raised when the URL cannot be fetched or parsed."""
    pass

class DatabaseConnectionError(RAGException):
    """Raised when PostgreSQL is unreachable."""
    pass

class LLMGenerationError(RAGException):
    """Raised when the text generation API fails."""
    pass