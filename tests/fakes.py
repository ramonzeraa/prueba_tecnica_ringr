"""Test doubles for the collaborators agents depend on.

These are the "simulated" ConversationModel/ParserModel the spec allows:
plain, fully controllable fakes with no real LLM behind them - each test
sets whatever `parse_data()` should return for the scenario under test.
"""

from __future__ import annotations

from typing import Any

from ringr_agents.integration import IntegrationClient, IntegrationResponse
from ringr_agents.models import ConversationModel, ParserModel


class FakeConversationModel(ConversationModel):
    def __init__(self, reply: str = "ok") -> None:
        self.reply = reply
        self.received_messages: list[str] = []

    def answer_user(self, user_message: str) -> str:
        self.received_messages.append(user_message)
        return self.reply


class FakeParserModel(ParserModel):
    def __init__(self, data: dict[str, Any] | None = None) -> None:
        self._data = data or {}

    def set_data(self, data: dict[str, Any]) -> None:
        """Simulates the parser's internal state advancing to a new turn."""
        self._data = data

    def parse_data(self) -> dict[str, Any]:
        return dict(self._data)


class SpyIntegrationClient(IntegrationClient):
    """Records every call instead of sending it anywhere, so tests can
    assert on what would have been sent."""

    def __init__(self, response: IntegrationResponse | None = None) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._response = response or IntegrationResponse(status_code=200, body={"status": "ok"})

    def post(self, endpoint: str, payload: dict[str, Any]) -> IntegrationResponse:
        self.calls.append((endpoint, payload))
        return self._response
