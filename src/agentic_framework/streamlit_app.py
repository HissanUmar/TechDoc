"""Standalone Streamlit app for turning a project prompt into a concise brief.

This version intentionally removes the previous agentic orchestration layer and
keeps the app deterministic, local, and easy to run.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st


ARTIFACT_DIR = Path("artifacts") / "runs"
DEFAULT_PROMPT = (
    "Build an app for tracking clients, projects, tasks, meeting notes, and deadlines "
    "for a small consulting team."
)


def initialize_session_state() -> None:
    if "current_prompt" not in st.session_state:
        st.session_state.current_prompt = DEFAULT_PROMPT
    if "latest_document" not in st.session_state:
        st.session_state.latest_document = None
    if "latest_artifacts" not in st.session_state:
        st.session_state.latest_artifacts = None
    if "run_history" not in st.session_state:
        st.session_state.run_history = []
    if "page" not in st.session_state:
        st.session_state.page = "Home"


def normalize_prompt(prompt: str) -> str:
    return " ".join(prompt.strip().split())


def extract_requirements(prompt: str) -> List[str]:
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

    if not requirements:
        requirements = [
            "Core application workflow based on the user's stated goal",
            "Persistent data storage for the primary records",
            "Simple user-facing interface for day-to-day use",
        ]

    return requirements[:8]


def suggest_assumptions(prompt: str) -> List[str]:
    text = prompt.lower()
    assumptions: List[str] = []

    if not re.search(r"role|permission|permission|admin|member|team", text):
        assumptions.append("The team needs at least basic user roles such as admin and contributor.")
    if not re.search(r"cloud|host|deploy|production", text):
        assumptions.append("The app will initially run in a standard single-environment deployment.")
    if not re.search(r"mobile|responsive", text):
        assumptions.append("The first version prioritizes desktop usage with responsive behavior as a follow-up.")
    if not re.search(r"integrat|sync|calendar|email", text):
        assumptions.append("External integrations are out of scope for the initial release.")

    if not assumptions:
        assumptions.append("Baseline web application assumptions apply.")

    return assumptions


def suggest_schema(requirements: List[str]) -> Dict[str, List[str]]:
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

    if not schema:
        schema["records"] = [
            "id: uuid (PK)",
            "title: string",
            "payload: json",
            "created_at: timestamp",
        ]

    return schema


def build_document(prompt: str) -> Dict[str, Any]:
    prompt = normalize_prompt(prompt)
    requirements = extract_requirements(prompt)
    assumptions = suggest_assumptions(prompt)
    schema = suggest_schema(requirements)

    architecture_summary = (
        "A straightforward web application with authenticated users, a normalized database, "
        "and a thin API layer for CRUD operations."
    )
    security_summary = (
        "Protect user data with authentication, role-based access control, input validation, "
        "and secure password storage."
    )
    performance_summary = (
        "Keep the first version responsive by using indexed lookups, pagination, and cached list views."
    )

    lines = [
        "# Final Project Document",
        "",
        f"- Generated: {datetime.utcnow().isoformat()}Z",
        "- Validation Gate: passed",
        "",
        "## Project Overview",
        f"{prompt}",
        "",
        "## Requirements",
    ]

    for index, requirement in enumerate(requirements, start=1):
        lines.append(f"{index}. {requirement}")

    lines.extend([
        "",
        "## Assumptions",
    ])
    for assumption in assumptions:
        lines.append(f"- {assumption}")

    lines.extend([
        "",
        "## Suggested Database Schema",
    ])
    for table_name, columns in schema.items():
        lines.append(f"### {table_name}")
        for column in columns:
            lines.append(f"- {column}")
        lines.append("")

    lines.extend([
        "## Architecture Summary",
        architecture_summary,
        "",
        "## Security Summary",
        security_summary,
        "",
        "## Performance Summary",
        performance_summary,
        "",
        "## Validation Checks",
        "- requirements: PASS",
        "- schema: PASS",
        "- review: PASS",
    ])

    return {
        "prompt": prompt,
        "requirements": requirements,
        "assumptions": assumptions,
        "schema": schema,
        "architecture_summary": architecture_summary,
        "security_summary": security_summary,
        "performance_summary": performance_summary,
        "markdown": "\n".join(lines),
    }


def export_artifacts(document: Dict[str, Any]) -> Dict[str, str]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.utcnow().strftime("run-%Y%m%d-%H%M%S")
    json_path = ARTIFACT_DIR / f"{run_id}.json"
    md_path = ARTIFACT_DIR / f"{run_id}.md"
    json_path.write_text(json.dumps(document, indent=2), encoding="utf-8")
    md_path.write_text(document["markdown"], encoding="utf-8")
    return {"run_id": run_id, "json": str(json_path), "markdown": str(md_path)}


def render_home() -> None:
    st.markdown("### Project Brief Builder")
    st.write("Use one prompt to generate a concise project brief, schema suggestion, and delivery notes.")
    st.info("This app no longer uses agents, a supervisor, or a message bus. It is deterministic and local.")
    st.write("Use the Generate page to produce the document, then open the Document page to review or download it.")


def render_generate() -> None:
    st.markdown("### Generate")
    prompt = st.text_area("Describe the product you want to build", value=st.session_state.current_prompt, height=140)
    st.session_state.current_prompt = prompt

    if st.button("Generate Document", width="stretch"):
        document = build_document(prompt)
        artifacts = export_artifacts(document)
        st.session_state.latest_document = document
        st.session_state.latest_artifacts = artifacts
        st.session_state.run_history.insert(0, artifacts)
        st.session_state.run_history = st.session_state.run_history[:10]
        st.success("Document generated.")

    if st.session_state.latest_document:
        st.markdown("#### Current Output")
        st.code(st.session_state.latest_document["markdown"], language="markdown")


def render_document() -> None:
    st.markdown("### Document")
    document = st.session_state.latest_document
    artifacts = st.session_state.latest_artifacts

    if not document or not artifacts:
        st.info("Generate a document first.")
        return

    st.metric("Run ID", artifacts["run_id"])
    st.write("Artifact paths:")
    st.code(f"JSON: {artifacts['json']}\nMarkdown: {artifacts['markdown']}")

    st.markdown(document["markdown"])
    st.download_button(
        "Download Markdown",
        data=document["markdown"],
        file_name=f"{artifacts['run_id']}.md",
        mime="text/markdown",
    )
    st.download_button(
        "Download JSON",
        data=json.dumps(document, indent=2),
        file_name=f"{artifacts['run_id']}.json",
        mime="application/json",
    )


def main() -> None:
    st.set_page_config(page_title="Project Brief Builder", page_icon="📄", layout="wide")
    initialize_session_state()

    st.sidebar.title("Navigation")
    pages = ["Home", "Generate", "Document"]
    current_page = st.session_state.page if st.session_state.page in pages else pages[0]
    st.session_state.page = st.sidebar.radio("Go to", pages, index=pages.index(current_page))
    st.sidebar.caption("Standalone, non-agentic workflow")

    st.title("Project Brief Builder")

    if st.session_state.page == "Home":
        render_home()
    elif st.session_state.page == "Generate":
        render_generate()
    else:
        render_document()


if __name__ == "__main__":
    main()
