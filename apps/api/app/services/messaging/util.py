"""Small helpers for messaging: phone numbers in the provider's format, and
checking inbound media by its bytes, never by its name or stated type."""

from app.core.config import settings
from app.models.messaging import INBOUND_MEDIA_TYPES

MAX_INBOUND_MEDIA_BYTES = 10 * 1024 * 1024  # same limit as uploads (T009)


def to_provider_number(value: str, country_code: str | None = None) -> str | None:
    """Digits only, with the country code (the provider's format, no '+').

    A 10-digit number gets the default country code. Anything that is not
    plausibly a phone number returns None and is not sent to.
    """
    cc = country_code or settings.messaging_default_country_code
    digits = "".join(ch for ch in value if ch.isdigit())
    if value.strip().startswith("00"):
        digits = digits[2:]
    if len(digits) == 10:
        digits = cc + digits
    elif len(digits) == 11 and digits.startswith("0"):
        digits = cc + digits[1:]
    if not 11 <= len(digits) <= 15:
        return None
    return digits


def same_number(stored: str, provider_number: str) -> bool:
    normalised = to_provider_number(stored)
    return normalised is not None and normalised == to_provider_number(provider_number)


def sniff_media_type(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"OggS"):
        return "audio/ogg"
    if data.startswith(b"#!AMR"):
        return "audio/amr"
    if data.startswith(b"ID3") or (len(data) > 1 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0):
        return "audio/mpeg"
    if len(data) > 11 and data[4:8] == b"ftyp" and data[8:11] in (b"M4A", b"mp4", b"iso", b"3gp"):
        return "audio/mp4"
    return None


class MediaRejected(ValueError):
    """Safe to show to staff."""


def check_inbound_media(data: bytes) -> str:
    if not data:
        raise MediaRejected("The file was empty.")
    if len(data) > MAX_INBOUND_MEDIA_BYTES:
        raise MediaRejected("The file is larger than 10 MB, so it was not kept.")
    kind = sniff_media_type(data)
    if kind is None or kind not in INBOUND_MEDIA_TYPES:
        raise MediaRejected("This kind of file is not accepted. Ask the sender to send a photo or voice note.")
    return kind
