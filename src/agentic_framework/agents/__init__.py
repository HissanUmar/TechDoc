from __future__ import annotations

from .planner import PlannerAgent
from .requirements import RequirementsAnalystAgent
from .architecture import ArchitectureDesignerAgent
from .security import SecurityValidatorAgent
from .performance import PerformanceAnalyzerAgent
from .reviewer import ReviewerAgent
from .documentation import DocumentationGeneratorAgent


AGENT_CLASSES = {
    "planner": PlannerAgent,
    "requirements": RequirementsAnalystAgent,
    "architecture": ArchitectureDesignerAgent,
    "security": SecurityValidatorAgent,
    "performance": PerformanceAnalyzerAgent,
    "reviewer": ReviewerAgent,
    "documentation": DocumentationGeneratorAgent,
}


def build_default_agents():
    return {name: agent_cls() for name, agent_cls in AGENT_CLASSES.items()}
