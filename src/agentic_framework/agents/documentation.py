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
        # If we have a clear problem statement and extracted artifacts, synthesize
        # a deterministic, structured document focused on the user's needs.
        problem = payload.get("problem_statement")
        requirements = payload.get("requirements", []) or []
        assumptions = payload.get("assumptions", []) or []
        questions = payload.get("questions", []) or []
        arch_type = payload.get("architecture_type", "unspecified")
        arch_summary = payload.get("architecture_summary", "")
        security_score = payload.get("security_score", None)
        security_summary = payload.get("security_summary", "")
        performance_summary = payload.get("performance_summary", "")

        if problem and requirements:
            lines: list[str] = []
            lines.append(f"# Project: {problem.splitlines()[0]}")
            lines.append("")
            lines.append("## Overview")
            lines.append(problem)
            lines.append("")
            lines.append("## Requirements")
            for i, r in enumerate(requirements, start=1):
                lines.append(f"{i}. {r}")
            lines.append("")
            if assumptions or questions:
                lines.append("## Assumptions & Clarifications")
                if assumptions:
                    lines.append("**Assumptions:**")
                    for a in assumptions:
                        lines.append(f"- {a}")
                if questions:
                    lines.append("")
                    lines.append("**Open Questions / Clarifications:**")
                    for q in questions:
                        lines.append(f"- {q}")
                lines.append("")

            # Database schema suggestions
            lines.append("## Suggested Database Schema")
            if any("auth" in r.lower() or "user" in r.lower() for r in requirements):
                lines.append("### users")
                lines.append("- id: uuid (PK)")
                lines.append("- username: string (unique)")
                lines.append("- email: string (unique)")
                lines.append("- password_hash: string")
                lines.append("- created_at: timestamp")
                lines.append("")
            lines.append("### resources")
            lines.append("- id: uuid (PK)")
            lines.append("- owner_id: uuid (FK -> users.id)  # optional")
            lines.append("- data: jsonb")
            lines.append("- created_at: timestamp")
            lines.append("")
            lines.append("### logs")
            lines.append("- id: uuid (PK)")
            lines.append("- source: string")
            lines.append("- level: string")
            lines.append("- message: text")
            lines.append("- ts: timestamp")
            lines.append("")

            # Architecture summary
            lines.append("## Architecture Summary")
            lines.append(f"Type: {arch_type}")
            if arch_summary:
                lines.append("")
                lines.append(arch_summary)
            lines.append("")

            # Security & Performance
            lines.append("## Security")
            if security_score is not None:
                lines.append(f"Security score (est.): {security_score}/10")
            if security_summary:
                lines.append("")
                lines.append(security_summary)
            lines.append("")

            lines.append("## Performance")
            if performance_summary:
                lines.append(performance_summary)
            else:
                lines.append("Typical considerations: caching, connection pooling, CDN for static assets.")
            lines.append("")

            # Next steps
            lines.append("## Next Steps / Actionable Tasks")
            lines.append("- Finalize and approve the requirements list.")
            lines.append("- Produce an ER diagram and finalize DB schema.")
            lines.append("- Write API specification (endpoints, auth, error codes).")
            lines.append("- Implement authentication and authorization.")
            lines.append("- Add integration tests and performance benchmarks.")
            lines.append("")

            doc_md = "\n".join(lines)
            sections = ["Overview", "Requirements", "Assumptions & Clarifications", "Suggested Database Schema", "Architecture Summary", "Security", "Performance", "Next Steps"]
            return {
                "documentation": doc_md,
                "sections": sections,
                "format": "markdown",
                "summary": f"Structured project document for: {problem.splitlines()[0]}",
            }

        # Fallback: ask the model if we lack structured inputs
        prompt = documentation_prompt(payload)
        response, parsed, status = run_prompted_model(self.model, prompt)
        return {
            "documentation": parsed.get("documentation", response.get("output", "")),
            "sections": parsed.get("sections", ["Overview", "Components", "Security", "Performance", "Deployment"]),
            "format": parsed.get("format", "markdown"),
            "summary": parsed.get("summary", "Documentation summarized for the current workflow state."),
        }
