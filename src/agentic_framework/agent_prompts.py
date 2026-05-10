from __future__ import annotations

import json
import re
from typing import Any, Dict, List


PIPELINE_ORDER = [
    "planner",
    "requirements",
    "architecture",
    "security",
    "performance",
    "reviewer",
    "documentation",
]


def _compact_json(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=True)


def extract_json_block(text: str) -> Dict[str, Any] | None:
    """Best-effort JSON extraction from model output."""
    if not text:
        return None

    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1)

    try:
        return json.loads(text)
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except Exception:
            return None
    return None


def requirements_prompt(user_input: str, clarification_answers: Dict[str, Any] | None = None) -> str:
    answers_text = _compact_json(clarification_answers or {})
    return f"""You are the Requirements Analyst.

Goal:
- Convert the raw request into a compact, actionable requirement set.
- Identify whether the current information is sufficient to proceed or whether clarification is required.

Rules:
- Be concise.
- Do not invent unsupported features.
- Identify assumptions explicitly.
- Prefer asking a small number of high-impact questions over making broad assumptions.
- Use any clarification answers provided below to refine the requirements.
- Return valid JSON only with keys:
    - requirements: list of 3 to 8 concise requirement strings
    - assumptions: list of strings
    - questions: list of strings
    - completeness_score: number from 0 to 100 indicating how complete the requirements are
    - critical_gaps: list of strings
    - summary: one short string

User request:
{user_input}

Clarification answers already provided:
{answers_text}
"""


def planner_prompt(goal: str, context: Dict[str, Any], available_agents: List[str] | None = None) -> str:
    if available_agents is None:
        available_agents = ["requirements", "architecture", "security", "performance", "documentation"]
    agents_list = ", ".join(available_agents)
    return f"""You are the Planner.

Goal:
- Convert the user's goal into a short execution plan for the agents.

Rules:
- Keep the plan compact and ordered.
- Choose only from the AVAILABLE AGENTS list below.
- Return valid JSON only with keys:
    - plan: list of agent names (must be chosen from the available agents list)
    - dependencies: list of agent names
    - next_agent: string (must be one of the available agents)
    - summary: one short string

AVAILABLE AGENTS:
{agents_list}

User goal:
{goal}

Current context:
{_compact_json(context)}
"""


def architecture_prompt(requirements: List[str]) -> str:
    return f"""You are the Architecture Designer.

Goal:
- Turn the requirements into a small architecture plan.

Rules:
- Keep the architecture realistic and minimal.
- Return valid JSON only with keys:
  - architecture_type: string
  - components: list of objects with name and role
  - deployment_model: string
  - tradeoffs: list of strings
  - summary: one short string

Requirements:
{_compact_json(requirements)}
"""


def security_prompt(architecture: Dict[str, Any]) -> str:
    return f"""You are the Security Validator.

Goal:
- Review the architecture for security issues and missing controls.

Rules:
- Focus on authentication, authorization, secrets, transport security, and abuse controls.
- Return valid JSON only with keys:
  - security_score: number from 0 to 10
  - vulnerabilities: list of strings
  - recommendations: list of strings
  - compliant: boolean
  - summary: one short string

Architecture:
{_compact_json(architecture)}
"""


def performance_prompt(architecture: Dict[str, Any]) -> str:
    return f"""You are the Performance Analyzer.

Goal:
- Estimate likely bottlenecks and improvement ideas for the design.

Rules:
- Be practical and concise.
- Return valid JSON only with keys:
  - estimated_latency_ms: number
  - throughput_rps: number
  - bottlenecks: list of strings
  - optimization_suggestions: list of strings
  - summary: one short string

Architecture:
{_compact_json(architecture)}
"""


def documentation_prompt(context: Dict[str, Any]) -> str:
    return f"""You are the Documentation Generator.

Goal:
- Produce a concise delivery document about the user's requested problem and solution.

Rules:
- Keep it short and readable.
- Focus on the user problem statement, key requirements, architecture choice, security/performance posture, and next actions.
- Do not describe internal prompts, model internals, chain-of-thought, or agent orchestration mechanics.
- Return valid JSON only with keys:
  - documentation: string
  - sections: list of strings
  - format: string
  - summary: one short string

Context:
{_compact_json(context)}
"""


def reviewer_prompt(context: Dict[str, Any]) -> str:
    return f"""You are the Reviewer.

Goal:
- Review the workflow outputs and judge whether the current state is complete enough to proceed.

Rules:
- Focus on gaps, contradictions, completeness, and readiness.
- Prefer progress over perfection: if the landscape is sufficiently covered and remaining gaps are minor, mark the workflow as ready.
- If critical areas are still missing, ask for clarification instead of forcing completion.
- Return valid JSON only with keys:
    - ready: boolean
    - decision: string (one of: "proceed", "clarify", "stop")
    - coverage_score: number from 0 to 100
    - gaps: list of strings
    - critical_gaps: list of strings
    - improvements: list of strings
    - summary: one short string

Workflow context:
{_compact_json(context)}
"""
