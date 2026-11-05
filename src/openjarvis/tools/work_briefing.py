"""Work Briefing & Standup Assistant tool — executive productivity automation.

Synthesizes tasks, notes, deadlines, and system readiness into structured daily briefings
and standup reports directly through natural conversation.
"""

from __future__ import annotations

import json
import os
import platform
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from openjarvis.core.paths import get_config_dir
from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec


def _get_notes_file(custom_dir: Optional[Path] = None) -> Path:
    if custom_dir is not None:
        custom_dir.mkdir(parents=True, exist_ok=True)
        return custom_dir / "quick_notes.json"
    try:
        base_dir = get_config_dir()
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir / "quick_notes.json"
    except (PermissionError, OSError):
        fallback_dir = Path.cwd() / ".openjarvis_data"
        fallback_dir.mkdir(parents=True, exist_ok=True)
        return fallback_dir / "quick_notes.json"


def _load_notes(custom_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    nf = _get_notes_file(custom_dir)
    if not nf.exists():
        return []
    try:
        return json.loads(nf.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_notes(notes: List[Dict[str, Any]], custom_dir: Optional[Path] = None) -> None:
    nf = _get_notes_file(custom_dir)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=nf.parent, prefix="notes_tmp_")
    with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
        json.dump(notes, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, nf)


@ToolRegistry.register("work_briefing")
class WorkBriefingTool(BaseTool):
    """Executive daily briefing, standup report, and quick note assistant."""

    tool_id = "work_briefing"

    def __init__(self, storage_dir: Optional[Path] = None) -> None:
        self._storage_dir = storage_dir

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="work_briefing",
            description=(
                "Work assistant and briefing generator. Actions: "
                "'daily_briefing' (synthesizes date, tasks, and system readiness into a personal morning briefing), "
                "'standup' (formats a 3-part work standup report: Completed, Today's Focus, and Blockers), "
                "'quick_note' (save a quick thought or meeting takeaway), "
                "'list_notes' (view recent saved notes)."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["daily_briefing", "standup", "quick_note", "list_notes"],
                        "description": "Briefing action to perform.",
                    },
                    "note": {
                        "type": "string",
                        "description": "Note content to save for 'quick_note'.",
                    },
                    "tag": {
                        "type": "string",
                        "description": "Optional category or tag for the note (e.g. 'meeting', 'idea', 'followup').",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max notes to display for 'list_notes' (default: 10).",
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
                tool_name="work_briefing",
                content="Error: 'action' parameter is required.",
                success=False,
            )

        now = datetime.now()
        date_str = now.strftime("%A, %B %d, %Y (%I:%M %p)")

        # Load tasks from task_manage file if available
        tasks: List[Dict[str, Any]] = []
        try:
            from openjarvis.tools.task_manage import _get_tasks_file, _load_tasks
            tasks = _load_tasks(_get_tasks_file())
        except Exception:
            pass

        if action == "daily_briefing":
            pending = [t for t in tasks if t.get("status") == "pending"]
            in_prog = [t for t in tasks if t.get("status") == "in_progress"]
            urgent = [t for t in pending if t.get("priority") == "urgent"]
            high = [t for t in pending if t.get("priority") == "high"]

            # System check
            sys_info = f"{platform.system()} on {platform.machine()}"

            lines = [
                f"☀️ Good day! Here is your OpenJarvis Briefing for {date_str}:",
                f"System Environment: {sys_info}",
                "",
                "📋 Work & Tasks Overview:",
                f"  * In Progress: {len(in_prog)} item(s)",
                f"  * Pending Tasks: {len(pending)} item(s)",
            ]
            if urgent:
                lines.append("  * 🚨 URGENT ACTION REQUIRED:")
                for u in urgent:
                    lines.append(f"    - [#{u['id']}] {u.get('title')} (Due: {u.get('due_date') or 'ASAP'})")
            if high:
                lines.append("  * ⚡ High Priority:")
                for h in high:
                    lines.append(f"    - [#{h['id']}] {h.get('title')} [{h.get('category', 'general')}]")

            # Check recent notes
            notes = _load_notes(self._storage_dir)
            if notes:
                lines.append("\n📝 Recent Notes / Takeaways:")
                for n in notes[-3:]:
                    lines.append(f"  * [{n.get('tag', 'note')}] {n.get('content')} ({n.get('created_at', '')})")

            lines.append("\nJarvis is ready for your instructions.")
            return ToolResult(
                tool_name="work_briefing",
                content="\n".join(lines),
                success=True,
                metadata={"pending_count": len(pending), "urgent_count": len(urgent)},
            )

        elif action == "standup":
            completed = [t for t in tasks if t.get("status") == "completed"]
            active = [t for t in tasks if t.get("status") in ("pending", "in_progress")]
            urgent = [t for t in active if t.get("priority") in ("urgent", "high")]

            lines = [
                f"📊 Daily Standup Report — {now.strftime('%b %d, %Y')}",
                "",
                "1. What was completed recently:",
            ]
            if completed:
                for c in completed[-5:]:
                    lines.append(f"   - [Completed] {c.get('title')} [{c.get('category', 'general')}]")
            else:
                lines.append("   - No recently marked completed tasks.")

            lines.append("\n2. What is planned for today:")
            if active:
                for a in active[:6]:
                    status_badge = "In Progress" if a.get("status") == "in_progress" else "Planned"
                    lines.append(f"   - [{status_badge}] {a.get('title')} ({a.get('priority', 'medium')})")
            else:
                lines.append("   - Backlog is clear / No pending tasks.")

            lines.append("\n3. Blockers & High-Priority Attention:")
            if urgent:
                for u in urgent:
                    lines.append(f"   - ⚠️ {u.get('title')} (Priority: {u.get('priority')})")
            else:
                lines.append("   - No blockers currently logged.")

            return ToolResult(
                tool_name="work_briefing",
                content="\n".join(lines),
                success=True,
            )

        elif action == "quick_note":
            content = str(params.get("note", "")).strip()
            if not content:
                return ToolResult(
                    tool_name="work_briefing",
                    content="Error: 'note' text is required for quick_note.",
                    success=False,
                )
            tag = str(params.get("tag", "general")).strip().lower() or "general"
            notes = _load_notes(self._storage_dir)
            new_note = {
                "id": len(notes) + 1,
                "content": content,
                "tag": tag,
                "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            }
            notes.append(new_note)
            _save_notes(notes, self._storage_dir)
            return ToolResult(
                tool_name="work_briefing",
                content=f"Saved quick note #{new_note['id']} [{tag}]: '{content}'",
                success=True,
                metadata={"note": new_note},
            )

        elif action == "list_notes":
            limit = int(params.get("limit", 10))
            notes = _load_notes(self._storage_dir)
            if not notes:
                return ToolResult(
                    tool_name="work_briefing",
                    content="No notes saved yet. Use 'quick_note' to save your first note.",
                    success=True,
                    metadata={"notes": []},
                )
            display_notes = notes[-limit:]
            lines = [f"Showing {len(display_notes)} recent note(s):"]
            for n in reversed(display_notes):
                lines.append(f"- [#{n['id']}] ({n.get('tag', 'general')}) {n.get('content')} — {n.get('created_at')}")
            return ToolResult(
                tool_name="work_briefing",
                content="\n".join(lines),
                success=True,
                metadata={"notes": display_notes},
            )

        return ToolResult(
            tool_name="work_briefing",
            content=f"Unknown action: '{action}'. Allowed: daily_briefing, standup, quick_note, list_notes",
            success=False,
        )
