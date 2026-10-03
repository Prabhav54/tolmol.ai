"""Turns current listings and recorded price snapshots into a comparison, history chart and buy/wait verdict."""

from collections import defaultdict
from datetime import datetime
from statistics import fmean
from typing import Any, Dict, List, Optional


def _day(value: Any) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    return str(value)[:10]


def _pct(part: float, whole: float) -> float:
    return round(part / whole * 100, 1) if whole else 0.0


def verdict(best: Optional[float], lowest: Optional[float], average: Optional[float], days: int) -> Dict[str, str]:
    if best is None:
        return {"label": "No price found", "tone": "neutral", "detail": "We couldn't find a current price for this product."}
    if days < 3 or lowest is None or average is None:
        return {
            "label": "Tracking started",
            "tone": "neutral",
            "detail": "We check prices daily. The buy-or-wait advice appears once a few days of history exist.",
        }
    if best <= lowest * 1.02:
        return {"label": "Great time to buy", "tone": "good", "detail": "Today's best price is the lowest we've recorded."}
    if best <= average:
        return {
            "label": "Good price",
            "tone": "good",
            "detail": f"Below its average of ₹{average:,.0f}, though it has been {_pct(best - lowest, lowest)}% cheaper.",
        }
    if best > average * 1.05:
        return {
            "label": "Consider waiting",
            "tone": "bad",
            "detail": f"{_pct(best - lowest, lowest)}% above the lowest price we've seen (₹{lowest:,.0f}).",
        }
    return {"label": "Fair price", "tone": "neutral", "detail": f"Close to its average price of ₹{average:,.0f}."}


def analyze(current: List[Dict[str, Any]], history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    current: listings with platform / price / mrp.
    history: snapshots with platform / price / captured_at.
    """
    priced = sorted((l for l in current if l.get("price")), key=lambda l: l["price"])
    best, worst = (priced[0], priced[-1]) if priced else (None, None)

    # Daily lowest price per platform (several checks on one day collapse to that day's minimum).
    per_day: Dict[str, Dict[str, float]] = defaultdict(dict)
    for snap in history:
        day, platform, price = _day(snap["captured_at"]), snap["platform"], float(snap["price"])
        per_day[day][platform] = min(price, per_day[day].get(platform, price))
    days = sorted(per_day)
    platforms = sorted({p for prices in per_day.values() for p in prices})
    daily_best = [min(per_day[d].values()) for d in days]

    lowest = highest = average = None
    lowest_at = None
    if daily_best:
        lowest, highest, average = min(daily_best), max(daily_best), round(fmean(daily_best), 2)
        low_day = days[daily_best.index(lowest)]
        low_platform = min(per_day[low_day], key=per_day[low_day].get)
        lowest_at = {"date": low_day, "platform": low_platform}

    per_platform = []
    for platform in platforms:
        series = [per_day[d][platform] for d in days if platform in per_day[d]]
        per_platform.append(
            {"platform": platform, "lowest": min(series), "highest": max(series), "points": len(series),
             "change": round(series[-1] - series[0], 2)}
        )

    best_price = best["price"] if best else None
    span_days = (datetime.fromisoformat(days[-1]) - datetime.fromisoformat(days[0])).days + 1 if days else 0
    summary: Dict[str, Any] = {
        "best": {"platform": best["platform"], "price": best_price} if best else None,
        "stores_with_price": len(priced),
        "savings": round(worst["price"] - best_price, 2) if best and worst else 0,
        "savings_pct": _pct(worst["price"] - best_price, worst["price"]) if best and worst else 0,
        "discount_pct": _pct(best["mrp"] - best_price, best["mrp"]) if best and best.get("mrp") and best["mrp"] > best_price else None,
        "lowest_recorded": lowest,
        "lowest_recorded_at": lowest_at,
        "highest_recorded": highest,
        "average_recorded": average,
        "days_tracked": span_days,
        "per_platform": per_platform,
        "verdict": verdict(best_price, lowest, average, span_days),
    }
    summary["chart"] = {
        "labels": days,
        "series": {p: [per_day[d].get(p) for d in days] for p in platforms},
        "best": daily_best,
    }
    return summary
