"""
Streamlit UI for the Multi-Agent AI Software Engineering System (TRS).
Provides interactive interface for building and running multi-agent workflows.
"""

import streamlit as st
import json as json_lib
from datetime import datetime
from typing import Dict, List, Any
import sys
from pathlib import Path

# Ensure package can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from agentic_framework.supervisor import Supervisor
from agentic_framework.database_state import DatabaseStateStore
from agentic_framework.message_bus import SimpleMessageBus
from agentic_framework.clarification import ClarificationEngine
from agentic_framework.schemas import SchemaValidator
from agentic_framework.hf_client import HfClient
from agentic_framework.agents import build_default_agents


# ============================================================================
# Session State Initialization
# ============================================================================

def initialize_session_state():
    """Initialize all Streamlit session state values used by the app."""
    if "supervisor" not in st.session_state:
        # Use persistent DatabaseStateStore for durability across Colab session restarts
        st.session_state.supervisor = Supervisor(
            state_store=DatabaseStateStore(),
            max_workers=4,
            retry_attempts=3,
        )

    if "agents_registry" not in st.session_state:
        st.session_state.agents_registry = {}

    if "dag_config" not in st.session_state:
        st.session_state.dag_config = {}

    if "workflow_results" not in st.session_state:
        st.session_state.workflow_results = None

    if "clarification_engine" not in st.session_state:
        st.session_state.clarification_engine = ClarificationEngine(max_rounds=5)

    if "schema_validator" not in st.session_state:
        st.session_state.schema_validator = SchemaValidator()

    if "hf_client" not in st.session_state:
        st.session_state.hf_client = HfClient(model="mistralai/Mistral-7B-Instruct-v0.1")

    if "activity_log" not in st.session_state:
        st.session_state.activity_log = []

    if "workflow_stage" not in st.session_state:
        st.session_state.workflow_stage = "Home"

    if "workflow_note" not in st.session_state:
        st.session_state.workflow_note = "Ready"

    if "workflow_bus" not in st.session_state:
        st.session_state.workflow_bus = SimpleMessageBus()

    if "workflow_context" not in st.session_state:
        st.session_state.workflow_context = {}

    if "handoff_trace" not in st.session_state:
        st.session_state.handoff_trace = []

    if "latest_run_bundle" not in st.session_state:
        st.session_state.latest_run_bundle = None

    if "latest_artifact_paths" not in st.session_state:
        st.session_state.latest_artifact_paths = None

    if "run_history" not in st.session_state:
        st.session_state.run_history = []

    if "workflow_prompt" not in st.session_state:
        st.session_state.workflow_prompt = ""

    if "pending_clarifications" not in st.session_state:
        st.session_state.pending_clarifications = []

    if "clarification_answers" not in st.session_state:
        st.session_state.clarification_answers = {}

    if "workflow_run_in_progress" not in st.session_state:
        st.session_state.workflow_run_in_progress = False

initialize_session_state()


# ============================================================================
# Helper Functions
# ============================================================================

def register_default_agents():
    """Register all default agents with supervisor."""
    initialize_session_state()
    for name, agent in build_default_agents().items():
        st.session_state.supervisor.register_agent(name, agent)
        st.session_state.agents_registry[name] = agent
    st.success("✓ Default agents registered")


def build_dag_from_form(agent_names: List[str]) -> Dict[str, List[str]]:
    """Build DAG from form selections."""
    dag = {}
    for i, agent in enumerate(agent_names):
        if i == 0:
            dag[agent] = []  # Entry point
        else:
            dag[agent] = [agent_names[i - 1]]  # Depends on previous
    return dag


def log_activity(step: str, status: str, detail: str = "", model: str = "") -> None:
    """Store a compact activity entry for the sidebar log."""
    initialize_session_state()

    entry = {
        "step": step,
        "status": status,
        "detail": detail,
        "model": model,
    }
    st.session_state.activity_log.insert(0, entry)
    st.session_state.activity_log = st.session_state.activity_log[:8]


def publish_handoff(source: str, target: str, payload: Dict[str, Any]) -> None:
    """Publish a compact handoff message for downstream workflow steps."""
    initialize_session_state()

    message = {
        "source": source,
        "target": target,
        "payload": payload,
    }
    st.session_state.workflow_bus.publish("handoff", message)
    st.session_state.workflow_context[target] = payload
    st.session_state.workflow_context["latest_handoff"] = message
    st.session_state.handoff_trace.append(
        {
            "source": source,
            "target": target,
            "summary": payload.get("summary") or payload.get("status") or payload.get("result") or "handoff",
        }
    )
    st.session_state.handoff_trace = st.session_state.handoff_trace[-8:]


def latest_handoff_message() -> Dict[str, Any] | None:
    """Get the latest handoff message without consuming the full workflow history."""
    initialize_session_state()
    if st.session_state.workflow_bus.empty("handoff"):
        return None
    try:
        return st.session_state.workflow_bus.consume("handoff", timeout=0.01)
    except Exception:
        return None


def render_sidebar_log_panel() -> None:
    """Render the live activity log in the sidebar."""
    initialize_session_state()

    st.sidebar.markdown("### Live Log")
    st.sidebar.caption("Small progress notes from the current session.")
    st.sidebar.markdown(f"**Stage:** {st.session_state.workflow_stage}")
    st.sidebar.caption(st.session_state.workflow_note)

    if not st.session_state.activity_log:
        st.sidebar.info("No activity yet.")
    else:
        for entry in st.session_state.activity_log[:5]:
            model_text = f" | {entry['model'].split('/')[-1]}" if entry.get("model") else ""
            detail_text = f"\n{entry['detail']}" if entry.get("detail") else ""
            st.sidebar.markdown(
                f"**{entry['step']}** · {entry['status']}{model_text}{detail_text}"
            )

    st.sidebar.markdown("### Handoff Trace")
    if not st.session_state.handoff_trace:
        st.sidebar.caption("No handoffs yet.")
        return

    for entry in st.session_state.handoff_trace[-4:]:
        st.sidebar.caption(f"{entry['source']} → {entry['target']} : {entry['summary']}")


def build_pipeline_analysis() -> Dict[str, Any]:
    """Build a compact status summary for the current pipeline and model setup."""
    initialize_session_state()

    supervisor = st.session_state.supervisor
    hf_status = st.session_state.hf_client.get_status()
    active_model = hf_status.get("active_model", "unknown")

    return {
        "stage": st.session_state.workflow_stage,
        "note": st.session_state.workflow_note,
        "pipeline": {
            "registered_count": len(st.session_state.agents_registry),
            "max_workers": supervisor.max_workers,
            "retry_attempts": supervisor.retry_attempts,
        },
        "model": {
            "used": active_model,
            "status": "Live" if hf_status.get("client_available", False) else "Fallback",
            "has_token": hf_status.get("has_token", False),
        },
        "state": {
            "version": supervisor.state.snapshot()[0],
            "keys": len(supervisor.state.keys()),
            "history": len(supervisor.state.history()),
        },
    }


def _sanitize_public_results(value: Any) -> Any:
    """Strip internal LLM plumbing fields from user-facing output artifacts."""
    if isinstance(value, dict):
        hidden_keys = {"prompt", "model_response"}
        cleaned: Dict[str, Any] = {}
        for key, item in value.items():
            if key in hidden_keys:
                continue
            cleaned[key] = _sanitize_public_results(item)
        return cleaned
    if isinstance(value, list):
        return [_sanitize_public_results(item) for item in value]
    return value


def _build_run_bundle(schema_name: str, gate_result: Dict[str, Any], results: Dict[str, Any]) -> Dict[str, Any]:
    run_id = datetime.utcnow().strftime("run-%Y%m%d-%H%M%S")
    public_results = _sanitize_public_results(results)
    return {
        "run_id": run_id,
        "generated_at_utc": datetime.utcnow().isoformat() + "Z",
        "schema_name": schema_name,
        "gate": gate_result,
        "handoff_trace": st.session_state.handoff_trace,
        "workflow_results": public_results,
    }


def _bundle_to_markdown(bundle: Dict[str, Any]) -> str:
    gate = bundle.get("gate", {})
    workflow_results = bundle.get("workflow_results", {}) or {}
    documentation = workflow_results.get("documentation", {}) if isinstance(workflow_results, dict) else {}
    documentation_text = ""
    if isinstance(documentation, dict):
        documentation_text = documentation.get("documentation") or documentation.get("summary") or ""
    elif isinstance(documentation, str):
        documentation_text = documentation

    requirements = workflow_results.get("requirements", {}) if isinstance(workflow_results, dict) else {}
    assumptions = requirements.get("assumptions", []) if isinstance(requirements, dict) else []
    req_items = requirements.get("requirements", []) if isinstance(requirements, dict) else []
    questions = requirements.get("questions", []) if isinstance(requirements, dict) else []
    architecture = workflow_results.get("architecture", {}) if isinstance(workflow_results, dict) else {}
    security = workflow_results.get("security", {}) if isinstance(workflow_results, dict) else {}
    performance = workflow_results.get("performance", {}) if isinstance(workflow_results, dict) else {}

    lines = [
        f"# Final Project Document",
        "",
        f"- Generated: {bundle.get('generated_at_utc', 'unknown')}",
        f"- Run ID: {bundle.get('run_id', 'unknown')}",
        f"- Schema: {bundle.get('schema_name', 'unknown')}",
        f"- Validation Gate: {gate.get('status', 'unknown')}",
        "",
        "## Project Overview",
        documentation_text.splitlines()[0] if documentation_text else "No project overview available.",
        "",
        "## Requirements",
    ]

    if req_items:
        for index, requirement in enumerate(req_items, start=1):
            lines.append(f"{index}. {requirement}")
    else:
        lines.append("No functional requirements captured.")

    lines.extend([
        "",
        "## Assumptions",
    ])
    if assumptions:
        for assumption in assumptions:
            lines.append(f"- {assumption}")
    else:
        lines.append("- None recorded.")

    lines.extend([
        "",
        "## Clarifications Resolved",
    ])
    if questions:
        for question in questions:
            lines.append(f"- {question}")
    else:
        lines.append("- No open questions remained at validation time.")

    lines.extend([
        "",
        "## Suggested Database Schema",
    ])
    if isinstance(documentation, dict) and documentation.get("documentation"):
        # Keep the schema guidance inside the final document content if the agent produced it.
        doc_lines = documentation.get("documentation", "").splitlines()
        schema_section_started = False
        for line in doc_lines:
            if line.strip().lower().startswith("## suggested database schema"):
                schema_section_started = True
                continue
            if line.strip().startswith("## ") and schema_section_started:
                break
            if schema_section_started:
                lines.append(line)
        if not schema_section_started:
            lines.append("No schema guidance was produced.")
    else:
        lines.append("No schema guidance was produced.")

    lines.extend([
        "",
        "## Architecture Summary",
        architecture.get("summary", "No architecture summary available.") if isinstance(architecture, dict) else str(architecture),
        "",
        "## Security Summary",
        security.get("summary", "No security summary available.") if isinstance(security, dict) else str(security),
        "",
        "## Performance Summary",
        performance.get("summary", "No performance summary available.") if isinstance(performance, dict) else str(performance),
        "",
        "## Validation Checks",
    ])

    for check_name, result in gate.get("checks", {}).items():
        mark = "PASS" if result.get("valid") else "FAIL"
        lines.append(f"- {check_name}: {mark}")
        for err in result.get("errors", []):
            lines.append(f"  - error: {err}")

    lines.extend([
        "",
        "## Handoff Trace",
    ])
    for handoff in bundle.get("handoff_trace", []):
        lines.append(f"- {handoff.get('source')} -> {handoff.get('target')}: {handoff.get('summary')}")
    return "\n".join(lines)


def export_run_artifacts(bundle: Dict[str, Any]) -> Dict[str, str]:
    artifacts_dir = Path("artifacts") / "runs"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    run_id = bundle["run_id"]
    json_path = artifacts_dir / f"{run_id}.json"
    md_path = artifacts_dir / f"{run_id}.md"

    json_path.write_text(json_lib.dumps(bundle, indent=2), encoding="utf-8")
    md_path.write_text(_bundle_to_markdown(bundle), encoding="utf-8")

    return {
        "json": str(json_path),
        "markdown": str(md_path),
    }


def summarize_run_changes(previous_bundle: Dict[str, Any] | None, current_bundle: Dict[str, Any]) -> List[str]:
    """Build a compact change list between two workflow runs."""
    if previous_bundle is None:
        return ["Initial run created. No previous execution to compare."]

    changes: List[str] = []

    prev_gate = previous_bundle.get("gate", {}).get("status")
    cur_gate = current_bundle.get("gate", {}).get("status")
    if prev_gate != cur_gate:
        changes.append(f"Gate status changed: {prev_gate} -> {cur_gate}")

    prev_checks = previous_bundle.get("gate", {}).get("checks", {})
    cur_checks = current_bundle.get("gate", {}).get("checks", {})
    for name in sorted(set(prev_checks.keys()) | set(cur_checks.keys())):
        prev_valid = prev_checks.get(name, {}).get("valid")
        cur_valid = cur_checks.get(name, {}).get("valid")
        if prev_valid != cur_valid:
            changes.append(f"Check changed ({name}): {prev_valid} -> {cur_valid}")

    prev_handoffs = len(previous_bundle.get("handoff_trace", []))
    cur_handoffs = len(current_bundle.get("handoff_trace", []))
    if prev_handoffs != cur_handoffs:
        changes.append(f"Handoff count changed: {prev_handoffs} -> {cur_handoffs}")

    prev_reviewer = previous_bundle.get("workflow_results", {}).get("reviewer", {}).get("summary", "")
    cur_reviewer = current_bundle.get("workflow_results", {}).get("reviewer", {}).get("summary", "")
    if prev_reviewer != cur_reviewer:
        changes.append("Reviewer summary changed")

    prev_doc = previous_bundle.get("workflow_results", {}).get("documentation", {}).get("summary", "")
    cur_doc = current_bundle.get("workflow_results", {}).get("documentation", {}).get("summary", "")
    if prev_doc != cur_doc:
        changes.append("Documentation summary changed")

    if not changes:
        changes.append("No material run-to-run changes detected.")
    return changes


def render_document_screen() -> None:
    """Render final run artifacts and visible execution changes."""
    st.markdown("### Document")
    st.write("Final run output, gate results, and visible changes from execution are shown here.")

    latest_bundle = st.session_state.latest_run_bundle
    artifact_paths = st.session_state.latest_artifact_paths

    if not latest_bundle or not artifact_paths:
        st.info("No run artifacts yet. Complete the Workflow -> Validate step first.")
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Run ID", latest_bundle.get("run_id", "unknown"))
    with col2:
        st.metric("Gate", latest_bundle.get("gate", {}).get("status", "unknown"))
    with col3:
        st.metric("Handoffs", len(latest_bundle.get("handoff_trace", [])))

    st.markdown("**Visible changes from execution**")
    for change in latest_bundle.get("changes", []):
        st.caption(f"- {change}")

    st.markdown("**Artifact paths**")
    st.code(f"JSON: {artifact_paths['json']}\nMarkdown: {artifact_paths['markdown']}")

    md_path = Path(artifact_paths["markdown"])

    with st.expander("Rendered final document", expanded=True):
        if md_path.exists():
            st.markdown(md_path.read_text(encoding="utf-8"), unsafe_allow_html=False)
        else:
            st.warning("Markdown artifact file not found.")


def render_pipeline_analysis_card(analysis: Dict[str, Any]):
    """Render the current pipeline/model state in the UI."""
    summary = analysis if isinstance(analysis, dict) and "model" in analysis else build_pipeline_analysis()

    st.subheader("📌 Current Status")

    st.caption(f"Stage: {summary['stage']} · Note: {summary['note']}")
    st.caption(f"State v{summary['state']['version']} · {summary['state']['keys']} keys · {summary['state']['history']} events")

    left, right = st.columns([1, 1])
    with left:
        st.markdown("**Done so far**")
        st.caption(f"Agents ready: {summary['pipeline']['registered_count']}")
        st.caption(f"Workers: {summary['pipeline']['max_workers']}")
        st.caption(f"Retry attempts: {summary['pipeline']['retry_attempts']}")
    with right:
        st.markdown("**Model details**")
        st.caption(f"Used: {summary['model']['used']}")
        st.caption(f"Status: {summary['model']['status']}")
        st.caption(f"Token: {'Present' if summary['model']['has_token'] else 'Missing'}")

    latest_handoff = st.session_state.workflow_context.get("latest_handoff")
    if latest_handoff:
        st.caption(f"Latest handoff: {latest_handoff['source']} -> {latest_handoff['target']}")


def display_results(results: Dict[str, Any]):
    """Display workflow results in organized tabs with model info prominent."""
    if not results:
        st.warning("No results to display")
        return
    
    cols = st.columns(len(results))
    for col, (agent_name, result) in zip(cols, results.items()):
        with col:
            st.subheader(f"🔹 {agent_name.title()}")
            
            # Extract and display model info if available
            if isinstance(result, dict):
                if "model_used" in result:
                    model_name = result.get("model_used", "unknown")
                    st.success(f"📊 Model: `{model_name}`")
                
                if "model_status" in result:
                    status = result.get("model_status", {})
                    active = status.get("active_model", "unknown")
                    has_token = status.get("has_token", False)
                    client = status.get("client_available", False)
                    
                    status_html = f"""
                    **Status:** {'✅ Live' if client else '⚠️ Fallback'}
                    
                    **Active Model:** `{active}`
                    **HF Token:** {'✓' if has_token else '✗'}
                    """
                    st.markdown(status_html)
                    st.divider()
            
            st.json(result)


def render_home_screen() -> None:
    """Render a concise landing page with the essential app summary."""
    summary = build_pipeline_analysis()

    st.markdown("### Multi-Agent TRS")
    st.write("One clean workflow page for setup, model status, clarification, and validation.")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Model", summary["model"]["used"].split("/")[-1] if "/" in summary["model"]["used"] else summary["model"]["used"])
    with col2:
        st.metric("Status", summary["model"]["status"])
    with col3:
        st.metric("Stage", summary["stage"])

    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown("**What this app does**")
        st.write("- Prepares a workflow")
        st.write("- Shows concise model status")
        st.write("- Helps clarify requirements")
        st.write("- Checks schema input")
    with col2:
        st.markdown("**Current snapshot**")
        st.write(f"- Agents ready: {summary['pipeline']['registered_count']}")
        st.write(f"- State version: {summary['state']['version']}")
        st.write(f"- State keys: {summary['state']['keys']}")
        st.write(f"- Note: {summary['note']}")

    if st.button("Open Workflow", width="stretch"):
        st.session_state.nav_page = "⚙️ Workflow"
        st.session_state.workflow_stage = "Workflow"
        st.session_state.workflow_note = "Opened from Home"
        log_activity("Home", "Opened", "Moved into the workflow workspace", summary["model"]["used"])
        st.rerun()


def render_workflow_screen() -> None:
    """Render the single workflow workspace with all steps visible at once."""
    initialize_session_state()

    required_agents = set(build_default_agents().keys())
    registered_agents = set(st.session_state.agents_registry.keys())
    if not required_agents.issubset(registered_agents):
        register_default_agents()
        st.session_state.workflow_note = "Default agents auto-loaded for the workflow"
        log_activity("Agents", "Loaded", "Auto-registered required agents", st.session_state.hf_client.get_status()["active_model"])

    summary = build_pipeline_analysis()

    st.markdown("### Workflow Workspace")
    st.write("Provide one prompt. The supervisor will decide which agent runs next, pause for clarifications if needed, and stop when the requirements landscape is complete enough.")

    progress_placeholder = st.empty()
    progress_lines: List[str] = []

    def append_progress(event: Dict[str, Any]) -> None:
        event_name = event.get("event", "progress")
        if event_name == "agent_start":
            line = f"Starting {event.get('agent')}"
        elif event_name == "agent_end":
            line = f"Finished {event.get('agent')}"
        elif event_name == "decision":
            line = f"Selected {event.get('agent')}: {event.get('reason', 'no reason provided')}"
        elif event_name == "planner_complete":
            line = f"Planner suggested: {', '.join(event.get('next_candidates', [])) or 'none'}"
        elif event_name == "fallback_plan":
            line = f"Using fallback order: {', '.join(event.get('next_candidates', [])) or 'none'}"
        elif event_name == "review_check":
            line = f"Review check after {event.get('after')}"
        elif event_name == "review_result":
            line = f"Reviewer ready={event.get('ready')} coverage={event.get('coverage_score', 0)}"
        elif event_name == "clarification_needed":
            line = f"Clarification needed from {event.get('agent')}"
            st.session_state.pending_clarifications = event.get("questions", [])
        elif event_name == "stop":
            line = f"Stopping: {event.get('reason')}"
        elif event_name == "skip":
            line = f"Skipping {event.get('agent')}: {event.get('reason')}"
        else:
            line = event_name

        progress_lines.append(line)
        progress_placeholder.markdown("\n".join([f"- {item}" for item in progress_lines[-12:]]))
        log_activity("Pipeline", event_name, line, st.session_state.hf_client.get_status().get("active_model", ""))

    def run_prompt_workflow(prompt_text: str, answers: Dict[str, str] | None = None) -> None:
        initialize_session_state()
        if not st.session_state.agents_registry:
            register_default_agents()

        initial_context = {
            "problem_statement": prompt_text,
            "workflow_name": st.session_state.get("workflow_name") or "Single prompt workflow",
            "clarification_answers": answers or {},
            "coverage_threshold": 80,
        }

        st.session_state.workflow_run_in_progress = True
        try:
            results, exec_order = st.session_state.supervisor.run_adaptive_workflow(
                initial_context,
                progress_callback=append_progress,
            )
        except Exception as e:
            st.session_state.workflow_run_in_progress = False
            st.error(f"Pipeline failed: {e}")
            raise

        if results.get("clarification_needed"):
            st.session_state.workflow_stage = "Clarification Needed"
            st.session_state.workflow_note = "Answer the questions below and continue the workflow"
            st.session_state.workflow_results = results
            st.session_state.workflow_prompt = prompt_text
            st.session_state.workflow_run_in_progress = False
            return

        st.session_state.workflow_results = results
        prev = "start"
        for node in exec_order:
            payload = results.get(node, {})
            publish_handoff(prev, node, payload if isinstance(payload, dict) else {"result": str(payload)})
            prev = node

        st.session_state.workflow_stage = "Validate Schema"
        st.session_state.workflow_note = "Supervisor completed the workflow and validated the final document"

        reviewer_result = results.get("reviewer")
        validator = st.session_state.schema_validator
        current_results = st.session_state.workflow_results or {}
        requirements_result = current_results.get("requirements", {})
        architecture_result = current_results.get("architecture", {})

        requirements_check = validator.validate({"requirements": requirements_result.get("requirements", [])}, "requirements")
        architecture_check = validator.validate(
            {
                "architecture": architecture_result.get("architecture_type", "unknown"),
                "components": architecture_result.get("components", []),
            },
            "architecture",
        )
        reviewer_check = validator.validate(
            {
                "valid": bool(reviewer_result and reviewer_result.get("ready", False)),
                "errors": reviewer_result.get("gaps", []) if isinstance(reviewer_result, dict) else [],
                "warnings": reviewer_result.get("improvements", []) if isinstance(reviewer_result, dict) else [],
            },
            "validation",
        )

        gate_checks = {
            "requirements_schema": requirements_check,
            "architecture_schema": architecture_check,
            "reviewer_gate": reviewer_check,
        }
        hard_pass = all(v.get("valid", False) for v in gate_checks.values())

        if hard_pass and "documentation" in st.session_state.agents_registry:
            documentation_agent = st.session_state.agents_registry.get("documentation")
            documentation_result = documentation_agent.process({
                "problem_statement": prompt_text,
                "requirements": requirements_result.get("requirements", []),
                "assumptions": requirements_result.get("assumptions", []),
                "questions": requirements_result.get("questions", []),
                "architecture_type": architecture_result.get("architecture_type", "unknown"),
                "architecture_summary": architecture_result.get("summary", ""),
                "security_score": current_results.get("security", {}).get("security_score", 0),
                "security_summary": current_results.get("security", {}).get("summary", ""),
                "performance_summary": current_results.get("performance", {}).get("summary", ""),
                "review": reviewer_result,
                "schema": st.session_state.get("schema_input", "requirements"),
            })
            publish_handoff("reviewer", "documentation", documentation_result)
            st.session_state.workflow_results = {**current_results, "documentation": documentation_result, "reviewer": reviewer_result}
            gate_status = "passed"
            st.session_state.workflow_note = "Final document generated from a complete-enough requirements landscape"
        else:
            documentation_result = {"summary": "Documentation generation blocked by gate failure.", "blocked": True}
            st.session_state.workflow_results = {**current_results, "reviewer": reviewer_result, "documentation": documentation_result}
            gate_status = "failed"
            st.session_state.workflow_note = "Validation gate failed or completeness threshold was not met"

        gate_result = {"status": gate_status, "checks": gate_checks}
        previous_bundle = st.session_state.latest_run_bundle
        final_bundle = _build_run_bundle(st.session_state.get("schema_input", "requirements"), gate_result, st.session_state.workflow_results)
        final_bundle["changes"] = summarize_run_changes(previous_bundle, final_bundle)
        artifact_paths = export_run_artifacts(final_bundle)

        st.session_state.latest_run_bundle = final_bundle
        st.session_state.latest_artifact_paths = artifact_paths
        st.session_state.run_history.append({"run_id": final_bundle["run_id"], "status": gate_status, "changes": final_bundle["changes"], "artifacts": artifact_paths})
        st.session_state.run_history = st.session_state.run_history[-10:]
        st.session_state.pending_clarifications = []
        st.session_state.workflow_run_in_progress = False

        if gate_status == "passed":
            st.success("Pipeline completed and validated. Artifacts exported.")
        else:
            st.error("Pipeline completed but validation failed. Artifacts exported with failure report.")

    prompt_value = st.text_area(
        "Start with one prompt",
        value=st.session_state.workflow_prompt or "Build an app for tracking clients, projects, tasks, meeting notes, and deadlines for a small consulting team.",
        height=120,
        key="single_prompt_input",
    )

    if st.session_state.pending_clarifications:
        st.info("The supervisor needs a few clarifications before it can continue.")
        clarification_answers: Dict[str, str] = {}
        for index, question in enumerate(st.session_state.pending_clarifications):
            question_text = question.get("question", str(question)) if isinstance(question, dict) else str(question)
            clarification_answers[question_text] = st.text_input(
                f"Clarification {index + 1}",
                value=st.session_state.clarification_answers.get(question_text, ""),
                key=f"clarify_{index}",
                placeholder=question_text,
            )

        if st.button("Continue Workflow", width="stretch"):
            st.session_state.clarification_answers = clarification_answers
            run_prompt_workflow(prompt_value, clarification_answers)
    else:
        if st.button("▶️ Run Full Pipeline", width='stretch'):
            st.session_state.clarification_answers = {}
            run_prompt_workflow(prompt_value, {})

    st.divider()
    render_pipeline_analysis_card(summary)
    st.caption("The workflow starts from one prompt, pauses for clarifications when needed, and stops once the requirements landscape is sufficiently complete.")
    return


# ============================================================================
# Streamlit App Layout
# ============================================================================

def main():
    # Ensure session state is initialized before any access
    initialize_session_state()
    
    st.set_page_config(
        page_title="Multi-Agent TRS",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    
    st.title("🤖 Multi-Agent AI Software Engineering System")
    st.markdown("Build, orchestrate, and run multi-agent workflows for technical requirement analysis.")
    
    # Sidebar Navigation
    with st.sidebar:
        st.header("Navigation")
        page = st.radio(
            "Select Page",
            ["🏠 Home", "⚙️ Workflow", "📄 Document"],
            label_visibility="collapsed",
            key="nav_page",
        )
        st.divider()
        render_sidebar_log_panel()

    if page == "🏠 Home":
        render_home_screen()
        return

    if page == "⚙️ Workflow":
        render_workflow_screen()
        return

    if page == "📄 Document":
        render_document_screen()
        return
    
    # ========================================================================
    # Page 1: Home
    # ========================================================================
    if page == "🏠 Home":
        st.markdown("""
        ### Welcome to the Multi-Agent TRS
        
        This system enables you to:
        - **Build workflows** by orchestrating specialized agents
        - **Analyze requirements** with clarification and validation
        - **Design architectures** with distributed agents
        - **Validate outputs** against JSON schemas
        - **Manage state** across complex workflows
        
        #### Quick Start
        1. Go to **Build Workflow** to create your first multi-agent pipeline
        2. Use **Clarify Requirements** to disambiguate vague input
        3. Run workflows and view results in real-time
        
        #### Available Agents
        """)
        
        # Show agents with their models
        col1, col2, col3 = st.columns(3)
        with col1:
            st.success("**Requirements Analyst**")
            st.caption("📊 Extracts structured requirements")
            st.markdown("`Model: Mistral-7B` (with fallback chain)")
        with col2:
            st.success("**Architecture Designer**")
            st.caption("🏗️ Designs system architecture")
            st.markdown("`Model: Mistral-7B` (with fallback chain)")
        with col3:
            st.success("**Security Validator**")
            st.caption("🔒 Validates security aspects")
            st.markdown("`Model: Mistral-7B` (with fallback chain)")
        
        col1, col2 = st.columns(2)
        with col1:
            st.success("**Performance Analyzer**")
            st.caption("⚡ Analyzes performance characteristics")
            st.markdown("`Model: Mistral-7B` (with fallback chain)")
        with col2:
            st.success("**Documentation Generator**")
            st.caption("📝 Generates technical docs")
            st.markdown("`Model: Mistral-7B` (with fallback chain)")
        
        st.divider()
        
        st.subheader("Model Fallback Chain")
        st.markdown("""
        If Mistral is unavailable, the system automatically tries:
        1. **mistralai/Mistral-7B-Instruct-v0.1** ← Primary
        2. **meta-llama/Llama-2-7b-chat-hf** ← Fallback 1
        3. **tiiuae/falcon-7b-instruct** ← Fallback 2
        4. **google/flan-t5-large** ← Fallback 3
        5. **gpt2 (stub)** ← Final fallback
        
        Each agent shows which model it's actually using in the results.
        """)
        
        st.divider()

        render_pipeline_analysis_card(build_pipeline_analysis())

        st.divider()
        
        if st.button("🚀 Initialize Default Agents", width='stretch'):
            register_default_agents()
    
    # ========================================================================
    # Page 2: Build Workflow
    # ========================================================================
    elif page == "🔧 Build Workflow":
        st.header("Build Multi-Agent Workflow")
        
        # Ensure session state is initialized (defensive check)
        if "agents_registry" not in st.session_state:
            initialize_session_state()
        
        # Initialize agents if needed
        if not st.session_state.agents_registry:
            st.info("Agents not initialized. Click button to register defaults.")
            if st.button("📥 Register Default Agents", width='stretch'):
                register_default_agents()
            st.stop()
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("Workflow Configuration")
            
            # Agent selection
            available_agents = list(st.session_state.agents_registry.keys())
            selected_agents = st.multiselect(
                "Select agents (order matters - first→last):",
                available_agents,
                default=available_agents[:3] if len(available_agents) >= 3 else available_agents,
                help="Agents will be chained in order (sequential dependency)"
            )
            
            if not selected_agents:
                st.warning("Select at least one agent")
                st.stop()
            
            # Build DAG
            dag = build_dag_from_form(selected_agents)
            
            st.subheader("DAG Structure")
            st.code(json_lib.dumps(dag, indent=2), language="json")
            
            # Input configuration
            st.subheader("Workflow Input")
            user_input = st.text_area(
                "Requirements or input text:",
                value="Build a scalable web application with authentication",
                help="This will be passed to the first agent"
            )
        
        with col2:
            st.subheader("Execution Settings")
            max_workers = st.slider("Max parallel workers:", 1, 8, 4)
            retry_attempts = st.slider("Retry attempts:", 1, 5, 3)
            st.session_state.supervisor.max_workers = max_workers
            st.session_state.supervisor.retry_attempts = retry_attempts
            
            st.info(f"""
            **Config:**
            - Workers: {max_workers}
            - Retries: {retry_attempts}
            - Agents: {len(selected_agents)}
            """)
        
        st.divider()
        
        # Run workflow
        if st.button("▶️ Run Workflow", width='stretch', type="primary"):
            with st.spinner("Executing workflow..."):
                try:
                    payloads = {
                        selected_agents[0]: {"user_input": user_input}
                    }
                    for agent in selected_agents[1:]:
                        payloads[agent] = {}
                    
                    results = st.session_state.supervisor.run_workflow(dag, payloads)
                    st.session_state.workflow_results = results
                    st.success("✓ Workflow completed successfully!")
                    
                except Exception as e:
                    st.error(f"Workflow failed: {str(e)}")
                    return
        
        # Display results
        if st.session_state.workflow_results:
            st.subheader("Workflow Results")
            display_results(st.session_state.workflow_results)
    
    # ========================================================================
    # Page 3: Model Status
    # ========================================================================
    elif page == "🤖 Model Status":
        st.header("Model Status & Configuration")
        st.markdown("View active models for each agent and model fallback status.")
        
        # Ensure session state is initialized (defensive check)
        if "agents_registry" not in st.session_state:
            initialize_session_state()
        
        # Initialize agents if needed
        if not st.session_state.agents_registry:
            st.info("Agents not initialized. Click button to register defaults.")
            if st.button("📥 Register Default Agents", width='stretch'):
                register_default_agents()
            st.stop()
        
        # HF Client Status
        st.subheader("🤖 HuggingFace Integration Status")
        hf_client = st.session_state.hf_client
        hf_status = hf_client.get_status()
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Requested Model", hf_status["requested_model"].split("/")[-1])
        with col2:
            st.metric("Active Model", hf_status["active_model"].split("/")[-1] if "/" in hf_status["active_model"] else hf_status["active_model"])
        with col3:
            status_text = "✅ Connected" if hf_status["client_available"] else "⚠️ Fallback"
            st.metric("HF Client", status_text)
        with col4:
            token_text = "✓ Present" if hf_status["has_token"] else "✗ Missing"
            st.metric("API Token", token_text)
        
        st.divider()
        
        # Model Fallback Chain
        st.subheader("📋 Model Fallback Chain")
        from agentic_framework.hf_client import MODEL_CHAIN
        
        fallback_data = []
        for i, model_name in enumerate(MODEL_CHAIN):
            status = hf_status["attempted_models"].get(model_name, "not_attempted")
            is_active = model_name == hf_status["active_model"]
            priority = "🔴 Final" if i == len(MODEL_CHAIN) - 1 else f"Priority {i+1}"
            
            fallback_data.append({
                "Position": priority,
                "Model": model_name.split("/")[-1] if "/" in model_name else model_name,
                "Status": "✅ Active" if is_active else ("❌ Failed" if "error" in status.lower() or status == "failed" else "Fallback"),
                "Details": status if isinstance(status, str) else "success",
            })
        
        st.dataframe(fallback_data, width='stretch')
        
        st.divider()
        
        # Agent Models
        st.subheader("🔹 Agent Model Assignments")
        
        agent_models = {}
        for agent_name, agent in st.session_state.agents_registry.items():
            if hasattr(agent, "model"):
                status = agent.model.get_status()
                agent_models[agent_name] = {
                    "Agent": agent_name.title(),
                    "Model": status["active_model"],
                    "Status": "✅ Live" if status["client_available"] else "⚠️ Fallback",
                }
        
        if agent_models:
            agent_data = list(agent_models.values())
            st.dataframe(agent_data, width='stretch')
        
        st.divider()
        
        # Configuration
        st.subheader("⚙️ Configuration")
        
        with st.expander("View Full HF Status JSON", expanded=False):
            st.json(hf_status)
        
        # Test Model
        st.subheader("🧪 Test Model")
        test_prompt = st.text_input(
            "Test prompt:",
            value="What is the purpose of a software architect?",
            placeholder="Enter a test prompt..."
        )
        
        if st.button("▶️ Run Test", width='stretch'):
            with st.spinner("Testing model..."):
                try:
                    response = hf_client.call_model(test_prompt)
                    st.success("✅ Model test successful!")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Model Used", response["model"])
                    with col2:
                        st.metric("Response Status", response.get("status", "unknown"))
                    
                    st.subheader("Response")
                    st.write(response["output"])
                    
                except Exception as e:
                    st.error(f"Model test failed: {str(e)}")
    
    # ========================================================================
    # Page 4: Clarify Requirements
    # ========================================================================
    elif page == "📋 Clarify Requirements":
        st.header("Requirement Clarification Engine")
        st.markdown("Detect vague terms and generate clarifying questions.")
        
        user_requirements = st.text_area(
            "Enter requirements to clarify:",
            value="We need a fast, scalable system that's reliable for many users",
            height=100
        )
        
        if st.button("🔍 Analyze Requirements", width='stretch'):
            # Ensure session state is initialized (defensive check)
            if "clarification_engine" not in st.session_state:
                initialize_session_state()
            engine = st.session_state.clarification_engine
            analysis = engine.analyze(user_requirements)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Vague Terms Found", len(analysis["vague_terms"]))
            with col2:
                st.metric("Questions Generated", len(analysis["questions"]))
            with col3:
                st.metric("Can Proceed", "Yes" if analysis["can_proceed"] else "No")
            
            st.subheader("Detected Vague Terms")
            if analysis["vague_terms"]:
                for term in analysis["vague_terms"]:
                    if isinstance(term, dict):
                        term_text = term.get("text") or term.get("term") or str(term)
                    else:
                        term_text = str(term)
                    st.badge(term_text)
            else:
                st.info("No vague terms detected")
            
            st.divider()
            
            st.subheader("Clarification Questions")
            engine.questions = analysis["questions"]
            
            for i, q in enumerate(analysis["questions"][:5]):
                if isinstance(q, dict):
                    q_text = q.get("text") or q.get("question") or q.get("title") or str(q)
                    priority = q.get("priority", "N/A")
                    category = q.get("category", "general")
                else:
                    q_text = str(q)
                    priority = "N/A"
                    category = "general"

                with st.expander(f"Q{i+1}: {q_text}", expanded=(i == 0)):
                    st.markdown(f"**Priority:** {priority}/10")
                    st.markdown(f"**Category:** {category}")

                    answer = st.text_input(
                        f"Your answer for Q{i+1}:",
                        key=f"answer_{i}",
                        placeholder="Enter your answer..."
                    )

                    if answer:
                        engine.add_answer(i, answer)
            
            st.divider()
            
            can_proceed, msg = engine.proceed_or_clarify()
            if can_proceed:
                st.success(f"✓ {msg}")
            else:
                st.warning(f"⚠️ {msg}")
            
            if st.button("📄 View Summary", width='stretch'):
                summary = engine.summary()
                st.json(summary)
    
    # ========================================================================
    # Page 5: Validate Schema
    # ========================================================================
    elif page == "✅ Validate Schema":
        st.header("Schema Validation")
        st.markdown("Validate data against predefined or custom schemas.")
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            schema_type = st.radio(
                "Schema Type",
                ["Built-in", "Custom"],
                label_visibility="collapsed"
            )
        
        with col2:
            if schema_type == "Built-in":
                schema_name = st.selectbox(
                    "Select schema:",
                    ["requirements", "architecture", "validation_result"],
                    label_visibility="collapsed"
                )
            else:
                schema_name = st.text_input(
                    "Custom schema name:",
                    placeholder="my_schema",
                    label_visibility="collapsed"
                )
        
        st.subheader("Data to Validate")
        data_json = st.text_area(
            "JSON data:",
            value='{"requirements": ["auth", "logging", "db"]}',
            height=150,
            language="json"
        )
        
        if st.button("✓ Validate", width='stretch'):
            try:
                # Ensure session state is initialized (defensive check)
                if "schema_validator" not in st.session_state:
                    initialize_session_state()
                data = json.loads(data_json)
                validator = st.session_state.schema_validator
                result = validator.validate(data, schema_name)
                
                col1, col2 = st.columns(2)
                with col1:
                    if result["valid"]:
                        st.success(f"✓ Valid against '{schema_name}'")
                    else:
                        st.error(f"✗ Invalid against '{schema_name}'")
                
                with col2:
                    st.metric("Errors", len(result.get("errors", [])))
                
                if result.get("errors"):
                    st.subheader("Validation Errors")
                    for error in result["errors"]:
                        st.warning(error)
                
            except json_lib.JSONDecodeError as e:
                st.error(f"Invalid JSON: {str(e)}")
    
    # ========================================================================
    # Page 6: State Management
    # ========================================================================
    elif page == "📊 State Management":
        st.header("Workflow State Management")
        st.markdown("View and manage versioned state across workflows.")

        render_pipeline_analysis_card(build_pipeline_analysis())

        st.divider()
        
        # Ensure session state is initialized (defensive check)
        if "supervisor" not in st.session_state:
            initialize_session_state()
        
        state = st.session_state.supervisor.state
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Keys", len(state.keys()))
        with col2:
            version, _ = state.snapshot()
            st.metric("Current Version", version)
        with col3:
            history = state.history()
            st.metric("History Events", len(history))
        
        st.divider()
        
        st.subheader("Set State Value")
        col1, col2 = st.columns([1, 1])
        with col1:
            key = st.text_input("Key:", placeholder="workflow_id")
        with col2:
            value = st.text_input("Value:", placeholder="my_value")
        
        if st.button("💾 Save", width='stretch'):
            if key and value:
                version = state.set(key, value)
                st.success(f"✓ Saved (version {version})")
            else:
                st.warning("Enter both key and value")
        
        st.divider()
        
        st.subheader("Current State")
        st.json(dict(state.keys()) if hasattr(state, 'keys') else {})
        
        st.subheader("State History")
        history = state.history()
        if history:
            history_df = [
                {"Version": v, "Key": k, "Value": str(val)[:50]}
                for v, k, val in history
            ]
            st.dataframe(history_df, width='stretch')
        else:
            st.info("No history yet")
    
    # ========================================================================
    # Page 7: About
    # ========================================================================
    elif page == "ℹ️ About":
        st.header("About Multi-Agent TRS")
        
        st.markdown("""
        ### Multi-Agent AI Software Engineering System
        
        A production-ready framework for orchestrating specialized AI agents in complex workflows.
        
        **Key Features:**
        - 🎯 Supervisor-based DAG orchestration with topological sorting
        - ⚙️ Fault-tolerant execution with automatic retries
        - 🔒 Thread-safe state management with versioning
        - 📨 Message bus for async decoupling
        - ✅ JSON schema validation
        - 🎤 Requirement clarification engine
        - 🤖 HuggingFace model integration
        
        **Built-in Agents:**
        - Requirements Analyst
        - Architecture Designer
        - Security Validator
        - Performance Analyzer
        - Documentation Generator
        
        **Technology Stack:**
        - Python 3.10+
        - Streamlit (UI)
        - jsonschema (validation)
        - HuggingFace Hub (models)
        - pytest (testing)
        
        **Repository:**
        https://github.com/your-org/agentic-framework
        
        **Documentation:**
        See README.md for detailed API reference and usage examples.
        """)
        
        st.divider()
        
        st.subheader("System Info")
        st.info(f"""
        - **Supervisor Workers:** {st.session_state.supervisor.max_workers}
        - **Registered Agents:** {len(st.session_state.agents_registry)}
        - **State Version:** {st.session_state.supervisor.state.snapshot()[0]}
        - **Clarification Max Rounds:** 5
        """)


if __name__ == "__main__":
    main()
