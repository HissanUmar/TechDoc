import concurrent.futures
import logging
import threading
import time
from typing import Dict, Any, List, Iterable

from .agent import AgentBase
from .state import InMemoryStateStore

logger = logging.getLogger(__name__)


class Supervisor:
    """Supervisor with basic DAG execution, retries and timeouts.

    - Workflows are defined as a DAG mapping node -> list of dependency node names.
    - Each node maps to a registered agent by the same name.
    - Nodes execute once their dependencies complete successfully.
    - Nodes are executed in parallel where dependencies allow.
    - On node failure, the supervisor retries up to `retry_attempts` with exponential backoff.
    """

    def __init__(
        self,
        state_store: InMemoryStateStore | None = None,
        max_workers: int = 4,
        retry_attempts: int = 3,
        retry_backoff: float = 1.0,
        agent_timeout: float | None = None,
    ) -> None:
        self.state = state_store or InMemoryStateStore()
        self.agents: Dict[str, AgentBase] = {}
        self.max_workers = max_workers
        self.retry_attempts = retry_attempts
        self.retry_backoff = retry_backoff
        self.agent_timeout = agent_timeout
        self._lock = threading.Lock()

    def register_agent(self, name: str, agent: AgentBase) -> None:
        self.agents[name] = agent
        agent.bind(supervisor=self)
        logger.info("Registered agent %s", name)

    def start_agent(self, name: str, payload: Dict[str, Any] | None = None) -> Any:
        """Backward-compatible single-agent start."""
        agent = self.agents.get(name)
        if agent is None:
            raise KeyError(f"Agent not found: {name}")
        return agent.process(payload or {})

    # -- workflow helpers -------------------------------------------------
    def _toposort(self, dag: Dict[str, List[str]]) -> List[str]:
        # Kahn's algorithm to detect cycles and produce topo order
        indeg: Dict[str, int] = {n: 0 for n in dag}
        for n, deps in dag.items():
            for d in deps:
                if d not in indeg:
                    raise KeyError(f"Dependency {d} not in DAG nodes")
                indeg[n] += 1

        q: List[str] = [n for n, v in indeg.items() if v == 0]
        order: List[str] = []
        while q:
            n = q.pop(0)
            order.append(n)
            for m, deps in dag.items():
                if n in deps:
                    indeg[m] -= 1
                    if indeg[m] == 0:
                        q.append(m)

        if len(order) != len(dag):
            raise ValueError("DAG has cycles or unreachable nodes")
        return order

    def run_workflow(self, dag: Dict[str, List[str]], payloads: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Execute the provided DAG.

        dag: mapping node -> list of dependency node names
        payloads: optional mapping node -> input payload for that node. If omitted,
                  an empty dict is passed to agents.

        Returns mapping node -> result for successful nodes. If any node fails after
        exhausting retries, an exception is raised and remaining dependent nodes are
        not executed.
        """
        if not isinstance(dag, dict):
            raise TypeError("dag must be a dict mapping node->dependencies")

        payloads = payloads or {}
        # validate nodes
        for node, deps in dag.items():
            for d in deps:
                if d not in dag:
                    raise KeyError(f"Node {d} (dependency of {node}) not in DAG")

        # no special-case single-node shortcut: use unified execution path

        # build reverse deps and indegree
        indeg: Dict[str, int] = {n: len(deps) for n, deps in dag.items()}
        rev: Dict[str, List[str]] = {n: [] for n in dag}
        for n, deps in dag.items():
            for d in deps:
                rev[d].append(n)

        results: Dict[str, Any] = {}
        failures: Dict[str, Exception] = {}

        def _node_callable(node: str):
            agent = self.agents.get(node)
            if agent is None:
                raise KeyError(f"Agent not registered for node {node}")

            attempts = self.retry_attempts
            backoff = self.retry_backoff
            last_exc: Exception | None = None
            for attempt in range(1, attempts + 1):
                try:
                    logger.info("Executing node %s attempt %d", node, attempt)
                    return agent.process(payloads.get(node, {}))
                except Exception as e:
                    last_exc = e
                    logger.exception("Agent %s failed on attempt %d: %s", node, attempt, e)
                    if attempt < attempts:
                        wait = backoff * (2 ** (attempt - 1))
                        time.sleep(wait)
            # exhausted
            raise last_exc

        # executor for parallel work
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            # queue ready nodes
            ready: List[str] = [n for n, d in indeg.items() if d == 0]
            futures: Dict[concurrent.futures.Future, str] = {}

            while ready or futures:
                # submit all ready nodes
                for node in ready:
                    fut = ex.submit(_node_callable, node)
                    futures[fut] = node
                ready = []

                # wait for at least one future to complete
                done, _ = concurrent.futures.wait(
                    list(futures.keys()), return_when=concurrent.futures.FIRST_COMPLETED
                )

                for fut in done:
                    node = futures.pop(fut)
                    try:
                        res = fut.result(timeout=self.agent_timeout)
                        results[node] = res
                        logger.info("Node %s completed", node)
                        # unlock dependents
                        for dep in rev.get(node, []):
                            indeg[dep] -= 1
                            if indeg[dep] == 0:
                                ready.append(dep)
                    except concurrent.futures.TimeoutError as te:
                        failures[node] = te
                        logger.exception("Node %s timed out", node)
                    except Exception as e:
                        failures[node] = e
                        logger.exception("Node %s failed", node)

                if failures:
                    # stop execution when any failure occurs; raise first failure
                    first = next(iter(failures.values()))
                    raise first

        return results

    def run_workflow_via_bus(self, dag: Dict[str, List[str]], payloads: Dict[str, Any] | None = None, bus=None) -> Dict[str, Any]:
        """Event-driven workflow over a message bus.

        - Publishes tasks to `tasks` topic.
        - Listens on `results` topic for completion or failure messages.
        - On failure, retries up to `retry_attempts` (with backoff) by re-publishing the task.
        """
        if bus is None:
            raise RuntimeError("bus is required for event-driven workflow")

        payloads = payloads or {}
        # validate nodes
        for node, deps in dag.items():
            for d in deps:
                if d not in dag:
                    raise KeyError(f"Node {d} (dependency of {node}) not in DAG")

        indeg: Dict[str, int] = {n: len(deps) for n, deps in dag.items()}
        rev: Dict[str, List[str]] = {n: [] for n in dag}
        for n, deps in dag.items():
            for d in deps:
                rev[d].append(n)

        results: Dict[str, Any] = {}
        attempts: Dict[str, int] = {n: 0 for n in dag}
        ready = [n for n, d in indeg.items() if d == 0]

        # publish initial ready tasks
        for node in ready:
            attempts[node] += 1
            bus.publish("tasks", {"node": node, "payload": payloads.get(node, {}), "attempt": attempts[node]})

        # wait for results until all nodes done or failure
        while len(results) < len(dag):
            msg = bus.consume("results", timeout=self.agent_timeout)
            node = msg.get("node")
            success = msg.get("success", False)

            if success:
                results[node] = msg.get("result")
                # unlock dependents
                for dep in rev.get(node, []):
                    indeg[dep] -= 1
                    if indeg[dep] == 0:
                        attempts[dep] += 1
                        bus.publish("tasks", {"node": dep, "payload": payloads.get(dep, {}), "attempt": attempts[dep]})
            else:
                # failure handling: retry or bail
                attempts[node] = attempts.get(node, 0) + 1
                if attempts[node] <= self.retry_attempts:
                    backoff = self.retry_backoff * (2 ** (attempts[node] - 1))
                    time.sleep(backoff)
                    bus.publish("tasks", {"node": node, "payload": payloads.get(node, {}), "attempt": attempts[node]})
                else:
                    raise RuntimeError(f"Node {node} failed after {self.retry_attempts} attempts: {msg.get('error')}")

        return results

