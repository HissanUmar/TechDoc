from __future__ import annotations

from typing import Any, Dict, Optional


class AgentBase:
    def __init__(self) -> None:
        self.supervisor: Optional[object] = None

    def bind(self, supervisor: object) -> None:
        self.supervisor = supervisor

    def process(self, payload: Dict[str, Any]) -> Any:
        """Process a single turn. Override in subclasses."""
        raise NotImplementedError()
