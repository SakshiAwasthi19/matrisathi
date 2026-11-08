"""The messaging provider adapter (W3-A1, T011).

One interface, one real implementation: Meta's WhatsApp Cloud API (D06's
recommendation, still awaiting the manager's decision). Errors are sorted by
what they mean for a retry:

- ProviderTransientError: the request certainly did not reach the provider,
  or the provider asked us to retry. Safe to retry later.
- ProviderPermanentError: the provider refused it. Retrying will not help.
- ProviderUnknownOutcome: the request may have been accepted (e.g. a read
  timeout). Never retried automatically, so nothing is ever sent twice.

Error text never contains the message, the token or the phone number.
"""

import hashlib
import hmac
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import Settings, settings


class ProviderError(Exception):
    """Base class. `str(err)` is a short, safe description."""


class ProviderTransientError(ProviderError):
    pass


class ProviderPermanentError(ProviderError):
    pass


class ProviderUnknownOutcome(ProviderError):
    pass


class ProviderNotConfigured(ProviderError):
    pass


@dataclass(frozen=True)
class SendResult:
    provider_message_id: str


@dataclass(frozen=True)
class MediaDownload:
    data: bytes
    declared_type: str | None


class MessagingProvider(Protocol):
    name: str

    def send_template(self, to: str, template_name: str, language: str, parameters: list[str]) -> SendResult: ...

    def send_text(self, to: str, body: str) -> SendResult: ...

    def download_media(self, media_id: str, max_bytes: int) -> MediaDownload: ...


def verify_signature(app_secret: str, body: bytes, header: str | None) -> bool:
    """Meta signs the raw body: X-Hub-Signature-256: sha256=<hex HMAC>."""
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


class MetaCloudProvider:
    name = "meta"

    def __init__(
        self, base_url: str, phone_number_id: str, access_token: str, client: httpx.Client | None = None
    ) -> None:
        self.base = base_url.rstrip("/")
        self.phone_number_id = phone_number_id
        self.headers = {"Authorization": f"Bearer {access_token}"}
        self.client = client or httpx.Client(timeout=httpx.Timeout(15.0, connect=5.0))

    def _post_message(self, payload: dict) -> SendResult:
        url = f"{self.base}/{self.phone_number_id}/messages"
        try:
            resp = self.client.post(url, json={"messaging_product": "whatsapp", **payload}, headers=self.headers)
        except (httpx.ConnectError, httpx.ConnectTimeout) as err:
            raise ProviderTransientError("could not reach the provider") from err
        except httpx.HTTPError as err:
            # Read/write timeouts or a dropped connection: the provider may
            # have accepted it. Do not retry.
            raise ProviderUnknownOutcome("no answer from the provider") from err
        if resp.status_code == 429 or resp.status_code == 503:
            raise ProviderTransientError(f"provider asked to retry ({resp.status_code})")
        if resp.status_code >= 500:
            raise ProviderUnknownOutcome(f"provider error ({resp.status_code})")
        if resp.status_code >= 400:
            code = ""
            try:
                code = str(resp.json().get("error", {}).get("code", ""))
            except ValueError:
                pass
            raise ProviderPermanentError(f"provider refused ({resp.status_code}{' code ' + code if code else ''})")
        try:
            message_id = resp.json()["messages"][0]["id"]
        except (ValueError, KeyError, IndexError, TypeError) as err:
            raise ProviderUnknownOutcome("provider answer had no message id") from err
        return SendResult(provider_message_id=str(message_id))

    def send_template(self, to: str, template_name: str, language: str, parameters: list[str]) -> SendResult:
        template: dict = {"name": template_name, "language": {"code": language}}
        if parameters:
            template["components"] = [
                {"type": "body", "parameters": [{"type": "text", "text": p} for p in parameters]}
            ]
        return self._post_message({"to": to, "type": "template", "template": template})

    def send_text(self, to: str, body: str) -> SendResult:
        return self._post_message({"to": to, "type": "text", "text": {"body": body, "preview_url": False}})

    def download_media(self, media_id: str, max_bytes: int) -> MediaDownload:
        """Two steps: ask for a short-lived URL, then fetch it with the token.
        The URL is used once and never stored."""
        try:
            meta = self.client.get(f"{self.base}/{media_id}", headers=self.headers)
            if meta.status_code != 200:
                raise ProviderPermanentError(f"media lookup failed ({meta.status_code})")
            info = meta.json()
            size = int(info.get("file_size") or 0)
            if size > max_bytes:
                raise ProviderPermanentError("media larger than the limit")
            resp = self.client.get(str(info["url"]), headers=self.headers)
        except (httpx.ConnectError, httpx.ConnectTimeout) as err:
            raise ProviderTransientError("could not reach the provider") from err
        except httpx.HTTPError as err:
            raise ProviderTransientError("media download interrupted") from err
        except (ValueError, KeyError) as err:
            raise ProviderPermanentError("media lookup answer was not understood") from err
        if resp.status_code != 200:
            raise ProviderTransientError(f"media download failed ({resp.status_code})")
        if len(resp.content) > max_bytes:
            raise ProviderPermanentError("media larger than the limit")
        return MediaDownload(data=resp.content, declared_type=info.get("mime_type"))


def build_provider(phone_number_id: str, config: Settings = settings) -> MessagingProvider:
    if config.messaging_provider == "meta":
        if not config.whatsapp_access_token:
            raise ProviderNotConfigured("WHATSAPP_ACCESS_TOKEN is not set")
        return MetaCloudProvider(config.whatsapp_api_base, phone_number_id, config.whatsapp_access_token)
    raise ProviderNotConfigured("messaging is disabled (MESSAGING_PROVIDER)")
