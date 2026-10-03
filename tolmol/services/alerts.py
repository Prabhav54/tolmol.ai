"""Price-drop alerts: shoppers set a target price; the daily refresh emails them when it is reached."""

import html
from typing import Any, Dict, Optional

import httpx
from sqlalchemy import func, insert, select, update

from tolmol.config import settings
from tolmol.db.models import price_alerts, tracked_products
from tolmol.db.session import get_engine
from tolmol.errors import NotFound
from tolmol.logger import get_logger

logger = get_logger(__name__)


def create_alert(product_id: int, email: str, target_price: float) -> Dict[str, Any]:
    with get_engine().begin() as conn:
        exists = conn.execute(select(tracked_products.c.id).where(tracked_products.c.id == product_id)).scalar()
        if not exists:
            raise NotFound("Product not found.")
        alert_id = conn.execute(
            insert(price_alerts).values(product_id=product_id, email=email.lower(), target_price=target_price)
            .returning(price_alerts.c.id)
        ).scalar_one()
    return {
        "id": alert_id,
        "email_delivery": bool(settings.RESEND_API_KEY),
        "message": f"We'll email {email} when the price drops to ₹{target_price:,.0f} or lower."
        if settings.RESEND_API_KEY
        else "Alert saved. Email delivery isn't configured on this server yet, so no email will be sent.",
    }


def _send_email(to: str, subject: str, html: str) -> bool:
    if not settings.RESEND_API_KEY:
        return False
    try:
        response = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
            json={"from": settings.ALERT_FROM_EMAIL, "to": [to], "subject": subject, "html": html},
            timeout=10,
        )
        response.raise_for_status()
        return True
    except httpx.HTTPError as exc:
        logger.error(f"Alert email to {to} failed: {exc}")
        return False


def check_alerts(product_id: int, title: str, best_price: Optional[float], best_platform: Optional[str]) -> int:
    """Emails every active alert whose target the current best price has reached. Returns emails sent."""
    if best_price is None:
        return 0
    with get_engine().connect() as conn:
        due = conn.execute(
            select(price_alerts.c.id, price_alerts.c.email, price_alerts.c.target_price).where(
                price_alerts.c.product_id == product_id,
                price_alerts.c.active.is_(True),
                price_alerts.c.target_price >= best_price,
            )
        ).mappings().all()

    sent = 0
    for alert in due:
        link = f"{settings.PUBLIC_BASE_URL}/?product={product_id}"
        # Titles and store names come from scraped pages and model output, so escape them for the email body.
        delivered = _send_email(
            alert["email"],
            f"Price drop: {title} is now ₹{best_price:,.0f}",
            f"<p><strong>{html.escape(title)}</strong> is now <strong>₹{best_price:,.0f}</strong> on "
            f"{html.escape(best_platform or 'a store')}, "
            f"at or below your target of ₹{float(alert['target_price']):,.0f}.</p>"
            f'<p><a href="{link}">See the full price comparison</a></p>',
        )
        if delivered:
            sent += 1
            with get_engine().begin() as conn:
                conn.execute(
                    update(price_alerts).where(price_alerts.c.id == alert["id"]).values(active=False, triggered_at=func.now())
                )
    return sent
