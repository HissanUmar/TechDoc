from __future__ import annotations

from typing import Any, Dict

from ..agent import AgentBase
from ..hf_client import HfClient
from ..agent_prompts import reviewer_prompt
from ..agents_common import run_prompted_model


class ReviewerAgent(AgentBase):
    def __init__(self, model_name: str = "mistralai/Mistral-7B-Instruct-v0.1"):
        super().__init__()
        self.model_name = model_name
        self.model = HfClient(model=model_name)

    def process(self, payload: Dict[str, Any]):
        prompt = reviewer_prompt(payload)
        response, parsed, status = run_prompted_model(self.model, prompt)
        decision = parsed.get("decision", "clarify" if not parsed.get("ready", False) else "proceed")
        coverage_score = parsed.get("coverage_score", 0 if decision == "clarify" else 80)
        return {
            "model_used": status["active_model"],
            "model_status": status,
            "prompt": prompt,
            "model_response": response.get("output", ""),
            "ready": parsed.get("ready", True),
            "decision": decision,
            "coverage_score": coverage_score,
            "gaps": parsed.get("gaps", []),
            "critical_gaps": parsed.get("critical_gaps", []),
            "improvements": parsed.get("improvements", []),
            "summary": parsed.get("summary", "Workflow reviewed for readiness."),
        }
