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
    def validate_and_normalize(self, parsed_data: dict[str, Any]) -> dict[str, Any] | None:
        """Validate the extracted data and, if it satisfies this action's
        conditions, return the normalized payload to send. Return None
        otherwise.

        This mirrors the spec's own wording ("validar y normalizar la
        informacion parseada y decidir si se debe ejecutar una accion") as
        a single step on purpose: an earlier version of this class split
        "decide" (`is_triggered`) and "build" (`build_payload`) into two
        separate methods that independently re-read the same fields from
        `parsed_data`, which meant nothing prevented a future subclass from
        building a payload without the matching validation. Doing both at
        once removes that failure mode structurally instead of relying on
        every implementation remembering to keep them in sync.
        """
        raise NotImplementedError

    def resolve(self, parsed_data: dict[str, Any]) -> OutboundAction | None:
        """Return the outbound call to send, or None if conditions aren't met."""
        payload = self.validate_and_normalize(parsed_data)
        if payload is None:
            return None
        return OutboundAction(key=self.key, endpoint=self.endpoint, payload=payload)
