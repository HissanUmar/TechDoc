"""Clarification engine for resolving ambiguous requirements."""

import logging
import re
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


class ClarificationEngine:
    """Detects vague requirements and generates targeted clarification questions.

    Features:
    - Identifies undefined actors, roles, and user groups.
    - Detects quantitatively vague statements ("fast", "many", "scalable").
    - Generates questions ranked by business impact.
    - Tracks clarification rounds (max 5 before proceeding with assumptions).
    - Documents assumptions made when proceeding without full clarification.
    """

    def __init__(self, max_rounds: int = 5) -> None:
        self.max_rounds = max_rounds
        self.round_count = 0
        self.questions: List[Dict[str, Any]] = []
        self.answers: Dict[str, str] = {}
        self.assumptions: List[str] = []

    def analyze(self, prompt: str) -> Dict[str, Any]:
        """Analyze a prompt for vagueness and generate clarification questions.

        Returns:
          - vague_terms: list of detected vague terms and their positions
          - missing_actors: list of undefined actor/role references
          - questions: list of clarification questions ranked by impact
          - can_proceed: bool, whether enough info exists to proceed
        """
        vague_terms = self._detect_vague_terms(prompt)
        missing_actors = self._detect_missing_actors(prompt)
        questions = self._generate_questions(vague_terms, missing_actors, prompt)

        return {
            "vague_terms": vague_terms,
            "missing_actors": missing_actors,
            "questions": questions,
            "can_proceed": len(questions) == 0,
        }

    def _detect_vague_terms(self, text: str) -> List[Dict[str, Any]]:
        """Find quantitatively vague or performance-related terms."""
        vague_patterns = {
            r"\b(fast|slow|quick|sluggish|responsive|snappy)\b": "performance",
            r"\b(many|few|lots of|a lot of|some|multiple)\s+\w+": "quantity",
            r"\b(scalable|scale|scaling|horizontal|vertical)\b": "scalability",
            r"\b(flexible|adaptable|extensible|modular)\b": "adaptability",
            r"\b(secure|safe|reliable|robust|stable)\b": "reliability",
            r"\b(simple|complex|easy|hard|lightweight|heavy)\b": "complexity",
        }

        found = []
        for pattern, category in vague_patterns.items():
            for match in re.finditer(pattern, text, re.IGNORECASE):
                found.append({
                    "term": match.group(0),
                    "category": category,
                    "position": match.start(),
                })
        return sorted(found, key=lambda x: x["position"])

    def _detect_missing_actors(self, text: str) -> List[str]:
        """Identify undefined user roles, actors, or personas."""
        actor_patterns = [
            r"\b(user|users|customer|customers|admin|administrator)\b",
            r"\b(client|clients|requester|requesters)\b",
            r"\b(stakeholder|stakeholders|team|teams)\b",
        ]

        actors = set()
        for pattern in actor_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                actors.add(match.group(0).lower())

        # If we find generic actors without specificity, flag as needing clarification
        generic_actors = ["user", "users", "client", "clients", "team"]
        if any(a in actors for a in generic_actors):
            return ["Undefined user roles or personas (e.g., 'users' without specification)"]
        return []

    def _generate_questions(self, vague_terms: List[Dict[str, Any]], missing_actors: List[str], prompt: str) -> List[Dict[str, Any]]:
        """Generate prioritized clarification questions."""
        questions = []
        impact_scores = {"quantity": 9, "scalability": 8, "performance": 7, "reliability": 6, "adaptability": 5, "complexity": 4}

        # Questions for vague terms
        seen_categories = set()
        for term_info in vague_terms:
            category = term_info["category"]
            if category in seen_categories:
                continue
            seen_categories.add(category)

            impact = impact_scores.get(category, 5)
            if category == "quantity":
                questions.append({
                    "priority": impact,
                    "category": category,
                    "question": f"You mentioned '{term_info['term']}' — can you provide a concrete number or range? (e.g., daily users, requests/sec)",
                    "answer": None,
                })
            elif category == "performance":
                questions.append({
                    "priority": impact,
                    "category": category,
                    "question": "What are your performance targets? (e.g., response time <100ms, latency <500ms, throughput >1000 req/s)",
                    "answer": None,
                })
            elif category == "scalability":
                questions.append({
                    "priority": impact,
                    "category": category,
                    "question": "What is your expected growth trajectory? (e.g., 10x users in 12 months, target scale)",
                    "answer": None,
                })
            elif category == "reliability":
                questions.append({
                    "priority": impact,
                    "category": category,
                    "question": "What is your target SLA/uptime? (e.g., 99.9%, 99.99%)",
                    "answer": None,
                })

        # Questions for missing actors
        if missing_actors:
            questions.append({
                "priority": 9,
                "category": "actors",
                "question": "Can you describe your user personas/roles? (e.g., end-user, admin, developer, business analyst)",
                "answer": None,
            })

        # Sort by priority descending
        return sorted(questions, key=lambda q: q["priority"], reverse=True)

    def add_answer(self, question_index: int, answer: str) -> bool:
        """Record an answer to a clarification question.

        Returns True if successful, False if question_index is invalid.
        """
        if question_index < 0 or question_index >= len(self.questions):
            return False
        self.questions[question_index]["answer"] = answer
        self.answers[self.questions[question_index]["question"]] = answer
        return True

    def proceed_or_clarify(self) -> Tuple[bool, str]:
        """Check if enough info exists to proceed, or if more rounds are needed.

        Returns:
          - (can_proceed: bool, message: str)
        """
        unanswered = [q for q in self.questions if q["answer"] is None]
        self.round_count += 1

        if not unanswered:
            return True, "All clarification questions answered."

        if self.round_count >= self.max_rounds:
            # Document assumptions and proceed
            for q in unanswered:
                assumption = f"Assumed for '{q['category']}': using best-effort defaults (question: {q['question'][:50]}...)"
                self.assumptions.append(assumption)
            return True, f"Max clarification rounds ({self.max_rounds}) reached. Proceeding with {len(self.assumptions)} assumptions documented."

        return False, f"Round {self.round_count}/{self.max_rounds}: {len(unanswered)} questions remain unanswered."

    def summary(self) -> Dict[str, Any]:
        """Return a summary of clarifications, answers, and assumptions."""
        return {
            "round_count": self.round_count,
            "max_rounds": self.max_rounds,
            "questions_asked": len(self.questions),
            "questions_answered": len([q for q in self.questions if q["answer"] is not None]),
            "answers": self.answers,
            "assumptions": self.assumptions,
        }
