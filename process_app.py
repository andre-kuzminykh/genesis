"""Process Automation Designer — Streamlit Application.

Multi-screen wizard: Input → Automation Opportunities (AS-IS) → Human Role (TO-BE) → Agents.
Run with: streamlit run process_app.py
"""

from __future__ import annotations

import asyncio
import tempfile
import time
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
        "screen": 1,
        "process_title": "",
        "raw_text": "",
        "transcript": None,
        "normalized_text": "",
        "asis": None,
        "automation_points": [],
        "selected_point_ids": [],
        "tobe": None,
        "human_role": None,
        "human_role_overrides": {},  # step_id -> HumanRoleLevel
        "html_report": "",
        "agents": [],  # generated agent list for screen 4
        "selected_agents": [],
        "loading": False,
        "loading_message": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _render_mermaid(mermaid_code: str, height: int = 420):
    """Render Mermaid diagram with proper initialization."""
    # Sanitize mermaid code: remove markdown fences if present
    code = mermaid_code.strip()
    if code.startswith("```"):
        code = code.split("\n", 1)[1] if "\n" in code else code[3:]
    if code.endswith("```"):
        code = code[:-3]
    code = code.strip()

    # Escape backticks and special chars for JS
    js_code = code.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")

    html = f"""
    <div id="mermaid-container" style="background:#fff; padding:16px; border-radius:12px; overflow-x:auto;">
      <div id="mermaid-output"></div>
    </div>
    <script type="module">
      import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
      mermaid.initialize({{
        startOnLoad: false,
        theme: 'default',
        securityLevel: 'loose',
        sequence: {{ mirrorActors: false }},
        flowchart: {{ useMaxWidth: true }}
      }});
      try {{
        const {{ svg }} = await mermaid.render('mermaid-graph', `{js_code}`);
        document.getElementById('mermaid-output').innerHTML = svg;
      }} catch(e) {{
        document.getElementById('mermaid-output').innerHTML =
          '<pre style="color:#c00; font-size:12px;">' + e.message + '</pre>' +
          '<pre style="color:#666; font-size:11px; white-space:pre-wrap;">' +
          `{js_code}`.substring(0, 500) + '</pre>';
      }}
    </script>
    """
    st.components.v1.html(html, height=height, scrolling=True)


def _avatar_circle(icon: str = "🎙", label: str = ""):
    """Render an avatar circle with optional label."""
    st.markdown(
        f"""
        <div style="text-align:center; margin-bottom:12px;">
            <div style="
                width:100px; height:100px;
                border-radius:50%;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                margin: 0 auto 8px auto;
                display:flex; align-items:center; justify-content:center;
                color: white; font-size: 40px;
                box-shadow: 0 4px 15px rgba(102,126,234,0.4);
                animation: pulse 2s ease-in-out infinite;
            ">{icon}</div>
            {f'<p style="color:#888; font-size:0.8rem; margin:0;">{label}</p>' if label else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _loading_with_avatar(icon: str, message: str):
    """Render the avatar circle with a spinning ring around it and status text below."""
    st.markdown(
        f"""
        <div style="text-align:center; padding:40px 20px;">
            <div style="
                width:120px; height:120px;
                border-radius:50%;
                margin: 0 auto 20px auto;
                position: relative;
                display:flex; align-items:center; justify-content:center;
            ">
                <!-- Spinning ring -->
                <div style="
                    position:absolute; inset:0;
                    border-radius:50%;
                    border: 4px solid rgba(102,126,234,0.15);
                    border-top-color: #667eea;
                    border-right-color: #764ba2;
                    animation: spin 1.2s linear infinite;
                "></div>
                <!-- Inner circle -->
                <div style="
                    width:100px; height:100px;
                    border-radius:50%;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    display:flex; align-items:center; justify-content:center;
                    color: white; font-size: 40px;
                    box-shadow: 0 4px 15px rgba(102,126,234,0.4);
                ">{icon}</div>
            </div>
            <p style="font-size:1.05rem; color:#555; margin:0; font-weight:500;">{message}</p>
        </div>
        <style>
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _screen_header(title: str, subtitle: str):
    """Render screen title centered."""
    st.markdown(
        f"""
        <div style="text-align:center; margin-bottom:20px;">
            <h2 style="margin:0 0 4px 0; font-size:1.4rem;">{title}</h2>
            <p style="color:#888; margin:0; font-size:0.9rem;">{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _back_button():
    """Render back button. Returns True if clicked."""
    if st.button("← Back", key=f"back_{st.session_state['screen']}"):
        st.session_state["screen"] -= 1
        st.rerun()



def _build_agents_from_points(points: list[AutomationPoint]) -> list[dict]:
    """Generate agent recommendations from selected automation points."""
    agents = []
    # Map of ready-made agent types (quick_wins are typically available)
    ready_types = {"deterministic", "hybrid"}

    for p in points:
        is_ready = (
            p.maturity.value == "quick_win"
            and p.automation_type.value in ready_types
        )
        agents.append({
            "id": p.id,
            "name": f"Agent: {p.stage}",
            "description": p.potential or p.system_action,
            "type": p.automation_type.value,
            "maturity": p.maturity.value,
            "step": p.stage,
            "manual_action": p.manual_action,
            "effect": p.effect,
            "status": "ready" if is_ready else "develop",
        })
    return agents


# ---------------------------------------------------------------------------
# Page config & CSS
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Process Automation Designer",
    page_icon="⚙️",
    layout="centered",
)

st.markdown(
    """
    <style>
    .block-container { max-width: 680px; padding: 1rem 1rem 4rem 1rem; }
    .streamlit-expanderHeader { font-size: 0.95rem; }
    header[data-testid="stHeader"] { display: none; }

    @keyframes pulse {
        0%, 100% { transform: scale(1); opacity: 1; }
        50% { transform: scale(1.05); opacity: 0.85; }
    }

    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 8px 16px;
        font-size: 0.85rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

_init_session()
ss = st.session_state

# ---------------------------------------------------------------------------
# SCREEN 1 — Input
# ---------------------------------------------------------------------------

if ss["screen"] == 1:
    st.markdown(
        """
        <div style="text-align:center; padding: 16px 0 8px 0;">
            <h1 style="margin:0; font-size:1.6rem;">⚙️ Process Automation Designer</h1>
            <p style="color:#888; margin:4px 0 0 0; font-size:0.9rem;">
                Analyze your process step by step
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _avatar_circle("🎙", "Describe your process")

    input_mode = st.radio(
        "How would you like to provide data?",
        ["Text", "Audio file", "Record"],
        horizontal=True,
        label_visibility="collapsed",
    )

    if input_mode == "Text":
        ss["raw_text"] = st.text_area(
            "Process description",
            value=ss["raw_text"],
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
            ss["_uploaded_audio"] = uploaded

    else:  # Record
        audio_bytes = st.audio_input("Record audio", label_visibility="collapsed")
        if audio_bytes:
            ss["_recorded_audio"] = audio_bytes

    lang = None
    if input_mode != "Text":
        lang = st.text_input(
            "Language hint (optional)",
            placeholder="e.g. ru, en",
            label_visibility="collapsed",
        )

    # --- Run button ---
    can_run = (
        (input_mode == "Text" and ss["raw_text"].strip())
        or (input_mode == "Audio file" and ss.get("_uploaded_audio"))
        or (input_mode == "Record" and ss.get("_recorded_audio"))
    )

    if st.button(
        "Analyze", type="primary", use_container_width=True, disabled=not can_run,
    ):
        if not config.LLM_API_KEY:
            st.error("Set PA_LLM_API_KEY in .env")
        else:
            # --- Loading phase: replace entire screen ---
            loading_container = st.empty()
            with loading_container.container():
                progress_placeholder = st.empty()

                def _show_progress(msg: str):
                    with progress_placeholder.container():
                        _loading_with_avatar("🎙", msg)

                try:
                    # Transcribe if audio
                    if input_mode == "Audio file":
                        f = ss["_uploaded_audio"]
                        if f.size > config.MAX_AUDIO_SIZE_MB * 1024 * 1024:
                            raise ValueError(f"File too large (max {config.MAX_AUDIO_SIZE_MB} MB)")
                        suffix = Path(f.name).suffix
                        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                            tmp.write(f.read())
                            tmp_path = Path(tmp.name)
                        _show_progress("Transcribing audio...")
                        transcript = run_async(transcribe_audio(tmp_path, lang or None))
                        tmp_path.unlink(missing_ok=True)
                        ss["transcript"] = transcript
                        ss["normalized_text"] = transcript
                    elif input_mode == "Record":
                        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                            tmp.write(ss["_recorded_audio"].read())
                            tmp_path = Path(tmp.name)
                        _show_progress("Transcribing recording...")
                        transcript = run_async(transcribe_audio(tmp_path, lang or None))
                        tmp_path.unlink(missing_ok=True)
                        ss["transcript"] = transcript
                        ss["normalized_text"] = transcript
                    else:
                        ss["normalized_text"] = ss["raw_text"].strip()

                    title = ss.get("process_title") or "Process"

                    _show_progress("Thinking... analyzing the process")
                    asis = run_async(generate_asis(title, ss["normalized_text"]))
                    ss["asis"] = asis
                    ss["state"] = SessionState.ASIS_GENERATED

                    _show_progress("Finding automation opportunities...")
                    points = run_async(diagnose_automation(title, asis))
                    ss["automation_points"] = points
                    ss["selected_point_ids"] = [p.id for p in points if p.default_selected]
                    ss["state"] = SessionState.AUTOMATION_DIAGNOSED

                    _show_progress("Almost done...")
                    time.sleep(0.5)

                    # Move to screen 2
                    ss["screen"] = 2
                    st.rerun()

                except Exception as e:
                    loading_container.empty()
                    st.error(str(e))

# ---------------------------------------------------------------------------
# SCREEN 2 — Automation Opportunities + AS-IS
# ---------------------------------------------------------------------------

elif ss["screen"] == 2:
    _back_button()
    _avatar_circle("🔍", "Analyzing opportunities")
    _screen_header("Automation Opportunities", "Select which steps to automate")

    asis = ss["asis"]
    points: list[AutomationPoint] = ss["automation_points"]
    selected_ids = set(ss["selected_point_ids"])

    maturity_emoji = {"quick_win": "🟢", "short_term": "🟡", "strategic": "🟣"}

    # --- Opportunity selection ---
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

    ss["selected_point_ids"] = list(selected_ids)
    st.caption(f"{len(selected_ids)} of {len(points)} selected")

    # --- Next button (BEFORE AS-IS) ---
    st.markdown("")
    can_next = len(selected_ids) > 0
    if st.button(
        "Next: Design TO-BE →",
        type="primary",
        use_container_width=True,
        disabled=not can_next,
    ):
        sel_points = [p for p in points if p.id in selected_ids]
        title = ss.get("process_title") or "Process"

        loading_container = st.empty()
        with loading_container.container():
            progress_ph = st.empty()

            def _show(msg):
                with progress_ph.container():
                    _loading_with_avatar("🔍", msg)

            try:
                _show("Building TO-BE process...")
                tobe = run_async(generate_tobe(title, asis, sel_points))
                ss["tobe"] = tobe
                ss["state"] = SessionState.TOBE_GENERATED

                _show("Designing new human role...")
                human_role = run_async(generate_human_role(title, asis, tobe, sel_points))
                ss["human_role"] = human_role

                _show("Preparing results...")
                time.sleep(0.5)

                ss["screen"] = 3
                st.rerun()
            except Exception as e:
                loading_container.empty()
                st.error(str(e))

    # --- AS-IS Section ---
    st.markdown("---")
    st.markdown(
        "<div style='text-align:center'><h4>AS-IS Process</h4></div>",
        unsafe_allow_html=True,
    )
    st.markdown(f"**Summary:** {asis.summary}")

    tab_mermaid, tab_steps, tab_metrics, tab_roles, tab_systems = st.tabs(
        ["Mermaid", "Steps", "Metrics", "Roles", "Systems"]
    )

    with tab_mermaid:
        if asis.mermaid_code:
            _render_mermaid(asis.mermaid_code)
        else:
            st.info("No diagram available")

    with tab_steps:
        for i, step in enumerate(asis.steps, 1):
            tag = "Decision" if step.is_decision else f"{i}."
            st.markdown(f"**{tag} {step.name}** — _{step.actor}_")
            st.caption(step.description)
            if step.pain_points:
                for pp in step.pain_points:
                    st.warning(pp)

    with tab_metrics:
        if asis.metrics:
            for m in asis.metrics:
                st.markdown(f"- {m}")
        else:
            st.info("No metrics identified")
        if asis.issues:
            st.markdown("**Issues:**")
            for issue in asis.issues:
                st.error(issue)

    with tab_roles:
        for role in asis.roles:
            st.markdown(f"**{role.name}** — {role.description}")
            if role.responsibilities:
                for r in role.responsibilities:
                    st.markdown(f"  - {r}")

    with tab_systems:
        if asis.systems:
            for s in asis.systems:
                st.markdown(f"- {s}")
        else:
            st.info("No systems identified")
        if asis.artifacts:
            st.markdown("**Artifacts:**")
            for a in asis.artifacts:
                st.markdown(f"- {a}")

# ---------------------------------------------------------------------------
# SCREEN 3 — Human Role + TO-BE
# ---------------------------------------------------------------------------

elif ss["screen"] == 3:
    _back_button()
    _avatar_circle("👤", "Designing new roles")
    _screen_header("New Human Role", "Define the role of the human after automation")

    tobe = ss["tobe"]
    human_role = ss["human_role"]
    points = ss["automation_points"]
    selected_ids = set(ss["selected_point_ids"])
    sel_points = [p for p in points if p.id in selected_ids]

    # --- Per-operation role selection ---
    st.markdown("**Choose role level for each automated operation:**")

    level_labels = {
        HumanRoleLevel.H0_OPERATOR: "Operator — monitors, handles exceptions",
        HumanRoleLevel.H1_SUPERVISOR: "Supervisor — reviews AI outputs",
        HumanRoleLevel.H2_MANAGER: "Manager — strategic decisions",
        HumanRoleLevel.H3_EXPERT: "Expert — designs rules, trains AI",
    }

    if "human_role_overrides" not in ss:
        ss["human_role_overrides"] = {}

    for point in sel_points:
        current_level = ss["human_role_overrides"].get(
            point.id, human_role.level if human_role else HumanRoleLevel.H1_SUPERVISOR
        )
        selected_level = st.selectbox(
            f"{point.stage}: {point.manual_action}",
            options=list(HumanRoleLevel),
            index=list(HumanRoleLevel).index(current_level),
            format_func=lambda x: f"{x.value} — {level_labels[x].split(' — ')[1]}",
            key=f"role_{point.id}",
        )
        ss["human_role_overrides"][point.id] = selected_level

    # --- Human role summary ---
    if human_role:
        st.markdown("---")
        st.markdown(
            f"<div style='text-align:center'>"
            f"<h4>{human_role.role_name}</h4>"
            f"<p style='color:#666;'>{human_role.mission}</p>"
            f"</div>",
            unsafe_allow_html=True,
        )

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

    # --- Next button (BEFORE TO-BE) ---
    st.markdown("")
    if st.button("Next: View Agents →", type="primary", use_container_width=True):
        # Build agent list from selected points
        sel_points = [p for p in points if p.id in selected_ids]
        ss["agents"] = _build_agents_from_points(sel_points)
        ss["selected_agents"] = [
            a["id"] for a in ss["agents"] if a["status"] == "ready"
        ]
        ss["screen"] = 4
        st.rerun()

    # --- TO-BE Section ---
    st.markdown("---")
    st.markdown(
        "<div style='text-align:center'><h4>TO-BE Process</h4></div>",
        unsafe_allow_html=True,
    )
    st.markdown(f"**Summary:** {tobe.summary}")

    tab_mermaid, tab_steps, tab_metrics, tab_roles, tab_systems = st.tabs(
        ["Mermaid", "Steps", "Metrics", "Roles", "Systems"]
    )

    with tab_mermaid:
        if tobe.mermaid_code:
            _render_mermaid(tobe.mermaid_code)
        else:
            st.info("No diagram available")

    with tab_steps:
        for i, step in enumerate(tobe.steps, 1):
            is_auto = any(
                w in step.actor.lower()
                for w in ("system", "ai", "rpa", "bot", "automat")
            )
            icon = "🤖" if is_auto else "👤"
            st.markdown(f"**{icon} {step.name}** — _{step.actor}_")
            st.caption(step.description)

    with tab_metrics:
        if tobe.changes_rationale:
            for r in tobe.changes_rationale:
                st.info(r)
        if tobe.assumptions:
            st.markdown("**Assumptions:**")
            for a in tobe.assumptions:
                st.markdown(f"- {a}")

    with tab_roles:
        actors_seen = set()
        for step in tobe.steps:
            if step.actor not in actors_seen:
                actors_seen.add(step.actor)
                is_auto = any(
                    w in step.actor.lower()
                    for w in ("system", "ai", "rpa", "bot", "automat")
                )
                icon = "🤖" if is_auto else "👤"
                st.markdown(f"{icon} **{step.actor}**")

    with tab_systems:
        systems_seen = set()
        for step in tobe.steps:
            for s in step.systems:
                systems_seen.add(s)
        if systems_seen:
            for s in sorted(systems_seen):
                st.markdown(f"- {s}")
        else:
            st.info("No systems specified")

# ---------------------------------------------------------------------------
# SCREEN 4 — Agents (implement / develop)
# ---------------------------------------------------------------------------

elif ss["screen"] == 4:
    _back_button()
    _avatar_circle("🤖", "Agent recommendations")
    _screen_header("Agents to Deploy", "Ready-made agents and agents to develop")

    agents = ss["agents"]
    selected_agents = set(ss.get("selected_agents", []))

    # Split into ready and develop
    ready_agents = [a for a in agents if a["status"] == "ready"]
    develop_agents = [a for a in agents if a["status"] == "develop"]

    # --- Ready to implement ---
    if ready_agents:
        st.markdown("### ✅ Ready to Implement")
        st.caption("These agents are available and can be deployed now")

        for agent in ready_agents:
            checked = st.checkbox(
                f"**{agent['name']}**",
                value=agent["id"] in selected_agents,
                key=f"agent_{agent['id']}",
            )
            if checked:
                selected_agents.add(agent["id"])
            else:
                selected_agents.discard(agent["id"])

            st.caption(f"{agent['description']}")
            st.caption(
                f"Type: {agent['type']} · "
                f"Maturity: {agent['maturity'].replace('_', ' ')} · "
                f"Effect: {agent['effect']}"
            )
            st.markdown("")

    # --- To develop ---
    if develop_agents:
        st.markdown("### 🔧 To Develop")
        st.caption("These agents need to be built — add them to the backlog")

        for agent in develop_agents:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**{agent['name']}**")
                st.caption(f"{agent['description']}")
                st.caption(
                    f"Type: {agent['type']} · "
                    f"Maturity: {agent['maturity'].replace('_', ' ')} · "
                    f"Effect: {agent['effect']}"
                )
            with col2:
                if st.button(
                    "Add to Backlog",
                    key=f"backlog_{agent['id']}",
                    use_container_width=True,
                ):
                    st.toast(f"Added to backlog: {agent['name']}")

            st.markdown("")

    ss["selected_agents"] = list(selected_agents)

    # --- Summary ---
    st.markdown("---")
    n_ready = len([a for a in ready_agents if a["id"] in selected_agents])
    st.markdown(
        f"**{n_ready}** agent(s) selected for deployment, "
        f"**{len(develop_agents)}** agent(s) for development"
    )

    # --- Deploy button (happy path) ---
    st.markdown("")
    if n_ready > 0:
        if st.button(
            "🚀 Deploy Selected Agents",
            type="primary",
            use_container_width=True,
        ):
            # Mock: show success and OS menu button
            st.balloons()
            st.success(
                f"Successfully deployed {n_ready} agent(s)! "
                "They are now active in your operating system."
            )
            st.markdown("")
            st.markdown(
                """
                <div style="text-align:center; padding: 20px;">
                    <button style="
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white;
                        border: none;
                        padding: 16px 48px;
                        border-radius: 12px;
                        font-size: 1.1rem;
                        font-weight: 600;
                        cursor: pointer;
                        box-shadow: 0 4px 15px rgba(102,126,234,0.4);
                    " onclick="alert('Opening Operating System main menu...')">
                        Open Operating System →
                    </button>
                    <p style="color:#888; font-size:0.8rem; margin-top:8px;">
                        Go to the main control panel
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # --- Download report ---
    st.markdown("---")
    if st.button("📄 Download Full Report", use_container_width=True):
        try:
            title = ss.get("process_title") or "Process"
            transcript = ss.get("transcript") or ss.get("normalized_text")
            html = build_html_report(
                title=title,
                transcript=transcript,
                asis=ss["asis"],
                automation_points=ss["automation_points"],
                selected_ids=ss["selected_point_ids"],
                tobe=ss["tobe"],
                human_role=ss["human_role"],
            )
            ss["html_report"] = html
            ss["state"] = SessionState.HTML_READY
            st.rerun()
        except Exception as e:
            st.error(str(e))

    if ss["state"] == SessionState.HTML_READY and ss["html_report"]:
        title = ss.get("process_title") or "Process"
        safe = "".join(c if c.isalnum() or c in " _-" else "_" for c in title)
        st.download_button(
            label="⬇️ Download HTML Report",
            data=ss["html_report"],
            file_name=f"{safe}_report.html",
            mime="text/html",
            use_container_width=True,
        )
