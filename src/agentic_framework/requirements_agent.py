from __future__ import annotations

import html
import json
import re
from datetime import datetime
from typing import Any, Dict, List
from urllib.parse import quote_plus, urljoin
from urllib.request import Request, urlopen


class RequirementsDocumentAgent:
    """Turn a user prompt into a requirements document with free web search support."""

    def __init__(self, max_search_results: int = 3, search_timeout: float = 8.0):
        self.max_search_results = max_search_results
        self.search_timeout = search_timeout
        # simple in-memory cache for query strategies (keyed by prompt fingerprint)
        self._query_cache: Dict[str, List[str]] = {}

    def run(self, prompt: str) -> Dict[str, Any]:
        prompt = self._normalize_prompt(prompt)
        requirements = self._extract_requirements(prompt)
        assumptions = self._suggest_assumptions(prompt)
        schema = self._suggest_schema(requirements)
        search_queries = self._build_search_queries(prompt, requirements)
        sources = self._search_sources(search_queries)
        research_notes = self._summarize_sources(sources)
        # Derive short summaries from research notes when available, otherwise leave empty.
        architecture_summary = self._infer_summary("architecture", research_notes, prompt)
        security_summary = self._infer_summary("security", research_notes, prompt)
        performance_summary = self._infer_summary("performance", research_notes, prompt)

        markdown = self._build_markdown(
            prompt=prompt,
            requirements=requirements,
            assumptions=assumptions,
            schema=schema,
            research_notes=research_notes,
            sources=sources,
            architecture_summary=architecture_summary,
            security_summary=security_summary,
            performance_summary=performance_summary,
        )

        return {
            "prompt": prompt,
            "requirements": requirements,
            "assumptions": assumptions,
            "schema": schema,
            "research_notes": research_notes,
            "sources": sources,
            "architecture_summary": architecture_summary,
            "security_summary": security_summary,
            "performance_summary": performance_summary,
            "generated_at_utc": datetime.utcnow().isoformat() + "Z",
            "markdown": markdown,
        }

    def _search_sources(self, queries: List[str]) -> List[Dict[str, str]]:
        sources: List[Dict[str, str]] = []
        seen_urls: set[str] = set()
        for query in queries:
            for result in self._duckduckgo_search(query):
                url = result.get("url", "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                sources.append(result)
                if len(sources) >= self.max_search_results:
                    return sources
        return sources

    def _duckduckgo_search(self, query: str) -> List[Dict[str, str]]:
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        request = Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                )
            },
        )

        try:
            with urlopen(request, timeout=self.search_timeout) as response:
                html_text = response.read().decode("utf-8", errors="ignore")
        except Exception:
            return []

        results: List[Dict[str, str]] = []
        for block in re.findall(r'<div class="result__body">(.*?)</div>\s*</div>', html_text, re.DOTALL):
            title_match = re.search(r'class="result__a" href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>', block, re.DOTALL)
            snippet_match = re.search(r'class="result__snippet"[^>]*>(?P<snippet>.*?)</a>', block, re.DOTALL)
            if not title_match:
                continue
            href = html.unescape(title_match.group("url"))
            title = self._strip_tags(html.unescape(title_match.group("title")))
            snippet = self._strip_tags(html.unescape(snippet_match.group("snippet"))) if snippet_match else ""
            results.append(
                {
                    "title": title,
                    "url": urljoin("https://html.duckduckgo.com", href),
                    "snippet": snippet,
                }
            )
        return results

    def _build_search_queries(self, prompt: str, requirements: List[str]) -> List[str]:
        # Hybrid Option C: semantic categorization + lightweight cache
        key = f"{prompt}|{','.join(requirements)}"
        if key in self._query_cache:
            return self._query_cache[key]

        text = prompt.lower()
        queries: List[str] = []

        # 1) Foundation / architecture query
        if any(w in text for w in ("consult", "consulting", "internal", "team")):
            queries.append("web application architecture for internal consulting tools CRUD database")
        elif any(w in text for w in ("dashboard", "report", "analytics")):
            queries.append("web application architecture for dashboards and reporting data aggregation")
        else:
            queries.append("web application architecture rest api database design best practices")

        # 2) Feature-focused queries based on extracted requirements
        if any("authentication" in r.lower() or "user" in r.lower() for r in requirements) or "auth" in text:
            queries.append("authentication authorization best practices web apps role based access control")
        if any("task" in r.lower() or "project" in r.lower() for r in requirements) or "task" in text:
            queries.append("project task management application design requirements")
        if any("note" in r.lower() for r in requirements) or "note" in text:
            queries.append("collaborative meeting notes application design synchronization")

        # 3) Quality / non-functional concerns
        if any(w in text for w in ("scale", "scalab", "performance", "users", "large")):
            queries.append("scaling web application performance caching indexing best practices")
        else:
            queries.append("web app performance best practices pagination caching index")

        # 4) Integration / notifications / reminders
        if any("deadline" in r.lower() or "remind" in text for r in requirements) or "deadline" in text:
            queries.append("notification reminders scheduling best practices web apps")

        # clean up duplicates and limit to 4
        final = list(dict.fromkeys([q for q in queries if q]))[:4]
        self._query_cache[key] = final
        return final

    def _normalize_prompt(self, prompt: str) -> str:
        return " ".join(prompt.strip().split())

    def _extract_requirements(self, prompt: str) -> List[str]:
        text = prompt.lower()
        requirements: List[str] = []

        keyword_map = [
            (r"auth|login|user|role", "User accounts and authentication"),
            (r"api|endpoint|rest", "RESTful API endpoints"),
            (r"database|persistence|store|save", "Database persistence"),
            (r"task|todo|ticket", "Task management"),
            (r"project|client|consulting", "Client and project tracking"),
            (r"meeting note|meeting notes|notes", "Meeting notes capture"),
            (r"deadline|due date|schedule", "Deadline tracking"),
            (r"log|error|audit", "Error handling and logging"),
            (r"report|dashboard|summary", "Reporting and dashboard views"),
            (r"search|filter|sort", "Search and filtering"),
        ]

        for pattern, label in keyword_map:
            if re.search(pattern, text):
                requirements.append(label)


        return requirements[:8]

    def _suggest_assumptions(self, prompt: str) -> List[str]:
        text = prompt.lower()
        assumptions: List[str] = []

        # Only suggest assumptions that can be reasonably inferred from the prompt.
        if re.search(r"role|permission|admin|member|team", text):
            assumptions.append("Requires user roles and basic permissions.")
        if re.search(r"cloud|host|deploy|production", text):
            assumptions.append("Target deployment environment expected (cloud or self-hosted) is specified.")
        if re.search(r"mobile|responsive", text):
            assumptions.append("Responsive or mobile-first UX considerations are required.")
        if re.search(r"integrat|sync|calendar|email|slack|gmail", text):
            assumptions.append("External integrations are in scope and need API considerations.")

        if not assumptions:
            assumptions.append("Baseline web application assumptions apply.")

        return assumptions

    def _suggest_schema(self, requirements: List[str]) -> Dict[str, List[str]]:
        includes_users = any("user" in req.lower() or "auth" in req.lower() for req in requirements)
        includes_clients = any("client" in req.lower() for req in requirements)
        includes_projects = any("project" in req.lower() for req in requirements)
        includes_tasks = any("task" in req.lower() for req in requirements)
        includes_notes = any("note" in req.lower() for req in requirements)
        includes_deadlines = any("deadline" in req.lower() or "due" in req.lower() for req in requirements)

        schema: Dict[str, List[str]] = {}
        if includes_users:
            schema["users"] = [
                "id: uuid (PK)",
                "name: string",
                "email: string (unique)",
                "role: string",
                "created_at: timestamp",
            ]
        if includes_clients:
            schema["clients"] = [
                "id: uuid (PK)",
                "name: string",
                "contact_email: string",
                "company: string",
                "created_at: timestamp",
            ]
        if includes_projects:
            schema["projects"] = [
                "id: uuid (PK)",
                "client_id: uuid (FK -> clients.id)",
                "owner_id: uuid (FK -> users.id)",
                "name: string",
                "status: string",
                "created_at: timestamp",
            ]
        if includes_tasks:
            schema["tasks"] = [
                "id: uuid (PK)",
                "project_id: uuid (FK -> projects.id)",
                "assignee_id: uuid (FK -> users.id)",
                "title: string",
                "status: string",
                "due_date: date",
            ]
        if includes_notes:
            schema["meeting_notes"] = [
                "id: uuid (PK)",
                "project_id: uuid (FK -> projects.id)",
                "author_id: uuid (FK -> users.id)",
                "summary: text",
                "created_at: timestamp",
            ]
        if includes_deadlines:
            schema["deadlines"] = [
                "id: uuid (PK)",
                "project_id: uuid (FK -> projects.id)",
                "task_id: uuid (FK -> tasks.id, optional)",
                "label: string",
                "due_at: timestamp",
            ]

        # Return only inferred schema pieces; do not add a generic fallback table.
        return schema

    def _summarize_sources(self, sources: List[Dict[str, str]]) -> List[str]:
        if not sources:
            return []
        notes: List[str] = []
        for source in sources:
            title = source.get("title", "Unknown source")
            snippet = source.get("snippet", "")
            if snippet:
                notes.append(f"{title}: {snippet}")
            else:
                notes.append(title)
        return notes[:5]

    def _infer_summary(self, kind: str, research_notes: List[str], prompt: str) -> str:
        """Return a short, conservative summary for architecture/security/performance.

        Prefer using a research note if available, otherwise infer from prompt keywords.
        """
        if research_notes:
            # use first research note as a short summary source
            return research_notes[0][:400]

        text = prompt.lower()
        if kind == "architecture":
            if any(w in text for w in ("dashboard", "report", "analytics")):
                return "Architecture: web app with backend APIs, OLAP-style reporting components."
            return "Architecture: web app with REST API and relational persistence."
        if kind == "security":
            if "auth" in text or "user" in text or "role" in text:
                return "Security: include authentication, authorization, and input validation."
            return "Security: standard web app security practices."
        if kind == "performance":
            if any(w in text for w in ("scale", "large", "performance")):
                return "Performance: plan for caching, indexing, and pagination for scale."
            return "Performance: responsive UX with pagination and indexed queries."
        return ""

    def _build_markdown(
        self,
        *,
        prompt: str,
        requirements: List[str],
        assumptions: List[str],
        schema: Dict[str, List[str]],
        research_notes: List[str],
        sources: List[Dict[str, str]],
        architecture_summary: str,
        security_summary: str,
        performance_summary: str,
    ) -> str:
        lines: List[str] = ["# Final Project Document", "", f"- Generated: {datetime.utcnow().isoformat()}Z", "", "## Project Overview", prompt, ""]

        # Requirements
        if requirements:
            lines.append("## Requirements")
            for index, requirement in enumerate(requirements, start=1):
                lines.append(f"{index}. {requirement}")
            lines.append("")

        # Research notes (only if present)
        if research_notes:
            lines.append("## Research Notes")
            for note in research_notes:
                lines.append(f"- {note}")
            lines.append("")

        # Assumptions
        if assumptions:
            lines.append("## Assumptions")
            for assumption in assumptions:
                lines.append(f"- {assumption}")
            lines.append("")

        # Suggested Database Schema
        if schema:
            lines.append("## Suggested Database Schema")
            for table_name, columns in schema.items():
                lines.append(f"### {table_name}")
                for column in columns:
                    lines.append(f"- {column}")
                lines.append("")

        # Summaries
        if architecture_summary:
            lines.extend(["## Architecture Summary", architecture_summary, ""])
        if security_summary:
            lines.extend(["## Security Summary", security_summary, ""])
        if performance_summary:
            lines.extend(["## Performance Summary", performance_summary, ""])

        # Sources
        if sources:
            lines.append("## Sources")
            for source in sources:
                title = source.get("title", "Unknown source")
                url = source.get("url", "")
                lines.append(f"- {title}: {url}".rstrip())
            lines.append("")

        # Validation checks computed from presence of key artifacts
        requirements_pass = bool(requirements)
        schema_pass = bool(schema)
        review_pass = requirements_pass and schema_pass

        lines.extend(["## Validation Checks", f"- requirements: {'PASS' if requirements_pass else 'FAIL'}", f"- schema: {'PASS' if schema_pass else 'FAIL'}", f"- review: {'PASS' if review_pass else 'FAIL'}"])

        return "\n".join(lines)

    @staticmethod
    def _strip_tags(text: str) -> str:
        return re.sub(r"<[^>]+>", "", text).strip()


__all__ = ["RequirementsDocumentAgent"]
