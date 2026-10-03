from scraper.dedup import detect_platform, normalize_url, url_hash


def test_amazon_urls_collapse_to_asin():
    a = "https://www.amazon.in/Nike-Revolution-Running-Shoe/dp/B0CHX1W1XY/ref=sr_1_3?keywords=nike&qid=1&sr=8-3"
    b = "amazon.in/dp/b0chx1w1xy"
    assert normalize_url(a) == "https://amazon.in/dp/B0CHX1W1XY"
    assert url_hash(a) == url_hash(b)


def test_tracking_params_fragments_and_case_are_ignored():
    a = "https://WWW.Flipkart.com/shoe/p/itm123?pid=SHOE42&lid=LST1&marketplace=FLIPKART&utm_source=x#reviews"
    b = "https://flipkart.com/shoe/p/itm123/?pid=SHOE42"
    assert url_hash(a) == url_hash(b)


def test_different_products_differ():
    assert url_hash("https://flipkart.com/p/itm1?pid=A") != url_hash("https://flipkart.com/p/itm1?pid=B")


def test_hash_is_sha256_hex():
    digest = url_hash("https://myntra.com/shirts/123/buy")
    assert len(digest) == 64 and int(digest, 16) >= 0


def test_detect_platform():
    assert detect_platform("https://www.myntra.com/x") == "Myntra"
    assert detect_platform("https://shop.example.com/x") == "Generic Retailer"
