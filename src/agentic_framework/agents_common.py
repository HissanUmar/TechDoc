from __future__ import annotations

from typing import Any, Dict, Tuple

from .hf_client import HfClient
from .agent_prompts import extract_json_block


def run_prompted_model(model: HfClient, prompt: str) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    response = model.call_model(prompt)
    parsed = extract_json_block(response.get("output", "")) or {}
    status = model.get_status()
    return response, parsed, status
