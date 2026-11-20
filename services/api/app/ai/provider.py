"""Bounded, structured requests to an explicitly configured chat provider."""

import json
from collections.abc import Mapping
from math import isfinite
from time import monotonic
from typing import Any, Protocol
from urllib.parse import urlsplit

import httpx

MAX_RESPONSE_BYTES = 64 * 1024
MAX_OUTPUT_TOKENS = 384


class ProviderError(RuntimeError):
    """The configured provider did not return a usable structured response."""


class JsonProvider(Protocol):
    def generate(
        self, system: str, user: dict[str, Any], schema: dict[str, Any]
    ) -> dict[str, Any]: ...


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for key, value in pairs:
        if key in values:
            raise ValueError("Duplicate JSON object key")
        values[key] = value
    return values


def _reject_constant(value: str) -> None:
    raise ValueError("Invalid JSON number: " + value)


def _parse_json(raw: bytes | str) -> dict[str, Any]:
    parsed = json.loads(raw, object_pairs_hook=_unique_keys, parse_constant=_reject_constant)
    if not isinstance(parsed, dict):
        raise ValueError("Expected a JSON object")
    return parsed


class HttpJsonProvider:
    """An OpenAI-compatible chat-completions adapter with no tools or retries."""

    def __init__(
        self,
        endpoint: str,
        model: str,
        api_key: str = "",
        timeout_seconds: float = 5,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        url = urlsplit(endpoint)
        is_loopback = url.hostname in {"localhost", "127.0.0.1", "::1"}
        if (
            not url.hostname
            or (url.scheme != "https" and not (is_loopback and url.scheme == "http"))
            or url.username is not None
            or url.password is not None
            or url.fragment
        ):
            raise ValueError("Configure an HTTPS provider URL or an HTTP loopback URL.")
        if not model.strip():
            raise ValueError("Configure a supported provider model.")
        if not isfinite(timeout_seconds) or not 0 < timeout_seconds <= 10:
            raise ValueError("Provider timeout must be above zero and at most ten seconds.")
        self._endpoint = endpoint
        self._model = model
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    def generate(self, system: str, user: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
        request = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
            ],
            "max_completion_tokens": MAX_OUTPUT_TOKENS,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "civitwin_response", "strict": True, "schema": schema},
            },
        }
        headers = {"Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        deadline = monotonic() + self._timeout_seconds
        try:
            with httpx.Client(
                timeout=self._timeout_seconds, trust_env=False, transport=self._transport
            ) as client:
                with client.stream("POST", self._endpoint, headers=headers, json=request) as reply:
                    reply.raise_for_status()
                    content = bytearray()
                    for chunk in reply.iter_bytes():
                        if (
                            monotonic() >= deadline
                            or len(content) + len(chunk) > MAX_RESPONSE_BYTES
                        ):
                            raise ProviderError("The provider response exceeded its limits.")
                        content.extend(chunk)
            envelope = _parse_json(bytes(content))
            choices = envelope["choices"]
            if not isinstance(choices, list) or len(choices) != 1:
                raise ValueError("Expected exactly one choice")
            choice = choices[0]
            if not isinstance(choice, Mapping) or choice.get("finish_reason") != "stop":
                raise ValueError("The response was incomplete")
            message = choice["message"]
            if (
                not isinstance(message, Mapping)
                or message.get("refusal")
                or message.get("tool_calls")
                or message.get("function_call")
                or not isinstance(message.get("content"), str)
            ):
                raise ValueError("The response was not a structured message")
            return _parse_json(message["content"])
        except (httpx.HTTPError, KeyError, TypeError, ValueError, RecursionError):
            raise ProviderError(
                "The configured provider did not return a usable response."
            ) from None
