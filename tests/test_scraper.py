import pytest

from core.exceptions import ScrapingError
from scraper.parser import extract_product, parse_price

JSON_LD_PAGE = """
<html><head><title>ignored</title>
<script type="application/ld+json">
{"@context": "https://schema.org", "@graph": [
  {"@type": "BreadcrumbList"},
  {"@type": "Product", "name": "Campus  North Plus Running Shoes", "brand": {"@type": "Brand", "name": "Campus"},
   "category": "Running Shoes", "description": "Lightweight &amp; breathable mesh upper.",
   "image": ["https://img.example.com/1.jpg"],
   "offers": {"@type": "Offer", "price": "1,299.00", "priceCurrency": "INR", "availability": "https://schema.org/InStock"},
   "aggregateRating": {"ratingValue": "4.3", "reviewCount": "2,315"}}
]}
</script></head><body></body></html>
"""

META_PAGE = """
<html><head>
<meta property="og:title" content="Cotton Kurta">
<meta property="og:description" content="Straight cut kurta">
<meta property="product:price:amount" content="899">
<meta property="product:price:currency" content="INR">
</head><body></body></html>
"""


def test_json_ld_extraction():
    product = extract_product(JSON_LD_PAGE, "https://www.flipkart.com/p/itm1?pid=X", use_llm=False)
    assert product.title == "Campus North Plus Running Shoes"
    assert product.brand == "Campus"
    assert product.price == 1299.0
    assert product.rating == 4.3 and product.rating_count == 2315
    assert product.in_stock is True
    assert product.platform == "Flipkart"
    assert product.description == "Lightweight & breathable mesh upper."


def test_meta_tag_fallback():
    product = extract_product(META_PAGE, "https://www.myntra.com/kurta/1/buy", use_llm=False)
    assert product.title == "Cotton Kurta" and product.price == 899.0 and product.platform == "Myntra"


def test_page_without_product_raises():
    with pytest.raises(ScrapingError):
        extract_product("<html><body>Robot check</body></html>", "https://amazon.in/dp/X", use_llm=False)


@pytest.mark.parametrize("raw, expected", [("₹1,299.00", 1299.0), ("Rs. 999", 999.0), (450, 450.0), ("free", None)])
def test_parse_price(raw, expected):
    assert parse_price(raw) == expected
