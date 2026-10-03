from __future__ import annotations

from pathlib import Path

import streamlit as st


BASE_DIR = Path(__file__).resolve().parents[2]

st.title("Settings")
st.caption("CashFlowAI system configuration")

database_path = (
    BASE_DIR
    / "data"
    / "cashflowai.db"
)

chroma_path = (
    BASE_DIR
    / "chroma_db"
)

env_path = (
    BASE_DIR
    / ".env"
)

c1, c2, c3 = st.columns(3)

with c1:
    st.metric(
        "Database",
        "Ready"
        if database_path.exists()
        else "Missing",
    )

with c2:
    st.metric(
        "Vector Store",
        "Ready"
        if chroma_path.exists()
        else "Missing",
    )

with c3:
    st.metric(
        "Environment",
        "Configured"
        if env_path.exists()
        else "Missing",
    )

st.divider()

st.subheader("AI Stack")

st.write("RAG: ChromaDB")
st.write("Embeddings: sentence-transformers")
st.write("Workflow: LangGraph")
st.write("Human approval: Enabled")

st.divider()

st.warning(
    "Keep API keys in .env and never commit real customer financial data to public GitHub."
)
