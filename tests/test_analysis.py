from tolmol.services.analysis import analyze


def snaps(rows):
    return [{"platform": p, "price": price, "captured_at": f"2026-09-{day:02d}T10:00:00+00:00"} for day, p, price in rows]


def test_best_deal_and_savings():
    current = [{"platform": "Amazon", "price": 26990, "mrp": 34990}, {"platform": "Croma", "price": 29990, "mrp": None}]
    result = analyze(current, snaps([(1, "Amazon", 26990), (1, "Croma", 29990)]))
    assert result["best"] == {"platform": "Amazon", "price": 26990}
    assert result["savings"] == 3000 and result["savings_pct"] == 10.0
    assert result["discount_pct"] == 22.9
    assert result["verdict"]["label"] == "Tracking started"


def test_great_time_to_buy_at_record_low():
    history = snaps([(1, "Amazon", 30000), (3, "Amazon", 29000), (6, "Amazon", 27000)])
    result = analyze([{"platform": "Amazon", "price": 27000}], history)
    assert result["verdict"]["label"] == "Great time to buy"
    assert result["lowest_recorded_at"] == {"date": "2026-09-06", "platform": "Amazon"}


def test_consider_waiting_when_well_above_low():
    history = snaps([(1, "Flipkart", 20000), (4, "Flipkart", 21000), (8, "Flipkart", 25000)])
    result = analyze([{"platform": "Flipkart", "price": 25000}], history)
    assert result["verdict"]["label"] == "Consider waiting"


def test_chart_uses_daily_minimum_per_platform():
    history = snaps([(1, "Amazon", 100), (1, "Amazon", 90), (2, "Croma", 95)])
    chart = analyze([{"platform": "Amazon", "price": 90}], history)["chart"]
    assert chart["labels"] == ["2026-09-01", "2026-09-02"]
    assert chart["series"]["Amazon"] == [90, None]
    assert chart["best"] == [90, 95]
