"""SG3 configuration safety: messaging cannot be switched on without its
secrets, and placeholder templates can never be allowed in production."""

import pytest

from app.core.config import Settings
from app.core.startup_checks import UnsafeConfigurationError, check_runtime_settings

SAFE = {
    "env": "staging",
    "jwt_secret": "x" * 40,
    "cookie_secure": True,
    "file_store_backend": "supabase",
    "supabase_url": "https://example.invalid",
    "supabase_service_role_key": "k",
}


def _settings(**kw: object) -> Settings:
    # conftest puts the test database's migrator URL in os.environ; pin the
    # field to its default (as tests/test_staging_safety.py does).
    default_migrator = Settings.model_fields["database_url_migrator"].default
    return Settings(_env_file=None, database_url_migrator=default_migrator, **{**SAFE, **kw})  # type: ignore[call-arg, arg-type]


def test_disabled_messaging_needs_no_secrets():
    check_runtime_settings(_settings(messaging_provider="disabled"), environ={})


def test_meta_without_its_secrets_refuses_to_start_and_names_only_the_settings():
    with pytest.raises(UnsafeConfigurationError) as err:
        check_runtime_settings(_settings(messaging_provider="meta", whatsapp_access_token="secret-token-value"), environ={})
    text = str(err.value)
    assert "WHATSAPP_APP_SECRET" in text and "WHATSAPP_VERIFY_TOKEN" in text
    assert "WHATSAPP_ACCESS_TOKEN" not in text
    assert "secret-token-value" not in text


def test_meta_with_all_secrets_starts():
    check_runtime_settings(
        _settings(
            messaging_provider="meta", whatsapp_access_token="a", whatsapp_app_secret="b", whatsapp_verify_token="c"
        ),
        environ={},
    )


def test_unknown_provider_and_placeholders_in_production_are_refused():
    with pytest.raises(UnsafeConfigurationError, match="MESSAGING_PROVIDER"):
        check_runtime_settings(_settings(messaging_provider="mock"), environ={})
    with pytest.raises(UnsafeConfigurationError, match="MESSAGING_ALLOW_PLACEHOLDER_TEMPLATES"):
        check_runtime_settings(_settings(env="production", messaging_allow_placeholder_templates=True), environ={})
