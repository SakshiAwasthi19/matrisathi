"""Provider webhooks (W3-A1; T011, G09; AT12, AT30).

This is the only route that accepts requests without a staff session, so it
trusts nothing it cannot verify:
- GET answers Meta's one-time subscription check with the verify token.
- POST must carry a valid X-Hub-Signature-256 over the raw body (HMAC with
  the app secret). Anything unsigned or wrongly signed is rejected with 401
  and processed not at all.
- With messaging disabled or the secret unset, both answer 503.

The body is processed once per provider event ID (see services/messaging/
inbound.py), so the provider's retries cannot create duplicates. Message
content and phone numbers are never logged.
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.services.messaging import inbound
from app.services.messaging.provider import verify_signature

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
log = logging.getLogger("matrisathi.webhooks")

MAX_BODY_BYTES = 1024 * 1024


def _enabled() -> None:
    if settings.messaging_provider != "meta" or not settings.whatsapp_app_secret:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="Messaging is not enabled.")


@router.get("/whatsapp")
def verify_subscription(
    mode: str = Query("", alias="hub.mode"),
    token: str = Query("", alias="hub.verify_token"),
    challenge: str = Query("", alias="hub.challenge"),
) -> Response:
    _enabled()
    expected = settings.whatsapp_verify_token
    if mode != "subscribe" or not expected or token != expected:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return Response(content=challenge, media_type="text/plain")


@router.post("/whatsapp")
async def receive(request: Request, db: Session = Depends(get_db)) -> dict[str, str]:
    _enabled()
    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Too large")
    assert settings.whatsapp_app_secret is not None
    if not verify_signature(settings.whatsapp_app_secret, body, request.headers.get("X-Hub-Signature-256")):
        log.warning("webhook rejected: bad or missing signature")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")
    try:
        payload = json.loads(body)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Not JSON") from None
    if not isinstance(payload, dict):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Not an object")
    counts = inbound.handle_webhook(db, payload)
    db.commit()
    log.info("webhook processed: %s", counts)
    return {"status": "ok"}
