from pathlib import Path

import streamlit as st


BASE_DIR = Path(__file__).resolve().parents[2]

POLICY_DIR = BASE_DIR / "data" / "policies"
POLICY_DIR.mkdir(parents=True, exist_ok=True)


st.title("Upload Center")

st.caption(
    "Upload your company's collection policy for AI recommendations."
)

st.divider()

st.subheader("Company Collection Policy")

st.write(
    "Upload a PDF containing your company's collection rules, "
    "payment terms, escalation rules, or credit policy."
)

policy_file = st.file_uploader(
    "Upload Company Policy PDF",
    type=["pdf"],
)

if policy_file is not None:

    st.write(
        f"Selected: **{policy_file.name}**"
    )

    if st.button(
        "Save Company Policy",
        type="primary",
        use_container_width=True,
    ):

        policy_path = POLICY_DIR / policy_file.name

        policy_path.write_bytes(
            policy_file.getbuffer()
        )

        st.success(
            "Company policy uploaded successfully."
        )

        st.info(
            "Policy document is ready for the RAG knowledge base."
        )


st.divider()

st.subheader("Current Policy")

policy_files = list(POLICY_DIR.glob("*.pdf"))

if policy_files:

    for policy in policy_files:
        st.write(f"📄 {policy.name}")

else:

    st.info(
        "No company policy uploaded yet."
    )