from __future__ import annotations

from typing import Any, Dict

from ..agent import AgentBase
from ..hf_client import HfClient
from ..agent_prompts import architecture_prompt
from ..agents_common import run_prompted_model


class ArchitectureDesignerAgent(AgentBase):
    def __init__(self, model_name: str = "mistralai/Mistral-7B-Instruct-v0.1"):
        super().__init__()
        self.model_name = model_name
        self.model = HfClient(model=model_name)

    def process(self, payload: Dict[str, Any]):
        requirements = payload.get("requirements", [])
        prompt = architecture_prompt(requirements)
        response, parsed, status = run_prompted_model(self.model, prompt)
        return {
            "model_used": status["active_model"],
            "model_status": status,
            "prompt": prompt,
            "model_response": response.get("output", ""),
            "architecture_type": parsed.get("architecture_type", "microservices"),
            "components": parsed.get("components", [
                {"name": "API Gateway", "role": "request routing"},
                {"name": "Service Layer", "role": "business logic"},
                {"name": "Data Layer", "role": "persistence"},
                {"name": "Cache Layer", "role": "performance"},
            ]),
            "deployment_model": parsed.get("deployment_model", "containerized"),
            "tradeoffs": parsed.get("tradeoffs", ["Balanced delivery speed against long-term scalability"]),
            "summary": parsed.get("summary", "Architecture shaped around a service-oriented implementation plan."),
            "requirements_addressed": len(requirements),
        }
