from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Any, Callable, Dict, Optional

from .agent import AgentBase
from .message_bus import SimpleMessageBus

logger = logging.getLogger(__name__)


class AgentWorker:
    """Worker that executes agents from a task queue or message bus.

    Usage:
      - create with a Supervisor-like registry (dict mapping name->AgentBase) or
        with a `resolve_agent` callable that returns an AgentBase for a given name.
      - call `start()` to begin background processing and `stop()` to shut down.
      - submit tasks via `submit(node, payload)` or publish messages to the
        provided `message_bus`.
    """

    def __init__(
        self,
        resolve_agent: Optional[Callable[[str], AgentBase]] = None,
        message_bus: Optional[SimpleMessageBus] = None,
    ) -> None:
        self._resolve_agent = resolve_agent
        self._queue: queue.Queue = queue.Queue()
        self._bus = message_bus
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self.results: Dict[str, Any] = {}

    def submit(self, node: str, payload: Any) -> None:
        """Submit a task to the internal queue."""
        self._queue.put((node, payload))

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("AgentWorker started")

    def stop(self, timeout: float | None = None) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=timeout)
        logger.info("AgentWorker stopped")

    def _resolve(self, node: str) -> AgentBase:
        if self._resolve_agent:
            return self._resolve_agent(node)
        raise RuntimeError("No agent resolver provided")

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                # prefer internal queue; fall back to message bus if present
                node = None
                payload = None
                try:
                    node, payload = self._queue.get(timeout=0.1)
                except queue.Empty:
                    if self._bus:
                        try:
                            msg = self._bus.consume("tasks", timeout=0.1)
                            node = msg.get("node")
                            payload = msg.get("payload")
                        except Exception:
                            continue
                    else:
                        continue

                agent = self._resolve(node)
                try:
                    res = agent.process(payload)
                    self.results[node] = res
                    logger.debug("Agent %s processed task", node)
                    # publish success result
                    if self._bus:
                        self._bus.publish("results", {"node": node, "success": True, "result": res})
                except Exception as exc:
                    logger.exception("Agent %s failed to process task", node)
                    if self._bus:
                        self._bus.publish("results", {"node": node, "success": False, "error": str(exc)})
                finally:
                    # mark task done if from internal queue
                    try:
                        self._queue.task_done()
                    except Exception:
                        pass
            except Exception:
                logger.exception("Unexpected error in worker loop")
                time.sleep(0.1)

    # helper for tests: run a single task synchronously
    def run_once(self, node: str, payload: Any) -> Any:
        agent = self._resolve(node)
        return agent.process(payload)
