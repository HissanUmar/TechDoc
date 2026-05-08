import time

from agentic_framework.worker import AgentWorker
from agentic_framework.agent import AgentBase


class DemoAgent(AgentBase):
    def __init__(self):
        super().__init__()
        self.seen = []

    def process(self, payload):
        self.seen.append(payload)
        return {"ok": True, "payload": payload}


def test_run_once():
    agent = DemoAgent()
    worker = AgentWorker(resolve_agent=lambda name: agent)
    out = worker.run_once("demo", {"x": 1})
    assert out["ok"] is True
    assert agent.seen == [{"x": 1}]


def test_background_processing():
    agent = DemoAgent()
    worker = AgentWorker(resolve_agent=lambda name: agent)
    worker.start()
    worker.submit("demo", {"a": 1})

    # wait for processing
    time.sleep(0.2)
    worker.stop()

    assert agent.seen and agent.seen[0] == {"a": 1}
