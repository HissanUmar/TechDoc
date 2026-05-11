# Project Brief Builder

A small Streamlit app that turns a single project prompt into a concise implementation brief.

## What it does

- Collects one user prompt
- Extracts a short requirement list with simple local heuristics
- Suggests assumptions and a lightweight database schema
- Produces a downloadable Markdown and JSON artifact

## Run it

```bash
streamlit run src/agentic_framework/streamlit_app.py
```

## Project Layout

- `src/agentic_framework/streamlit_app.py` - standalone Streamlit UI and document generator
- `src/agentic_framework/cli.py` - lightweight CLI entry point
- `tests/test_cli.py` - basic scaffold test

## Notes

The earlier agentic orchestration layer, message bus, and agent modules have been removed. The app now runs as a deterministic, local workflow.
