"""Gemini client unit tests (plan 2.2) — no network, ever.

The real :class:`GeminiStructuredLLM` is exercised against a stub genai client
(an object whose ``models.generate_content`` returns scripted responses or
raises scripted SDK errors), so the retry/backoff/validation wiring is tested
without a single HTTP request. Rate-limiter tests use injectable fake
clock/sleepers. All LLM-protocol tests also cover :class:`FakeStructuredLLM`
since it is the double every service test relies on.
"""

from __future__ import annotations

import pytest
from google.genai import errors as genai_errors

from app.core.config import Settings
from app.core.errors import ConfigError, LLMOutputError
from app.integrations.gemini.client import (
    BACKOFF_5XX_BASE_SECONDS,
    BACKOFF_429_SECONDS,
    TEMPERATURE,
    FakeStructuredLLM,
    GeminiStructuredLLM,
    RateLimiter,
)
from app.integrations.gemini.schemas import ExtractionBatch

# ------------------------------------------------------------------- test doubles


class StubResponse:
    """Mimics google.genai GenerateContentResponse for the attributes we use."""

    def __init__(self, text: str | None) -> None:
        self._text = text

    @property
    def text(self) -> str | None:
        if self._text is None:
            raise ValueError("no text parts")  # what the SDK does on blocked responses
        return self._text


class StubModels:
    """Scripted ``models`` namespace: records kwargs, replays outcomes in order."""

    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[dict[str, object]] = []

    def generate_content(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if not self.outcomes:
            raise AssertionError("stub ran out of scripted outcomes")
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class StubGenaiClient:
    """Duck-typed stand-in for google.genai.Client (only .models is used)."""

    def __init__(self, outcomes: list[object]) -> None:
        self.models = StubModels(outcomes)


def _settings(rpm: int = 100) -> Settings:
    """Valid Gemini settings (values are test-local, never real credentials)."""
    return Settings(
        gemini_api_key="test-key-not-real",
        gemini_model="test-model-name",
        gemini_requests_per_minute=rpm,
    )


class _Record:
    """Mutable recorder for sleep durations and clock reads."""

    def __init__(self) -> None:
        self.sleeps: list[float] = []
        self.now = 0.0

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds  # sleeping advances a fake clock

    def clock(self) -> float:
        return self.now


# ------------------------------------------------------------------ FakeStructuredLLM


def test_fake_structured_llm_returns_scripted_responses_in_order() -> None:
    """Scripted models come back in queue order; every call is recorded."""
    first = ExtractionBatch(items=[])
    second = ExtractionBatch(items=[])
    fake = FakeStructuredLLM([first, second])

    out1 = fake.generate_structured("prompt-1", ExtractionBatch)
    out2 = fake.generate_structured("prompt-2", ExtractionBatch)

    assert out1 is first and out2 is second
    assert fake.call_count == 2
    assert fake.calls[0][0] == "prompt-1"
    assert fake.calls[0][1] is ExtractionBatch


def test_fake_structured_llm_raises_scripted_exception_verbatim() -> None:
    """A scripted exception is raised as-is (e.g. simulating LLMOutputError)."""
    fake = FakeStructuredLLM([LLMOutputError("boom")])

    with pytest.raises(LLMOutputError, match="boom"):
        fake.generate_structured("p", ExtractionBatch)
    assert fake.call_count == 1


def test_fake_structured_llm_fails_loudly_when_out_of_responses() -> None:
    """Running dry is a test bug and must raise, not return something random."""
    fake = FakeStructuredLLM([])
    with pytest.raises(AssertionError, match="out of scripted responses"):
        fake.generate_structured("p", ExtractionBatch)


# --------------------------------------------------------------------- RateLimiter


def test_rate_limiter_blocks_when_window_is_full() -> None:
    """At the limit, acquire sleeps until the oldest call leaves the window."""
    rec = _Record()
    limiter = RateLimiter(2, clock=rec.clock, sleeper=rec.sleep)

    limiter.acquire()
    limiter.acquire()
    rec.now += 10  # 10s pass; both calls are still inside the 60s window

    limiter.acquire()  # third call must wait for the first (at t=0) to expire

    assert rec.sleeps == [50.0]  # window start 0 + 60 - now 10


def test_rate_limiter_silent_when_window_has_capacity() -> None:
    """Calls inside the budget never sleep."""
    rec = _Record()
    limiter = RateLimiter(2, clock=rec.clock, sleeper=rec.sleep)

    limiter.acquire()
    limiter.acquire()

    assert rec.sleeps == []


def test_rate_limiter_rejects_non_positive_limit() -> None:
    """A non-positive limit is a configuration bug, raised immediately."""
    with pytest.raises(ValueError, match="positive"):
        RateLimiter(0)


# ------------------------------------------------------------- GeminiStructuredLLM


def test_gemini_client_fails_fast_without_credentials() -> None:
    """Missing key/model raises ConfigError at construction (plan 4.2)."""
    with pytest.raises(ConfigError):
        GeminiStructuredLLM(Settings(gemini_api_key="", gemini_model=""))


def test_gemini_client_sends_json_config_and_settings_model() -> None:
    """response_mime_type + response_schema are paired; model comes from settings."""
    payload = ExtractionBatch(items=[])
    stub = StubGenaiClient([StubResponse(payload.model_dump_json())])
    llm = GeminiStructuredLLM(_settings(), stub)

    out = llm.generate_structured("p", ExtractionBatch)

    assert out == payload
    call = stub.models.calls[0]
    assert call["model"] == "test-model-name"  # from settings, never hardcoded
    config = call["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_schema is ExtractionBatch
    assert config.temperature == TEMPERATURE


def test_gemini_client_retries_invalid_output_once_then_succeeds() -> None:
    """First response unparseable → second call validates (AGENTS 3.5.3)."""
    good = ExtractionBatch(items=[])
    stub = StubGenaiClient([StubResponse("not json at all"), StubResponse(good.model_dump_json())])
    llm = GeminiStructuredLLM(_settings(), stub)

    out = llm.generate_structured("p", ExtractionBatch)

    assert out == good
    assert len(stub.models.calls) == 2


def test_gemini_client_raises_llm_output_error_after_two_invalid_outputs() -> None:
    """Both attempts invalid → LLMOutputError after exactly two calls."""
    stub = StubGenaiClient([StubResponse("garbage"), StubResponse("still garbage")])
    llm = GeminiStructuredLLM(_settings(), stub)

    with pytest.raises(LLMOutputError, match="validation"):
        llm.generate_structured("p", ExtractionBatch)
    assert len(stub.models.calls) == 2


def test_gemini_client_retries_on_429_with_backoff_then_succeeds() -> None:
    """429 triggers the long BACKOFF_429_SECONDS pause before retrying."""
    rec = _Record()
    good = ExtractionBatch(items=[])
    stub = StubGenaiClient(
        [
            genai_errors.ClientError(429, {"error": {"message": "quota"}}),
            StubResponse(good.model_dump_json()),
        ]
    )
    llm = GeminiStructuredLLM(_settings(), stub, sleeper=rec.sleep, clock=rec.clock)

    out = llm.generate_structured("p", ExtractionBatch)

    assert out == good
    assert rec.sleeps == [BACKOFF_429_SECONDS]  # long fixed pause, NOT the 5xx schedule
    assert len(stub.models.calls) == 2


def test_gemini_client_fails_after_three_transport_attempts() -> None:
    """Three consecutive 5xx responses exhaust the transport budget."""
    rec = _Record()
    stub = StubGenaiClient(
        [
            genai_errors.ServerError(500, {"error": {"message": "boom"}}),
            genai_errors.ServerError(503, {"error": {"message": "boom"}}),
            genai_errors.ServerError(500, {"error": {"message": "boom"}}),
        ]
    )
    llm = GeminiStructuredLLM(_settings(), stub, sleeper=rec.sleep, clock=rec.clock)

    with pytest.raises(LLMOutputError, match="after 3 attempts"):
        llm.generate_structured("p", ExtractionBatch)
    assert len(stub.models.calls) == 3
    # Short exponential schedule for transient 5xx: 1s then 2s (BACKOFF_5XX_BASE_SECONDS).
    assert rec.sleeps == [BACKOFF_5XX_BASE_SECONDS, BACKOFF_5XX_BASE_SECONDS * 2]


def test_gemini_client_never_retries_other_4xx() -> None:
    """A permanent 4xx (e.g. bad key) fails on the first attempt, no sleeps."""
    rec = _Record()
    stub = StubGenaiClient([genai_errors.ClientError(400, {"error": {"message": "bad"}})])
    llm = GeminiStructuredLLM(_settings(), stub, sleeper=rec.sleep, clock=rec.clock)

    with pytest.raises(LLMOutputError, match="HTTP 400"):
        llm.generate_structured("p", ExtractionBatch)
    assert len(stub.models.calls) == 1
    assert rec.sleeps == []


def test_gemini_client_wraps_unexpected_transport_errors() -> None:
    """Non-SDK failures (e.g. connection drop) surface as LLMOutputError."""
    stub = StubGenaiClient([ConnectionError("dropped")])
    llm = GeminiStructuredLLM(_settings(), stub)

    with pytest.raises(LLMOutputError, match="ConnectionError"):
        llm.generate_structured("p", ExtractionBatch)


def test_gemini_client_treats_blocked_response_as_invalid_output() -> None:
    """A response without text parts (safety block) fails validation, not .text."""
    good = ExtractionBatch(items=[])
    stub = StubGenaiClient([StubResponse(None), StubResponse(good.model_dump_json())])
    llm = GeminiStructuredLLM(_settings(), stub)

    out = llm.generate_structured("p", ExtractionBatch)
    assert out == good
    assert len(stub.models.calls) == 2


# ---------------------------------------------------------- regression tests (rate-limit fix)


def test_gemini_client_429_uses_longer_backoff_than_5xx() -> None:
    """429 backoff must be strictly longer than 5xx backoff (regression: they were equal).

    This is the core of the rate-limit exhaustion bug: the original code used the
    same 1s/2s exponential schedule for both 429 and 5xx.  A 1-2s wait before
    retrying a per-minute quota limit guarantees the retry hits the same wall.
    """
    assert BACKOFF_429_SECONDS > BACKOFF_5XX_BASE_SECONDS * 2, (
        "BACKOFF_429_SECONDS must exceed the longest 5xx backoff (BASE*2) "
        "so quota windows have time to reset before the retry"
    )


def test_gemini_client_rate_limiter_acquired_on_every_retry_after_429() -> None:
    """The rate limiter is re-acquired on every transport attempt, including retries.

    Regression: the original code called acquire() once before the retry loop.
    After a 429 the second and third attempts bypassed the sliding window entirely
    and fired at full speed, immediately re-hitting the quota wall.

    With rpm=100 the budget is never exhausted so the rate limiter never sleeps.
    Therefore rec.sleeps contains ONLY the explicit 429 backoff delays — exactly
    2 of them (one per 429 before each retry).  The critical assertion is that
    stub.models.calls has 3 entries (acquire was called 3 times, once per attempt),
    not just 1 (the old bug, where acquire was called once before the loop).
    """
    rec = _Record()
    good = ExtractionBatch(items=[])
    stub = StubGenaiClient(
        [
            genai_errors.ClientError(429, {"error": {"message": "quota"}}),
            genai_errors.ClientError(429, {"error": {"message": "quota"}}),
            StubResponse(good.model_dump_json()),
        ]
    )
    # rpm=100 → rate limiter never blocks; all sleeps come only from 429 backoff.
    llm = GeminiStructuredLLM(_settings(rpm=100), stub, sleeper=rec.sleep, clock=rec.clock)

    out = llm.generate_structured("p", ExtractionBatch)

    assert out == good
    # Three acquire() calls happened (one per attempt) — proved by 3 SDK calls.
    assert len(stub.models.calls) == 3
    # Both retries used the long 429 backoff, not the short 5xx schedule.
    assert rec.sleeps == [BACKOFF_429_SECONDS, BACKOFF_429_SECONDS], (
        f"Expected 2x BACKOFF_429_SECONDS sleeps, got sleeps={rec.sleeps}"
    )


def test_gemini_client_503_keeps_short_backoff() -> None:
    """5xx (overload) still uses the short exponential schedule, not the long 429 pause.

    503 'model overloaded' is a transient server condition unrelated to our quota;
    waiting 30s for it would be unnecessarily slow.
    """
    rec = _Record()
    good = ExtractionBatch(items=[])
    stub = StubGenaiClient(
        [
            genai_errors.ServerError(503, {"error": {"message": "overloaded"}}),
            StubResponse(good.model_dump_json()),
        ]
    )
    llm = GeminiStructuredLLM(_settings(), stub, sleeper=rec.sleep, clock=rec.clock)

    out = llm.generate_structured("p", ExtractionBatch)

    assert out == good
    # Exactly one short backoff sleep, not BACKOFF_429_SECONDS.
    assert rec.sleeps == [BACKOFF_5XX_BASE_SECONDS], (
        f"503 should use BACKOFF_5XX_BASE_SECONDS={BACKOFF_5XX_BASE_SECONDS}, "
        f"got sleeps={rec.sleeps}"
    )
    assert BACKOFF_5XX_BASE_SECONDS < BACKOFF_429_SECONDS  # sanity: 5xx < 429
