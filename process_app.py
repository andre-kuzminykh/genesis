"""Process Automation Designer — Streamlit Application.

Minimalist step-by-step vertical layout, mobile-friendly.
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


def _render_mermaid(mermaid_code: str, height: int = 400):
    html = f"""
    <div style="background:#fff; padding:12px; border-radius:8px;">
      <div class="mermaid" style="overflow-x:auto;">{mermaid_code}</div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
    <script>mermaid.initialize({{startOnLoad:true, theme:'default'}});</script>
    """
    st.components.v1.html(html, height=height, scrolling=True)


def _video_placeholder():
    """Render a circular video placeholder."""
    st.markdown(
        """
        <div style="
            width:120px; height:120px;
            border-radius:50%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            margin: 0 auto 16px auto;
            display:flex; align-items:center; justify-content:center;
            color: white; font-size: 36px;
            box-shadow: 0 4px 15px rgba(102,126,234,0.4);
        ">&#9654;</div>
        """,
        unsafe_allow_html=True,
    )


def _step_header(number: int, title: str, subtitle: str):
    """Render step number badge + title + subtitle, centered."""
    st.markdown(
        f"""
        <div style="text-align:center; margin-bottom:12px;">
            <div style="
                display:inline-block;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color:white; border-radius:50%;
                width:32px; height:32px; line-height:32px;
                font-weight:700; font-size:14px;
                margin-bottom:8px;
            ">{number}</div>
            <h3 style="margin:0 0 4px 0;">{title}</h3>
            <p style="color:#888; margin:0; font-size:0.9rem;">{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Page config & custom CSS
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Process Automation Designer",
    page_icon="⚙️",
    layout="centered",
)

st.markdown(
    """
    <style>
    /* Mobile-friendly defaults */
    .block-container { max-width: 640px; padding: 1rem 1rem 4rem 1rem; }
    /* Compact expanders */
    .streamlit-expanderHeader { font-size: 0.95rem; }
    /* Step card */
    .step-card {
        background: var(--background-color);
        border: 1px solid rgba(128,128,128,0.15);
        border-radius: 12px;
        padding: 24px 16px;
        margin-bottom: 16px;
    }
    /* Hide default header padding */
    header[data-testid="stHeader"] { display: none; }
    </style>
    """,
    unsafe_allow_html=True,
)

_init_session()
state = st.session_state

# ---------------------------------------------------------------------------
# Title
# ---------------------------------------------------------------------------

st.markdown(
    """
    <div style="text-align:center; padding: 16px 0 24px 0;">
        <h1 style="margin:0; font-size:1.6rem;">⚙️ Process Automation Designer</h1>
        <p style="color:#888; margin:4px 0 0 0; font-size:0.9rem;">
            Analyze your process step by step
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# STEP 1 — Input
# ---------------------------------------------------------------------------

with st.container():
    _video_placeholder()
    _step_header(1, "Describe your process", "Upload audio or paste text of an interview")

    input_mode = st.radio(
        "How would you like to provide data?",
        ["Text", "Audio file", "Record"],
        horizontal=True,
        label_visibility="collapsed",
    )

    if input_mode == "Text":
        state["raw_text"] = st.text_area(
            "Process description",
            value=state["raw_text"],
            height=180,
            max_chars=config.MAX_TEXT_LENGTH,
            placeholder="Describe the current process or paste an interview transcript...",
            label_visibility="collapsed",
        )

    elif input_mode == "Audio file":
        uploaded = st.file_uploader(
            "Upload audio",
            type=["mp3", "wav", "m4a", "ogg"],
            help=f"Max {config.MAX_AUDIO_SIZE_MB} MB",
            label_visibility="collapsed",
        )
        if uploaded:
            state["_uploaded_audio"] = uploaded

    else:  # Record
        audio_bytes = st.audio_input("Record audio", label_visibility="collapsed")
        if audio_bytes:
            state["_recorded_audio"] = audio_bytes

    lang = st.text_input(
        "Language hint (optional)", placeholder="e.g. ru, en", label_visibility="collapsed",
    ) if input_mode != "Text" else None

    # --- Run button ---
    can_run = (
        (input_mode == "Text" and state["raw_text"].strip())
        or (input_mode == "Audio file" and state.get("_uploaded_audio"))
        or (input_mode == "Record" and state.get("_recorded_audio"))
    )

    if state["state"] == SessionState.INPUT:
        if st.button(
            "Analyze", type="primary", use_container_width=True, disabled=not can_run,
        ):
            if not config.LLM_API_KEY:
                st.error("Set PA_LLM_API_KEY in .env")
            else:
                with st.status("Analyzing...", expanded=True) as status:
                    try:
                        # Transcribe if audio
                        if input_mode == "Audio file":
                            f = state["_uploaded_audio"]
                            if f.size > config.MAX_AUDIO_SIZE_MB * 1024 * 1024:
                                raise ValueError(f"File too large (max {config.MAX_AUDIO_SIZE_MB} MB)")
                            suffix = Path(f.name).suffix
                            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                                tmp.write(f.read())
                                tmp_path = Path(tmp.name)
                            st.write("Transcribing...")
                            transcript = run_async(transcribe_audio(tmp_path, lang or None))
                            tmp_path.unlink(missing_ok=True)
                            state["transcript"] = transcript
                            state["normalized_text"] = transcript
                        elif input_mode == "Record":
                            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                                tmp.write(state["_recorded_audio"].read())
                                tmp_path = Path(tmp.name)
                            st.write("Transcribing...")
                            transcript = run_async(transcribe_audio(tmp_path, lang or None))
                            tmp_path.unlink(missing_ok=True)
                            state["transcript"] = transcript
                            state["normalized_text"] = transcript
                        else:
                            state["normalized_text"] = state["raw_text"].strip()

                        title = state.get("process_title") or "Process"

                        st.write("Building AS-IS model...")
                        asis = run_async(generate_asis(title, state["normalized_text"]))
                        state["asis"] = asis
                        state["state"] = SessionState.ASIS_GENERATED

                        st.write("Finding automation opportunities...")
                        points = run_async(diagnose_automation(title, asis))
                        state["automation_points"] = points
                        state["selected_point_ids"] = [p.id for p in points if p.default_selected]
                        state["state"] = SessionState.AUTOMATION_DIAGNOSED

                        status.update(label="Done!", state="complete")
                    except Exception as e:
                        status.update(label="Error", state="error")
                        st.error(str(e))

                if state["state"] == SessionState.AUTOMATION_DIAGNOSED:
                    st.rerun()

    # Result for step 1
    if state.get("transcript"):
        with st.expander("Transcript"):
            st.text(state["transcript"][:2000])

st.divider()

# ---------------------------------------------------------------------------
# STEP 2 — AS-IS Results
# ---------------------------------------------------------------------------

step2_done = state["state"].value in (
    SessionState.ASIS_GENERATED.value,
    SessionState.AUTOMATION_DIAGNOSED.value,
    SessionState.TOBE_GENERATED.value,
    SessionState.HTML_READY.value,
)

with st.container():
    _video_placeholder()
    _step_header(2, "AS-IS Analysis", "How your process works today")

    if not step2_done:
        st.info("Complete step 1 to see the analysis.")
    else:
        asis = state["asis"]

        st.markdown(f"**Summary:** {asis.summary}")

        with st.expander("Process diagram"):
            if asis.mermaid_code:
                _render_mermaid(asis.mermaid_code)

        with st.expander("Steps"):
            for i, step in enumerate(asis.steps, 1):
                tag = "Decision" if step.is_decision else f"{i}."
                st.markdown(f"**{tag} {step.name}** — _{step.actor}_")
                st.caption(step.description)
                if step.pain_points:
                    for pp in step.pain_points:
                        st.warning(pp)

        with st.expander("Roles & Systems"):
            for role in asis.roles:
                st.markdown(f"**{role.name}** — {role.description}")
            if asis.systems:
                st.markdown("**Systems:** " + ", ".join(asis.systems))
            if asis.artifacts:
                st.markdown("**Artifacts:** " + ", ".join(asis.artifacts))

        if asis.issues:
            with st.expander("Issues"):
                for issue in asis.issues:
                    st.error(issue)

st.divider()

# ---------------------------------------------------------------------------
# STEP 3 — Automation Points
# ---------------------------------------------------------------------------

step3_done = state["state"].value in (
    SessionState.AUTOMATION_DIAGNOSED.value,
    SessionState.TOBE_GENERATED.value,
    SessionState.HTML_READY.value,
)

with st.container():
    _video_placeholder()
    _step_header(3, "Automation Opportunities", "Choose what to automate")

    if not step3_done:
        st.info("Complete previous steps first.")
    else:
        points: list[AutomationPoint] = state["automation_points"]
        selected_ids = set(state["selected_point_ids"])

        maturity_emoji = {"quick_win": "🟢", "short_term": "🟡", "strategic": "🟣"}

        for point in points:
            emoji = maturity_emoji.get(point.maturity.value, "⚪")
            checked = st.checkbox(
                f"{emoji} {point.stage} — {point.manual_action}",
                value=point.id in selected_ids,
                key=f"ap_{point.id}",
            )
            if checked:
                selected_ids.add(point.id)
            else:
                selected_ids.discard(point.id)

            with st.expander("Details", expanded=False):
                st.caption(
                    f"Type: {point.automation_type.value} · "
                    f"Maturity: {point.maturity.value.replace('_', ' ')} · "
                    f"Effect: {point.effect}"
                )
                if point.potential:
                    st.write(f"**Potential:** {point.potential}")
                if point.system_action:
                    st.write(f"**System:** {point.system_action}")
                if point.human_action:
                    st.write(f"**Human:** {point.human_action}")

        state["selected_point_ids"] = list(selected_ids)

        st.caption(f"{len(selected_ids)} of {len(points)} selected")

        can_generate = (
            len(selected_ids) > 0
            and state["state"].value not in (
                SessionState.TOBE_GENERATED.value,
                SessionState.HTML_READY.value,
            )
        )

        if st.button(
            "Generate TO-BE",
            type="primary",
            use_container_width=True,
            disabled=not can_generate,
        ):
            asis = state["asis"]
            sel_points = [p for p in points if p.id in selected_ids]
            title = state.get("process_title") or "Process"

            with st.status("Generating...", expanded=True) as status:
                try:
                    st.write("Building TO-BE process...")
                    tobe = run_async(generate_tobe(title, asis, sel_points))
                    state["tobe"] = tobe
                    state["state"] = SessionState.TOBE_GENERATED

                    st.write("Designing human role...")
                    human_role = run_async(generate_human_role(title, asis, tobe, sel_points))
                    state["human_role"] = human_role

                    status.update(label="Done!", state="complete")
                except Exception as e:
                    status.update(label="Error", state="error")
                    st.error(str(e))

            if state["state"] == SessionState.TOBE_GENERATED:
                st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# STEP 4 — TO-BE & Human Role
# ---------------------------------------------------------------------------

step4_done = state["state"].value in (
    SessionState.TOBE_GENERATED.value,
    SessionState.HTML_READY.value,
)

with st.container():
    _video_placeholder()
    _step_header(4, "TO-BE Process", "How the process will work after automation")

    if not step4_done:
        st.info("Complete previous steps first.")
    else:
        tobe = state["tobe"]

        st.markdown(f"**Summary:** {tobe.summary}")

        with st.expander("Process diagram"):
            if tobe.mermaid_code:
                _render_mermaid(tobe.mermaid_code)

        with st.expander("Steps"):
            for i, step in enumerate(tobe.steps, 1):
                is_auto = any(
                    w in step.actor.lower()
                    for w in ("system", "ai", "rpa", "bot", "automat")
                )
                icon = "🤖" if is_auto else "👤"
                st.markdown(f"**{icon} {step.name}** — _{step.actor}_")
                st.caption(step.description)

        if tobe.changes_rationale:
            with st.expander("Changes rationale"):
                for r in tobe.changes_rationale:
                    st.info(r)

        # Human role
        human_role = state["human_role"]
        if human_role:
            st.markdown("---")
            st.markdown(
                f"<div style='text-align:center'><h4>New Human Role</h4></div>",
                unsafe_allow_html=True,
            )

            level_desc = {
                HumanRoleLevel.H0_OPERATOR: "Operator — monitors, handles exceptions",
                HumanRoleLevel.H1_SUPERVISOR: "Supervisor — reviews AI outputs",
                HumanRoleLevel.H2_MANAGER: "Manager — strategic decisions",
                HumanRoleLevel.H3_EXPERT: "Expert — designs rules, trains AI",
            }

            selected_level = st.selectbox(
                "Role level",
                options=list(HumanRoleLevel),
                index=list(HumanRoleLevel).index(human_role.level),
                format_func=lambda x: f"{x.value} — {level_desc[x].split(' — ')[1]}",
            )
            if selected_level != human_role.level:
                human_role.level = selected_level

            st.markdown(f"**{human_role.role_name}**")
            st.markdown(f"_{human_role.mission}_")

            with st.expander("Responsibilities"):
                for r in human_role.responsibilities:
                    st.markdown(f"- {r}")

            if human_role.kpis:
                with st.expander("KPIs"):
                    for kpi in human_role.kpis:
                        st.markdown(f"- {kpi}")

            if human_role.tools:
                with st.expander("Tools & Systems"):
                    for t in human_role.tools:
                        st.markdown(f"- {t}")

st.divider()

# ---------------------------------------------------------------------------
# STEP 5 — Final Report
# ---------------------------------------------------------------------------

with st.container():
    _video_placeholder()
    _step_header(5, "Final Report", "Download the complete analysis")

    if not step4_done:
        st.info("Complete previous steps first.")
    elif state["state"] != SessionState.HTML_READY:
        if st.button("Generate Report", type="primary", use_container_width=True):
            try:
                title = state.get("process_title") or "Process"
                transcript = state.get("transcript") or state.get("normalized_text")
                html = build_html_report(
                    title=title,
                    transcript=transcript,
                    asis=state["asis"],
                    automation_points=state["automation_points"],
                    selected_ids=state["selected_point_ids"],
                    tobe=state["tobe"],
                    human_role=state["human_role"],
                )
                state["html_report"] = html
                state["state"] = SessionState.HTML_READY
                st.rerun()
            except Exception as e:
                st.error(str(e))
    else:
        html = state["html_report"]

        with st.expander("Preview report"):
            st.components.v1.html(html, height=600, scrolling=True)

        title = state.get("process_title") or "Process"
        safe = "".join(c if c.isalnum() or c in " _-" else "_" for c in title)

        st.download_button(
            label="Download HTML Report",
            data=html,
            file_name=f"{safe}_report.html",
            mime="text/html",
            type="primary",
            use_container_width=True,
        )
