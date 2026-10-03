import pytest

from engines.query_parser import keyword_stems, parse_query
from engines.router import SEMANTIC, SQL, route_query


def test_price_and_rating_constraints():
    f = parse_query("shoes under ₹2000 with rating > 4.2")
    assert f.max_price == 2000
    assert f.min_rating == 4.2
    assert f.min_price is None
    assert f.keywords == ["shoes"]


@pytest.mark.parametrize(
    "query, low, high",
    [
        ("phones between 10k and 20k", 10000, 20000),
        ("laptops from rs 50,000 to 80,000", 50000, 80000),
        ("bags between 3000 and 1000", 1000, 3000),
    ],
)
def test_price_ranges(query, low, high):
    f = parse_query(query)
    assert (f.min_price, f.max_price) == (low, high)


def test_specs_are_not_prices():
    f = parse_query("500w mixer grinder")
    assert f.max_price is None and f.min_price is None
    assert route_query("4k smart tv with dolby vision").route == SEMANTIC


def test_min_price_and_platform():
    f = parse_query("jeans from myntra above 1500")
    assert f.min_price == 1500
    assert f.platforms == ["Myntra"]
    assert f.keywords == ["jeans"]


def test_star_ratings():
    assert parse_query("backpacks with 4+ stars").min_rating == 4
    assert parse_query("rated at least 4.5").min_rating == 4.5


def test_sort_and_limit():
    f = parse_query("top 5 rated smartwatches")
    assert f.sort == "rating_desc" and f.limit == 5
    f = parse_query("3 cheapest bluetooth speakers")
    assert f.sort == "price_asc" and f.limit == 3


def test_aggregates_and_grouping():
    f = parse_query("average price of t-shirts by platform")
    assert f.aggregate == "avg_price" and f.group_by == "platform"
    assert f.keywords == ["t-shirts"]
    f = parse_query("number of products per category")
    assert f.aggregate == "count" and f.group_by == "category"
    assert parse_query("how many products are under 1000").aggregate == "count"


def test_thread_count_is_not_an_aggregate():
    f = parse_query("high thread count cotton bedsheets")
    assert f.aggregate is None
    assert route_query("high thread count cotton bedsheets").route == SEMANTIC


def test_descriptive_queries_go_semantic():
    decision = route_query("breathable summer running wear")
    assert decision.route == SEMANTIC
    assert decision.filters.keywords == ["breathable", "summer", "running", "wear"]


def test_constraint_queries_go_sql():
    assert route_query("cheapest bluetooth speaker").route == SQL
    assert route_query("headphones on amazon below rs 1500").route == SQL


def test_keyword_stems():
    assert keyword_stems(["shoes", "watches", "glasses", "accessories", "dress"]) == [
        "shoe", "watch", "glass", "accessory", "dress",
    ]
