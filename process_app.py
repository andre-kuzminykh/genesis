"""Process Automation Designer — Streamlit Application.

Run with: streamlit run process_app.py
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import streamlit as st

from src.process_analyzer import config
from src.process_analyzer.schemas.models import (
    AutomationPoint,
    HumanRoleLevel,
    SessionState,
)
from src.process_analyzer.services.asis_analysis import generate_asis
from src.process_analyzer.services.automation_diagnosis import diagnose_automation
from src.process_analyzer.services.html_report import build_html_report
from src.process_analyzer.services.human_role import generate_human_role
from src.process_analyzer.services.tobe_design import generate_tobe
from src.process_analyzer.services.transcription import transcribe_audio

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_async(coro):
    """Run an async coroutine from sync Streamlit context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _init_session():
    defaults = {
        "state": SessionState.INPUT,
        "process_title": "",
        "raw_text": "",
        "transcript": None,
        "normalized_text": "",
        "asis": None,
        "automation_points": [],
        "selected_point_ids": [],
        "tobe": None,
        "human_role": None,
        "html_report": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _reset_session():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    _init_session()


def _render_mermaid(mermaid_code: str):
    """Render a Mermaid diagram using an HTML component."""
    html = f"""
    <div class="mermaid" style="overflow-x:auto;">
    {mermaid_code}
    </div>
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
    <script>mermaid.initialize({{startOnLoad:true, theme:'default'}});</script>
    """
    st.components.v1.html(html, height=500, scrolling=True)


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Process Automation Designer",
    page_icon="⚙️",
    layout="wide",
)
_init_session()

# ---------------------------------------------------------------------------
# Sidebar navigation
# ---------------------------------------------------------------------------

st.sidebar.title("Process Automation Designer")

current = st.session_state["state"]

# Determine which screens are available based on state
screens = ["Input"]
if current.value in (
    SessionState.ASIS_GENERATED.value,
    SessionState.AUTOMATION_DIAGNOSED.value,
    SessionState.TOBE_GENERATED.value,
    SessionState.HTML_READY.value,
):
    screens.append("AS-IS")
if current.value in (
    SessionState.AUTOMATION_DIAGNOSED.value,
    SessionState.TOBE_GENERATED.value,
    SessionState.HTML_READY.value,
):
    screens.append("Automation Points")
if current.value in (
    SessionState.TOBE_GENERATED.value,
    SessionState.HTML_READY.value,
):
    screens.append("TO-BE & New Role")
if current.value == SessionState.HTML_READY.value:
    screens.append("HTML Report")

page = st.sidebar.radio("Navigation", screens, index=len(screens) - 1)

st.sidebar.divider()
if st.sidebar.button("New Process", use_container_width=True):
    _reset_session()
    st.rerun()

# Show state
state_labels = {
    SessionState.INPUT: "Awaiting input",
    SessionState.TRANSCRIBED: "Transcribed",
    SessionState.ASIS_GENERATED: "AS-IS ready",
    SessionState.AUTOMATION_DIAGNOSED: "Automation diagnosed",
    SessionState.TOBE_GENERATED: "TO-BE ready",
    SessionState.HTML_READY: "Report ready",
}
st.sidebar.caption(f"Status: {state_labels.get(current, current.value)}")

# ---------------------------------------------------------------------------
# Screen: Input
# ---------------------------------------------------------------------------

if page == "Input":
    st.header("Process Input")

    st.session_state["process_title"] = st.text_input(
        "Process title",
        value=st.session_state["process_title"],
        placeholder="e.g. Invoice Approval Process",
    )

    input_mode = st.radio("Input type", ["Text", "Audio"], horizontal=True)

    if input_mode == "Text":
        st.session_state["raw_text"] = st.text_area(
            "Paste interview transcript or process description",
            value=st.session_state["raw_text"],
            height=300,
            max_chars=config.MAX_TEXT_LENGTH,
            placeholder="Describe the current process or paste an interview transcript...",
        )

        if st.button("Analyze Process", type="primary", use_container_width=True):
            text = st.session_state["raw_text"].strip()
            title = st.session_state["process_title"].strip() or "Untitled Process"

            if not text:
                st.error("Please enter process text.")
            elif not config.LLM_API_KEY:
                st.error("LLM API key not configured. Set PA_LLM_API_KEY in .env")
            else:
                st.session_state["normalized_text"] = text
                with st.status("Analyzing process...", expanded=True) as status:
                    try:
                        st.write("Generating AS-IS model...")
                        asis = run_async(generate_asis(title, text))
                        st.session_state["asis"] = asis
                        st.session_state["state"] = SessionState.ASIS_GENERATED

                        st.write("Identifying automation opportunities...")
                        points = run_async(diagnose_automation(title, asis))
                        st.session_state["automation_points"] = points
                        st.session_state["selected_point_ids"] = [
                            p.id for p in points if p.default_selected
                        ]
                        st.session_state["state"] = SessionState.AUTOMATION_DIAGNOSED
                        status.update(label="Analysis complete!", state="complete")
                    except Exception as e:
                        status.update(label="Analysis failed", state="error")
                        st.error(f"Error: {e}")

                if st.session_state["state"] == SessionState.AUTOMATION_DIAGNOSED:
                    st.rerun()

    else:  # Audio
        uploaded = st.file_uploader(
            "Upload audio file",
            type=["mp3", "wav", "m4a", "ogg"],
            help=f"Max {config.MAX_AUDIO_SIZE_MB} MB",
        )
        language_hint = st.text_input(
            "Language hint (optional)",
            placeholder="e.g. ru, en",
        )

        if uploaded and st.button("Analyze Process", type="primary", use_container_width=True):
            title = st.session_state["process_title"].strip() or "Untitled Process"

            if not config.LLM_API_KEY:
                st.error("LLM API key not configured. Set PA_LLM_API_KEY in .env")
            elif uploaded.size > config.MAX_AUDIO_SIZE_MB * 1024 * 1024:
                st.error(f"File too large. Maximum: {config.MAX_AUDIO_SIZE_MB} MB")
            else:
                suffix = Path(uploaded.name).suffix
                with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                    tmp.write(uploaded.read())
                    tmp_path = Path(tmp.name)

                with st.status("Processing audio...", expanded=True) as status:
                    try:
                        st.write("Transcribing audio...")
                        transcript = run_async(
                            transcribe_audio(tmp_path, language_hint or None)
                        )
                        st.session_state["transcript"] = transcript
                        st.session_state["normalized_text"] = transcript
                        st.session_state["state"] = SessionState.TRANSCRIBED

                        st.write("Generating AS-IS model...")
                        asis = run_async(generate_asis(title, transcript))
                        st.session_state["asis"] = asis
                        st.session_state["state"] = SessionState.ASIS_GENERATED

                        st.write("Identifying automation opportunities...")
                        points = run_async(diagnose_automation(title, asis))
                        st.session_state["automation_points"] = points
                        st.session_state["selected_point_ids"] = [
                            p.id for p in points if p.default_selected
                        ]
                        st.session_state["state"] = SessionState.AUTOMATION_DIAGNOSED
                        status.update(label="Analysis complete!", state="complete")
                    except Exception as e:
                        status.update(label="Processing failed", state="error")
                        st.error(f"Error: {e}")
                        if st.session_state["state"] == SessionState.INPUT:
                            st.info("Try pasting text directly instead.")
                    finally:
                        tmp_path.unlink(missing_ok=True)

                if st.session_state["state"] == SessionState.AUTOMATION_DIAGNOSED:
                    st.rerun()

    # Show transcript if available
    if st.session_state.get("transcript"):
        with st.expander("Transcript", expanded=False):
            st.text_area(
                "Transcript text",
                value=st.session_state["transcript"],
                height=200,
                disabled=True,
                label_visibility="collapsed",
            )

# ---------------------------------------------------------------------------
# Screen: AS-IS
# ---------------------------------------------------------------------------

elif page == "AS-IS":
    st.header("AS-IS Process")
    asis = st.session_state["asis"]
    if not asis:
        st.warning("No AS-IS data. Go back to Input.")
    else:
        st.subheader("Summary")
        st.write(asis.summary)

        if asis.mermaid_code:
            st.subheader("Process Diagram")
            _render_mermaid(asis.mermaid_code)
            with st.expander("Mermaid source"):
                st.code(asis.mermaid_code, language="mermaid")

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Roles")
            for role in asis.roles:
                with st.expander(role.name):
                    st.write(role.description)
                    if role.responsibilities:
                        st.write("**Responsibilities:**")
                        for r in role.responsibilities:
                            st.write(f"- {r}")

        with col2:
            st.subheader("Artifacts & Systems")
            if asis.artifacts:
                st.write("**Artifacts:**")
                for a in asis.artifacts:
                    st.write(f"- {a}")
            if asis.systems:
                st.write("**Systems:**")
                for s in asis.systems:
                    st.write(f"- {s}")

        st.subheader("Process Steps")
        for i, step in enumerate(asis.steps, 1):
            icon = "🔀" if step.is_decision else f"**{i}.**"
            with st.expander(f"{icon} {step.name} ({step.actor})"):
                st.write(step.description)
                if step.systems:
                    st.write(f"**Systems:** {', '.join(step.systems)}")
                if step.inputs:
                    st.write(f"**Inputs:** {', '.join(step.inputs)}")
                if step.outputs:
                    st.write(f"**Outputs:** {', '.join(step.outputs)}")
                if step.pain_points:
                    st.write("**Pain points:**")
                    for pp in step.pain_points:
                        st.warning(pp)

        if asis.issues:
            st.subheader("Issues & Bottlenecks")
            for issue in asis.issues:
                st.error(issue)

# ---------------------------------------------------------------------------
# Screen: Automation Points
# ---------------------------------------------------------------------------

elif page == "Automation Points":
    st.header("Automation Opportunities")

    points: list[AutomationPoint] = st.session_state["automation_points"]
    if not points:
        st.warning("No automation points diagnosed.")
    else:
        st.write("Select the automation points to include in the TO-BE design:")

        selected_ids = set(st.session_state["selected_point_ids"])

        # Render each point as a card with checkbox
        for point in points:
            maturity_colors = {
                "quick_win": "🟢",
                "short_term": "🟡",
                "strategic": "🟣",
            }
            type_labels = {
                "deterministic": "Deterministic (RPA/rules)",
                "intelligent": "Intelligent (AI/ML)",
                "hybrid": "Hybrid",
            }
            icon = maturity_colors.get(point.maturity.value, "⚪")

            col_check, col_info = st.columns([0.05, 0.95])
            with col_check:
                checked = st.checkbox(
                    point.id,
                    value=point.id in selected_ids,
                    key=f"ap_{point.id}",
                    label_visibility="collapsed",
                )
                if checked and point.id not in selected_ids:
                    selected_ids.add(point.id)
                elif not checked and point.id in selected_ids:
                    selected_ids.discard(point.id)

            with col_info:
                st.markdown(
                    f"**{icon} {point.stage}** — {point.manual_action}"
                )
                st.caption(
                    f"Type: {type_labels.get(point.automation_type.value, point.automation_type.value)} | "
                    f"Maturity: {point.maturity.value.replace('_', ' ')} | "
                    f"Effect: {point.effect}"
                )
                st.caption(f"Potential: {point.potential}")
            st.divider()

        st.session_state["selected_point_ids"] = list(selected_ids)

        st.write(f"**{len(selected_ids)}** of **{len(points)}** points selected.")

        if st.button("Generate TO-BE", type="primary", use_container_width=True):
            if not selected_ids:
                st.warning("Select at least one automation point.")
            else:
                title = st.session_state["process_title"] or "Untitled Process"
                asis = st.session_state["asis"]
                sel_points = [p for p in points if p.id in selected_ids]

                with st.status("Generating TO-BE...", expanded=True) as status:
                    try:
                        st.write("Building TO-BE process model...")
                        tobe = run_async(generate_tobe(title, asis, sel_points))
                        st.session_state["tobe"] = tobe
                        st.session_state["state"] = SessionState.TOBE_GENERATED

                        st.write("Designing new human role...")
                        human_role = run_async(
                            generate_human_role(title, asis, tobe, sel_points)
                        )
                        st.session_state["human_role"] = human_role
                        status.update(label="TO-BE generated!", state="complete")
                    except Exception as e:
                        status.update(label="Generation failed", state="error")
                        st.error(f"Error: {e}")

                if st.session_state["state"] == SessionState.TOBE_GENERATED:
                    st.rerun()

# ---------------------------------------------------------------------------
# Screen: TO-BE & New Role
# ---------------------------------------------------------------------------

elif page == "TO-BE & New Role":
    st.header("TO-BE Process")
    tobe = st.session_state["tobe"]
    human_role = st.session_state["human_role"]

    if not tobe:
        st.warning("No TO-BE data. Generate it from Automation Points screen.")
    else:
        st.subheader("Summary")
        st.write(tobe.summary)

        if tobe.mermaid_code:
            st.subheader("Process Diagram")
            _render_mermaid(tobe.mermaid_code)
            with st.expander("Mermaid source"):
                st.code(tobe.mermaid_code, language="mermaid")

        st.subheader("Process Steps")
        for i, step in enumerate(tobe.steps, 1):
            is_automated = step.actor.lower() in (
                "system", "ai", "rpa bot", "automation",
            ) or "automat" in step.actor.lower()
            icon = "🤖" if is_automated else "👤"
            with st.expander(f"{icon} {step.name} ({step.actor})"):
                st.write(step.description)
                if step.systems:
                    st.write(f"**Systems:** {', '.join(step.systems)}")

        if tobe.changes_rationale:
            st.subheader("Changes Rationale")
            for r in tobe.changes_rationale:
                st.info(r)

        if tobe.assumptions:
            with st.expander("Assumptions"):
                for a in tobe.assumptions:
                    st.write(f"- {a}")

        # New Human Role
        st.divider()
        st.header("New Human Role")

        if human_role:
            level_descriptions = {
                HumanRoleLevel.H0_OPERATOR: "Operator — monitors automated processes, handles simple exceptions",
                HumanRoleLevel.H1_SUPERVISOR: "Supervisor — reviews AI outputs, manages escalations",
                HumanRoleLevel.H2_MANAGER: "Manager — makes strategic decisions, drives improvement",
                HumanRoleLevel.H3_EXPERT: "Expert — designs rules, trains AI, handles complex cases",
            }

            # Role level selector
            current_level = human_role.level
            level_options = list(HumanRoleLevel)
            level_index = level_options.index(current_level)

            selected_level = st.selectbox(
                "Role level",
                options=level_options,
                index=level_index,
                format_func=lambda x: f"{x.value} — {level_descriptions[x].split(' — ')[1]}",
            )

            if selected_level != current_level:
                st.info(
                    f"Role level changed to {selected_level.value}. "
                    "Regenerate TO-BE to update the role description for this level."
                )
                human_role.level = selected_level

            col_role, col_kpi = st.columns([1, 1])
            with col_role:
                st.subheader(f"{human_role.level.value} — {human_role.role_name}")
                st.write(f"**Mission:** {human_role.mission}")

                st.write("**Responsibilities:**")
                for r in human_role.responsibilities:
                    st.write(f"- {r}")

                if human_role.boundaries:
                    st.write(f"**Boundaries:** {human_role.boundaries}")

            with col_kpi:
                if human_role.kpis:
                    st.subheader("KPIs")
                    for kpi in human_role.kpis:
                        st.metric(label=kpi, value="—")

                if human_role.tools:
                    st.subheader("Tools & Systems")
                    for t in human_role.tools:
                        st.write(f"- {t}")

            # Generate HTML report button
            st.divider()
            if st.button("Generate HTML Report", type="primary", use_container_width=True):
                try:
                    asis = st.session_state["asis"]
                    automation_points = st.session_state["automation_points"]
                    selected_ids = st.session_state["selected_point_ids"]
                    title = st.session_state["process_title"] or "Untitled Process"
                    transcript = st.session_state.get("transcript") or st.session_state.get("normalized_text")

                    html = build_html_report(
                        title=title,
                        transcript=transcript,
                        asis=asis,
                        automation_points=automation_points,
                        selected_ids=selected_ids,
                        tobe=tobe,
                        human_role=human_role,
                    )
                    st.session_state["html_report"] = html
                    st.session_state["state"] = SessionState.HTML_READY
                    st.rerun()
                except Exception as e:
                    st.error(f"Error generating report: {e}")

# ---------------------------------------------------------------------------
# Screen: HTML Report
# ---------------------------------------------------------------------------

elif page == "HTML Report":
    st.header("HTML Report")

    html = st.session_state.get("html_report", "")
    if not html:
        st.warning("No report generated yet.")
    else:
        st.subheader("Preview")
        st.components.v1.html(html, height=800, scrolling=True)

        title = st.session_state.get("process_title", "process")
        safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in title)
        filename = f"{safe_title}_report.html"

        st.download_button(
            label="Download HTML Report",
            data=html,
            file_name=filename,
            mime="text/html",
            type="primary",
            use_container_width=True,
        )
