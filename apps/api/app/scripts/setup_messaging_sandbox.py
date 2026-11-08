"""Sets up WhatsApp for one organization on a provider SANDBOX / test number
(SG3, while D06 and template approval are pending).

Adds:
- the messaging channel (the provider's phone-number ID for the test number);
- SYNTHETIC PLACEHOLDER message templates, labelled on every screen. They
  must also exist, with the same names and text, in the provider's
  dashboard. They may be sent only when MESSAGING_ALLOW_PLACEHOLDER_TEMPLATES
  is true, and only to consenting staff test phones (SG3 gate rules).

Writes through the migrator role. Refused when ENV=production. Safe to run
more than once.

Usage:
  uv run python -m app.scripts.setup_messaging_sandbox --organization "Synthetic Org" --phone-number-id 1234567890
"""

import argparse

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.care import TemplateStatus
from app.models.messaging import DetailLevel, MessagePurpose, MessageTemplate, MessagingChannel
from app.models.organization import Organization

VERSION = "placeholder-1"
PREFIX = "SYNTHETIC PLACEHOLDER – NOT APPROVED: "

# (purpose, detail, provider name, text, variables). MINIMAL says nothing
# about pregnancy or care, for shared phones.
TEMPLATES = [
    (
        MessagePurpose.APPOINTMENT_REMINDER,
        DetailLevel.MINIMAL,
        "ms_placeholder_reminder_minimal",
        PREFIX + "Reminder from {{1}}: please come on {{2}}. Reply here if you cannot come.",
        ["facility_name", "appointment_date"],
    ),
    (
        MessagePurpose.APPOINTMENT_REMINDER,
        DetailLevel.STANDARD,
        "ms_placeholder_reminder_standard",
        PREFIX + "Your visit at {{1}} is on {{2}} {{3}}. Reply here if you cannot come or need help.",
        ["place", "appointment_date", "appointment_time"],
    ),
    (
        MessagePurpose.FOLLOW_UP,
        DetailLevel.MINIMAL,
        "ms_placeholder_follow_up_minimal",
        PREFIX + "{{1}} tried to reach you. Please reply or call us.",
        ["facility_name"],
    ),
    (
        MessagePurpose.FOLLOW_UP,
        DetailLevel.STANDARD,
        "ms_placeholder_follow_up_standard",
        PREFIX + "{{1}} would like to talk to you about your next visit. Please reply or call us.",
        ["facility_name"],
    ),
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--organization", required=True)
    parser.add_argument("--phone-number-id", required=True)
    parser.add_argument("--label", default="Sandbox test number")
    parser.add_argument("--language", default="en")
    args = parser.parse_args()
    if settings.env.strip().lower() == "production":
        raise SystemExit("Refusing to set up placeholder messaging in production.")
    engine = create_engine(settings.database_url_migrator)
    with Session(engine) as db:
        org = db.execute(select(Organization).where(Organization.name == args.organization)).scalar_one_or_none()
        if org is None:
            raise SystemExit(f"No organization is named {args.organization!r}.")
        channel = db.execute(
            select(MessagingChannel).where(MessagingChannel.phone_number_id == args.phone_number_id)
        ).scalar_one_or_none()
        if channel is None:
            db.add(
                MessagingChannel(
                    organization_id=org.id,
                    provider="meta",
                    phone_number_id=args.phone_number_id,
                    display_label=args.label,
                    active=True,
                )
            )
        elif channel.organization_id != org.id:
            raise SystemExit("That phone-number ID already belongs to another organization.")
        added = 0
        for purpose, detail, name, body, variables in TEMPLATES:
            exists = db.execute(
                select(MessageTemplate).where(
                    MessageTemplate.organization_id == org.id,
                    MessageTemplate.purpose == purpose,
                    MessageTemplate.language == args.language,
                    MessageTemplate.detail_level == detail,
                    MessageTemplate.version_label == VERSION,
                )
            ).first()
            if exists:
                continue
            db.add(
                MessageTemplate(
                    organization_id=org.id,
                    purpose=purpose,
                    language=args.language,
                    detail_level=detail,
                    version_label=VERSION,
                    provider_template_name=name,
                    body_text=body,
                    variable_names=variables,
                    status=TemplateStatus.APPROVED,
                    is_placeholder=True,
                )
            )
            added += 1
        db.commit()
    engine.dispose()
    print(f"Channel ready for {args.organization!r}; {added} placeholder template(s) added.")


if __name__ == "__main__":
    main()
