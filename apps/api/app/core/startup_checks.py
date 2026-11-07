"""Refuses to run the API with development defaults outside development.

Called once at import time from app/main.py. Deliberately NOT implemented as
a pydantic validator on Settings: a pydantic ValidationError prints the
input values, which would put database URLs and secrets into the startup
log. Every message here names the setting, never its value.
"""

import os
from collections.abc import Mapping

from app.core.config import Settings

DEVELOPMENT = "development"
MIN_JWT_SECRET_LENGTH = 32


class UnsafeConfigurationError(RuntimeError):
    pass


def is_development(env: str) -> bool:
    return env.strip().lower() == DEVELOPMENT


def _field_default(name: str) -> object:
    return Settings.model_fields[name].default


def check_runtime_settings(settings: Settings, environ: Mapping[str, str] | None = None) -> None:
    """Raises UnsafeConfigurationError listing every unsafe setting, unless
    ENV is development. `environ` defaults to the process environment."""
    if is_development(settings.env):
        return
    env_vars = os.environ if environ is None else environ

    problems: list[str] = []

    if settings.jwt_secret == _field_default("jwt_secret") or len(settings.jwt_secret) < MIN_JWT_SECRET_LENGTH:
        problems.append(
            f"JWT_SECRET must be set to a non-default value of at least {MIN_JWT_SECRET_LENGTH} characters"
        )

    # The API process must hold only the restricted app-role credentials.
    # Migrations run as a separate release step with migrator credentials.
    migrator_in_env = any(key.upper() == "DATABASE_URL_MIGRATOR" for key in env_vars)
    if migrator_in_env or settings.database_url_migrator != _field_default("database_url_migrator"):
        problems.append(
            "DATABASE_URL_MIGRATOR must not be configured for the API process "
            "(run migrations as a separate release step)"
        )

    if not settings.cookie_secure:
        problems.append("COOKIE_SECURE must be true")

    # Local disk on a hosted web service is temporary and shared by nothing;
    # private files must go to the configured private bucket (W2-A1).
    if settings.file_store_backend != "supabase" or not settings.supabase_url or not settings.supabase_service_role_key:
        problems.append(
            "FILE_STORE_BACKEND must be 'supabase' with SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY set"
        )

    if problems:
        raise UnsafeConfigurationError(
            f"Refusing to start with ENV={settings.env.strip()!r}: " + "; ".join(problems)
        )
