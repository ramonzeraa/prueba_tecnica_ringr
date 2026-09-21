"""Outbound HTTP integration boundary.

`IntegrationClient` is the abstraction agents depend on (Dependency
Inversion): agents never know or care whether calls are simulated or real.
`SimulatedIntegrationClient` is the implementation used everywhere in this
project, per the spec's explicit requirement that integrations "no deben
ejecutarse realmente" (must never actually hit the network). It still builds
the request exactly as a real client would (headers + body), so the wiring
is production-shaped and swapping in a real `requests`-based client later is
a one-class change.

Auth requirement (from the spec): every call carries the Bearer token in the
`Authorization` header, plus additional headers mirroring the data returned
by `ParserModel`, using the same field names. Since every `AgentAction` in
this project builds its payload directly from `ParserModel.parse_data()`
output with unchanged field names (see `agents/debt_agent.py` and
`agents/assistance_agent.py`), `payload` *is* "the data returned by
ParserModel, with the same names" - so mirroring `payload` into headers
satisfies the requirement without the client needing a second, separate
copy of the parsed data.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from .auth import RINGR_TEST_TOKEN


@dataclass(frozen=True)
class IntegrationResponse:
    status_code: int
    body: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300


@dataclass(frozen=True)
class SentRequest:
    """Record of a request the simulated client would have sent, kept for
    inspection in tests and demos."""

    endpoint: str
    headers: dict[str, str]
    body: dict[str, Any]


class IntegrationClient(ABC):
    """Sends the outbound call an `AgentAction` decided to trigger."""

    @abstractmethod
    def post(self, endpoint: str, payload: dict[str, Any]) -> IntegrationResponse:
        raise NotImplementedError


class SimulatedIntegrationClient(IntegrationClient):
    """Never performs a real network call.

    Per the spec, a successful call is assumed to always return 200 OK, so
    that's what `post` returns once it has recorded the fully-built request.
    """

    def __init__(self, auth_token: str = RINGR_TEST_TOKEN) -> None:
        self._auth_token = auth_token
        self.sent_requests: list[SentRequest] = []

    def post(self, endpoint: str, payload: dict[str, Any]) -> IntegrationResponse:
        headers = {
            "Authorization": f"Bearer {self._auth_token}",
            "Content-Type": "application/json",
            **self._as_header_values(payload),
        }
        body = dict(payload)

        self.sent_requests.append(SentRequest(endpoint=endpoint, headers=headers, body=body))

        return IntegrationResponse(status_code=200, body={"status": "ok"})

    @staticmethod
    def _as_header_values(payload: dict[str, Any]) -> dict[str, str]:
        """HTTP headers must be strings; None fields are dropped since a
        triggered action's payload never legitimately carries one."""
        return {key: str(value) for key, value in payload.items() if value is not None}
