"""AssistanceAgent: registers customer-service requests for human follow-up.

Parsed data contract (produced by `ParserModel.parse_data()` for this use
case):
    request: None | str

When present and non-empty, the request is registered via
POST https://api.ringr.assistance.v1/request.
"""

from __future__ import annotations

from typing import Any

from ..actions import AgentAction
from ..agent import BaseAgent
from ..integration import IntegrationClient
from ..models import ConversationModel, ParserModel


class RegisterAssistanceRequestAction(AgentAction):
    key = "assistance.register_request"
    endpoint = "https://api.ringr.assistance.v1/request"

    def is_triggered(self, parsed_data: dict[str, Any]) -> bool:
        request = parsed_data.get("request")
        return isinstance(request, str) and request.strip() != ""

    def build_payload(self, parsed_data: dict[str, Any]) -> dict[str, Any]:
        return {"request": parsed_data["request"].strip()}


class AssistanceAgent(BaseAgent):
    """Agente de atencion al cliente: resuelve consultas y registra
    solicitudes para gestion por agentes humanos."""

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
            actions=[RegisterAssistanceRequestAction()],
        )
