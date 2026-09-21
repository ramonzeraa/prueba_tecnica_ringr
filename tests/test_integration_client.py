from ringr_agents.auth import RINGR_TEST_TOKEN
from ringr_agents.integration import SimulatedIntegrationClient


def test_never_performs_a_real_network_call_and_always_returns_200():
    client = SimulatedIntegrationClient()

    response = client.post("https://api.ringr.debt/v1/commitment", {"committed_amount": 10.0})

    assert response.ok
    assert response.status_code == 200


def test_records_the_request_it_would_have_sent():
    client = SimulatedIntegrationClient()

    client.post("https://api.ringr.debt/v1/commitment", {"committed_amount": 10.0})

    assert len(client.sent_requests) == 1
    assert client.sent_requests[0].endpoint == "https://api.ringr.debt/v1/commitment"


def test_bearer_token_is_present_in_authorization_header():
    client = SimulatedIntegrationClient()

    client.post("https://api.ringr.assistance/v1/request", {"request": "algo"})

    sent = client.sent_requests[0]
    assert sent.headers["Authorization"] == f"Bearer {RINGR_TEST_TOKEN}"


def test_payload_fields_are_mirrored_as_additional_headers_with_the_same_names():
    """Spec: 'considerar como headers adicionales los datos devueltos por el
    ParserModel con los mismos nombres'. Every AgentAction in this project
    builds its payload straight from ParserModel's fields, so payload IS
    that data - it must show up as headers under identical keys."""
    client = SimulatedIntegrationClient()

    client.post(
        "https://api.ringr.debt/v1/commitment",
        {"commitment_date": "2026-01-15", "committed_amount": 150.0},
    )

    sent = client.sent_requests[0]
    assert sent.headers["commitment_date"] == "2026-01-15"
    assert sent.headers["committed_amount"] == "150.0"


def test_none_fields_are_not_turned_into_headers():
    client = SimulatedIntegrationClient()

    client.post("https://api.ringr.assistance/v1/request", {"request": "algo", "unused": None})

    sent = client.sent_requests[0]
    assert "unused" not in sent.headers


def test_body_matches_the_payload_exactly():
    client = SimulatedIntegrationClient()

    payload = {"commitment_date": "2026-01-15", "committed_amount": 150.0}
    client.post("https://api.ringr.debt/v1/commitment", payload)

    assert client.sent_requests[0].body == payload
