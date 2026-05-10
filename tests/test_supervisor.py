import time
import pytest

from agentic_framework.supervisor import Supervisor
from agentic_framework.agent import AgentBase


class SimpleAgent(AgentBase):
    def __init__(self, name=None):
        super().__init__()
        self.name = name

    def process(self, payload):
        return {"name": self.name, "payload": payload}


class FailNTimesAgent(AgentBase):
    def __init__(self, n_failures: int):
        super().__init__()
        self.remaining = n_failures

    def process(self, payload):
        if self.remaining > 0:
            self.remaining -= 1
            raise RuntimeError("transient")
        return {"ok": True}


class PlannerAgent(AgentBase):
    def process(self, payload):
        return {
            "next_agent": "requirements",
            "plan": ["requirements", "architecture", "documentation"],
            "summary": "Plan generated",
        }


class ReviewerAgent(AgentBase):
    def process(self, payload):
        workflow_results = payload.get("workflow_results", {})
        return {
            "ready": "architecture" in workflow_results,
            "gaps": [] if "architecture" in workflow_results else ["Need architecture"],
            "improvements": [],
            "summary": "Reviewed",
        }


class ClarifyingRequirementsAgent(AgentBase):
    def process(self, payload):
        answers = payload.get("clarification_answers", {}) or {}
        if answers:
            return {
                "requirements": ["Multi-user authentication", "Task tracking"],
                "assumptions": ["Role names supplied by user"],
                "questions": [],
                "critical_gaps": [],
                "completeness_score": 90,
                "needs_clarification": False,
                "summary": "Requirements complete enough to proceed",
            }
        return {
            "requirements": ["Task tracking"],
            "assumptions": [],
            "questions": ["Who are the user roles?"],
            "critical_gaps": ["Missing roles"],
            "completeness_score": 40,
            "needs_clarification": True,
            "summary": "Clarification needed",
        }


class TolerantReviewerAgent(AgentBase):
    def __init__(self, coverage_score=85, decision="proceed"):
        super().__init__()
        self.coverage_score = coverage_score
        self.decision = decision

    def process(self, payload):
        ready = self.decision in {"proceed", "stop"}
        return {
            "ready": ready,
            "decision": self.decision,
            "coverage_score": self.coverage_score,
            "gaps": [] if ready else ["Need clarification"],
            "critical_gaps": [],
            "improvements": [],
            "summary": "Reviewed",
        }


def test_simple_dag_execution():
    # A and B -> C
    sup = Supervisor(max_workers=3)
    sup.register_agent("A", SimpleAgent("A"))
    sup.register_agent("B", SimpleAgent("B"))
    sup.register_agent("C", SimpleAgent("C"))

    dag = {"A": [], "B": [], "C": ["A", "B"]}
    payloads = {"A": {"x": 1}, "B": {"y": 2}, "C": {"z": 3}}

    results = sup.run_workflow(dag, payloads)
    assert set(results.keys()) == {"A", "B", "C"}
    assert results["A"]["name"] == "A"
    assert results["B"]["payload"]["y"] == 2


def test_retry_succeeds_after_transient_failure():
    sup = Supervisor(max_workers=1, retry_attempts=3, retry_backoff=0.01)
    sup.register_agent("flaky", FailNTimesAgent(2))

    dag = {"flaky": []}
    res = sup.run_workflow(dag)
    assert res["flaky"]["ok"] is True


def test_retry_exhausts_and_raises():
    sup = Supervisor(max_workers=1, retry_attempts=2, retry_backoff=0.001)

    class AlwaysFail(AgentBase):
        def process(self, payload):
            raise RuntimeError("permanent")

    sup.register_agent("bad", AlwaysFail())
    dag = {"bad": []}
    with pytest.raises(RuntimeError):
        sup.run_workflow(dag)


def test_adaptive_workflow_streams_progress_and_stops_when_ready():
    sup = Supervisor(max_workers=1)
    sup.register_agent("planner", PlannerAgent())
    sup.register_agent("requirements", SimpleAgent("requirements"))
    sup.register_agent("architecture", SimpleAgent("architecture"))
    sup.register_agent("documentation", SimpleAgent("documentation"))
    sup.register_agent("reviewer", ReviewerAgent())

    events = []

    def capture(event):
        events.append(event)

    results, order = sup.run_adaptive_workflow(
        {"problem_statement": "Build a product"},
        progress_callback=capture,
    )

    assert "planner" in results
    assert "requirements" in results
    assert "architecture" in results
    assert "documentation" not in results
    assert any(event["event"] == "decision" and event.get("reason") for event in events)
    assert any(event["event"] == "planner_complete" for event in events)
    assert any(event["event"] == "review_result" and event["ready"] is True for event in events)
    assert any(event["event"] == "stop" and event["reason"] == "coverage_sufficient" for event in events)
    assert order[0] == "planner"


def test_adaptive_workflow_uses_fallback_plan_when_planner_absent():
    sup = Supervisor(max_workers=1)
    sup.register_agent("requirements", SimpleAgent("requirements"))
    sup.register_agent("architecture", SimpleAgent("architecture"))

    events = []

    results, order = sup.run_adaptive_workflow(
        {"problem_statement": "Build a product"},
        progress_callback=events.append,
    )

    assert "requirements" in results
    assert "architecture" in results
    assert any(event["event"] == "fallback_plan" for event in events)
    assert order[0] == "requirements"


def test_adaptive_workflow_pauses_for_clarification_then_resumes_with_answers():
    sup = Supervisor(max_workers=1)
    sup.register_agent("planner", PlannerAgent())
    sup.register_agent("requirements", ClarifyingRequirementsAgent())
    sup.register_agent("architecture", SimpleAgent("architecture"))
    sup.register_agent("reviewer", ReviewerAgent())

    events = []
    results, order = sup.run_adaptive_workflow(
        {"problem_statement": "Build a product"},
        progress_callback=events.append,
    )

    assert "clarification_needed" in results
    assert any(event["event"] == "clarification_needed" for event in events)

    events.clear()
    results, order = sup.run_adaptive_workflow(
        {
            "problem_statement": "Build a product",
            "clarification_answers": {"Who are the user roles?": "admin and contributors"},
        },
        progress_callback=events.append,
    )

    assert "clarification_needed" not in results
    assert "architecture" in results
    assert any(event["event"] == "stop" and event["reason"] == "coverage_sufficient" for event in events)


def test_adaptive_workflow_honors_completeness_tolerance():
    sup = Supervisor(max_workers=1)
    sup.register_agent("planner", PlannerAgent())
    sup.register_agent("requirements", ClarifyingRequirementsAgent())
    sup.register_agent("architecture", SimpleAgent("architecture"))
    sup.register_agent("reviewer", TolerantReviewerAgent(coverage_score=85, decision="proceed"))

    events = []
    results, order = sup.run_adaptive_workflow(
        {
            "problem_statement": "Build a product",
            "clarification_answers": {"Who are the user roles?": "admin and contributors"},
            "coverage_threshold": 80,
        },
        progress_callback=events.append,
    )

    assert "architecture" in results
    assert any(event["event"] == "review_result" and event.get("coverage_score") == 85 for event in events)
    assert any(event["event"] == "stop" and event["reason"] == "coverage_sufficient" for event in events)
