from __future__ import annotations

from typing import Any, Dict

from ..agent import AgentBase
from ..hf_client import HfClient
from ..agent_prompts import planner_prompt
from ..agents_common import run_prompted_model


class PlannerAgent(AgentBase):
    def __init__(self, model_name: str = "mistralai/Mistral-7B-Instruct-v0.1"):
        super().__init__()
        self.model_name = model_name
        self.model = HfClient(model=model_name)

    def process(self, payload: Dict[str, Any]):
        goal = payload.get("goal", "")
        context = payload.get("context", {})
        available_agents = payload.get("available_agents", ["requirements", "architecture", "security", "performance", "documentation"])
        prompt = planner_prompt(goal, context, available_agents)
        response, parsed, status = run_prompted_model(self.model, prompt)
        return {
            "model_used": status["active_model"],
            "model_status": status,
            "prompt": prompt,
            "model_response": response.get("output", ""),
            "plan": parsed.get("plan", ["requirements", "architecture", "security", "performance", "documentation"]),
            "dependencies": parsed.get("dependencies", ["requirements"]),
            "next_agent": parsed.get("next_agent", "requirements"),
            "summary": parsed.get("summary", "Plan generated for the workflow."),
        }
