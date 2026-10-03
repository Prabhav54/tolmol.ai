from tolmol.scraping.platforms import platform_by_name, platform_for_url, search_link, stores_for_category
from tolmol.scraping.urls import normalize_url, slug_title, url_hash


def test_platform_detection():
    assert platform_for_url("https://www.amazon.in/dp/B09XS7JWHH").name == "Amazon"
    assert platform_for_url("https://dl.flipkart.com/s/abc").name == "Flipkart"
    assert platform_for_url("https://evil-amazon.in.example.com/x") is None
    assert platform_for_url("https://www.croma.com/p/1").name == "Croma"


def test_platform_names_from_llm_output():
    assert platform_by_name("Amazon.in").name == "Amazon"
    assert platform_by_name("Reliance").name == "Reliance Digital"
    assert platform_by_name("Tata CLiQ").name == "Tata CLiQ"
    assert platform_by_name("Some Random Shop") is None


def test_search_links_are_encoded():
    link = search_link(platform_by_name("Flipkart"), "Sony WH-1000XM5 (Black)")
    assert link == "https://www.flipkart.com/search?q=Sony+WH-1000XM5+%28Black%29"


def test_store_selection_by_category():
    names = {p.name for p in stores_for_category("Running Shoes")}
    assert "Myntra" in names and "Croma" not in names
    names = {p.name for p in stores_for_category("Smartphones")}
    assert "Croma" in names and "Myntra" not in names


def test_url_normalization_and_hash():
    a = "https://www.amazon.in/Sony-WH-1000XM5-Cancelling/dp/B09XS7JWHH/ref=sr_1_3?keywords=sony&qid=1"
    assert normalize_url(a) == "https://amazon.in/dp/B09XS7JWHH"
    assert url_hash(a) == url_hash("amazon.in/dp/b09xs7jwhh")


def test_slug_title():
    url = "https://www.amazon.in/Sony-WH-1000XM5-Cancelling-Headphones/dp/B09XS7JWHH"
    assert slug_title(url) == "Sony WH 1000XM5 Cancelling Headphones"
    assert slug_title("https://www.amazon.in/dp/B09XS7JWHH") is None
