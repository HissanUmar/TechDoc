import argparse
import logging

from .supervisor import Supervisor
from .agent import AgentBase

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(prog="agentic-framework")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    sup = Supervisor()

    # register a trivial agent for demo purposes
    class EchoAgent(AgentBase):
        def process(self, payload):
            print("EchoAgent received:", payload)
            return {"echo": payload}

    sup.register_agent("echo", EchoAgent())
    sup.run_workflow("echo", {"hello": "agentic"})


if __name__ == "__main__":
    main()
