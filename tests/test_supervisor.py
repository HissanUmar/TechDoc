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
