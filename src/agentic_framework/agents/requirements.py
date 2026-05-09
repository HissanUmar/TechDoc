from __future__ import annotations

from typing import Any, Dict

from ..agent import AgentBase
from ..hf_client import HfClient
from ..agent_prompts import requirements_prompt
from ..agents_common import run_prompted_model


class RequirementsAnalystAgent(AgentBase):
    def __init__(self, model_name: str = "mistralai/Mistral-7B-Instruct-v0.1"):
        super().__init__()
        self.model_name = model_name
        self.model = HfClient(model=model_name)

    def process(self, payload: Dict[str, Any]):
        user_input = payload.get("user_input", "")
        prompt = requirements_prompt(user_input)
        response, parsed, status = run_prompted_model(self.model, prompt)
        requirements = parsed.get("requirements", [
            "Multi-user authentication",
            "RESTful API endpoints",
            "Database persistence",
            "Error handling and logging",
        ])
        return {
            "model_used": status["active_model"],
            "model_status": status,
            "prompt": prompt,
            "model_response": response.get("output", ""),
            "requirements": requirements,
            "assumptions": parsed.get("assumptions", ["Assumed baseline web application capabilities based on user goal"]),
            "questions": parsed.get("questions", []),
            "summary": parsed.get("summary", "Requirements shaped into a compact engineering brief."),
            "source": user_input[:50] if user_input else "default",
            "count": len(requirements),
        }
