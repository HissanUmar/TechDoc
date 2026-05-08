import time

from agentic_framework.message_bus import SimpleMessageBus
from agentic_framework.supervisor import Supervisor
from agentic_framework.worker import AgentWorker
from agentic_framework.agent import AgentBase


class FlakyAgent(AgentBase):
    def __init__(self, n_failures: int):
        super().__init__()
        self.remaining = n_failures

    def process(self, payload):
        if self.remaining > 0:
            self.remaining -= 1
            raise RuntimeError("transient")
        return {"ok": True, "payload": payload}


def test_bus_orchestrated_workflow_with_retries():
    bus = SimpleMessageBus()
    sup = Supervisor()
    sup.register_agent("flaky", FlakyAgent(2))

    # worker will pull from 'tasks' and publish to 'results'
    worker = AgentWorker(resolve_agent=lambda name: sup.agents[name], message_bus=bus)
    worker.start()

    dag = {"flaky": []}
    results = sup.run_workflow_via_bus(dag, payloads={"flaky": {"x": 1}}, bus=bus)

    worker.stop()
    assert results["flaky"]["ok"] is True
