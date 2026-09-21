from ringr_agents.auth import RINGR_TEST_TOKEN
from ringr_agents.integration import SimulatedIntegrationClient


def test_never_performs_a_real_network_call_and_always_returns_200():
    client = SimulatedIntegrationClient()

    response = client.post("https://api.debt.v1/commitment", {"committed_amount": 10.0})

    assert response.ok
    assert response.status_code == 200


def test_records_the_request_it_would_have_sent():
    client = SimulatedIntegrationClient()

    client.post("https://api.debt.v1/commitment", {"committed_amount": 10.0})

    assert len(client.sent_requests) == 1
    assert client.sent_requests[0].endpoint == "https://api.debt.v1/commitment"


def test_bearer_token_is_present_in_header_and_body():
    client = SimulatedIntegrationClient()

    client.post("https://api.ringr.assistance.v1/request", {"request": "algo"})

    sent = client.sent_requests[0]
    assert sent.headers["Authorization"] == f"Bearer {RINGR_TEST_TOKEN}"
    assert sent.body["auth_token"] == RINGR_TEST_TOKEN


def test_additional_headers_from_token_metadata_are_attached():
    client = SimulatedIntegrationClient()

    client.post("https://api.ringr.assistance.v1/request", {"request": "algo"})

    sent = client.sent_requests[0]
    assert "X-Ringr-Client-Id" in sent.headers
    assert "X-Ringr-Token-Scope" in sent.headers


def test_original_payload_fields_are_preserved_in_body():
    client = SimulatedIntegrationClient()

    client.post("https://api.debt.v1/commitment", {"commitment_date": "2026-01-15", "committed_amount": 150.0})

    sent = client.sent_requests[0]
    assert sent.body["commitment_date"] == "2026-01-15"
    assert sent.body["committed_amount"] == 150.0
