from fakes import FakeConversationModel, FakeParserModel, SpyIntegrationClient

from ringr_agents.agents.assistance_agent import AssistanceAgent


def make_agent(parser: FakeParserModel, integration: SpyIntegrationClient) -> AssistanceAgent:
    return AssistanceAgent(
        conversation_id="conv-assistance-test",
        conversation_model=FakeConversationModel(reply="claro, lo registro"),
        parser_model=parser,
        integration_client=integration,
    )


def test_fires_request_when_present():
    parser = FakeParserModel({"request": "Necesito hablar con un agente humano"})
    integration = SpyIntegrationClient()
    agent = make_agent(parser, integration)

    reply = agent.handle_turn("Quiero hablar con una persona")

    assert reply == "claro, lo registro"
    assert len(integration.calls) == 1
    endpoint, payload = integration.calls[0]
    assert endpoint == "https://api.ringr.assistance/v1/request"
    assert payload == {"request": "Necesito hablar con un agente humano"}


def test_does_not_fire_when_request_is_none():
    parser = FakeParserModel({"request": None})
    integration = SpyIntegrationClient()
    agent = make_agent(parser, integration)

    agent.handle_turn("Solo estoy mirando, gracias")

    assert integration.calls == []


def test_does_not_fire_when_request_is_blank():
    parser = FakeParserModel({"request": "   "})
    integration = SpyIntegrationClient()
    agent = make_agent(parser, integration)

    agent.handle_turn("...")

    assert integration.calls == []


def test_payload_is_trimmed():
    parser = FakeParserModel({"request": "  cambiar mi direccion de envio  "})
    integration = SpyIntegrationClient()
    agent = make_agent(parser, integration)

    agent.handle_turn("Necesito cambiar mi direccion")

    _, payload = integration.calls[0]
    assert payload == {"request": "cambiar mi direccion de envio"}


def test_does_not_fire_twice_for_the_same_conversation():
    parser = FakeParserModel({"request": "Quiero cancelar mi pedido"})
    integration = SpyIntegrationClient()
    agent = make_agent(parser, integration)

    agent.handle_turn("Quiero cancelar mi pedido")
    agent.handle_turn("¿Ya lo registraste?")
    agent.handle_turn("Repito: quiero cancelar mi pedido")

    assert len(integration.calls) == 1
