from fakes import FakeConversationModel, FakeParserModel, SpyIntegrationClient

from ringr_agents.agents.debt_agent import DebtAgent


def make_agent(parser: FakeParserModel, integration: SpyIntegrationClient) -> DebtAgent:
    return DebtAgent(
        conversation_model=FakeConversationModel(reply="entendido"),
        parser_model=parser,
        integration_client=integration,
    )


def test_fires_commitment_when_both_fields_present():
    parser = FakeParserModel({"commitment_date": "2026-01-15", "committed_amount": 150.0})
    integration = SpyIntegrationClient()
    agent = make_agent(parser, integration)

    reply = agent.handle_turn("Puedo pagar 150 el 15 de enero")

    assert reply == "entendido"
    assert len(integration.calls) == 1
    endpoint, payload = integration.calls[0]
    assert endpoint == "https://api.ringr.debt/v1/commitment"
    assert payload == {"commitment_date": "2026-01-15", "committed_amount": 150.0}


def test_does_not_fire_when_date_missing():
    parser = FakeParserModel({"commitment_date": None, "committed_amount": 150.0})
    integration = SpyIntegrationClient()
    agent = make_agent(parser, integration)

    agent.handle_turn("Puedo pagar 150")

    assert integration.calls == []


def test_does_not_fire_when_amount_missing():
    parser = FakeParserModel({"commitment_date": "2026-01-15", "committed_amount": None})
    integration = SpyIntegrationClient()
    agent = make_agent(parser, integration)

    agent.handle_turn("El 15 de enero puedo pagar")

    assert integration.calls == []


def test_does_not_fire_with_invalid_date_format():
    parser = FakeParserModel({"commitment_date": "15/01/2026", "committed_amount": 150.0})
    integration = SpyIntegrationClient()
    agent = make_agent(parser, integration)

    agent.handle_turn("Pago el 15/01/2026")

    assert integration.calls == []


def test_does_not_fire_twice_across_turns_with_same_data():
    parser = FakeParserModel({"commitment_date": "2026-01-15", "committed_amount": 150.0})
    integration = SpyIntegrationClient()
    agent = make_agent(parser, integration)

    agent.handle_turn("Puedo pagar 150 el 15 de enero")
    agent.handle_turn("Confirmo lo mismo")
    agent.handle_turn("Si, 150 el 15 de enero")

    assert len(integration.calls) == 1


def test_does_not_fire_again_once_data_changes_after_being_sent():
    parser = FakeParserModel({"commitment_date": "2026-01-15", "committed_amount": 150.0})
    integration = SpyIntegrationClient()
    agent = make_agent(parser, integration)

    agent.handle_turn("Puedo pagar 150 el 15 de enero")
    parser.set_data({"commitment_date": "2026-02-01", "committed_amount": 200.0})
    agent.handle_turn("Mejor cambio a 200 el 1 de febrero")

    # Only one commitment per conversation is registered by this agent's
    # action (idempotency is keyed by action type, not by payload value).
    assert len(integration.calls) == 1
