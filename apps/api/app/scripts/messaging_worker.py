"""Sends queued WhatsApp messages and fetches inbound voice notes and photos
(W3-A1, W3-A2). Runs as its own process, next to the API, with the app role.

Several copies may run at once: rows are claimed with FOR UPDATE SKIP LOCKED
and a lease, so no message is sent twice.

Usage:
  uv run python -m app.scripts.messaging_worker          # loop every 5 s
  uv run python -m app.scripts.messaging_worker --once   # one pass, then exit
"""

import argparse
import logging
import os
import socket
import time

from app.core.config import settings
from app.core.db import SessionLocal
from app.services.file_store import build_file_store
from app.services.messaging import inbound, outbox
from app.services.messaging.provider import MessagingProvider, build_provider

log = logging.getLogger("matrisathi.worker")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=float, default=5.0)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    if settings.messaging_provider == "disabled":
        raise SystemExit("MESSAGING_PROVIDER is 'disabled'; nothing to send.")

    providers: dict[str, MessagingProvider] = {}

    def provider_for(phone_number_id: str) -> MessagingProvider:
        if phone_number_id not in providers:
            providers[phone_number_id] = build_provider(phone_number_id)
        return providers[phone_number_id]

    worker_id = f"{socket.gethostname()}-{os.getpid()}"[:64]
    store = build_file_store()
    log.info("messaging worker %s started", worker_id)
    while True:
        counts = outbox.run_once(SessionLocal, provider_for, worker_id)
        fetched = inbound.fetch_pending_media(SessionLocal, provider_for, store)
        if counts or fetched:
            log.info("sent: %s; media stored: %d", counts, fetched)
        if args.once:
            return
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
