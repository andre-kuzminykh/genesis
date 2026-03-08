"""Process Automation Designer — Streamlit Application.

Run with: streamlit run process_app.py
"""

from __future__ import annotations

import asyncio
import json
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
    if "processes" not in st.session_state:
        st.session_state["processes"] = {}  # title -> process data dict
    if "active_process" not in st.session_state:
        st.session_state["active_process"] = None
    if "creating_new" not in st.session_state:
        st.session_state["creating_new"] = False


def _new_process_data() -> dict:
    return {
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


def _get_active_data() -> dict | None:
    title = st.session_state.get("active_process")
    if title and title in st.session_state["processes"]:
        return st.session_state["processes"][title]
    return None


def _render_mermaid(mermaid_code: str, height: int = 500):
    """Render a Mermaid diagram with white background for readability."""
    html = f"""
    <div style="background:#fff; padding:16px; border-radius:8px;">
      <div class="mermaid" style="overflow-x:auto;">
      {mermaid_code}
      </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
    <script>mermaid.initialize({{startOnLoad:true, theme:'default'}});</script>
    """
    st.components.v1.html(html, height=height, scrolling=True)


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
# Sidebar — process list
# ---------------------------------------------------------------------------

st.sidebar.title("Process Automation Designer")

processes = st.session_state["processes"]
active = st.session_state["active_process"]

st.sidebar.subheader("Processes")

if st.sidebar.button("+ New Process", use_container_width=True):
    st.session_state["creating_new"] = True
    st.session_state["active_process"] = None
    st.rerun()

# List existing processes
for title in processes:
    is_active = (title == active)
    label = f"{'> ' if is_active else ''}{title}"
    state = processes[title]["state"]
    state_labels = {
        SessionState.INPUT: "Input",
        SessionState.TRANSCRIBED: "Transcribed",
        SessionState.ASIS_GENERATED: "AS-IS",
        SessionState.AUTOMATION_DIAGNOSED: "Automation",
        SessionState.TOBE_GENERATED: "TO-BE",
        SessionState.HTML_READY: "Done",
    }
    badge = state_labels.get(state, state.value)
    if st.sidebar.button(
        f"{title}  [{badge}]",
        key=f"proc_{title}",
        use_container_width=True,
        type="primary" if is_active else "secondary",
    ):
        st.session_state["active_process"] = title
        st.session_state["creating_new"] = False
        st.rerun()

st.sidebar.divider()

# ---------------------------------------------------------------------------
# No active process — create new or welcome
# ---------------------------------------------------------------------------

data = _get_active_data()

if st.session_state.get("creating_new") and data is None:
    st.header("Create New Process")
    new_title = st.text_input(
        "Process name",
        placeholder="e.g. Invoice Approval Process",
        key="new_proc_title",
    )
    if st.button("Create", type="primary"):
        name = new_title.strip()
        if not name:
            st.error("Enter a process name.")
        elif name in processes:
            st.error("Process with this name already exists.")
        else:
            proc_data = _new_process_data()
            proc_data["process_title"] = name
            st.session_state["processes"][name] = proc_data
            st.session_state["active_process"] = name
            st.session_state["creating_new"] = False
            st.rerun()

elif data is None:
    st.header("Process Automation Designer")
    st.info("Create a new process using the sidebar or select an existing one.")

# ---------------------------------------------------------------------------
# Active process — show screens
# ---------------------------------------------------------------------------

if data is not None:
    current = data["state"]
    title = data["process_title"]

    # Sub-navigation for active process
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

    st.sidebar.caption(f"Current: {title}")
    page = st.sidebar.radio("Navigation", screens, index=len(screens) - 1, key="page_nav")

    # -----------------------------------------------------------------------
    # Screen: Input
    # -----------------------------------------------------------------------
    if page == "Input":
        st.header(f"Input — {title}")

        input_mode = st.radio("Input type", ["Text", "Audio Upload", "Record Audio"], horizontal=True)

        if input_mode == "Text":
            data["raw_text"] = st.text_area(
                "Paste interview transcript or process description",
                value=data["raw_text"],
                height=300,
                max_chars=config.MAX_TEXT_LENGTH,
                placeholder="Describe the current process or paste an interview transcript...",
            )

            if st.button("Analyze Process", type="primary", use_container_width=True):
                text = data["raw_text"].strip()
                if not text:
                    st.error("Please enter process text.")
                elif not config.LLM_API_KEY:
                    st.error("LLM API key not configured. Set PA_LLM_API_KEY in .env")
                else:
                    data["normalized_text"] = text
                    with st.status("Analyzing process...", expanded=True) as status:
                        try:
                            st.write("Generating AS-IS model...")
                            asis = run_async(generate_asis(title, text))
                            data["asis"] = asis
                            data["state"] = SessionState.ASIS_GENERATED

                            st.write("Identifying automation opportunities...")
                            points = run_async(diagnose_automation(title, asis))
                            data["automation_points"] = points
                            data["selected_point_ids"] = [
                                p.id for p in points if p.default_selected
                            ]
                            data["state"] = SessionState.AUTOMATION_DIAGNOSED
                            status.update(label="Analysis complete!", state="complete")
                        except Exception as e:
                            status.update(label="Analysis failed", state="error")
                            st.error(f"Error: {e}")

                    if data["state"] == SessionState.AUTOMATION_DIAGNOSED:
                        st.rerun()

        elif input_mode == "Audio Upload":
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
                            data["transcript"] = transcript
                            data["normalized_text"] = transcript
                            data["state"] = SessionState.TRANSCRIBED

                            st.write("Generating AS-IS model...")
                            asis = run_async(generate_asis(title, transcript))
                            data["asis"] = asis
                            data["state"] = SessionState.ASIS_GENERATED

                            st.write("Identifying automation opportunities...")
                            points = run_async(diagnose_automation(title, asis))
                            data["automation_points"] = points
                            data["selected_point_ids"] = [
                                p.id for p in points if p.default_selected
                            ]
                            data["state"] = SessionState.AUTOMATION_DIAGNOSED
                            status.update(label="Analysis complete!", state="complete")
                        except Exception as e:
                            status.update(label="Processing failed", state="error")
                            st.error(f"Error: {e}")
                            if data["state"] == SessionState.INPUT:
                                st.info("Try pasting text directly instead.")
                        finally:
                            tmp_path.unlink(missing_ok=True)

                    if data["state"] == SessionState.AUTOMATION_DIAGNOSED:
                        st.rerun()

        else:  # Record Audio
            st.info("Use the microphone button below to record audio directly in the browser.")
            audio_bytes = st.audio_input("Record audio", key="audio_recorder")
            language_hint = st.text_input(
                "Language hint (optional)",
                placeholder="e.g. ru, en",
                key="rec_lang",
            )

            if audio_bytes and st.button("Analyze Recorded Audio", type="primary", use_container_width=True):
                if not config.LLM_API_KEY:
                    st.error("LLM API key not configured. Set PA_LLM_API_KEY in .env")
                else:
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                        tmp.write(audio_bytes.read())
                        tmp_path = Path(tmp.name)

                    with st.status("Processing recorded audio...", expanded=True) as status:
                        try:
                            st.write("Transcribing audio...")
                            transcript = run_async(
                                transcribe_audio(tmp_path, language_hint or None)
                            )
                            data["transcript"] = transcript
                            data["normalized_text"] = transcript
                            data["state"] = SessionState.TRANSCRIBED

                            st.write("Generating AS-IS model...")
                            asis = run_async(generate_asis(title, transcript))
                            data["asis"] = asis
                            data["state"] = SessionState.ASIS_GENERATED

                            st.write("Identifying automation opportunities...")
                            points = run_async(diagnose_automation(title, asis))
                            data["automation_points"] = points
                            data["selected_point_ids"] = [
                                p.id for p in points if p.default_selected
                            ]
                            data["state"] = SessionState.AUTOMATION_DIAGNOSED
                            status.update(label="Analysis complete!", state="complete")
                        except Exception as e:
                            status.update(label="Processing failed", state="error")
                            st.error(f"Error: {e}")
                        finally:
                            tmp_path.unlink(missing_ok=True)

                    if data["state"] == SessionState.AUTOMATION_DIAGNOSED:
                        st.rerun()

        # Show transcript if available
        if data.get("transcript"):
            with st.expander("Transcript", expanded=False):
                st.text_area(
                    "Transcript text",
                    value=data["transcript"],
                    height=200,
                    disabled=True,
                    label_visibility="collapsed",
                )

    # -----------------------------------------------------------------------
    # Screen: AS-IS
    # -----------------------------------------------------------------------
    elif page == "AS-IS":
        st.header(f"AS-IS — {title}")
        asis = data["asis"]
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
                icon = "Decision" if step.is_decision else f"**{i}.**"
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

    # -----------------------------------------------------------------------
    # Screen: Automation Points
    # -----------------------------------------------------------------------
    elif page == "Automation Points":
        st.header(f"Automation Opportunities — {title}")

        points: list[AutomationPoint] = data["automation_points"]
        if not points:
            st.warning("No automation points diagnosed.")
        else:
            st.write("Select the automation points to include in the TO-BE design:")

            selected_ids = set(data["selected_point_ids"])

            for point in points:
                maturity_colors = {
                    "quick_win": "green",
                    "short_term": "orange",
                    "strategic": "violet",
                }
                type_labels = {
                    "deterministic": "Deterministic (RPA/rules)",
                    "intelligent": "Intelligent (AI/ML)",
                    "hybrid": "Hybrid",
                }

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
                    maturity_color = maturity_colors.get(point.maturity.value, "gray")
                    st.markdown(f"**{point.stage}** — {point.manual_action}")
                    st.caption(
                        f"Type: {type_labels.get(point.automation_type.value, point.automation_type.value)} | "
                        f"Maturity: :{maturity_color}[{point.maturity.value.replace('_', ' ')}] | "
                        f"Effect: {point.effect}"
                    )

                    # Expanded details per PRD
                    with st.expander("Details"):
                        st.write(f"**Automation Potential:** {point.potential}")
                        if point.human_role_description:
                            st.write(f"**Human Role:** {point.human_role_description}")
                        if point.system_action:
                            st.write(f"**System Action:** {point.system_action}")
                        if point.human_action:
                            st.write(f"**Human Action:** {point.human_action}")
                        if point.interaction_description:
                            st.write(f"**Interaction:** {point.interaction_description}")

                st.divider()

            data["selected_point_ids"] = list(selected_ids)

            st.write(f"**{len(selected_ids)}** of **{len(points)}** points selected.")

            if st.button("Generate TO-BE", type="primary", use_container_width=True):
                if not selected_ids:
                    st.warning("Select at least one automation point.")
                else:
                    asis = data["asis"]
                    sel_points = [p for p in points if p.id in selected_ids]

                    with st.status("Generating TO-BE...", expanded=True) as status:
                        try:
                            st.write("Building TO-BE process model...")
                            tobe = run_async(generate_tobe(title, asis, sel_points))
                            data["tobe"] = tobe
                            data["state"] = SessionState.TOBE_GENERATED

                            st.write("Designing new human role...")
                            human_role = run_async(
                                generate_human_role(title, asis, tobe, sel_points)
                            )
                            data["human_role"] = human_role
                            status.update(label="TO-BE generated!", state="complete")
                        except Exception as e:
                            status.update(label="Generation failed", state="error")
                            st.error(f"Error: {e}")

                    if data["state"] == SessionState.TOBE_GENERATED:
                        st.rerun()

    # -----------------------------------------------------------------------
    # Screen: TO-BE & New Role
    # -----------------------------------------------------------------------
    elif page == "TO-BE & New Role":
        st.header(f"TO-BE — {title}")
        tobe = data["tobe"]
        human_role = data["human_role"]

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
                icon = "Robot" if is_automated else "Person"
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
                if st.button("Done — Generate Final Report", type="primary", use_container_width=True):
                    try:
                        asis = data["asis"]
                        automation_points = data["automation_points"]
                        selected_ids = data["selected_point_ids"]
                        transcript = data.get("transcript") or data.get("normalized_text")

                        html = build_html_report(
                            title=title,
                            transcript=transcript,
                            asis=asis,
                            automation_points=automation_points,
                            selected_ids=selected_ids,
                            tobe=tobe,
                            human_role=human_role,
                        )
                        data["html_report"] = html
                        data["state"] = SessionState.HTML_READY
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error generating report: {e}")

    # -----------------------------------------------------------------------
    # Screen: HTML Report
    # -----------------------------------------------------------------------
    elif page == "HTML Report":
        st.header(f"Final Report — {title}")

        html = data.get("html_report", "")
        if not html:
            st.warning("No report generated yet.")
        else:
            st.subheader("Preview")
            st.components.v1.html(html, height=800, scrolling=True)

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
