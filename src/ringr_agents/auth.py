"""Bearer-token auth helpers for outbound integration calls.

ASSUMPTION: the test spec's wording on auth was partially garbled by OCR
("...Bearer Token (header, body) y considerar como headers adicionales los
datos devueltos por ringr_test_token_9f3a2c1d"). This module implements the
most literal reading that still makes sense end to end:

  1. The token is sent in the `Authorization` header, AND duplicated in the
     request body (the spec explicitly says "header, body").
  2. "Los datos devueltos por" is read as: a real auth service would
     validate the token and return metadata (client id, granted scope) that
     gets attached as additional headers. Since no real auth service exists
     here, `resolve_token_metadata` mocks that lookup with fixed values.

This is documented as an assumption in the README.
"""

from __future__ import annotations

RINGR_TEST_TOKEN = "ringr_test_token_9f3a2c1d"


def resolve_token_metadata(token: str) -> dict[str, str]:
    """Mock of the metadata a real auth service would return after
    validating `token`. Kept as a pure function so a real lookup can
    replace it later without changing any caller.
    """
    return {
        "X-Ringr-Client-Id": "ringr-agents-demo",
        "X-Ringr-Token-Scope": "agents:actions:write",
    }
