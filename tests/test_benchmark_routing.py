from benchmark.evaluator import evaluate_routing, load_golden_set


def test_golden_set_routing_is_perfect():
    report = evaluate_routing(load_golden_set())
    assert report["failures"] == []
    assert report["accuracy"] == 1.0
