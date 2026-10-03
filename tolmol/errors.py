class TolmolError(Exception):
    """Base exception for tolmol.ai."""


class ScrapingError(TolmolError):
    """A product page could not be fetched or understood."""


class ProductNotIdentified(TolmolError):
    """We could not work out which product a link, query or photo refers to."""


class ProviderError(TolmolError):
    """An AI provider (Gemini / Hugging Face) failed or is not configured."""


class DatabaseUnavailable(TolmolError):
    """PostgreSQL is unreachable or has an incompatible schema."""


class RateLimited(TolmolError):
    """The caller exceeded their request allowance."""


class NotFound(TolmolError):
    """A requested record does not exist."""
