"""Typed application settings — the ONLY place environment variables are read (AGENTS.md 3.3.3).

Resolution precedence: explicit constructor kwargs, process env vars, then
``backend/.env`` (read relative to the working directory; the Makefile always
runs from ``backend/``). Validators implement the fail-fast rule from BUILD_PLAN 4.2:
live SerpApi mode without an API key refuses to start, while Gemini credentials are
checked lazily via :meth:`Settings.require_gemini` so the app can boot without them
(Gemini is not used until Phase 2).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.errors import ConfigError


class Settings(BaseSettings):
    """Environment-backed configuration for the whole backend.

    Every value in ``backend/.env.example`` maps to one field here; nothing else
    in the codebase may touch the environment (AGENTS.md 3.3.3).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # Tolerate unknown keys in .env so a stale file cannot block startup;
        # every declared field still gets typed validation below.
        extra="ignore",
    )

    # --- App ---
    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = "sqlite:///./data/pathfinder.db"
    # Comma-separated origins; parsed by the cors_origins_list property.
    cors_origins: str = "http://localhost:5173"
    admin_token: str = "change-me"

    # --- SerpApi (AGENTS.md 3.4) ---
    serpapi_api_key: str = ""
    serpapi_use_fixtures: bool = True
    serpapi_daily_call_cap: int = Field(default=60, gt=0)
    serpapi_jobs_max_pages: int = Field(default=3, gt=0)
    # Where fixture-mode reads recordings from. Default: the committed
    # backend/tests/fixtures/serpapi directory (resolved by the client so the
    # value stays None in config). Tests override it to a tmp_path seam.
    serpapi_fixture_dir: str | None = None

    # --- Gemini (Phase 2; AGENTS.md 3.5) ---
    gemini_api_key: str = ""
    gemini_model: str = ""
    # Default is conservative (5/min) to stay within the free-tier limit for
    # gemini-2.5-flash (10 RPM) while leaving headroom for bursts and retries.
    # Override via GEMINI_REQUESTS_PER_MINUTE in .env for paid-tier accounts.
    gemini_requests_per_minute: int = Field(default=5, gt=0)

    # --- Scheduler (Phase 5) ---
    scheduler_enabled: bool = False
    jobs_daily_cron: str = "0 3 * * *"
    jobs_india_weekly_cron: str = "0 4 * * 1"
    scholar_weekly_cron: str = "0 5 * * 1"

    # --- Quiz / demo ---
    allow_unverified_questions: bool = False
    demo_mode: bool = False

    @property
    def cors_origins_list(self) -> list[str]:
        """Return the CORS origins as a cleaned list (env value is comma-separated)."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def _require_key_outside_fixture_mode(self) -> Settings:
        """Fail fast when live mode is selected without an API key (BUILD_PLAN 4.2)."""
        if not self.serpapi_use_fixtures and not self.serpapi_api_key:
            raise ValueError(
                "SERPAPI_API_KEY must be set when SERPAPI_USE_FIXTURES=false "
                "(or switch back to fixture mode)"
            )
        return self

    def require_gemini(self) -> None:
        """Validate Gemini credentials at the moment a Gemini feature is invoked.

        Raises:
            ConfigError: when GEMINI_API_KEY or GEMINI_MODEL is empty. Deliberately
                not a startup validator — the app must run keyless until Phase 2.
        """
        if not self.gemini_api_key or not self.gemini_model:
            raise ConfigError("Gemini feature invoked without GEMINI_API_KEY and GEMINI_MODEL set")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached Settings instance (call ``get_settings.cache_clear()`` in tests)."""
    return Settings()
