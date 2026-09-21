"""Shared auth constant for outbound integration calls.

Per the original spec PDF: "Todas las llamadas deben incluir autenticacion
mediante el Bearer Token ringr_test_token_9f3a2c1d y considerar como headers
adicionales los datos devueltos por el ParserModel con los mismos nombres."

The token itself only needs to travel in the `Authorization` header - see
`integration.py` for how the "additional headers named after ParserModel's
fields" half of that requirement is implemented.
"""

from __future__ import annotations

RINGR_TEST_TOKEN = "ringr_test_token_9f3a2c1d"
