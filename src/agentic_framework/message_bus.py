from __future__ import annotations

import queue
from typing import Any, Dict


class SimpleMessageBus:
    """Topic-capable in-process message bus.

    Topics are backed by independent queues. Common topics used:
      - 'tasks': supervisor -> workers
      - 'results': workers -> supervisor
      - 'dlq': dead-letter queue for failed messages
    """

    def __init__(self) -> None:
        self._topics: Dict[str, queue.Queue] = {}

    def _ensure(self, topic: str) -> queue.Queue:
        if topic not in self._topics:
            self._topics[topic] = queue.Queue()
        return self._topics[topic]

    def publish(self, topic: str, message: Any) -> None:
        q = self._ensure(topic)
        q.put(message)

    def consume(self, topic: str, timeout: float | None = None) -> Any:
        q = self._ensure(topic)
        return q.get(timeout=timeout)

    def empty(self, topic: str) -> bool:
        q = self._ensure(topic)
        return q.empty()

