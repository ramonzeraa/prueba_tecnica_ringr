"""Tests BaseAgent's own contract in isolation from any concrete agent,
using a throwaway AgentAction. This is also a live demonstration of the
extensibility requirement: a brand new action type plugs straight into
BaseAgent with zero changes to it.
"""

from __future__ import annotations

from typing import Any

from fakes import FakeConversationModel, FakeParserModel, SpyIntegrationClient

from ringr_agents.actions import AgentAction
from ringr_agents.agent import BaseAgent
from ringr_agents.integration import IntegrationResponse


class AlwaysOnAction(AgentAction):
    key = "test.always_on"
    endpoint = "https://api.example.test/always-on"

    def is_triggered(self, parsed_data: dict[str, Any]) -> bool:
        return True

    def build_payload(self, parsed_data: dict[str, Any]) -> dict[str, Any]:
        return {"echo": parsed_data.get("value")}


class NeverOnAction(AgentAction):
    key = "test.never_on"
    endpoint = "https://api.example.test/never-on"

    def is_triggered(self, parsed_data: dict[str, Any]) -> bool:
        return False

    def build_payload(self, parsed_data: dict[str, Any]) -> dict[str, Any]:
        raise AssertionError("build_payload must not be called when is_triggered is False")


def test_only_triggered_actions_fire_when_an_agent_has_several():
    parser = FakeParserModel({"value": 1})
    integration = SpyIntegrationClient()
    agent = BaseAgent(
        conversation_model=FakeConversationModel(),
        parser_model=parser,
        integration_client=integration,
        actions=[AlwaysOnAction(), NeverOnAction()],
    )

    agent.handle_turn("hola")

    assert [endpoint for endpoint, _ in integration.calls] == ["https://api.example.test/always-on"]


def test_a_failed_integration_call_is_retried_on_a_later_turn():
    parser = FakeParserModel({"value": 1})
    failing_integration = SpyIntegrationClient(response=IntegrationResponse(status_code=500))
    agent = BaseAgent(
        conversation_model=FakeConversationModel(),
        parser_model=parser,
        integration_client=failing_integration,
        actions=[AlwaysOnAction()],
    )

    agent.handle_turn("primer intento")
    agent.handle_turn("segundo intento")

    # Neither attempt succeeded, so idempotency tracking never kicks in and
    # every turn keeps retrying - a failed call must not be silently dropped.
    assert len(failing_integration.calls) == 2


def test_a_successful_call_is_never_retried():
    parser = FakeParserModel({"value": 1})
    integration = SpyIntegrationClient()
    agent = BaseAgent(
        conversation_model=FakeConversationModel(),
        parser_model=parser,
        integration_client=integration,
        actions=[AlwaysOnAction()],
    )

    agent.handle_turn("primer turno")
    agent.handle_turn("segundo turno")
    agent.handle_turn("tercer turno")

    assert len(integration.calls) == 1
