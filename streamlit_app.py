"""Streamlit Web UI for Idea Validation Pipeline."""

import time

import httpx
import streamlit as st

API_BASE = "http://localhost:8000"

st.set_page_config(page_title="Idea Validation Pipeline", layout="wide")
st.title("Idea Validation Pipeline")

# --- Sidebar navigation ---
page = st.sidebar.radio(
    "Navigation",
    ["New Validation", "Check Status", "View Report", "Rerun Validation"],
)

# --- New Validation ---
if page == "New Validation":
    st.header("Submit a New Idea for Validation")

    with st.form("idea_form"):
        title = st.text_input("Idea Title *", max_chars=500)
        target_user = st.text_area("Target User *", max_chars=2000)
        problem_statement = st.text_area("Problem Statement *", max_chars=5000)
        proposed_solution = st.text_area("Proposed Solution *", max_chars=5000)
        assumptions = st.text_area("Key Assumptions (optional)", max_chars=3000)
        market_context = st.text_area("Market / Context Notes (optional)", max_chars=3000)
        submitted = st.form_submit_button("Submit for Validation")

    if submitted:
        if not title or not target_user or not problem_statement or not proposed_solution:
            st.error("Please fill in all required fields (marked with *).")
        else:
            payload = {
                "idea": {
                    "title": title,
                    "target_user": target_user,
                    "problem_statement": problem_statement,
                    "proposed_solution": proposed_solution,
                    "assumptions": assumptions or None,
                    "market_context": market_context or None,
                }
            }
            try:
                resp = httpx.post(f"{API_BASE}/validation-runs", json=payload, timeout=10)
                if resp.status_code == 201:
                    data = resp.json()
                    st.success(f"Validation run created! Run ID: `{data['id']}`")
                    st.json(data)
                else:
                    st.error(f"Error {resp.status_code}: {resp.text}")
            except httpx.ConnectError:
                st.error("Cannot connect to API. Make sure the backend is running.")

# --- Check Status ---
elif page == "Check Status":
    st.header("Check Validation Run Status")
    run_id = st.text_input("Enter Run ID")

    if run_id and st.button("Check Status"):
        try:
            resp = httpx.get(f"{API_BASE}/validation-runs/{run_id}", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                st.metric("State", data["state"])
                st.json(data)
            else:
                st.error(f"Error {resp.status_code}: {resp.text}")
        except httpx.ConnectError:
            st.error("Cannot connect to API.")

    if run_id and st.button("View Event Log"):
        try:
            resp = httpx.get(f"{API_BASE}/validation-runs/{run_id}/events", timeout=10)
            if resp.status_code == 200:
                events = resp.json()
                for ev in events:
                    st.write(f"**{ev['from_state']}** → **{ev['to_state']}** — {ev.get('message', '')}")
            else:
                st.error(f"Error {resp.status_code}: {resp.text}")
        except httpx.ConnectError:
            st.error("Cannot connect to API.")

# --- View Report ---
elif page == "View Report":
    st.header("Validation Report")
    run_id = st.text_input("Enter Run ID")

    if run_id and st.button("Load Report"):
        try:
            resp = httpx.get(f"{API_BASE}/validation-runs/{run_id}/report", timeout=10)
            if resp.status_code == 200:
                report = resp.json()

                # Idea summary
                st.subheader("Idea Summary")
                idea = report["idea"]
                st.write(f"**Title:** {idea['title']}")
                st.write(f"**Target User:** {idea['target_user']}")
                st.write(f"**Problem:** {idea['problem_statement']}")
                st.write(f"**Solution:** {idea['proposed_solution']}")

                # Scorecard
                if report["score_card"]:
                    sc = report["score_card"]
                    st.subheader("Scorecard")

                    col1, col2, col3 = st.columns(3)
                    col1.metric("Overall Score", f"{sc['overall_score']:.2f}")
                    col2.metric("Confidence", sc["overall_confidence"])
                    col3.metric("Recommendation", sc["recommendation"].upper())

                    st.subheader("Dimension Scores")
                    for ds in sc["dimension_scores"]:
                        with st.expander(
                            f"{ds['dimension']} — Score: {ds['score']:.2f} ({ds['confidence']})"
                        ):
                            st.write(f"**Rationale:** {ds['rationale']}")
                            if ds.get("missing_evidence"):
                                st.warning(f"Missing: {ds['missing_evidence']}")

                    st.subheader("Recommendation")
                    st.info(sc["recommendation_rationale"])

                    if sc.get("next_steps"):
                        st.subheader("Next Steps")
                        st.markdown(sc["next_steps"])

                    if sc.get("follow_up_questions"):
                        st.subheader("Follow-up Questions")
                        st.warning(sc["follow_up_questions"])

                # Evidence
                if report["evidence"]:
                    st.subheader("Evidence")
                    for ev in report["evidence"]:
                        with st.expander(f"{ev['dimension']} ({ev['source']})"):
                            st.write(ev["content"])
                            st.caption(f"Confidence: {ev['confidence']}")

            elif resp.status_code == 409:
                st.warning(f"Report not ready yet: {resp.json().get('detail', '')}")
            else:
                st.error(f"Error {resp.status_code}: {resp.text}")
        except httpx.ConnectError:
            st.error("Cannot connect to API.")

# --- Rerun Validation ---
elif page == "Rerun Validation":
    st.header("Create a New Iteration")
    parent_run_id = st.text_input("Parent Run ID")
    reuse = st.checkbox("Reuse original idea (no changes)", value=True)

    if not reuse:
        with st.form("rerun_form"):
            title = st.text_input("Updated Title *", max_chars=500)
            target_user = st.text_area("Updated Target User *", max_chars=2000)
            problem_statement = st.text_area("Updated Problem Statement *", max_chars=5000)
            proposed_solution = st.text_area("Updated Proposed Solution *", max_chars=5000)
            assumptions = st.text_area("Updated Assumptions (optional)", max_chars=3000)
            market_context = st.text_area("Updated Market Context (optional)", max_chars=3000)
            submitted = st.form_submit_button("Submit Rerun")

        if submitted and parent_run_id:
            payload = {
                "idea_updates": {
                    "title": title,
                    "target_user": target_user,
                    "problem_statement": problem_statement,
                    "proposed_solution": proposed_solution,
                    "assumptions": assumptions or None,
                    "market_context": market_context or None,
                }
            }
            try:
                resp = httpx.post(
                    f"{API_BASE}/validation-runs/{parent_run_id}/rerun",
                    json=payload,
                    timeout=10,
                )
                if resp.status_code == 201:
                    data = resp.json()
                    st.success(f"Rerun created! New Run ID: `{data['id']}`")
                    st.json(data)
                else:
                    st.error(f"Error {resp.status_code}: {resp.text}")
            except httpx.ConnectError:
                st.error("Cannot connect to API.")
    else:
        if parent_run_id and st.button("Rerun with Original Idea"):
            try:
                resp = httpx.post(
                    f"{API_BASE}/validation-runs/{parent_run_id}/rerun",
                    json={},
                    timeout=10,
                )
                if resp.status_code == 201:
                    data = resp.json()
                    st.success(f"Rerun created! New Run ID: `{data['id']}`")
                    st.json(data)
                else:
                    st.error(f"Error {resp.status_code}: {resp.text}")
            except httpx.ConnectError:
                st.error("Cannot connect to API.")

    # Show history
    if parent_run_id and st.button("View Iteration History"):
        try:
            resp = httpx.get(
                f"{API_BASE}/validation-runs/{parent_run_id}/history", timeout=10
            )
            if resp.status_code == 200:
                history = resp.json()
                st.subheader("Iteration History")
                for run in history["runs"]:
                    st.write(
                        f"**Iteration {run['iteration_number']}** — "
                        f"ID: `{run['id']}` — State: {run['state']}"
                    )
            else:
                st.error(f"Error {resp.status_code}: {resp.text}")
        except httpx.ConnectError:
            st.error("Cannot connect to API.")
