"""Task Board — Streamlit Application.

Screen-based navigation:
  - flow:           Flow graph + card list, collapsible detail panel on right
  - task_fullscreen: Full-screen task editor
  - file_view:      File content viewer + chat

Left sidebar (Files) is ALWAYS visible on every screen.
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
        "detail_open": True,           # right panel open/collapsed in flow
        "screen": "flow",              # flow | task_fullscreen | file_view
        "screen_stack": [],            # for Back button
        "file_tree_root": os.getcwd(),
        "expanded_dirs": set(),
        # file viewer
        "viewing_path": None,          # str path or None
        "viewing_folder": None,        # str path if viewing folder
        "file_chat_history": [],       # list of {role, content}
        "file_chat_input": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _board() -> TaskBoard | None:
    bid = st.session_state["active_board_id"]
    if bid:
        return st.session_state["boards"].get(bid)
    return None


def _navigate(screen: str, **kwargs):
    """Push current screen to stack and navigate to new screen."""
    current = st.session_state["screen"]
    if current != screen:
        st.session_state["screen_stack"].append(current)
    st.session_state["screen"] = screen
    for k, v in kwargs.items():
        st.session_state[k] = v


def _go_back():
    """Pop previous screen from stack."""
    stack = st.session_state["screen_stack"]
    if stack:
        st.session_state["screen"] = stack.pop()
    else:
        st.session_state["screen"] = "flow"


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


def _file_icon(path: Path) -> str:
    ext = path.suffix.lower()
    icons = {
        ".py": "🐍", ".js": "📜", ".ts": "📜", ".json": "📋",
        ".md": "📝", ".txt": "📃", ".yaml": "⚙️", ".yml": "⚙️",
        ".html": "🌐", ".css": "🎨", ".toml": "⚙️", ".cfg": "⚙️",
    }
    return icons.get(ext, "📄")


# ---------------------------------------------------------------------------
# Page config & CSS
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Task Board", page_icon="📋", layout="wide")

st.markdown(
    """
    <style>
    header[data-testid="stHeader"] { display: none; }
    .block-container { padding-top: 0.5rem; padding-bottom: 0.5rem; }
    section[data-testid="stSidebar"] { min-width: 260px; max-width: 320px; }
    section[data-testid="stSidebar"] .block-container { padding-top: 0.5rem; }

    .task-card {
        border: 1px solid rgba(128,128,128,0.2);
        border-radius: 10px;
        padding: 10px 14px;
        margin-bottom: 6px;
        background: var(--background-color);
        transition: box-shadow 0.15s;
        cursor: pointer;
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

    .file-tree-item {
        padding: 2px 4px; border-radius: 4px;
        font-size: 0.8rem; transition: background 0.15s;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }

    .chat-msg {
        padding: 8px 12px; border-radius: 10px; margin-bottom: 6px;
        font-size: 0.88rem; line-height: 1.4;
    }
    .chat-user { background: #e3f2fd; margin-left: 20%; }
    .chat-assistant { background: #f5f5f5; margin-right: 20%; }

    .back-btn { margin-bottom: 8px; }
    </style>
    """,
    unsafe_allow_html=True,
)

_init()


# =========================================================================
# LEFT SIDEBAR — File tree (ALWAYS visible)
# =========================================================================

with st.sidebar:
    st.markdown("### 📁 Files")

    root = st.session_state["file_tree_root"]
    new_root = st.text_input(
        "Root", value=root, key="ft_root", label_visibility="collapsed",
        placeholder="Project root path",
    )
    if new_root != root:
        st.session_state["file_tree_root"] = new_root
        st.rerun()

    root_path = Path(root)
    board = _board()

    if not root_path.is_dir():
        st.error("Invalid directory")
    else:
        def _render_sidebar_tree(dirpath: Path, depth: int = 0):
            try:
                entries = sorted(
                    dirpath.iterdir(),
                    key=lambda p: (not p.is_dir(), p.name.lower()),
                )
            except PermissionError:
                return

            for entry in entries:
                if entry.name.startswith(".") or entry.name in ("__pycache__", "node_modules", ".git"):
                    continue

                indent = depth * 12
                if entry.is_dir():
                    is_expanded = str(entry) in st.session_state["expanded_dirs"]
                    icon = "📂" if is_expanded else "📁"

                    c1, c2 = st.columns([5, 1])
                    with c1:
                        if st.button(
                            f"{'　' * depth}{icon} {entry.name}",
                            key=f"sdir_{entry}",
                            use_container_width=True,
                        ):
                            if is_expanded:
                                st.session_state["expanded_dirs"].discard(str(entry))
                            else:
                                st.session_state["expanded_dirs"].add(str(entry))
                            st.rerun()
                    with c2:
                        # Open folder view (chat with all files in folder)
                        if st.button("💬", key=f"sfchat_{entry}"):
                            _navigate(
                                "file_view",
                                viewing_path=None,
                                viewing_folder=str(entry),
                                file_chat_history=[],
                            )
                            st.rerun()

                    if is_expanded:
                        _render_sidebar_tree(entry, depth + 1)
                else:
                    icon = _file_icon(entry)
                    if st.button(
                        f"{'　' * depth}{icon} {entry.name}",
                        key=f"sfile_{entry}",
                        use_container_width=True,
                    ):
                        _navigate(
                            "file_view",
                            viewing_path=str(entry),
                            viewing_folder=None,
                            file_chat_history=[],
                        )
                        st.rerun()

        _render_sidebar_tree(root_path)


# =========================================================================
# Header bar
# =========================================================================

hcol1, hcol2, hcol3 = st.columns([4, 1.5, 1.5])
with hcol1:
    st.markdown("### 📋 Task Board")
with hcol2:
    if st.button("＋ New Board", use_container_width=True):
        b = TaskBoard()
        st.session_state["boards"][b.id] = b
        st.session_state["active_board_id"] = b.id
        st.session_state["selected_task_id"] = None
        st.session_state["screen"] = "flow"
        st.rerun()
with hcol3:
    boards_dict = st.session_state["boards"]
    if boards_dict:
        options = {bid: b.name for bid, b in boards_dict.items()}
        active = st.session_state["active_board_id"]
        sel = st.selectbox(
            "Board", options=list(options.keys()),
            format_func=lambda x: options[x],
            index=list(options.keys()).index(active) if active in options else 0,
            label_visibility="collapsed",
        )
        if sel != st.session_state["active_board_id"]:
            st.session_state["active_board_id"] = sel
            st.session_state["selected_task_id"] = None
            st.session_state["screen"] = "flow"
            st.rerun()

board = _board()

if not board:
    st.markdown(
        "<div style='text-align:center;padding:80px 20px;color:#888;'>"
        "<p style='font-size:3rem;'>📋</p>"
        "<p>No task boards yet. Click <b>＋ New Board</b>.</p></div>",
        unsafe_allow_html=True,
    )
    st.stop()


# =========================================================================
# Task detail panel (reusable, used in flow + fullscreen)
# =========================================================================

def _render_detail(board: TaskBoard, task: Task, prefix: str = "d"):
    """Render full task editor. prefix avoids widget key collisions."""

    st.markdown(f"#### {_status_icon(task.status)} {_type_icon(task.task_type)} {task.title or 'Untitled'}")

    # Title
    new_title = st.text_input("Title", value=task.title, key=f"{prefix}_title")
    if new_title != task.title:
        task.title = new_title
        task.touch()

    # Task type
    type_options = list(TaskType)
    new_type = st.radio(
        "Type", type_options,
        index=type_options.index(task.task_type),
        format_func=lambda t: f"{_type_icon(t)} {t.value}",
        horizontal=True, key=f"{prefix}_type",
    )
    if new_type != task.task_type:
        task.task_type = new_type
        task.touch()

    # Type-specific fields
    if task.task_type == TaskType.INTELLIGENT:
        new_desc = st.text_area(
            "Prompt", value=task.description, height=120, key=f"{prefix}_prompt",
            placeholder="Describe what this task should do. Sent to LLM.",
        )
        if new_desc != task.description:
            task.description = new_desc
            task.touch()

    elif task.task_type == TaskType.CODE:
        new_code = st.text_area(
            "Python Code", value=task.code, height=180, key=f"{prefix}_code",
            placeholder="# Python code to execute\nresult = 'hello'",
        )
        if new_code != task.code:
            task.code = new_code
            task.touch()
        new_desc = st.text_input("Description", value=task.description, key=f"{prefix}_cdesc",
                                 placeholder="What does this code do?")
        if new_desc != task.description:
            task.description = new_desc
            task.touch()

    elif task.task_type == TaskType.MCP:
        mcp = task.mcp_config
        new_server = st.text_input("MCP Server", value=mcp.server, key=f"{prefix}_msrv",
                                   placeholder="e.g. filesystem, brave-search")
        if new_server != mcp.server:
            mcp.server = new_server
            task.touch()
        new_tool = st.text_input("Tool Name", value=mcp.tool_name, key=f"{prefix}_mtool",
                                 placeholder="e.g. read_file, search")
        if new_tool != mcp.tool_name:
            mcp.tool_name = new_tool
            task.touch()
        st.markdown("**Parameters** (key = value, one per line)")
        params_text = "\n".join(f"{k} = {v}" for k, v in mcp.parameters.items())
        new_params_text = st.text_area(
            "Params", value=params_text, height=80, key=f"{prefix}_mpar",
            placeholder="path = /tmp/file.txt\nquery = search term", label_visibility="collapsed",
        )
        new_params = {}
        for line in new_params_text.strip().split("\n"):
            if "=" in line:
                k, v = line.split("=", 1)
                new_params[k.strip()] = v.strip()
        if new_params != mcp.parameters:
            mcp.parameters = new_params
            task.touch()
        new_desc = st.text_input("Description", value=task.description, key=f"{prefix}_mdesc",
                                 placeholder="What does this MCP call do?")
        if new_desc != task.description:
            task.description = new_desc
            task.touch()

    # Status
    status_options = list(TaskStatus)
    new_status = st.selectbox(
        "Status", options=status_options,
        index=status_options.index(task.status),
        format_func=lambda s: f"{_status_icon(s)} {s.value}",
        key=f"{prefix}_status",
    )
    if new_status != task.status:
        task.status = new_status
        task.touch()

    # Parent
    other = [(tid, t.title) for tid, t in board.tasks.items() if tid != task.id]
    parent_opts = [("", "— None —")] + other
    p_ids = [p[0] for p in parent_opts]
    p_labels = [p[1] for p in parent_opts]
    cur_p = p_ids.index(task.parent_id) if task.parent_id in p_ids else 0
    new_parent = st.selectbox(
        "Parent task", options=p_ids, index=cur_p,
        format_func=lambda x: p_labels[p_ids.index(x)],
        key=f"{prefix}_parent",
    )
    if new_parent != (task.parent_id or ""):
        task.parent_id = new_parent if new_parent else None
        task.touch()

    # Dependencies
    available_deps = [(tid, t.title) for tid, t in board.tasks.items() if tid != task.id]
    if available_deps:
        dep_ids = [d[0] for d in available_deps]
        dep_labels = {d[0]: d[1] for d in available_deps}
        current_deps = [d for d in task.dependency_ids if d in dep_ids]
        new_deps = st.multiselect(
            "Depends on", options=dep_ids, default=current_deps,
            format_func=lambda x: dep_labels.get(x, x), key=f"{prefix}_deps",
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
            "Input artifacts", options=art_keys, default=current_inputs, key=f"{prefix}_inputs",
        )
        if set(new_inputs) != set(task.input_artifacts):
            task.input_artifacts = new_inputs
            task.touch()

    # Output artifact
    out_name = st.text_input(
        "Output artifact", value=task.output_artifact or "",
        placeholder="e.g. result.md", key=f"{prefix}_out",
    )
    if out_name != (task.output_artifact or ""):
        task.output_artifact = out_name if out_name else None
        task.touch()

    # Output content
    if task.output_content:
        with st.expander("Generated output", expanded=False):
            st.code(task.output_content, language="markdown")

    # Buttons
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

        if st.button("▶ Run", type="primary", use_container_width=True,
                      disabled=not can_run, key=f"{prefix}_run"):
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
        if st.button("✓ Done", use_container_width=True, key=f"{prefix}_done"):
            task.status = TaskStatus.DONE
            task.touch()
            st.rerun()

    with b3:
        if st.button("🗑 Del", use_container_width=True, key=f"{prefix}_del"):
            board.remove_task(task.id)
            st.session_state["selected_task_id"] = None
            if st.session_state["screen"] == "task_fullscreen":
                _go_back()
            st.rerun()

    if st.button("＋ Add Subtask", use_container_width=True, key=f"{prefix}_sub"):
        sub = board.add_task(title=f"Subtask of {task.title}", parent_id=task.id)
        st.session_state["selected_task_id"] = sub.id
        st.rerun()

    st.caption(f"Created: {task.created_at}")


def _execute_task(board: TaskBoard, task: Task) -> str:
    """Execute task based on its type."""
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
            system="You are a helpful assistant. Complete the task described by the user.",
            user=user_prompt,
        ))
    elif task.task_type == TaskType.CODE:
        namespace = {"__builtins__": __builtins__}
        if context_str:
            namespace["context"] = context_str
        exec(task.code, namespace)  # noqa: S102
        return str(namespace.get("result", "Code executed (no `result` variable set)"))
    elif task.task_type == TaskType.MCP:
        mcp = task.mcp_config
        params_str = "\n".join(f"  {k}: {v}" for k, v in mcp.parameters.items())
        return (
            f"MCP Call (mock):\n  Server: {mcp.server}\n  Tool: {mcp.tool_name}\n"
            f"  Parameters:\n{params_str}\n\n"
            f"[MCP execution not yet connected]"
        )
    return "Unknown task type"


# =========================================================================
# Render a task card (reusable)
# =========================================================================

def _render_card(task: Task, board: TaskBoard, key_prefix: str):
    """Render a single task card with Open / FullScreen / + Child buttons."""
    selected = st.session_state["selected_task_id"] == task.id
    icon = _status_icon(task.status)
    type_i = _type_icon(task.task_type)
    color = _status_color(task.status)
    card_cls = "task-card task-card-selected" if selected else "task-card"
    type_cls = f"type-{task.task_type.value.lower()}"

    blockers = board.get_blocking(task)
    dep_html = ""
    if blockers:
        dep_html = " ".join(f'<span class="dep-badge">⛔ {b.title}</span>' for b in blockers)
    art_html = ""
    if task.output_artifact:
        art_html = f'<span class="artifact-badge">📄 {task.output_artifact}</span>'

    children_count = len(board.get_children(task.id))
    children_badge = f'<span style="font-size:0.65rem;color:#888;">👶 {children_count}</span>' if children_count else ""

    st.markdown(
        f"""<div class="{card_cls}">
            <div style="display:flex;align-items:center;gap:6px;">
                <span>{icon}</span>
                <span style="flex:1;font-weight:500;font-size:0.88rem;">{task.title or 'Untitled'}</span>
                {children_badge}
                <span class="type-badge {type_cls}">{type_i} {task.task_type.value}</span>
                <span style="font-size:0.6rem;padding:2px 6px;border-radius:10px;color:white;background:{color};">{task.status.value}</span>
            </div>
            {f'<div style="margin-top:3px;">{dep_html}</div>' if dep_html else ''}
            {f'<div style="margin-top:3px;">{art_html}</div>' if art_html else ''}
        </div>""",
        unsafe_allow_html=True,
    )

    bc1, bc2, bc3 = st.columns(3)
    with bc1:
        if st.button("Open", key=f"{key_prefix}_open_{task.id}", use_container_width=True):
            st.session_state["selected_task_id"] = task.id
            st.session_state["detail_open"] = True
            st.rerun()
    with bc2:
        # "Fullscreen" — equivalent of double-click
        if st.button("⛶", key=f"{key_prefix}_fs_{task.id}", use_container_width=True,
                      help="Open fullscreen"):
            st.session_state["selected_task_id"] = task.id
            _navigate("task_fullscreen")
            st.rerun()
    with bc3:
        if st.button("＋", key=f"{key_prefix}_child_{task.id}", use_container_width=True,
                      help="Add child task"):
            child = board.add_task(title=f"Subtask of {task.title}", parent_id=task.id)
            st.session_state["selected_task_id"] = child.id
            st.session_state["detail_open"] = True
            st.rerun()


# =========================================================================
# SCREEN: file_view — file content + chat
# =========================================================================

def _screen_file_view():
    # Back button
    if st.button("← Back", key="fv_back"):
        _go_back()
        st.rerun()

    viewing_path = st.session_state.get("viewing_path")
    viewing_folder = st.session_state.get("viewing_folder")

    if viewing_folder:
        # Folder mode: show all files + combined chat
        folder = Path(viewing_folder)
        st.markdown(f"### 📁 {folder.name}")

        files_content = {}
        try:
            for f in sorted(folder.iterdir()):
                if f.is_file() and not f.name.startswith("."):
                    try:
                        files_content[f.name] = f.read_text(errors="replace")[:30000]
                    except Exception:
                        pass
        except PermissionError:
            st.error("No permission")
            return

        if not files_content:
            st.info("No readable files in this folder.")
            return

        col_files, col_chat = st.columns([3, 3])

        with col_files:
            st.markdown(f"**{len(files_content)} files**")
            for fname, content in files_content.items():
                with st.expander(f"{_file_icon(Path(fname))} {fname}", expanded=False):
                    lang = "python" if fname.endswith(".py") else "text"
                    st.code(content[:5000], language=lang)
                    if len(content) > 5000:
                        st.caption(f"... truncated ({len(content)} chars total)")

                    # Attach to task button
                    if board and st.session_state["selected_task_id"]:
                        task = board.tasks.get(st.session_state["selected_task_id"])
                        if task:
                            rel = str(Path(viewing_folder).relative_to(st.session_state["file_tree_root"]) / fname)
                            if rel not in task.input_artifacts:
                                if st.button(f"Attach to task", key=f"fattach_{fname}"):
                                    board.save_artifact(rel, content)
                                    task.input_artifacts.append(rel)
                                    task.touch()
                                    st.rerun()

        with col_chat:
            st.markdown("**💬 Chat about these files**")
            _render_file_chat(
                context="\n\n".join(
                    f"=== {fname} ===\n{c[:10000]}" for fname, c in files_content.items()
                ),
                label=f"folder {folder.name}",
            )

    elif viewing_path:
        # Single file mode
        fpath = Path(viewing_path)
        st.markdown(f"### {_file_icon(fpath)} {fpath.name}")
        st.caption(str(fpath))

        try:
            content = fpath.read_text(errors="replace")[:50000]
        except Exception as e:
            st.error(f"Cannot read: {e}")
            return

        col_code, col_chat = st.columns([3, 3])

        with col_code:
            lang = "python" if fpath.suffix == ".py" else "text"
            st.code(content[:10000], language=lang, line_numbers=True)
            if len(content) > 10000:
                st.caption(f"... truncated ({len(content)} chars total)")

            # Attach to selected task
            if board and st.session_state["selected_task_id"]:
                task = board.tasks.get(st.session_state["selected_task_id"])
                if task:
                    try:
                        rel = str(fpath.relative_to(st.session_state["file_tree_root"]))
                    except ValueError:
                        rel = fpath.name
                    if rel not in task.input_artifacts:
                        if st.button(f"📎 Attach to task «{task.title}»", key="fv_attach"):
                            board.save_artifact(rel, content)
                            task.input_artifacts.append(rel)
                            task.touch()
                            st.rerun()
                    else:
                        st.success(f"Already attached to «{task.title}»")

        with col_chat:
            st.markdown("**💬 Chat about this file**")
            _render_file_chat(context=content, label=fpath.name)

    else:
        st.info("No file selected.")


def _render_file_chat(context: str, label: str):
    """Render a simple chat interface about file content."""
    history = st.session_state["file_chat_history"]

    # Display history
    for msg in history:
        cls = "chat-user" if msg["role"] == "user" else "chat-assistant"
        st.markdown(f'<div class="chat-msg {cls}">{msg["content"]}</div>', unsafe_allow_html=True)

    # Input
    user_input = st.text_input("Ask about this file...", key="fc_input", label_visibility="collapsed",
                               placeholder=f"Ask about {label}...")
    if st.button("Send", key="fc_send") and user_input.strip():
        history.append({"role": "user", "content": user_input})

        if config.LLM_API_KEY:
            with st.spinner("Thinking..."):
                try:
                    prompt = (
                        f"File context:\n{context[:15000]}\n\n"
                        f"Chat history:\n"
                        + "\n".join(f"{m['role']}: {m['content']}" for m in history[-6:])
                    )
                    answer = run_async(chat_completion(
                        system="You are a helpful coding assistant. Answer questions about the provided file(s). Be concise.",
                        user=prompt,
                    ))
                    history.append({"role": "assistant", "content": answer})
                except Exception as e:
                    history.append({"role": "assistant", "content": f"Error: {e}"})
        else:
            history.append({"role": "assistant", "content": "Set PA_LLM_API_KEY to enable chat."})

        st.session_state["file_chat_history"] = history
        st.rerun()


# =========================================================================
# SCREEN: task_fullscreen
# =========================================================================

def _screen_task_fullscreen():
    if st.button("← Back to Flow", key="fs_back"):
        _go_back()
        st.rerun()

    sel_id = st.session_state["selected_task_id"]
    task = board.tasks.get(sel_id) if sel_id else None

    if not task:
        st.info("No task selected.")
        return

    _render_detail(board, task, prefix="fs")


# =========================================================================
# SCREEN: flow — Flow graph + cards, collapsible detail
# =========================================================================

def _screen_flow():
    # Board name
    new_name = st.text_input("Board name", value=board.name, label_visibility="collapsed", key="bname")
    if new_name != board.name:
        board.name = new_name

    # Toggle detail panel
    tcol1, tcol2 = st.columns([5, 1])
    with tcol2:
        panel_label = "◀ Hide" if st.session_state["detail_open"] else "▶ Detail"
        if st.button(panel_label, key="toggle_detail", use_container_width=True):
            st.session_state["detail_open"] = not st.session_state["detail_open"]
            st.rerun()

    detail_open = st.session_state["detail_open"]

    if detail_open:
        col_flow, col_detail = st.columns([3, 2.5])
    else:
        col_flow = st.container()
        col_detail = None

    # --- FLOW column ---
    with col_flow:
        if st.button("＋ Add Task", key="flow_add", use_container_width=True):
            new_task = board.add_task(title="New task")
            st.session_state["selected_task_id"] = new_task.id
            st.session_state["detail_open"] = True
            st.rerun()

        if not board.tasks:
            st.info("No tasks yet. Click '＋ Add Task'.")
        else:
            # Mermaid flow graph
            lines = ["graph TD"]
            for t in board.tasks.values():
                safe_title = t.title.replace('"', "'").replace("\n", " ")
                shape_l, shape_r = ("[", "]")
                if t.status == TaskStatus.DONE:
                    shape_l, shape_r = ("([", "])")
                elif t.status == TaskStatus.IN_PROGRESS:
                    shape_l, shape_r = ("[[", "]]")

                lines.append(
                    f'    {t.id}{shape_l}"{_type_icon(t.task_type)} {safe_title}<br/>'
                    f'<small>{t.status.value}</small>"{shape_r}'
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
            <div style="background:#fff;padding:12px;border-radius:12px;overflow:auto;">
              <div id="flow-output"></div>
            </div>
            <script type="module">
              import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
              mermaid.initialize({{startOnLoad:false,theme:'default',securityLevel:'loose',
                flowchart:{{useMaxWidth:true,curve:'basis',htmlLabels:true}}}});
              try {{
                const {{svg}} = await mermaid.render('flow-graph',`{js_code}`);
                document.getElementById('flow-output').innerHTML = svg;
              }} catch(e) {{
                document.getElementById('flow-output').innerHTML =
                  '<pre style="color:#c00;font-size:11px;">'+e.message+'</pre>';
              }}
            </script>
            """
            st.components.v1.html(html, height=max(300, len(board.tasks) * 80), scrolling=True)

            # Card list
            st.markdown("---")
            for task in sorted(board.tasks.values(), key=lambda t: t.created_at):
                _render_card(task, board, key_prefix="fl")

    # --- DETAIL column ---
    if col_detail is not None:
        with col_detail:
            sel_id = st.session_state["selected_task_id"]
            task = board.tasks.get(sel_id) if sel_id else None
            if not task:
                st.markdown(
                    "<div style='text-align:center;padding:40px;color:#999;'>"
                    "<p style='font-size:1.5rem;'>👈</p>"
                    "<p>Click <b>Open</b> on a card</p>"
                    "<p style='font-size:0.8rem;'>or <b>⛶</b> for fullscreen</p></div>",
                    unsafe_allow_html=True,
                )
            else:
                _render_detail(board, task, prefix="d")

    # Legend
    st.markdown(
        """<div style="text-align:center;padding:4px;font-size:0.72rem;color:#888;">
            ── dep &nbsp; - - parent &nbsp;
            <span style="color:#6c757d;">■</span> To Do &nbsp;
            <span style="color:#0d6efd;">■</span> In Progress &nbsp;
            <span style="color:#198754;">■</span> Done &nbsp; | &nbsp;
            🧠 Intelligent &nbsp; 🔌 MCP &nbsp; 🐍 Code &nbsp; | &nbsp;
            <b>⛶</b> = fullscreen
        </div>""",
        unsafe_allow_html=True,
    )


# =========================================================================
# Route to current screen
# =========================================================================

screen = st.session_state["screen"]

if screen == "file_view":
    _screen_file_view()
elif screen == "task_fullscreen":
    _screen_task_fullscreen()
else:
    _screen_flow()
