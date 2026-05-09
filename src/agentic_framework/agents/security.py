from __future__ import annotations

from typing import Any, Dict

from ..agent import AgentBase
from ..hf_client import HfClient
from ..agent_prompts import security_prompt
from ..agents_common import run_prompted_model


class SecurityValidatorAgent(AgentBase):
    def __init__(self, model_name: str = "mistralai/Mistral-7B-Instruct-v0.1"):
        super().__init__()
        self.model_name = model_name
        self.model = HfClient(model=model_name)

    def process(self, payload: Dict[str, Any]):
        prompt = security_prompt(payload)
        response, parsed, status = run_prompted_model(self.model, prompt)
        return {
            "model_used": status["active_model"],
            "model_status": status,
            "prompt": prompt,
            "model_response": response.get("output", ""),
            "security_score": parsed.get("security_score", 8.5),
            "vulnerabilities": parsed.get("vulnerabilities", []),
            "recommendations": parsed.get("recommendations", [
                "Implement API authentication (OAuth 2.0)",
                "Enable encryption at rest and in transit",
                "Add rate limiting",
            ]),
            "compliant": parsed.get("compliant", True),
            "summary": parsed.get("summary", "Security posture reviewed for the placeholder architecture."),
        }
