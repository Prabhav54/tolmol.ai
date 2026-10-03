import pytest

from tolmol.services.chat_router import PRICE, REVIEWS, SPECS, detect_language, route_question

# Labelled questions (English + Hinglish) for measuring the rule-based router.
GOLDEN = [
    ("Where is it cheapest right now?", PRICE),
    ("What was the lowest price on Flipkart?", PRICE),
    ("Should I wait for a price drop?", PRICE),
    ("kitne ka hai amazon pe?", PRICE),
    ("sasta kahan milega", PRICE),
    ("What is the battery capacity?", SPECS),
    ("Does it support fast charging?", SPECS),
    ("screen size and refresh rate?", SPECS),
    ("kitni battery hai iski", SPECS),
    ("camera kaisa hai?", SPECS),
    ("Is it worth buying?", REVIEWS),
    ("What do people say about the build quality?", REVIEWS),
    ("any heating problems?", REVIEWS),
    ("lena chahiye ya nahi?", REVIEWS),
]


@pytest.mark.parametrize("question, route", GOLDEN)
def test_rule_routing(question, route):
    assert route_question(question, use_llm=False).route == route


def test_hinglish_detection():
    assert detect_language("battery kaisi hai") == "hinglish"
    assert detect_language("How good is the battery?") == "english"
