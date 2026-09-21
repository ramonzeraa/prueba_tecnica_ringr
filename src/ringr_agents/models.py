"""Contracts for the conversational engine primitives Ringr provides.

Concrete implementations (backed by whatever LLM/NLU stack Ringr runs) live
outside this project's scope. Agents only depend on these abstractions, so
any compliant implementation can be swapped in without touching agent code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ConversationModel(ABC):
    """Produces the agent's reply for the current turn.

    A concrete implementation is expected to keep the full turn history in
    its own internal state (previous messages, persona, business rules,
    etc.), so this interface only needs to expose the single entry point
    agents rely on.
    """

    @abstractmethod
    def answer_user(self, user_message: str) -> str:
        """Return the agent's reply to `user_message`."""
        raise NotImplementedError


class ParserModel(ABC):
    """Extracts structured, use-case-specific data from the conversation.

    The internal state is assumed to already hold everything needed to
    adapt to the calling agent's use case (which keys matter, how to read
    them out of the conversation). The returned dict's keys are therefore
    use-case-specific and documented per agent, not by this interface.
    """

    @abstractmethod
    def parse_data(self) -> dict[str, Any]:
        """Return the structured data extracted from the conversation so far."""
        raise NotImplementedError
