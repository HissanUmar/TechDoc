from __future__ import annotations

from typing import Any, Dict

from ..agent import AgentBase
from ..hf_client import HfClient
from ..agent_prompts import performance_prompt
from ..agents_common import run_prompted_model


class PerformanceAnalyzerAgent(AgentBase):
    def __init__(self, model_name: str = "mistralai/Mistral-7B-Instruct-v0.1"):
        super().__init__()
        self.model_name = model_name
        self.model = HfClient(model=model_name)

    def process(self, payload: Dict[str, Any]):
        components = payload.get("components", [])
        prompt = performance_prompt(payload)
        response, parsed, status = run_prompted_model(self.model, prompt)
        return {
            "model_used": status["active_model"],
            "model_status": status,
            "prompt": prompt,
            "model_response": response.get("output", ""),
            "estimated_latency_ms": parsed.get("estimated_latency_ms", 50),
            "throughput_rps": parsed.get("throughput_rps", 10000),
            "bottlenecks": parsed.get("bottlenecks", ["Database queries", "Network I/O"]),
            "optimization_suggestions": parsed.get("optimization_suggestions", [
                "Add caching layer",
                "Implement connection pooling",
                "Consider CDN for static assets",
            ]),
            "summary": parsed.get("summary", "Performance reviewed for the current design proposal."),
            "components_analyzed": len(components),
        }
