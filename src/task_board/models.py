"""Task Board data models stored in session state."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class TaskStatus(str, Enum):
    TODO = "To Do"
    IN_PROGRESS = "In Progress"
    DONE = "Done"


class TaskType(str, Enum):
    INTELLIGENT = "Intelligent"  # LLM-based execution
    MCP = "MCP"  # MCP tool call — fill in fields
    CODE = "Code"  # Python code execution


@dataclass
class MCPConfig:
    """Configuration for MCP tool call tasks."""
    server: str = ""
    tool_name: str = ""
    parameters: dict[str, str] = field(default_factory=dict)


@dataclass
class Task:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str = ""
    description: str = ""  # prompt for LLM / code content / MCP description
    status: TaskStatus = TaskStatus.TODO
    task_type: TaskType = TaskType.INTELLIGENT
    code: str = ""  # Python code for CODE type
    mcp_config: MCPConfig = field(default_factory=MCPConfig)  # MCP type config
    parent_id: Optional[str] = None
    dependency_ids: list[str] = field(default_factory=list)
    input_artifacts: list[str] = field(default_factory=list)  # artifact keys
    output_artifact: Optional[str] = None  # artifact key
    output_content: Optional[str] = None  # generated content
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def touch(self):
        self.updated_at = datetime.now().isoformat(timespec="seconds")


@dataclass
class TaskBoard:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "New Task Board"
    tasks: dict[str, Task] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)  # key -> content
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    # ---- task helpers ----

    def add_task(self, **kwargs) -> Task:
        t = Task(**kwargs)
        self.tasks[t.id] = t
        return t

    def remove_task(self, task_id: str):
        self.tasks.pop(task_id, None)
        # Clean up references
        for t in self.tasks.values():
            if task_id in t.dependency_ids:
                t.dependency_ids.remove(task_id)
            if t.parent_id == task_id:
                t.parent_id = None

    def get_children(self, parent_id: str | None) -> list[Task]:
        """Return direct children sorted by created_at."""
        return sorted(
            [t for t in self.tasks.values() if t.parent_id == parent_id],
            key=lambda t: t.created_at,
        )

    def get_root_tasks(self) -> list[Task]:
        return self.get_children(None)

    def get_blocking(self, task: Task) -> list[Task]:
        """Return dependency tasks that are not Done."""
        blockers = []
        for dep_id in task.dependency_ids:
            dep = self.tasks.get(dep_id)
            if dep and dep.status != TaskStatus.DONE:
                blockers.append(dep)
        return blockers

    def is_runnable(self, task: Task) -> bool:
        return len(self.get_blocking(task)) == 0

    def save_artifact(self, key: str, content: str):
        self.artifacts[key] = content

    def all_task_ids_titles(self) -> list[tuple[str, str]]:
        """Return [(id, title), ...] for all tasks."""
        return [(t.id, t.title) for t in self.tasks.values() if t.title]
