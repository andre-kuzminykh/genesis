"""Task Board — Streamlit Application.

Hierarchical task cards with dependencies, statuses, Flow View, and LLM execution.
Run with: streamlit run task_board_app.py
"""

from __future__ import annotations

import asyncio

import streamlit as st

from src.process_analyzer import config
from src.process_analyzer.services.llm_client import chat_completion
from src.task_board.models import Task, TaskBoard, TaskStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _init():
    if "boards" not in st.session_state:
        st.session_state["boards"] = {}  # id -> TaskBoard
    if "active_board_id" not in st.session_state:
        st.session_state["active_board_id"] = None
    if "selected_task_id" not in st.session_state:
        st.session_state["selected_task_id"] = None
    if "view_mode" not in st.session_state:
        st.session_state["view_mode"] = "board"  # "board" or "flow"


def _board() -> TaskBoard | None:
    bid = st.session_state["active_board_id"]
    if bid:
        return st.session_state["boards"].get(bid)
    return None


def _status_color(status: TaskStatus) -> str:
    return {
        TaskStatus.TODO: "#6c757d",
        TaskStatus.IN_PROGRESS: "#0d6efd",
        TaskStatus.DONE: "#198754",
    }[status]


def _status_icon(status: TaskStatus) -> str:
    return {
        TaskStatus.TODO: "⬜",
        TaskStatus.IN_PROGRESS: "🔄",
        TaskStatus.DONE: "✅",
    }[status]


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Task Board", page_icon="📋", layout="wide")

st.markdown(
    """
    <style>
    header[data-testid="stHeader"] { display: none; }
    .block-container { padding-top: 1rem; }
    .task-card {
        border: 1px solid rgba(128,128,128,0.2);
        border-radius: 10px;
        padding: 12px 16px;
        margin-bottom: 8px;
        background: var(--background-color);
        transition: box-shadow 0.2s;
    }
    .task-card:hover {
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
    .task-card-selected {
        border-color: #667eea;
        box-shadow: 0 0 0 2px rgba(102,126,234,0.3);
    }
    .dep-badge {
        display: inline-block;
        background: #f0f0f0;
        color: #555;
        border-radius: 4px;
        padding: 2px 6px;
        font-size: 0.75rem;
        margin-right: 4px;
    }
    .artifact-badge {
        display: inline-block;
        background: #e8f5e9;
        color: #2e7d32;
        border-radius: 4px;
        padding: 2px 6px;
        font-size: 0.75rem;
        margin-right: 4px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

_init()

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

hcol1, hcol2, hcol3 = st.columns([3, 2, 2])
with hcol1:
    st.markdown("### 📋 Task Board")
with hcol2:
    if st.button("＋ New Task Board", use_container_width=True):
        board = TaskBoard()
        st.session_state["boards"][board.id] = board
        st.session_state["active_board_id"] = board.id
        st.session_state["selected_task_id"] = None
        st.rerun()
with hcol3:
    boards = st.session_state["boards"]
    if boards:
        board_options = {bid: b.name for bid, b in boards.items()}
        active = st.session_state["active_board_id"]
        selected_bid = st.selectbox(
            "Board",
            options=list(board_options.keys()),
            format_func=lambda x: board_options[x],
            index=list(board_options.keys()).index(active) if active in board_options else 0,
            label_visibility="collapsed",
        )
        if selected_bid != st.session_state["active_board_id"]:
            st.session_state["active_board_id"] = selected_bid
            st.session_state["selected_task_id"] = None
            st.rerun()

board = _board()

if not board:
    st.markdown(
        """
        <div style="text-align:center; padding:80px 20px; color:#888;">
            <p style="font-size:3rem; margin-bottom:12px;">📋</p>
            <p style="font-size:1.1rem;">No task boards yet</p>
            <p>Click <b>New Task Board</b> to get started</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

# ---------------------------------------------------------------------------
# Board name & view toggle
# ---------------------------------------------------------------------------

tcol1, tcol2 = st.columns([4, 2])
with tcol1:
    new_name = st.text_input("Board name", value=board.name, label_visibility="collapsed")
    if new_name != board.name:
        board.name = new_name
with tcol2:
    view = st.radio(
        "View",
        ["Board View", "Flow View"],
        horizontal=True,
        label_visibility="collapsed",
        index=0 if st.session_state["view_mode"] == "board" else 1,
    )
    st.session_state["view_mode"] = "board" if view == "Board View" else "flow"


# =========================================================================
# FLOW VIEW
# =========================================================================

if st.session_state["view_mode"] == "flow":
    st.markdown("---")
    st.markdown(
        "<div style='text-align:center'><h4>Flow View</h4>"
        "<p style='color:#888; font-size:0.85rem;'>Task structure and dependencies</p></div>",
        unsafe_allow_html=True,
    )

    # Build Mermaid flowchart
    lines = ["graph LR"]
    for t in board.tasks.values():
        status_label = t.status.value
        shape_l, shape_r = ("[", "]")
        if t.status == TaskStatus.DONE:
            shape_l, shape_r = ("([", "])")
        elif t.status == TaskStatus.IN_PROGRESS:
            shape_l, shape_r = ("[[", "]]")

        safe_title = t.title.replace('"', "'")
        lines.append(f'    {t.id}{shape_l}"{safe_title}\\n{status_label}"{shape_r}')

        # Style
        color = _status_color(t.status)
        lines.append(f"    style {t.id} stroke:{color},stroke-width:2px")

        # Dependency edges
        for dep_id in t.dependency_ids:
            if dep_id in board.tasks:
                lines.append(f"    {dep_id} --> {t.id}")

        # Parent-child edges (dashed)
        if t.parent_id and t.parent_id in board.tasks:
            lines.append(f"    {t.parent_id} -.-> {t.id}")

    mermaid_code = "\n".join(lines)

    if len(board.tasks) == 0:
        st.info("No tasks yet. Switch to Board View to add tasks.")
    else:
        # Render mermaid
        js_code = mermaid_code.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
        html = f"""
        <div id="flow-container" style="background:#fff; padding:20px; border-radius:12px; overflow-x:auto;">
          <div id="flow-output"></div>
        </div>
        <script type="module">
          import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
          mermaid.initialize({{
            startOnLoad: false, theme: 'default', securityLevel: 'loose',
            flowchart: {{ useMaxWidth: true, curve: 'basis' }}
          }});
          try {{
            const {{ svg }} = await mermaid.render('flow-graph', `{js_code}`);
            document.getElementById('flow-output').innerHTML = svg;
          }} catch(e) {{
            document.getElementById('flow-output').innerHTML =
              '<pre style="color:#c00;">' + e.message + '</pre>';
          }}
        </script>
        """
        st.components.v1.html(html, height=max(300, len(board.tasks) * 80), scrolling=True)

    # Legend
    st.markdown(
        """
        <div style="text-align:center; padding:8px; font-size:0.8rem; color:#888;">
            ── dependency &nbsp;&nbsp; - - parent/child &nbsp;&nbsp;
            <span style="color:#6c757d;">■</span> To Do &nbsp;
            <span style="color:#0d6efd;">■</span> In Progress &nbsp;
            <span style="color:#198754;">■</span> Done
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()


# =========================================================================
# BOARD VIEW — main layout
# =========================================================================

st.markdown("---")

# Two columns: task list (left) + detail panel (right)
col_list, col_detail = st.columns([3, 4])

# ---------------------------------------------------------------------------
# LEFT: hierarchical task list
# ---------------------------------------------------------------------------

with col_list:
    # Add task button
    if st.button("＋ Add Task", use_container_width=True):
        new_task = board.add_task(title="New task")
        st.session_state["selected_task_id"] = new_task.id
        st.rerun()

    def _render_task_tree(parent_id: str | None, depth: int = 0):
        """Recursively render tasks as indented cards."""
        children = board.get_children(parent_id)
        for task in children:
            selected = st.session_state["selected_task_id"] == task.id
            blockers = board.get_blocking(task)
            icon = _status_icon(task.status)
            color = _status_color(task.status)

            indent = depth * 24
            card_class = "task-card task-card-selected" if selected else "task-card"

            # Dependency badges
            dep_html = ""
            if blockers:
                badges = "".join(
                    f'<span class="dep-badge">⛔ {b.title}</span>' for b in blockers
                )
                dep_html = f'<div style="margin-top:4px;">{badges}</div>'

            # Artifact badge
            art_html = ""
            if task.output_artifact:
                art_html = f'<span class="artifact-badge">📄 {task.output_artifact}</span>'

            st.markdown(
                f"""
                <div class="{card_class}" style="margin-left:{indent}px;">
                    <div style="display:flex; align-items:center; gap:8px;">
                        <span>{icon}</span>
                        <span style="flex:1; font-weight:500;">{task.title or 'Untitled'}</span>
                        <span style="
                            font-size:0.7rem; padding:2px 8px;
                            border-radius:10px; color:white;
                            background:{color};
                        ">{task.status.value}</span>
                    </div>
                    {dep_html}
                    {f'<div style="margin-top:4px;">{art_html}</div>' if art_html else ''}
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Select button
            if st.button(
                f"Open: {task.title or 'Untitled'}",
                key=f"sel_{task.id}",
                use_container_width=True,
            ):
                st.session_state["selected_task_id"] = task.id
                st.rerun()

            # Render children recursively
            _render_task_tree(task.id, depth + 1)

    if not board.tasks:
        st.caption("No tasks. Click '+ Add Task' to begin.")
    else:
        _render_task_tree(None)


# ---------------------------------------------------------------------------
# RIGHT: detail panel
# ---------------------------------------------------------------------------

with col_detail:
    sel_id = st.session_state["selected_task_id"]
    task = board.tasks.get(sel_id) if sel_id else None

    if not task:
        st.markdown(
            """
            <div style="text-align:center; padding:60px 20px; color:#999;">
                <p style="font-size:2rem;">👈</p>
                <p>Select a task to view details</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(f"#### {_status_icon(task.status)} Task Details")

        # Title
        new_title = st.text_input("Title", value=task.title, key="detail_title")
        if new_title != task.title:
            task.title = new_title
            task.touch()

        # Description / prompt
        new_desc = st.text_area(
            "Description / Prompt",
            value=task.description,
            height=120,
            key="detail_desc",
            placeholder="Describe what this task should do. This text is sent as prompt to LLM when you Run.",
        )
        if new_desc != task.description:
            task.description = new_desc
            task.touch()

        # Status
        status_options = list(TaskStatus)
        new_status = st.selectbox(
            "Status",
            options=status_options,
            index=status_options.index(task.status),
            format_func=lambda s: f"{_status_icon(s)} {s.value}",
            key="detail_status",
        )
        if new_status != task.status:
            task.status = new_status
            task.touch()

        # Parent task
        st.markdown("**Parent task**")
        other_tasks = [(tid, t.title) for tid, t in board.tasks.items() if tid != task.id]
        parent_options = [("", "— None —")] + other_tasks
        parent_ids = [p[0] for p in parent_options]
        parent_labels = [p[1] for p in parent_options]
        current_parent_idx = parent_ids.index(task.parent_id) if task.parent_id in parent_ids else 0
        new_parent = st.selectbox(
            "Parent",
            options=parent_ids,
            index=current_parent_idx,
            format_func=lambda x: parent_labels[parent_ids.index(x)],
            label_visibility="collapsed",
            key="detail_parent",
        )
        if new_parent != (task.parent_id or ""):
            task.parent_id = new_parent if new_parent else None
            task.touch()

        # Dependencies
        st.markdown("**Dependencies**")
        available_deps = [
            (tid, t.title)
            for tid, t in board.tasks.items()
            if tid != task.id
        ]
        if available_deps:
            dep_ids = [d[0] for d in available_deps]
            dep_labels = {d[0]: d[1] for d in available_deps}
            current_deps = [d for d in task.dependency_ids if d in dep_ids]
            new_deps = st.multiselect(
                "Depends on",
                options=dep_ids,
                default=current_deps,
                format_func=lambda x: dep_labels.get(x, x),
                label_visibility="collapsed",
                key="detail_deps",
            )
            if set(new_deps) != set(task.dependency_ids):
                task.dependency_ids = new_deps
                task.touch()

            # Show blockers
            blockers = board.get_blocking(task)
            if blockers:
                st.warning(f"Blocked by: {', '.join(b.title for b in blockers)}")
        else:
            st.caption("No other tasks to depend on")

        # Input artifacts
        st.markdown("**Input artifacts**")
        if board.artifacts:
            art_keys = list(board.artifacts.keys())
            current_inputs = [a for a in task.input_artifacts if a in art_keys]
            new_inputs = st.multiselect(
                "Input files",
                options=art_keys,
                default=current_inputs,
                label_visibility="collapsed",
                key="detail_inputs",
            )
            if set(new_inputs) != set(task.input_artifacts):
                task.input_artifacts = new_inputs
                task.touch()
        else:
            st.caption("No artifacts available yet")

        # Output artifact
        st.markdown("**Output artifact**")
        out_name = st.text_input(
            "Output file name",
            value=task.output_artifact or "",
            placeholder="e.g. prd_draft.md",
            label_visibility="collapsed",
            key="detail_output",
        )
        if out_name != (task.output_artifact or ""):
            task.output_artifact = out_name if out_name else None
            task.touch()

        # Show output content if exists
        if task.output_content:
            with st.expander("Generated output", expanded=False):
                st.markdown(task.output_content)

        # --- Action buttons ---
        st.markdown("---")
        btn_cols = st.columns(3)

        with btn_cols[0]:
            can_run = (
                board.is_runnable(task)
                and task.description.strip()
                and config.LLM_API_KEY
            )
            if st.button(
                "▶ Run",
                type="primary",
                use_container_width=True,
                disabled=not can_run,
            ):
                # Build context from input artifacts
                context_parts = []
                for art_key in task.input_artifacts:
                    content = board.artifacts.get(art_key, "")
                    if content:
                        context_parts.append(f"--- {art_key} ---\n{content}")

                context_str = "\n\n".join(context_parts)
                user_prompt = task.description
                if context_str:
                    user_prompt += f"\n\nContext:\n{context_str}"

                task.status = TaskStatus.IN_PROGRESS
                task.touch()

                with st.spinner("Running task..."):
                    try:
                        result = run_async(chat_completion(
                            system="You are a helpful assistant. Complete the task described by the user. Be thorough and structured.",
                            user=user_prompt,
                        ))
                        task.output_content = result
                        task.status = TaskStatus.DONE
                        task.touch()

                        # Save as artifact
                        if task.output_artifact:
                            board.save_artifact(task.output_artifact, result)

                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

            if not config.LLM_API_KEY:
                st.caption("Set PA_LLM_API_KEY")
            elif not task.description.strip():
                st.caption("Add a prompt first")
            elif not board.is_runnable(task):
                st.caption("Has blockers")

        with btn_cols[1]:
            if st.button("✓ Mark Done", use_container_width=True):
                task.status = TaskStatus.DONE
                task.touch()
                st.rerun()

        with btn_cols[2]:
            if st.button("🗑 Delete", use_container_width=True):
                board.remove_task(task.id)
                st.session_state["selected_task_id"] = None
                st.rerun()

        # --- Add subtask ---
        st.markdown("---")
        if st.button("＋ Add Subtask", use_container_width=True):
            sub = board.add_task(title=f"Subtask of {task.title}", parent_id=task.id)
            st.session_state["selected_task_id"] = sub.id
            st.rerun()

        # Timestamps
        st.caption(f"Created: {task.created_at} · Updated: {task.updated_at}")
