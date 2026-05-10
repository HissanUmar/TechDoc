import concurrent.futures
import logging
import threading
import time
from typing import Dict, Any, List, Iterable, Callable

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

    def run_adaptive_workflow(
        self,
        initial_context: Dict[str, Any],
        max_steps: int = 20,
        progress_callback: Callable[[Dict[str, Any]], None] | None = None,
    ) -> (Dict[str, Any], List[str]):
        """Run an adaptive pipeline where the supervisor chooses which agent to run next.

        Behavior:
        - Call the `planner` agent first (if registered) to obtain a suggested `next_agent` or `plan`.
        - Execute agents iteratively following the planner suggestion. After each agent run,
          check the `reviewer` agent (if registered) to determine if the workflow is ready.
        - Stop early when the `reviewer` indicates `ready: True` or when no more agents are suggested.

        Returns a tuple of (results_mapping, execution_order_list).
        """
        if not isinstance(initial_context, dict):
            raise TypeError("initial_context must be a dict")

        results: Dict[str, Any] = {}
        order: List[str] = []
        clarification_answers = initial_context.get("clarification_answers", {}) or {}
        coverage_threshold = int(initial_context.get("coverage_threshold", 80))

        def _emit(event: str, **data: Any) -> None:
            if progress_callback is not None:
                progress_callback({"event": event, **data})

        # Helper to safely run an agent and record result
        def _run(name: str, payload: Dict[str, Any] | None = None):
            _emit("agent_start", agent=name, payload_keys=sorted((payload or {}).keys()))
            res = self.start_agent(name, payload or {})
            results[name] = res
            order.append(name)
            _emit("agent_end", agent=name, result_keys=sorted(res.keys()) if isinstance(res, dict) else [])
            return res

        # 1) Planner step (optional)
        next_candidates: List[str] = []
        candidate_reasons: Dict[str, str] = {}
        if "planner" in self.agents:
            _emit("decision", agent="planner", reason="bootstrap workflow from the user problem statement")
            plan_res = _run("planner", {"goal": initial_context.get("problem_statement", ""), "context": initial_context})
            # planner may expose next_agent or plan list
            if isinstance(plan_res, dict):
                na = plan_res.get("next_agent")
                if na:
                    next_candidates.append(na)
                    candidate_reasons[na] = "planner chose this next agent"
                plan_list = plan_res.get("plan") or []
                for step in plan_list:
                    if isinstance(step, str) and step not in next_candidates:
                        next_candidates.append(step)
                    if isinstance(step, str):
                        candidate_reasons.setdefault(step, "planner included this step in its plan")
            _emit("planner_complete", next_candidates=list(next_candidates))

        if "requirements" in self.agents:
            _emit("decision", agent="requirements", reason="extract baseline requirements and detect clarification gaps")
            req_payload = {
                "user_input": initial_context.get("problem_statement", ""),
                "clarification_answers": clarification_answers,
            }
            requirements_result = _run("requirements", req_payload)
            questions = requirements_result.get("questions", []) if isinstance(requirements_result, dict) else []
            needs_clarification = bool(questions) and not clarification_answers
            if needs_clarification:
                _emit("clarification_needed", agent="requirements", questions=questions, reason="requirements_incomplete")
                _emit("stop", reason="clarification_needed")
                results["clarification_needed"] = {"questions": questions}
                return results, order

        # Fallback to known agent ordering if none suggested
        if not next_candidates:
            next_candidates = [n for n in list(self.agents.keys()) if n not in {"planner", "requirements"}]
            for name in next_candidates:
                candidate_reasons[name] = "fallback ordering because planner did not return a next step"
            _emit("fallback_plan", next_candidates=list(next_candidates))

        # requirements is handled as the intake stage above, so do not run it again later
        next_candidates = [name for name in next_candidates if name != "requirements"]

        steps = 0
        # Execute adaptively
        for candidate in next_candidates:
            if steps >= max_steps:
                _emit("stop", reason="max_steps_reached", steps=steps)
                break
            if candidate not in self.agents:
                _emit("skip", agent=candidate, reason="not_registered")
                continue

            # build payload from current context and accumulated results
            payload = {"initial_context": initial_context, "workflow_results": results}
            _emit("decision", agent=candidate, reason=candidate_reasons.get(candidate, "selected by supervisor"))
            _run(candidate, payload)
            steps += 1

            # after each agent, ask reviewer if present
            if "reviewer" in self.agents:
                rev_payload = {"workflow_results": results}
                _emit("review_check", agent="reviewer", after=candidate)
                rev_res = self.start_agent("reviewer", rev_payload)
                results["reviewer"] = rev_res
                if "reviewer" not in order:
                    order.append("reviewer")
                decision = rev_res.get("decision") if isinstance(rev_res, dict) else None
                coverage_score = rev_res.get("coverage_score", 0) if isinstance(rev_res, dict) else 0
                ready = bool(isinstance(rev_res, dict) and rev_res.get("ready"))
                if not ready and coverage_score >= coverage_threshold and decision != "clarify":
                    ready = True
                _emit(
                    "review_result",
                    ready=ready,
                    decision=decision,
                    coverage_score=coverage_score,
                    gaps=rev_res.get("gaps", []) if isinstance(rev_res, dict) else [],
                )
                if ready:
                    _emit("stop", reason="coverage_sufficient", after=candidate)
                    break
        else:
            _emit("stop", reason="plan_exhausted")

        return results, order

