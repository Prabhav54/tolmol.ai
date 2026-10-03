import html
import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator


def clean_text(value: Optional[str]) -> Optional[str]:
    """Unescapes HTML entities and collapses whitespace left behind by scraped markup."""
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", html.unescape(str(value))).strip()
    return cleaned or None


class ProductData(BaseModel):
    """A single catalog product, as produced by the scraper or supplied by a bulk import."""

    url: str
    title: str
    price: Optional[float] = Field(default=None, ge=0)
    currency: str = "INR"
    rating: Optional[float] = Field(default=None, ge=0, le=5)
    rating_count: Optional[int] = Field(default=None, ge=0)
    brand: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    in_stock: Optional[bool] = None
    platform: Optional[str] = None

    @field_validator("title", "brand", "category", "description", mode="before")
    @classmethod
    def _clean(cls, value):
        return clean_text(value)

    @field_validator("currency", mode="before")
    @classmethod
    def _currency(cls, value):
        return (clean_text(value) or "INR").upper()

    def embedding_text(self) -> str:
        """The text that represents this product in vector space."""
        parts = [self.title]
        if self.brand:
            parts.append(f"Brand: {self.brand}")
        if self.category:
            parts.append(f"Category: {self.category}")
        if self.description:
            parts.append(self.description[:2000])
        return "\n".join(parts)
