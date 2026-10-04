"""Recorder guards (plan step 0.5): refuse, abort, parse --force — never network."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import httpx
import pytest
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.integrations.serpapi.client import SerpApiClient
from app.integrations.serpapi.queries import FixtureSpec

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "record_fixtures.py"


def _load_module() -> ModuleType:
    """Import the recorder script from its file path (scripts/ is not a package)."""
    spec = importlib.util.spec_from_file_location("record_fixtures", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_record_fixtures_refuses_in_fixture_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """With fixtures on (the default), recording must refuse without prompting or calling."""
    monkeypatch.setenv("SERPAPI_USE_FIXTURES", "true")
    monkeypatch.setenv("SERPAPI_API_KEY", "")
    get_settings.cache_clear()
    module = _load_module()

    assert module.main([]) == 1


def test_record_fixtures_refuses_without_key_in_live_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Live mode with an empty key trips Settings' fail-fast, reported as exit code 1."""
    monkeypatch.setenv("SERPAPI_USE_FIXTURES", "false")
    monkeypatch.setenv("SERPAPI_API_KEY", "")
    get_settings.cache_clear()
    module = _load_module()

    assert module.main([]) == 1


def test_record_fixtures_aborts_on_no_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 'n' at the y/N prompt exits 0 before any DB work or network call."""
    monkeypatch.setenv("SERPAPI_USE_FIXTURES", "false")
    monkeypatch.setenv("SERPAPI_API_KEY", "fake-key-for-prompt-test")
    get_settings.cache_clear()
    module = _load_module()
    monkeypatch.setattr("builtins.input", lambda _prompt: "n")

    assert module.main([]) == 0


def test_record_fixtures_force_flag_parses() -> None:
    """--force is the only flag; it maps to the overwrite behavior."""
    module = _load_module()

    assert module.build_parser().parse_args([]).force is False
    assert module.build_parser().parse_args(["--force"]).force is True


def test_record_one_saves_empty_result_as_recorded_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    """An empty response from SerpApi is saved as a fixture and reported as 'recorded (empty)'."""
    module = _load_module()
    monkeypatch.setattr(module, "FIXTURE_DIR", tmp_path)

    empty_payload = {"error": "Google hasn't returned any results for this query."}
    settings = Settings(
        serpapi_use_fixtures=False,
        serpapi_api_key="test-api-key",
        serpapi_daily_call_cap=60,
    )
    http = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=empty_payload))
    )
    client = SerpApiClient(settings, lambda: db_session, http_client=http, fixture_dir=tmp_path)
    spec = FixtureSpec(engine="google_jobs", query="quantum obscure role", variant="global_p1")

    status, payload, path = module._record_one(
        client, spec, variant="global_p1", next_page_token=None, force=False
    )

    assert status == "recorded (empty)"
    assert status != "failed"
    assert payload == empty_payload
    assert path.is_file()
    assert json.loads(path.read_text(encoding="utf-8")) == empty_payload
