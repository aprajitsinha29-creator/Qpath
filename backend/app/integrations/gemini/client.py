"""Gemini structured-output client — the ONLY module allowed to talk to the Gemini API.

Phase 2 step 2.2 (AGENTS 3.5). Three pieces:

- :class:`StructuredLLM` — the Protocol every service codes against, so tests
  inject :class:`FakeStructuredLLM` and **no test ever touches the network**.
- :class:`GeminiStructuredLLM` — the real implementation on ``google-genai``
  (never the deprecated ``google-generativeai``): one
  ``models.generate_content`` call with ``response_mime_type="application/json"``
  paired with ``response_schema`` (AGENTS 3.5.2), a client-side sliding-window
  rate limiter at ``GEMINI_REQUESTS_PER_MINUTE``, exponential backoff on
  429/5xx (max 3 attempts), and Pydantic validation of the response text with
  **one retry on invalid output** before raising :class:`LLMOutputError`
  (AGENTS 3.5.3/3.5.4).
- :class:`FakeStructuredLLM` — scripted double for tests and fixture runs.

Model name, key and rate limit all come from Settings (AGENTS 3.3.3) — nothing
here is hardcoded beyond protocol-level constants (temperature, attempt counts).
Transport and validation failures both surface as :class:`LLMOutputError` so
callers handle exactly one LLM failure type; the original cause is always chained.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from collections.abc import Callable
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ValidationError

from app.core.config import Settings
from app.core.errors import LLMOutputError

logger = logging.getLogger(__name__)

#: Sampling temperature (plan 3.5.2 wording: temperature=0.1 for stable output).
TEMPERATURE = 0.1

#: Transport attempts per generate_content call on 429/5xx (AGENTS 3.5.4).
MAX_TRANSPORT_ATTEMPTS = 3

#: Exponential backoff base in seconds: wait = BASE * 2**attempt → 1s, 2s, 4s.
BACKOFF_BASE_SECONDS = 1.0

#: Validation attempts per generate_structured call: initial + one retry
#: on invalid output (AGENTS 3.5.3) before LLMOutputError.
MAX_VALIDATION_ATTEMPTS = 2


@runtime_checkable
class StructuredLLM(Protocol):
    """Anything that can return schema-validated structured output for one prompt.

    Services depend on this Protocol (not the concrete client) so the real
    Gemini client and the test fake are interchangeable (AGENTS 3.5.1).

    Args:
        prompt: the fully rendered prompt text (see ``prompts.py``).
        schema: the Pydantic model class the output must validate against.

    Returns:
        An instance of ``schema`` built from the model's JSON output.

    Raises:
        LLMOutputError: the model could not produce valid output (transport
            failure or validation failure after the allowed retries).
    """

    def generate_structured(self, prompt: str, schema: type[BaseModel]) -> BaseModel:
        """Return one schema-validated object for the prompt (see class docstring)."""
        ...  # pragma: no cover - Protocol body never runs


class RateLimiter:
    """Client-side sliding-window rate limiter (AGENTS 3.5.4).

    Keeps at most ``requests_per_minute`` call timestamps within the last 60 s;
    ``acquire()`` sleeps until the oldest timestamp leaves the window when the
    budget is exhausted. Clock and sleeper are injectable so tests can verify
    the behavior without real waiting.
    """

    WINDOW_SECONDS = 60.0

    def __init__(
        self,
        requests_per_minute: int,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        """Store the limit and the injectable time sources.

        Args:
            requests_per_minute: maximum calls allowed per window (from Settings).
            clock: monotonic seconds source.
            sleeper: blocking sleep used when the budget is exhausted.
        """
        if requests_per_minute <= 0:
            raise ValueError("requests_per_minute must be positive")
        self._rpm = requests_per_minute
        self._clock = clock
        self._sleeper = sleeper
        self._call_times: deque[float] = deque()

    def acquire(self) -> None:
        """Block until a call is allowed, then record this call's timestamp."""
        now = self._clock()
        while self._call_times and self._call_times[0] <= now - self.WINDOW_SECONDS:
            self._call_times.popleft()
        if len(self._call_times) >= self._rpm:
            wait = self._call_times[0] + self.WINDOW_SECONDS - now
            if wait > 0:
                logger.debug("gemini rate limit reached, sleeping %.2fs", wait)
                self._sleeper(wait)
        self._call_times.append(self._clock())


class GeminiStructuredLLM:
    """Real :class:`StructuredLLM` on the google-genai SDK (sync path).

    Args:
        settings: cached Settings; must carry ``gemini_api_key`` and
            ``gemini_model`` (validated via ``settings.require_gemini()``).
        genai_client: optional prebuilt ``google.genai.Client`` — tests inject
            a stub whose ``models.generate_content`` returns scripted objects;
            otherwise a real client is created (and owned) from the key.
        sleeper: blocking sleep used by backoff and the rate limiter (tests
            pass a recorder instead of really waiting).
        clock: monotonic seconds source for the rate limiter.

    Raises:
        ConfigError: the settings lack a Gemini key or model (fail fast at
            construction, before any request is attempted).
    """

    def __init__(
        self,
        settings: Settings,
        genai_client: object | None = None,
        *,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        settings.require_gemini()
        self._settings = settings
        self._model_name = settings.gemini_model
        self._owns_client = genai_client is None
        self._sleeper = sleeper
        self._limiter = RateLimiter(
            settings.gemini_requests_per_minute, clock=clock, sleeper=sleeper
        )
        if genai_client is not None:
            # Structural duck-typing: the stub only needs .models.generate_content.
            self._client = genai_client
        else:
            from google import genai  # imported here so import failure is local

            self._client = genai.Client(api_key=settings.gemini_api_key)

    def close(self) -> None:
        """Release resources (the SDK client needs no explicit shutdown today)."""
        return None

    def generate_structured(self, prompt: str, schema: type[BaseModel]) -> BaseModel:
        """Run one structured generation and return a validated ``schema`` instance.

        Args:
            prompt: fully rendered prompt text.
            schema: Pydantic model the JSON output must validate against.

        Returns:
            The validated model instance.

        Raises:
            LLMOutputError: transport failed after backoff retries, or the
                output failed schema validation on the initial call and one
                retry (AGENTS 3.5.3).
        """
        last_error: Exception | None = None
        for _ in range(MAX_VALIDATION_ATTEMPTS):
            text = self._call_with_backoff(prompt, schema)
            try:
                return schema.model_validate_json(text)
            except ValidationError as exc:
                # Invalid output → one retry allowed; the next loop pass re-calls.
                last_error = exc
                logger.warning("gemini output failed schema validation, retrying once")
        raise LLMOutputError(
            f"Gemini returned output that failed {schema.__name__} validation "
            f"after {MAX_VALIDATION_ATTEMPTS} attempts"
        ) from last_error

    def _call_with_backoff(self, prompt: str, schema: type[BaseModel]) -> str:
        """Call generate_content once (rate-limited, retried on 429/5xx).

        Args:
            prompt: prompt text.
            schema: response_schema passed to the SDK alongside JSON mime type.

        Returns:
            The response text (possibly empty — validation then fails upstream).

        Raises:
            LLMOutputError: after MAX_TRANSPORT_ATTEMPTS on 429/5xx, or
                immediately on any other SDK/transport failure. Messages carry
                only the exception type and status code — never payload text
                that could embed credentials.
        """
        from google.genai import errors as genai_errors
        from google.genai import types as genai_types

        self._limiter.acquire()
        last_code: int | str | None = None
        for attempt in range(1, MAX_TRANSPORT_ATTEMPTS + 1):
            response = None
            retryable = False
            try:
                response = self._client.models.generate_content(  # type: ignore[attr-defined]
                    model=self._model_name,
                    contents=prompt,
                    config=genai_types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=schema,
                        temperature=TEMPERATURE,
                    ),
                )
            except genai_errors.ServerError as exc:
                # 5xx: transient on Google's side — back off and retry.
                last_code = exc.code
                retryable = True
            except genai_errors.ClientError as exc:
                # 429 (quota/rate) is the one retryable 4xx; any other 4xx is
                # a permanent request problem — never retried (mirrors the
                # SerpApi client's rule, AGENTS 3.4.6).
                last_code = exc.code
                if exc.code != 429:
                    raise LLMOutputError(f"Gemini rejected the request (HTTP {exc.code})") from exc
                retryable = True
            except Exception as exc:
                # Only the exception type is surfaced: SDK messages can embed
                # request payloads we must not log (AGENTS 3.3.6 spirit).
                raise LLMOutputError(f"Gemini request failed ({type(exc).__name__})") from exc
            if retryable and attempt < MAX_TRANSPORT_ATTEMPTS:
                delay = BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
                logger.warning(
                    "gemini transport error (code=%s), backing off %.1fs",
                    last_code,
                    delay,
                )
                self._sleeper(delay)
                continue
            if retryable:
                raise LLMOutputError(
                    f"Gemini request failed after {MAX_TRANSPORT_ATTEMPTS} attempts "
                    f"(last status code: {last_code})"
                )
            # Success path: extract text defensively — blocked/empty responses
            # raise or return None depending on SDK version; both mean
            # "invalid output" and are handled by the validation retry above.
            try:
                return response.text or ""
            except Exception:
                return ""
        raise LLMOutputError(  # pragma: no cover - loop always returns or raises
            "Gemini request loop exited unexpectedly"
        )


class FakeStructuredLLM:
    """Scripted :class:`StructuredLLM` for tests — never touches the network.

    Responses are consumed in order; an entry may be an exception (raised
    verbatim, e.g. ``LLMOutputError``) or a Pydantic instance returned as-is.
    ``calls`` records every ``(prompt, schema)`` so tests can assert on batch
    sizes, prompt contents and call counts (e.g. "retry once" → 2 calls).
    """

    def __init__(self, responses: list[BaseModel | Exception]) -> None:
        """Queue the responses to hand out, in call order.

        Args:
            responses: scripted results; exceptions are raised, models returned.
        """
        self._responses = list(responses)
        self.calls: list[tuple[str, type[BaseModel]]] = []

    @property
    def call_count(self) -> int:
        """Return how many times generate_structured was called."""
        return len(self.calls)

    def generate_structured(self, prompt: str, schema: type[BaseModel]) -> BaseModel:
        """Pop and return the next scripted response (raising it if an exception).

        Args:
            prompt: recorded into ``calls`` for assertions.
            schema: recorded into ``calls`` for assertions.

        Returns:
            The next scripted Pydantic instance.

        Raises:
            AssertionError: no scripted response remains (a test bug — better
                loud than silently wrong).
            Exception: verbatim, when the next scripted entry is an exception.
        """
        self.calls.append((prompt, schema))
        if not self._responses:
            raise AssertionError("FakeStructuredLLM ran out of scripted responses")
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response
