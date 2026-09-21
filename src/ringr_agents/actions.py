"""Pluggable business rules that turn parsed conversation data into an
outbound integration call.

Adding a new action type (or a new agent that needs one) never requires
touching `BaseAgent`: it only requires a new `AgentAction` subclass.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OutboundAction:
    """A concrete, ready-to-send integration call resolved from parsed data."""

    key: str
    endpoint: str
    payload: dict[str, Any]


class AgentAction(ABC):
    """A single business rule: when must it fire, and what should it send.

    `key` must be stable and unique per action *type* within an agent -
    it's what idempotency tracking is keyed on.
    """

    key: str
    endpoint: str

    @abstractmethod
    def is_triggered(self, parsed_data: dict[str, Any]) -> bool:
        """Whether the extracted data satisfies this action's conditions."""
        raise NotImplementedError

    @abstractmethod
    def build_payload(self, parsed_data: dict[str, Any]) -> dict[str, Any]:
        """Build the integration payload. Only called when `is_triggered` is True."""
        raise NotImplementedError

    def resolve(self, parsed_data: dict[str, Any]) -> OutboundAction | None:
        """Return the outbound call to send, or None if conditions aren't met."""
        if not self.is_triggered(parsed_data):
            return None
        return OutboundAction(
            key=self.key,
            endpoint=self.endpoint,
            payload=self.build_payload(parsed_data),
        )
