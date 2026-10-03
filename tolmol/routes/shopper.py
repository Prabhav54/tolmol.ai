import base64
import binascii

from fastapi import APIRouter, Depends, HTTPException, Request

from tolmol.schemas import AlertRequest, ChatRequest, CompareRequest, PhotoRequest, SearchRequest
from tolmol.services import alerts, chat, tracker
from tolmol.services.access import Client, identify_client, logged
from tolmol.services.compare import compare
from tolmol.services.identity import identify_from_photo, identify_from_url, identity_from_candidate, search_products
from tolmol.services.insights import build_insights

router = APIRouter(prefix="/api", tags=["Shopper"])


def client_dependency(request: Request) -> Client:
    return identify_client(request)


@router.post("/compare")
def compare_product(payload: CompareRequest, client: Client = Depends(client_dependency)):
    """Paste a product link (or pick a search result): live prices across Indian stores, history and a verdict."""
    query = payload.url or payload.product.title
    with logged(client, "compare", query) as entry:
        identity = identify_from_url(payload.url) if payload.url else identity_from_candidate(payload.product)
        view = compare(identity, refresh=payload.refresh)
        entry["product_id"] = view["product"]["id"]
        return view


@router.post("/search")
def search(payload: SearchRequest, client: Client = Depends(client_dependency)):
    """Search by name, in English or Hinglish ("joote 2000 ke andar"). Returns products to pick from."""
    with logged(client, "search", payload.query):
        return search_products(payload.query)


@router.post("/search/photo")
def search_by_photo(payload: PhotoRequest, client: Client = Depends(client_dependency)):
    """Search by photo: identifies the product in an image so it can be compared."""
    try:
        image = base64.b64decode(payload.image_base64.split(",")[-1], validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=422, detail="The image could not be read. Upload a JPEG, PNG or WebP file.")
    with logged(client, "photo", f"photo ({len(image) // 1024} KB)"):
        return identify_from_photo(image, payload.mime_type)


@router.get("/products/recent")
def recent():
    return {"items": tracker.recent_products()}


@router.get("/products/{product_id}")
def product(product_id: int):
    return tracker.product_view(product_id)


@router.post("/products/{product_id}/insights")
def insights(product_id: int, refresh: bool = False, client: Client = Depends(client_dependency)):
    """Specs and review analysis researched from the web (built once, then cached)."""
    view = tracker.product_view(product_id)
    if view["insights"]["ready"] and not refresh:
        return view["insights"]
    with logged(client, "insights", view["product"]["title"]) as entry:
        entry["product_id"] = product_id
        return build_insights(product_id)


@router.post("/products/{product_id}/chat")
def chat_with_product(product_id: int, payload: ChatRequest, client: Client = Depends(client_dependency)):
    """Ask about price, specs or reviews. Routed to SQL or hybrid vector search, answered only from those facts."""
    with logged(client, "chat", payload.question) as entry:
        entry["product_id"] = product_id
        return chat.answer(product_id, payload.question, payload.history)


@router.post("/products/{product_id}/alerts")
def create_alert(product_id: int, payload: AlertRequest):
    return alerts.create_alert(product_id, payload.email, payload.target_price)
