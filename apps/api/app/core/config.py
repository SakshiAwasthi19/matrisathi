from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # extra="ignore": .env legitimately carries keys this object never reads
    # directly — e.g. MATRISATHI_APP_DB_PASSWORD, consumed via os.environ by
    # a migration script, not through this class. Unknown keys here are a
    # much smaller risk than a hard crash (with the offending value printed
    # in the traceback) every time someone adds one.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = "development"

    # Two distinct DB credentials: migrator owns/alters schema, app is restricted
    # (requirement: separate migration-owner and restricted application DB roles).
    database_url_migrator: str = (
        "postgresql+psycopg://matrisathi_migrator:matrisathi_migrator_dev_pw@localhost:5433/matrisathi"
    )
    database_url_app: str = (
        "postgresql+psycopg://matrisathi_app:matrisathi_app_dev_pw@localhost:5433/matrisathi"
    )

    jwt_secret: str = "dev-only-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 14

    # Browser storage: both tokens ride as httpOnly cookies, never localStorage,
    # so they are unreachable from page JavaScript (XSS mitigation).
    cookie_secure: bool = False  # must be True behind HTTPS in any real deployment
    cookie_domain: str | None = None
    # "lax" works for local dev (frontend and backend share localhost, just
    # different ports — not cross-site as far as cookies are concerned).
    # A deployment that splits frontend and backend across different
    # domains (e.g. Vercel + Render) IS cross-site, and a Lax cookie is not
    # sent on a cross-site fetch() at all — set this to "none" (together
    # with cookie_secure=true, which browsers require for SameSite=None)
    # for that case.
    cookie_samesite: str = "lax"

    # CSRF mitigation for the cookie-based session: the frontend must send this
    # header on every mutating request; a cross-site form post cannot set it,
    # and CORS blocks a cross-origin script from setting it either.
    csrf_header_name: str = "X-MatriSathi-Client"
    csrf_header_value: str = "web"

    # Comma-separated. Local dev is one origin; a staging deployment adds
    # its actual Vercel URL here (e.g. via Render's env var UI) rather than
    # this file ever hardcoding a specific deployed URL.
    cors_allowed_origins: str = "http://localhost:5173"

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    # Private file storage (W2-A1, T009). "local" writes under
    # file_store_local_root (development and tests only); "supabase" uses the
    # Supabase Storage HTTP API with the service-role key, server side only.
    # Outside development the API refuses to start unless it is "supabase".
    file_store_backend: str = "local"
    file_store_local_root: str = ".data/files"
    supabase_storage_bucket: str = "matrisathi-files"

    # "Today" for scheduling and "future vs past" decisions. India has no
    # daylight saving, so a fixed offset (UTC+05:30) is exact and needs no
    # timezone-database package.
    local_utc_offset_minutes: int = 330

    # D07 (patient/caregiver access) is not decided. Until it is, every
    # patient/caregiver access check answers "no", whatever grants exist.
    patient_access_enabled: bool = False

    login_throttle_max_attempts: int = 5
    login_throttle_window_minutes: int = 15

    # Not read anywhere in the app yet (see .env.example) — declared
    # explicitly so a teammate filling in the optional Supabase/GitHub
    # section of .env doesn't hit a validation error on startup. Any other
    # unrecognized key still fails loudly, which is what we want for
    # catching real typos in the required settings above.
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_service_role_key: str | None = None
    github_token: str | None = None


settings = Settings()
