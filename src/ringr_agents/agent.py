"""Agent lifecycle shared by every concrete agent.

`BaseAgent.handle_turn` is a template method: the four steps described by
the spec (get a reply, parse data, decide, act) always happen in that
order and are always the same shape - only the injected collaborators
(`ConversationModel`, `ParserModel`, `AgentAction`s) change per use case.

Each `BaseAgent` instance represents exactly one conversation, and
`conversation_id` makes that identity explicit: it correlates this agent's
log lines when many conversations run concurrently, and is the other half
(together with `AgentAction.key`) of the key a production idempotency store
would use if the in-memory `_executed_action_keys` set were ever swapped
for a shared one (see the README's "Escalabilidad" section).
"""

from __future__ import annotations

import logging

from .actions import AgentAction
from .integration import IntegrationClient
from .models import ConversationModel, ParserModel

logger = logging.getLogger(__name__)


class BaseAgent:
    def __init__(
        self,
        conversation_id: str,
        conversation_model: ConversationModel,
        parser_model: ParserModel,
        integration_client: IntegrationClient,
        actions: list[AgentAction],
    ) -> None:
        if not conversation_id:
            raise ValueError("conversation_id must be a non-empty string")

        self._conversation_id = conversation_id
        self._conversation_model = conversation_model
        self._parser_model = parser_model
        self._integration_client = integration_client
        self._actions = actions
        self._executed_action_keys: set[str] = set()

    @property
    def conversation_id(self) -> str:
        return self._conversation_id

    def handle_turn(self, user_message: str) -> str:
        """Run one conversation turn: reply, extract data, and fire any
        action whose conditions are now met.

        Idempotency: an action's `key` is only added to
        `_executed_action_keys` once the integration call succeeds, so a
        failed call may be retried on a later turn, but a successful one
        never fires twice for the lifetime of this agent instance (i.e.
        for this conversation).
        """
        reply = self._conversation_model.answer_user(user_message)
        parsed_data = self._parser_model.parse_data()

        for action in self._actions:
            if action.key in self._executed_action_keys:
                logger.debug(
                    "[%s] Action '%s' already executed for this conversation, skipping.",
                    self._conversation_id,
                    action.key,
                )
                continue

            outbound = action.resolve(parsed_data)
            if outbound is None:
                logger.debug(
                    "[%s] Action '%s' conditions not met this turn, skipping.",
                    self._conversation_id,
                    action.key,
                )
                continue

            # Only the conversation id, action key and endpoint are logged,
            # never the payload itself: parsed conversation data (debt
            # amounts, support requests, ...) may be sensitive and has no
            # reason to end up in log storage.
            response = self._integration_client.post(outbound.endpoint, outbound.payload)
            if response.ok:
                self._executed_action_keys.add(action.key)
                logger.info(
                    "[%s] Action '%s' executed successfully (endpoint=%s).",
                    self._conversation_id,
                    action.key,
                    outbound.endpoint,
                )
            else:
                logger.warning(
                    "[%s] Action '%s' integration call failed (status=%s, endpoint=%s); will retry next turn.",
                    self._conversation_id,
                    action.key,
                    response.status_code,
                    outbound.endpoint,
                )

        return reply
