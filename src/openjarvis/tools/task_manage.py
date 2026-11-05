"""Task & Reminder Management tool — conversational task automation for OpenJarvis.

Enables agents to create, list, complete, prioritize, and search tasks, reminders,
and to-dos stored persistently under the OpenJarvis user directory.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from openjarvis.core.paths import get_config_dir
from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

_VALID_PRIORITIES = {"low", "medium", "high", "urgent"}
_VALID_STATUSES = {"pending", "in_progress", "completed", "cancelled"}


def _get_tasks_file(custom_path: Optional[Path] = None) -> Path:
    if custom_path is not None:
        custom_path.parent.mkdir(parents=True, exist_ok=True)
        return custom_path
    try:
        base_dir = get_config_dir()
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir / "tasks.json"
    except (PermissionError, OSError):
        fallback_dir = Path.cwd() / ".openjarvis_data"
        fallback_dir.mkdir(parents=True, exist_ok=True)
        return fallback_dir / "tasks.json"


def _load_tasks(file_path: Path) -> List[Dict[str, Any]]:
    if not file_path.exists():
        return []
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "tasks" in data:
            return data["tasks"]
        return []
    except Exception:
        return []


def _save_tasks(file_path: Path, tasks: List[Dict[str, Any]]) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=file_path.parent, prefix="tasks_tmp_")
    with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, file_path)


@ToolRegistry.register("task_manage")
class TaskManageTool(BaseTool):
    """Conversational task and reminder management tool."""

    tool_id = "task_manage"

    def __init__(self, storage_path: Optional[Path] = None) -> None:
        self._storage_path = storage_path

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="task_manage",
            description=(
                "Conversational task, to-do, and reminder manager. "
                "Actions: 'add', 'list', 'complete', 'update', 'delete', 'search', 'summary', 'clear_completed'. "
                "Allows tracking work items with priorities (low/medium/high/urgent) and categories."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "add",
                            "list",
                            "complete",
                            "update",
                            "delete",
                            "search",
                            "summary",
                            "clear_completed",
                        ],
                        "description": "Task action to perform.",
                    },
                    "title": {
                        "type": "string",
                        "description": "Title or description of the task/reminder (for 'add' or 'update').",
                    },
                    "task_id": {
                        "type": "integer",
                        "description": "Numeric ID of the task to complete, update, or delete.",
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "urgent"],
                        "description": "Priority level (default: 'medium').",
                    },
                    "category": {
                        "type": "string",
                        "description": "Category tag, e.g. 'work', 'personal', 'code', 'meeting', 'errand'.",
                    },
                    "due_date": {
                        "type": "string",
                        "description": "Optional due date or time (e.g. '2026-11-07', 'today 5pm').",
                    },
                    "notes": {
                        "type": "string",
                        "description": "Additional context, notes, or checklist items.",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["pending", "in_progress", "completed", "cancelled", "all"],
                        "description": "Filter or update status (default: 'pending' for list).",
                    },
                    "query": {
                        "type": "string",
                        "description": "Search keyword for 'search' action.",
                    },
                },
                "required": ["action"],
            },
            category="productivity",
        )

    def execute(self, **params: Any) -> ToolResult:
        action = str(params.get("action", "")).strip().lower()
        if not action:
            return ToolResult(
                tool_name="task_manage",
                content="Error: 'action' parameter is required.",
                success=False,
            )

        file_path = _get_tasks_file(self._storage_path)
        tasks = _load_tasks(file_path)

        if action == "add":
            title = str(params.get("title", "")).strip()
            if not title:
                return ToolResult(
                    tool_name="task_manage",
                    content="Error: 'title' is required when adding a task.",
                    success=False,
                )
            priority = str(params.get("priority", "medium")).lower()
            if priority not in _VALID_PRIORITIES:
                priority = "medium"
            category = str(params.get("category", "general")).strip().lower() or "general"
            due_date = str(params.get("due_date", "")).strip()
            notes = str(params.get("notes", "")).strip()

            next_id = max([t.get("id", 0) for t in tasks], default=0) + 1
            now_iso = datetime.now().isoformat(timespec="seconds")

            new_task = {
                "id": next_id,
                "title": title,
                "priority": priority,
                "category": category,
                "status": "pending",
                "due_date": due_date,
                "notes": notes,
                "created_at": now_iso,
                "completed_at": None,
            }
            tasks.append(new_task)
            _save_tasks(file_path, tasks)
            return ToolResult(
                tool_name="task_manage",
                content=f"Task #{next_id} created: '{title}' [Priority: {priority.upper()}, Category: {category}]",
                success=True,
                metadata={"task": new_task},
            )

        elif action == "list":
            status_filter = str(params.get("status", "pending")).lower()
            category_filter = str(params.get("category", "")).lower()
            priority_filter = str(params.get("priority", "")).lower()

            filtered = tasks
            if status_filter and status_filter != "all":
                filtered = [t for t in filtered if t.get("status", "pending") == status_filter]
            if category_filter:
                filtered = [t for t in filtered if t.get("category", "") == category_filter]
            if priority_filter:
                filtered = [t for t in filtered if t.get("priority", "") == priority_filter]

            if not filtered:
                return ToolResult(
                    tool_name="task_manage",
                    content=f"No tasks found matching criteria (status: {status_filter or 'any'}).",
                    success=True,
                    metadata={"tasks": []},
                )

            lines = [f"Found {len(filtered)} task(s):"]
            for t in filtered:
                due_info = f" | Due: {t['due_date']}" if t.get("due_date") else ""
                lines.append(
                    f"- [#{t['id']}] [{t.get('status', 'pending').upper()}] ({t.get('priority', 'medium')}) "
                    f"{t.get('title')} [{t.get('category', 'general')}]{due_info}"
                )
                if t.get("notes"):
                    lines.append(f"    Notes: {t['notes']}")
            return ToolResult(
                tool_name="task_manage",
                content="\n".join(lines),
                success=True,
                metadata={"tasks": filtered},
            )

        elif action == "complete":
            tid = params.get("task_id")
            if tid is None:
                return ToolResult(
                    tool_name="task_manage",
                    content="Error: 'task_id' is required to mark a task as completed.",
                    success=False,
                )
            try:
                tid = int(tid)
            except ValueError:
                return ToolResult(
                    tool_name="task_manage",
                    content=f"Error: Invalid task_id '{tid}'. Must be an integer.",
                    success=False,
                )

            for t in tasks:
                if t.get("id") == tid:
                    t["status"] = "completed"
                    t["completed_at"] = datetime.now().isoformat(timespec="seconds")
                    _save_tasks(file_path, tasks)
                    return ToolResult(
                        tool_name="task_manage",
                        content=f"Task #{tid} marked as completed: '{t.get('title')}'",
                        success=True,
                        metadata={"task": t},
                    )
            return ToolResult(
                tool_name="task_manage",
                content=f"Error: Task #{tid} not found.",
                success=False,
            )

        elif action == "update":
            tid = params.get("task_id")
            if tid is None:
                return ToolResult(
                    tool_name="task_manage",
                    content="Error: 'task_id' is required for 'update'.",
                    success=False,
                )
            try:
                tid = int(tid)
            except ValueError:
                return ToolResult(
                    tool_name="task_manage",
                    content=f"Error: Invalid task_id '{tid}'.",
                    success=False,
                )

            found = False
            for t in tasks:
                if t.get("id") == tid:
                    found = True
                    if "title" in params and params["title"]:
                        t["title"] = str(params["title"]).strip()
                    if "priority" in params and params["priority"].lower() in _VALID_PRIORITIES:
                        t["priority"] = params["priority"].lower()
                    if "status" in params and params["status"].lower() in _VALID_STATUSES:
                        t["status"] = params["status"].lower()
                        if t["status"] == "completed" and not t.get("completed_at"):
                            t["completed_at"] = datetime.now().isoformat(timespec="seconds")
                    if "category" in params and params["category"]:
                        t["category"] = str(params["category"]).strip().lower()
                    if "due_date" in params:
                        t["due_date"] = str(params["due_date"]).strip()
                    if "notes" in params:
                        t["notes"] = str(params["notes"]).strip()
                    _save_tasks(file_path, tasks)
                    return ToolResult(
                        tool_name="task_manage",
                        content=f"Task #{tid} updated successfully.",
                        success=True,
                        metadata={"task": t},
                    )
            return ToolResult(
                tool_name="task_manage",
                content=f"Error: Task #{tid} not found.",
                success=False,
            )

        elif action == "delete":
            tid = params.get("task_id")
            if tid is None:
                return ToolResult(
                    tool_name="task_manage",
                    content="Error: 'task_id' is required for 'delete'.",
                    success=False,
                )
            try:
                tid = int(tid)
            except ValueError:
                return ToolResult(
                    tool_name="task_manage",
                    content=f"Error: Invalid task_id '{tid}'.",
                    success=False,
                )

            initial_len = len(tasks)
            tasks = [t for t in tasks if t.get("id") != tid]
            if len(tasks) < initial_len:
                _save_tasks(file_path, tasks)
                return ToolResult(
                    tool_name="task_manage",
                    content=f"Task #{tid} deleted.",
                    success=True,
                )
            return ToolResult(
                tool_name="task_manage",
                content=f"Error: Task #{tid} not found.",
                success=False,
            )

        elif action == "search":
            query = str(params.get("query", "")).strip().lower()
            if not query:
                return ToolResult(
                    tool_name="task_manage",
                    content="Error: 'query' parameter is required for search.",
                    success=False,
                )
            matches = [
                t
                for t in tasks
                if query in t.get("title", "").lower()
                or query in t.get("notes", "").lower()
                or query in t.get("category", "").lower()
            ]
            if not matches:
                return ToolResult(
                    tool_name="task_manage",
                    content=f"No tasks found matching '{query}'.",
                    success=True,
                    metadata={"tasks": []},
                )
            lines = [f"Found {len(matches)} matching task(s):"]
            for t in matches:
                lines.append(
                    f"- [#{t['id']}] [{t.get('status', 'pending').upper()}] {t.get('title')} ({t.get('priority')})"
                )
            return ToolResult(
                tool_name="task_manage",
                content="\n".join(lines),
                success=True,
                metadata={"tasks": matches},
            )

        elif action == "summary":
            pending = [t for t in tasks if t.get("status") == "pending"]
            in_progress = [t for t in tasks if t.get("status") == "in_progress"]
            completed = [t for t in tasks if t.get("status") == "completed"]
            urgent = [t for t in pending if t.get("priority") == "urgent"]
            high = [t for t in pending if t.get("priority") == "high"]

            lines = [
                "=== Task & Routine Summary ===",
                f"Total tasks: {len(tasks)} (Pending: {len(pending)}, In Progress: {len(in_progress)}, Completed: {len(completed)})",
            ]
            if urgent:
                lines.append("\n⚠️ URGENT Items:")
                for t in urgent:
                    lines.append(f"  * [#{t['id']}] {t.get('title')} (Due: {t.get('due_date') or 'No date'})")
            if high:
                lines.append("\n⚡ High Priority Items:")
                for t in high:
                    lines.append(f"  * [#{t['id']}] {t.get('title')} [{t.get('category')}]")
            if not urgent and not high and pending:
                lines.append("\nUpcoming Pending Items:")
                for t in pending[:5]:
                    lines.append(f"  * [#{t['id']}] {t.get('title')} ({t.get('priority')})")
            return ToolResult(
                tool_name="task_manage",
                content="\n".join(lines),
                success=True,
                metadata={
                    "total": len(tasks),
                    "pending": len(pending),
                    "in_progress": len(in_progress),
                    "completed": len(completed),
                    "urgent_count": len(urgent),
                },
            )

        elif action == "clear_completed":
            before = len(tasks)
            tasks = [t for t in tasks if t.get("status") != "completed"]
            cleared = before - len(tasks)
            _save_tasks(file_path, tasks)
            return ToolResult(
                tool_name="task_manage",
                content=f"Cleared {cleared} completed task(s).",
                success=True,
            )

        return ToolResult(
            tool_name="task_manage",
            content=f"Unknown action: '{action}'. Allowed: add, list, complete, update, delete, search, summary, clear_completed",
            success=False,
        )
