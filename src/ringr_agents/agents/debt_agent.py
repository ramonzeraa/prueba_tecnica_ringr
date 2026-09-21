"""DebtAgent: registers payment commitments for pending debts.

Parsed data contract (produced by `ParserModel.parse_data()` for this use
case):
    commitment_date:   None | str  -- ISO format 'yyyy-mm-dd'
    committed_amount:  None | float

When both are present (not None) and valid, a commitment is registered via
POST https://api.debt.v1/commitment.
"""

from __future__ import annotations

from datetime import date
from numbers import Real
from typing import Any

from ..actions import AgentAction
from ..agent import BaseAgent
from ..integration import IntegrationClient
from ..models import ConversationModel, ParserModel


class RegisterDebtCommitmentAction(AgentAction):
    key = "debt.register_commitment"
    endpoint = "https://api.debt.v1/commitment"

    def is_triggered(self, parsed_data: dict[str, Any]) -> bool:
        return self._is_valid_date(parsed_data.get("commitment_date")) and self._is_valid_amount(
            parsed_data.get("committed_amount")
        )

    def build_payload(self, parsed_data: dict[str, Any]) -> dict[str, Any]:
        return {
            "commitment_date": parsed_data["commitment_date"],
            "committed_amount": float(parsed_data["committed_amount"]),
        }

    @staticmethod
    def _is_valid_date(value: Any) -> bool:
        if not isinstance(value, str):
            return False
        try:
            date.fromisoformat(value)
        except ValueError:
            return False
        return True

    @staticmethod
    def _is_valid_amount(value: Any) -> bool:
        # bool is a Real subclass in Python; explicitly excluded so a
        # stray `True`/`False` from a parser bug can't slip through.
        return isinstance(value, Real) and not isinstance(value, bool)


class DebtAgent(BaseAgent):
    """Agente de cobros: registra compromisos de pago de deudas pendientes."""

    def __init__(
        self,
        conversation_model: ConversationModel,
        parser_model: ParserModel,
        integration_client: IntegrationClient,
    ) -> None:
        super().__init__(
            conversation_model=conversation_model,
            parser_model=parser_model,
            integration_client=integration_client,
            actions=[RegisterDebtCommitmentAction()],
        )
