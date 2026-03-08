"""Task Board — Streamlit Application.

3-column layout in Flow View: File Tree | Flow Graph | Task Detail.
Board View: hierarchical card list + detail panel.
Run with: streamlit run task_board_app.py
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import streamlit as st

from src.process_analyzer import config
from src.process_analyzer.services.llm_client import chat_completion
from src.task_board.models import MCPConfig, Task, TaskBoard, TaskStatus, TaskType

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
    defaults = {
        "boards": {},
        "active_board_id": None,
        "selected_task_id": None,
        "view_mode": "flow",
        "file_tree_root": os.getcwd(),
        "expanded_dirs": set(),
        "dragged_file": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


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


def _type_icon(task_type: TaskType) -> str:
    return {
        TaskType.INTELLIGENT: "🧠",
        TaskType.MCP: "🔌",
        TaskType.CODE: "🐍",
    }[task_type]


def _select_task(task_id: str):
    st.session_state["selected_task_id"] = task_id


# ---------------------------------------------------------------------------
# Page config & CSS
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Task Board", page_icon="📋", layout="wide")

st.markdown(
    """
    <style>
    header[data-testid="stHeader"] { display: none; }
    .block-container { padding-top: 0.5rem; padding-bottom: 1rem; }

    .task-card {
        border: 1px solid rgba(128,128,128,0.2);
        border-radius: 10px;
        padding: 10px 14px;
        margin-bottom: 6px;
        background: var(--background-color);
        transition: box-shadow 0.15s;
    }
    .task-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
    .task-card-selected {
        border-color: #667eea;
        box-shadow: 0 0 0 2px rgba(102,126,234,0.3);
    }
    .dep-badge {
        display: inline-block; background: #f0f0f0; color: #555;
        border-radius: 4px; padding: 1px 5px; font-size: 0.7rem; margin-right: 3px;
    }
    .artifact-badge {
        display: inline-block; background: #e8f5e9; color: #2e7d32;
        border-radius: 4px; padding: 1px 5px; font-size: 0.7rem; margin-right: 3px;
    }
    .type-badge {
        display: inline-block; border-radius: 4px; padding: 1px 5px;
        font-size: 0.7rem; margin-right: 3px;
    }
    .type-intelligent { background: #e3f2fd; color: #1565c0; }
    .type-mcp { background: #fce4ec; color: #c62828; }
    .type-code { background: #fff3e0; color: #e65100; }

    .file-item {
        padding: 3px 6px; border-radius: 4px; cursor: pointer;
        font-size: 0.82rem; transition: background 0.15s;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .file-item:hover { background: rgba(102,126,234,0.1); }

    /* Compact buttons in file tree */
    .file-tree-btn .stButton > button {
        padding: 2px 6px; font-size: 0.75rem; min-height: 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

_init()

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

hcol1, hcol2, hcol3, hcol4 = st.columns([3, 1.5, 1.5, 2])
with hcol1:
    st.markdown("### 📋 Task Board")
with hcol2:
    if st.button("＋ New Board", use_container_width=True):
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
with hcol4:
    view = st.radio(
        "View",
        ["Board View", "Flow View"],
        horizontal=True,
        label_visibility="collapsed",
        index=1 if st.session_state["view_mode"] == "flow" else 0,
    )
    st.session_state["view_mode"] = "flow" if view == "Flow View" else "board"

board = _board()

if not board:
    st.markdown(
        """
        <div style="text-align:center; padding:80px 20px; color:#888;">
            <p style="font-size:3rem; margin-bottom:12px;">📋</p>
            <p style="font-size:1.1rem;">No task boards yet</p>
            <p>Click <b>＋ New Board</b> to get started</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

# Board name
new_name = st.text_input("Board name", value=board.name, label_visibility="collapsed", key="bname")
if new_name != board.name:
    board.name = new_name


# =========================================================================
# Detail panel (shared between views)
# =========================================================================

def _render_detail_panel(board: TaskBoard):
    """Render task detail panel in current column context."""
    sel_id = st.session_state["selected_task_id"]
    task = board.tasks.get(sel_id) if sel_id else None

    if not task:
        st.markdown(
            "<div style='text-align:center; padding:40px 20px; color:#999;'>"
            "<p style='font-size:1.5rem;'>👈</p>"
            "<p style='font-size:0.9rem;'>Select a task</p></div>",
            unsafe_allow_html=True,
        )
        return

    st.markdown(f"#### {_status_icon(task.status)} {_type_icon(task.task_type)} Task")

    # Title
    new_title = st.text_input("Title", value=task.title, key="d_title")
    if new_title != task.title:
        task.title = new_title
        task.touch()

    # Task type selector
    type_options = list(TaskType)
    new_type = st.radio(
        "Type",
        type_options,
        index=type_options.index(task.task_type),
        format_func=lambda t: f"{_type_icon(t)} {t.value}",
        horizontal=True,
        key="d_type",
    )
    if new_type != task.task_type:
        task.task_type = new_type
        task.touch()

    # --- Type-specific fields ---
    if task.task_type == TaskType.INTELLIGENT:
        new_desc = st.text_area(
            "Prompt",
            value=task.description,
            height=100,
            key="d_prompt",
            placeholder="Describe what this task should do. Sent to LLM.",
        )
        if new_desc != task.description:
            task.description = new_desc
            task.touch()

    elif task.task_type == TaskType.CODE:
        new_code = st.text_area(
            "Python Code",
            value=task.code,
            height=140,
            key="d_code",
            placeholder="# Python code to execute\nresult = 'hello'",
        )
        if new_code != task.code:
            task.code = new_code
            task.touch()

        new_desc = st.text_input(
            "Description",
            value=task.description,
            key="d_code_desc",
            placeholder="What does this code do?",
        )
        if new_desc != task.description:
            task.description = new_desc
            task.touch()

    elif task.task_type == TaskType.MCP:
        mcp = task.mcp_config
        new_server = st.text_input("MCP Server", value=mcp.server, key="d_mcp_server",
                                   placeholder="e.g. filesystem, brave-search")
        if new_server != mcp.server:
            mcp.server = new_server
            task.touch()

        new_tool = st.text_input("Tool Name", value=mcp.tool_name, key="d_mcp_tool",
                                 placeholder="e.g. read_file, search")
        if new_tool != mcp.tool_name:
            mcp.tool_name = new_tool
            task.touch()

        st.markdown("**Parameters** (key = value, one per line)")
        params_text = "\n".join(f"{k} = {v}" for k, v in mcp.parameters.items())
        new_params_text = st.text_area(
            "Params",
            value=params_text,
            height=80,
            key="d_mcp_params",
            placeholder="path = /tmp/file.txt\nquery = search term",
            label_visibility="collapsed",
        )
        # Parse params
        new_params = {}
        for line in new_params_text.strip().split("\n"):
            if "=" in line:
                k, v = line.split("=", 1)
                new_params[k.strip()] = v.strip()
        if new_params != mcp.parameters:
            mcp.parameters = new_params
            task.touch()

        new_desc = st.text_input(
            "Description",
            value=task.description,
            key="d_mcp_desc",
            placeholder="What does this MCP call do?",
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
        key="d_status",
    )
    if new_status != task.status:
        task.status = new_status
        task.touch()

    # Dependencies
    available_deps = [(tid, t.title) for tid, t in board.tasks.items() if tid != task.id]
    if available_deps:
        dep_ids = [d[0] for d in available_deps]
        dep_labels = {d[0]: d[1] for d in available_deps}
        current_deps = [d for d in task.dependency_ids if d in dep_ids]
        new_deps = st.multiselect(
            "Depends on",
            options=dep_ids,
            default=current_deps,
            format_func=lambda x: dep_labels.get(x, x),
            key="d_deps",
        )
        if set(new_deps) != set(task.dependency_ids):
            task.dependency_ids = new_deps
            task.touch()
        blockers = board.get_blocking(task)
        if blockers:
            st.warning(f"Blocked by: {', '.join(b.title for b in blockers)}")

    # Input artifacts
    if board.artifacts:
        art_keys = list(board.artifacts.keys())
        current_inputs = [a for a in task.input_artifacts if a in art_keys]
        new_inputs = st.multiselect(
            "Input artifacts",
            options=art_keys,
            default=current_inputs,
            key="d_inputs",
        )
        if set(new_inputs) != set(task.input_artifacts):
            task.input_artifacts = new_inputs
            task.touch()

    # Output artifact
    out_name = st.text_input(
        "Output artifact",
        value=task.output_artifact or "",
        placeholder="e.g. result.md",
        key="d_output",
    )
    if out_name != (task.output_artifact or ""):
        task.output_artifact = out_name if out_name else None
        task.touch()

    # Output content preview
    if task.output_content:
        with st.expander("Generated output", expanded=False):
            st.code(task.output_content, language="markdown")

    # --- Buttons ---
    st.markdown("---")
    b1, b2, b3 = st.columns(3)

    with b1:
        can_run = board.is_runnable(task) and config.LLM_API_KEY
        if task.task_type == TaskType.INTELLIGENT:
            can_run = can_run and bool(task.description.strip())
        elif task.task_type == TaskType.CODE:
            can_run = can_run and bool(task.code.strip())
        elif task.task_type == TaskType.MCP:
            can_run = can_run and bool(task.mcp_config.tool_name)

        if st.button("▶ Run", type="primary", use_container_width=True, disabled=not can_run, key="d_run"):
            task.status = TaskStatus.IN_PROGRESS
            task.touch()

            with st.spinner("Running..."):
                try:
                    result = _execute_task(board, task)
                    task.output_content = result
                    task.status = TaskStatus.DONE
                    task.touch()
                    if task.output_artifact:
                        board.save_artifact(task.output_artifact, result)
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    with b2:
        if st.button("✓ Done", use_container_width=True, key="d_done"):
            task.status = TaskStatus.DONE
            task.touch()
            st.rerun()

    with b3:
        if st.button("🗑 Del", use_container_width=True, key="d_del"):
            board.remove_task(task.id)
            st.session_state["selected_task_id"] = None
            st.rerun()

    # Add child
    if st.button("＋ Add Subtask", use_container_width=True, key="d_sub"):
        sub = board.add_task(title=f"Subtask of {task.title}", parent_id=task.id)
        st.session_state["selected_task_id"] = sub.id
        st.rerun()

    st.caption(f"Created: {task.created_at}")


def _execute_task(board: TaskBoard, task: Task) -> str:
    """Execute task based on its type. Returns result string."""
    # Build context from input artifacts
    context_parts = []
    for art_key in task.input_artifacts:
        content = board.artifacts.get(art_key, "")
        if content:
            context_parts.append(f"--- {art_key} ---\n{content}")
    context_str = "\n\n".join(context_parts)

    if task.task_type == TaskType.INTELLIGENT:
        user_prompt = task.description
        if context_str:
            user_prompt += f"\n\nContext:\n{context_str}"
        return run_async(chat_completion(
            system="You are a helpful assistant. Complete the task described by the user. Be thorough and structured.",
            user=user_prompt,
        ))

    elif task.task_type == TaskType.CODE:
        # Execute Python code in isolated namespace
        namespace = {"__builtins__": __builtins__}
        if context_str:
            namespace["context"] = context_str
        exec(task.code, namespace)  # noqa: S102
        return str(namespace.get("result", "Code executed (no `result` variable set)"))

    elif task.task_type == TaskType.MCP:
        # MCP is a stub — show what would be called
        mcp = task.mcp_config
        params_str = "\n".join(f"  {k}: {v}" for k, v in mcp.parameters.items())
        return (
            f"MCP Call (mock):\n"
            f"  Server: {mcp.server}\n"
            f"  Tool: {mcp.tool_name}\n"
            f"  Parameters:\n{params_str}\n\n"
            f"[MCP execution not yet connected — result would appear here]"
        )

    return "Unknown task type"


# =========================================================================
# File tree renderer
# =========================================================================

def _render_file_tree(board: TaskBoard):
    """Render file tree in current column. Clicking a file adds it as input artifact."""
    root = st.session_state["file_tree_root"]
    st.markdown("**Files**")

    new_root = st.text_input("Root path", value=root, key="ft_root", label_visibility="collapsed")
    if new_root != root:
        st.session_state["file_tree_root"] = new_root

    root_path = Path(root)
    if not root_path.is_dir():
        st.error("Invalid directory")
        return

    def _render_dir(dirpath: Path, depth: int = 0):
        try:
            entries = sorted(dirpath.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            return

        for entry in entries:
            if entry.name.startswith(".") or entry.name == "__pycache__":
                continue

            indent = depth * 16
            if entry.is_dir():
                is_expanded = str(entry) in st.session_state["expanded_dirs"]
                folder_icon = "📂" if is_expanded else "📁"
                if st.button(
                    f"{folder_icon} {entry.name}",
                    key=f"dir_{entry}",
                    use_container_width=True,
                ):
                    if is_expanded:
                        st.session_state["expanded_dirs"].discard(str(entry))
                    else:
                        st.session_state["expanded_dirs"].add(str(entry))
                    st.rerun()

                if is_expanded:
                    _render_dir(entry, depth + 1)
            else:
                # File — click to attach to selected task as input artifact
                ext = entry.suffix.lower()
                file_icon = "🐍" if ext == ".py" else "📄"
                rel = entry.relative_to(root_path)
                btn_label = f"{file_icon} {entry.name}"

                col_f, col_a = st.columns([4, 1])
                with col_f:
                    st.markdown(
                        f"<div class='file-item' style='margin-left:{indent}px;'>"
                        f"{btn_label}</div>",
                        unsafe_allow_html=True,
                    )
                with col_a:
                    sel_id = st.session_state["selected_task_id"]
                    task = board.tasks.get(sel_id) if sel_id else None
                    if task:
                        art_key = str(rel)
                        already = art_key in task.input_artifacts
                        if st.button(
                            "✓" if already else "＋",
                            key=f"attach_{entry}",
                            use_container_width=True,
                            disabled=already,
                        ):
                            # Read file and save as artifact, attach to task
                            try:
                                content = entry.read_text(errors="replace")[:50000]
                                board.save_artifact(art_key, content)
                                task.input_artifacts.append(art_key)
                                task.touch()
                                st.rerun()
                            except Exception:
                                pass

    _render_dir(root_path)


# =========================================================================
# FLOW VIEW — 3 columns: Files | Flow | Detail
# =========================================================================

if st.session_state["view_mode"] == "flow":
    st.markdown("---")

    col_files, col_flow, col_detail = st.columns([1.5, 3.5, 2.5])

    # --- LEFT: File tree ---
    with col_files:
        _render_file_tree(board)

    # --- CENTER: Flow graph + task cards ---
    with col_flow:
        # Add task button
        if st.button("＋ Add Task", key="flow_add", use_container_width=True):
            new_task = board.add_task(title="New task")
            st.session_state["selected_task_id"] = new_task.id
            st.rerun()

        if not board.tasks:
            st.info("No tasks yet. Click '+ Add Task'.")
        else:
            # --- Mermaid flow graph ---
            lines = ["graph TD"]
            for t in board.tasks.values():
                status_label = t.status.value
                type_label = t.task_type.value
                shape_l, shape_r = ("[", "]")
                if t.status == TaskStatus.DONE:
                    shape_l, shape_r = ("([", "])")
                elif t.status == TaskStatus.IN_PROGRESS:
                    shape_l, shape_r = ("[[", "]]")

                safe_title = t.title.replace('"', "'").replace("\n", " ")
                lines.append(
                    f'    {t.id}{shape_l}"{_type_icon(t.task_type)} {safe_title}<br/>'
                    f'<small>{status_label} · {type_label}</small>"{shape_r}'
                )

                color = _status_color(t.status)
                lines.append(f"    style {t.id} stroke:{color},stroke-width:2px")

                for dep_id in t.dependency_ids:
                    if dep_id in board.tasks:
                        lines.append(f"    {dep_id} --> {t.id}")

                if t.parent_id and t.parent_id in board.tasks:
                    lines.append(f"    {t.parent_id} -.-> {t.id}")

            mermaid_code = "\n".join(lines)
            js_code = mermaid_code.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
            html = f"""
            <div id="flow-container" style="background:#fff; padding:16px; border-radius:12px; overflow:auto;">
              <div id="flow-output"></div>
            </div>
            <script type="module">
              import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
              mermaid.initialize({{
                startOnLoad: false, theme: 'default', securityLevel: 'loose',
                flowchart: {{ useMaxWidth: true, curve: 'basis', htmlLabels: true }}
              }});
              try {{
                const {{ svg }} = await mermaid.render('flow-graph', `{js_code}`);
                document.getElementById('flow-output').innerHTML = svg;
              }} catch(e) {{
                document.getElementById('flow-output').innerHTML =
                  '<pre style="color:#c00;font-size:12px;">' + e.message + '</pre>';
              }}
            </script>
            """
            st.components.v1.html(html, height=max(350, len(board.tasks) * 90), scrolling=True)

            # --- Card list with Open / + buttons ---
            st.markdown("---")
            for task in sorted(board.tasks.values(), key=lambda t: t.created_at):
                selected = st.session_state["selected_task_id"] == task.id
                icon = _status_icon(task.status)
                type_i = _type_icon(task.task_type)
                color = _status_color(task.status)
                card_cls = "task-card task-card-selected" if selected else "task-card"
                type_cls = f"type-{task.task_type.value.lower()}"

                # Blocker badges
                blockers = board.get_blocking(task)
                dep_html = ""
                if blockers:
                    dep_html = " ".join(
                        f'<span class="dep-badge">⛔ {b.title}</span>' for b in blockers
                    )

                art_html = ""
                if task.output_artifact:
                    art_html = f'<span class="artifact-badge">📄 {task.output_artifact}</span>'

                st.markdown(
                    f"""<div class="{card_cls}">
                        <div style="display:flex;align-items:center;gap:6px;">
                            <span>{icon}</span>
                            <span style="flex:1;font-weight:500;font-size:0.9rem;">{task.title or 'Untitled'}</span>
                            <span class="type-badge {type_cls}">{type_i} {task.task_type.value}</span>
                            <span style="font-size:0.65rem;padding:2px 6px;border-radius:10px;color:white;background:{color};">{task.status.value}</span>
                        </div>
                        {f'<div style="margin-top:3px;">{dep_html}</div>' if dep_html else ''}
                        {f'<div style="margin-top:3px;">{art_html}</div>' if art_html else ''}
                    </div>""",
                    unsafe_allow_html=True,
                )

                bc1, bc2 = st.columns(2)
                with bc1:
                    if st.button("Open", key=f"fopen_{task.id}", use_container_width=True):
                        _select_task(task.id)
                        st.rerun()
                with bc2:
                    if st.button("＋ Child", key=f"fchild_{task.id}", use_container_width=True):
                        child = board.add_task(
                            title=f"Subtask of {task.title}",
                            parent_id=task.id,
                        )
                        _select_task(child.id)
                        st.rerun()

    # --- RIGHT: Detail panel ---
    with col_detail:
        _render_detail_panel(board)

    # Legend
    st.markdown(
        """<div style="text-align:center;padding:4px;font-size:0.75rem;color:#888;">
            ── dep &nbsp; - - parent &nbsp;
            <span style="color:#6c757d;">■</span> To Do &nbsp;
            <span style="color:#0d6efd;">■</span> In Progress &nbsp;
            <span style="color:#198754;">■</span> Done &nbsp; | &nbsp;
            🧠 Intelligent &nbsp; 🔌 MCP &nbsp; 🐍 Code
        </div>""",
        unsafe_allow_html=True,
    )
    st.stop()


# =========================================================================
# BOARD VIEW — 2 columns: card list | detail
# =========================================================================

st.markdown("---")
col_list, col_detail = st.columns([3, 4])

with col_list:
    if st.button("＋ Add Task", use_container_width=True, key="board_add"):
        new_task = board.add_task(title="New task")
        st.session_state["selected_task_id"] = new_task.id
        st.rerun()

    def _render_task_tree(parent_id: str | None, depth: int = 0):
        children = board.get_children(parent_id)
        for task in children:
            selected = st.session_state["selected_task_id"] == task.id
            blockers = board.get_blocking(task)
            icon = _status_icon(task.status)
            type_i = _type_icon(task.task_type)
            color = _status_color(task.status)
            indent = depth * 20
            card_cls = "task-card task-card-selected" if selected else "task-card"
            type_cls = f"type-{task.task_type.value.lower()}"

            dep_html = ""
            if blockers:
                dep_html = " ".join(
                    f'<span class="dep-badge">⛔ {b.title}</span>' for b in blockers
                )

            art_html = ""
            if task.output_artifact:
                art_html = f'<span class="artifact-badge">📄 {task.output_artifact}</span>'

            st.markdown(
                f"""<div class="{card_cls}" style="margin-left:{indent}px;">
                    <div style="display:flex;align-items:center;gap:6px;">
                        <span>{icon}</span>
                        <span style="flex:1;font-weight:500;font-size:0.9rem;">{task.title or 'Untitled'}</span>
                        <span class="type-badge {type_cls}">{type_i} {task.task_type.value}</span>
                        <span style="font-size:0.65rem;padding:2px 6px;border-radius:10px;color:white;background:{color};">{task.status.value}</span>
                    </div>
                    {f'<div style="margin-top:3px;">{dep_html}</div>' if dep_html else ''}
                    {f'<div style="margin-top:3px;">{art_html}</div>' if art_html else ''}
                </div>""",
                unsafe_allow_html=True,
            )

            bc1, bc2 = st.columns(2)
            with bc1:
                if st.button("Open", key=f"bopen_{task.id}", use_container_width=True):
                    _select_task(task.id)
                    st.rerun()
            with bc2:
                if st.button("＋", key=f"bchild_{task.id}", use_container_width=True):
                    child = board.add_task(title=f"Subtask of {task.title}", parent_id=task.id)
                    _select_task(child.id)
                    st.rerun()

            _render_task_tree(task.id, depth + 1)

    if not board.tasks:
        st.caption("No tasks. Click '+ Add Task' to begin.")
    else:
        _render_task_tree(None)

with col_detail:
    _render_detail_panel(board)
