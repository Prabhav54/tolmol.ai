from tolmol.schemas import ProductIdentity
from tolmol.services.matching import match_score, model_keys, price_outliers


def test_model_keys():
    assert "wh1000xm5" in model_keys("Sony WH-1000XM5 Wireless")
    assert "s24" not in model_keys("S24")  # too short to be a reliable model code on its own
    assert not model_keys("128GB 5000mAh 120Hz")


def test_same_product_different_store_titles():
    score, note = match_score(
        "Sony WH-1000XM5 Wireless Noise Cancelling Headphones",
        "WH-1000XM5",
        "SONY WH-1000XM5 Bluetooth Headphone with Mic (Auto Noise Cancellation, Over Ear, Black)",
    )
    assert score >= 0.8 and note is None


def test_different_model_is_rejected():
    score, _ = match_score("Sony WH-1000XM5 Headphones", "WH-1000XM5", "Sony WH-1000XM4 Headphones")
    assert score < 0.45


def test_model_code_with_colour_suffix_still_matches():
    score, _ = match_score("Sony WH-1000XM5 Headphones", "WH-1000XM5", "Sony WH-1000XM5/B Wireless Headphones, Black")
    assert score >= 0.8


def test_edition_mismatch_is_rejected():
    score, _ = match_score("Samsung Galaxy S24 FE 5G (8GB, 128GB)", None, "Samsung Galaxy S24 Ultra 5G (12GB, 256GB)")
    assert score < 0.45


def test_storage_variant_is_flagged():
    score, note = match_score("Apple iPhone 15 (128 GB) - Black", None, "Apple iPhone 15 (256 GB) - Black")
    assert note == "Different variant: 256gb" and score < 0.75


def test_price_outlier_bounds():
    low, high = price_outliers([26990, 29990, 28990, 2999], anchor=27990)
    assert 2999 < low <= 26990 and high > 29990


def test_identity_key_is_store_independent():
    a = ProductIdentity(title="Sony WH-1000XM5 Headphones", brand="Sony", model_number="WH-1000XM5")
    b = ProductIdentity(title="SONY WH1000XM5 Black", brand="SONY", model_number="wh1000xm5")
    assert a.identity_key() == b.identity_key()
    c = ProductIdentity(title="boAt Rockerz 450", brand="boAt")
    d = ProductIdentity(title="Rockerz 450 boAt")
    assert c.identity_key() == d.identity_key()
