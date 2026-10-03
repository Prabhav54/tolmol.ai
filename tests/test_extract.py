import pytest

from tolmol.ai.llm import extract_json
from tolmol.errors import ProviderError
from tolmol.scraping.extract import extract_product, parse_price

JSON_LD = """<html><head><script type="application/ld+json">
{"@context": "https://schema.org", "@graph": [{"@type": "BreadcrumbList"},
 {"@type": "Product", "name": "Sony  WH-1000XM5", "mpn": "WH1000XM5/B", "brand": {"name": "Sony"},
  "image": ["https://img.example.com/1.jpg"],
  "offers": {"@type": "Offer", "price": "26,990.00", "priceCurrency": "INR", "availability": "https://schema.org/InStock"},
  "aggregateRating": {"ratingValue": "4.4", "reviewCount": "1,203"}}]}
</script></head></html>"""


def test_json_ld():
    product = extract_product(JSON_LD)
    assert product.title == "Sony WH-1000XM5" and product.model_number == "WH1000XM5/B"
    assert product.price == 26990.0 and product.in_stock is True and product.rating_count == 1203


def test_blocked_page_returns_none():
    assert extract_product("<html><head><title>Robot Check</title></head></html>") is None


@pytest.mark.parametrize("raw, expected", [("₹1,299.00", 1299.0), ("Rs. 999", 999.0), (450, 450.0), ("n/a", None)])
def test_parse_price(raw, expected):
    assert parse_price(raw) == expected


def test_extract_json_from_fenced_reply():
    fence = "`" * 3
    assert extract_json(f"Here you go:\n{fence}json\n[{{\"a\": 1}}]\n{fence}") == [{"a": 1}]
    assert extract_json('prefix {"b": [1, 2]} suffix') == {"b": [1, 2]}
    with pytest.raises(ProviderError):
        extract_json("no json here")
