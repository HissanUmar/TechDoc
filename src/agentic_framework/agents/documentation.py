from __future__ import annotations

from typing import Any, Dict

from ..agent import AgentBase
from ..hf_client import HfClient
from ..agent_prompts import documentation_prompt
from ..agents_common import run_prompted_model


class DocumentationGeneratorAgent(AgentBase):
    def __init__(self, model_name: str = "mistralai/Mistral-7B-Instruct-v0.1"):
        super().__init__()
        self.model_name = model_name
        self.model = HfClient(model=model_name)

    def process(self, payload: Dict[str, Any]):
        architecture = payload.get("architecture_type", "unknown")
        security_score = payload.get("security_score", 0)
        prompt = documentation_prompt(payload)
        response, parsed, status = run_prompted_model(self.model, prompt)
        return {
            "model_used": status["active_model"],
            "model_status": status,
            "prompt": prompt,
            "model_response": response.get("output", ""),
            "documentation": parsed.get(
                "documentation",
                f"Technical Architecture Document\nArchitecture Type: {architecture}\nSecurity Score: {security_score}/10\nGenerated: Successfully",
            ),
            "sections": parsed.get("sections", ["Overview", "Components", "Security", "Performance", "Deployment"]),
            "format": parsed.get("format", "markdown"),
            "summary": parsed.get("summary", "Documentation summarized for the current workflow state."),
        }
