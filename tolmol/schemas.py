import re
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from tolmol.scraping.urls import sha256_hex


class ProductCandidate(BaseModel):
    """A product as identified from a link, a search query or a photo."""

    title: str = Field(..., min_length=2, max_length=300)
    brand: Optional[str] = None
    model_number: Optional[str] = None
    variant: Optional[str] = Field(None, description="Storage / size / colour, e.g. '8GB/128GB, Blue'")
    category: Optional[str] = None
    image_url: Optional[str] = None
    approx_price: Optional[float] = None


class ProductIdentity(ProductCandidate):
    """A candidate plus what we learned from the page the shopper pasted (if any)."""

    source_url: Optional[str] = None
    source_platform: Optional[str] = None
    source_price: Optional[float] = None
    source_mrp: Optional[float] = None
    source_in_stock: Optional[bool] = None
    source_rating: Optional[float] = None
    source_is_live: bool = False  # True when the price was read from the store page itself

    def identity_key(self) -> str:
        """Same product -> same key, whichever store or link it came from."""

        def norm(value: Optional[str]) -> str:
            return re.sub(r"[^a-z0-9]+", "", (value or "").lower())

        if self.model_number and len(norm(self.model_number)) >= 4:
            basis = f"{norm(self.brand)}|{norm(self.model_number)}|{norm(self.variant)}"
        else:
            words = sorted(set(re.findall(r"[a-z0-9]+", f"{self.title} {self.variant or ''}".lower())))
            basis = "title|" + " ".join(words)
        return sha256_hex(basis)

    def search_name(self) -> str:
        parts = [self.title]
        if self.variant and self.variant.lower() not in self.title.lower():
            parts.append(f"({self.variant})")
        return " ".join(parts)


class CompareRequest(BaseModel):
    url: Optional[str] = Field(None, max_length=2000, examples=["https://www.amazon.in/dp/B09XS7JWHH"])
    product: Optional[ProductCandidate] = None
    refresh: bool = False

    @model_validator(mode="after")
    def _one_input(self):
        if bool(self.url) == bool(self.product):
            raise ValueError("Send either a product link (url) or a product picked from search results (product).")
        return self


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=200, examples=["joote 2000 ke andar", "iphone 15 128gb"])


class PhotoRequest(BaseModel):
    image_base64: str = Field(..., min_length=100, max_length=6_000_000)
    mime_type: str = "image/jpeg"

    @field_validator("mime_type")
    @classmethod
    def _image_type(cls, value: str) -> str:
        if value not in ("image/jpeg", "image/png", "image/webp"):
            raise ValueError("Upload a JPEG, PNG or WebP image.")
        return value


class ChatTurn(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., max_length=2000)


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    history: List[ChatTurn] = Field(default_factory=list, max_length=8)


class AlertRequest(BaseModel):
    email: str = Field(..., max_length=254)
    target_price: float = Field(..., gt=0)

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        value = value.strip()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Enter a valid email address.")
        return value


class ApiKeyRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    daily_limit: Optional[int] = Field(None, ge=1, le=1_000_000)
