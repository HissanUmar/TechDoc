"""Standalone Streamlit app for sending a prompt to the requirements agent."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import streamlit as st

from .requirements_agent import RequirementsDocumentAgent


ARTIFACT_DIR = Path("artifacts") / "runs"
_agent = RequirementsDocumentAgent()
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


def export_artifacts(document: Dict[str, Any]) -> Dict[str, str]:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.utcnow().strftime("run-%Y%m%d-%H%M%S")
    json_path = ARTIFACT_DIR / f"{run_id}.json"
    md_path = ARTIFACT_DIR / f"{run_id}.md"
    json_path.write_text(json.dumps(document, indent=2), encoding="utf-8")
    md_path.write_text(document["response"], encoding="utf-8")
    return {"run_id": run_id, "json": str(json_path), "markdown": str(md_path)}


def render_home() -> None:
    st.markdown("### Project Brief Builder")
    st.write("Send one prompt to the requirements agent and display the full raw response.")
    st.info("The app now shows the agent output directly without extractor-based postprocessing.")
    st.write("Use the Generate page to run the agent, then open the Document page to review or download the output.")


def render_generate() -> None:
    st.markdown("### Generate")
    prompt = st.text_area("Describe the product you want to build", value=st.session_state.current_prompt, height=140)
    st.session_state.current_prompt = prompt

    if st.button("Generate Document", width="stretch"):
        try:
            with st.spinner("Generating raw agent response with web search..."):
                document = _agent.run(prompt)
            artifacts = export_artifacts(document)
            st.session_state.latest_document = document
            st.session_state.latest_artifacts = artifacts
            st.session_state.run_history.insert(0, artifacts)
            st.session_state.run_history = st.session_state.run_history[:10]
            st.success("Agent response generated.")
        except Exception as e:
            st.error(f"Error generating document: {e}")

    if st.session_state.latest_document:
        st.markdown("#### Current Output")
        st.text_area("Agent response", value=st.session_state.latest_document["response"], height=400)


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

    st.text_area("Agent response", value=document["response"], height=500)
    st.download_button(
        "Download Markdown",
        data=document["response"],
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
