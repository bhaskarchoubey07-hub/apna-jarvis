"""Unit tests for the task_manage tool."""

from __future__ import annotations

import tempfile
from pathlib import Path

from openjarvis.core.registry import ToolRegistry
from openjarvis.tools.task_manage import TaskManageTool


class TestTaskManageTool:
    def test_registered(self):
        assert ToolRegistry.contains("task_manage")
        tool_cls = ToolRegistry.get("task_manage")
        assert tool_cls is TaskManageTool

    def test_add_and_list_tasks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_file = Path(tmpdir) / "test_tasks.json"
            tool = TaskManageTool(storage_path=db_file)

            # Add tasks
            res1 = tool.execute(action="add", title="Write architecture RFC", priority="high", category="work")
            assert res1.success is True
            assert "Task #1 created" in res1.content

            res2 = tool.execute(action="add", title="Buy coffee beans", priority="low", category="personal")
            assert res2.success is True
            assert "Task #2 created" in res2.content

            # List all pending
            list_res = tool.execute(action="list", status="pending")
            assert list_res.success is True
            assert "Write architecture RFC" in list_res.content
            assert "Buy coffee beans" in list_res.content

            # Filter by category
            filter_res = tool.execute(action="list", category="work")
            assert filter_res.success is True
            assert "Write architecture RFC" in filter_res.content
            assert "Buy coffee beans" not in filter_res.content

    def test_complete_and_delete_task(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_file = Path(tmpdir) / "test_tasks.json"
            tool = TaskManageTool(storage_path=db_file)

            tool.execute(action="add", title="Prepare release notes", priority="urgent")
            comp_res = tool.execute(action="complete", task_id=1)
            assert comp_res.success is True
            assert "marked as completed" in comp_res.content

            # Verify in summary
            sum_res = tool.execute(action="summary")
            assert sum_res.success is True
            assert "Completed: 1" in sum_res.content

            # Delete
            del_res = tool.execute(action="delete", task_id=1)
            assert del_res.success is True
            assert "Task #1 deleted" in del_res.content

    def test_search_and_update(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_file = Path(tmpdir) / "test_tasks.json"
            tool = TaskManageTool(storage_path=db_file)

            tool.execute(action="add", title="Fix SQLite concurrency lock", priority="medium")
            # Search
            s_res = tool.execute(action="search", query="sqlite")
            assert s_res.success is True
            assert "Fix SQLite concurrency lock" in s_res.content

            # Update
            up_res = tool.execute(action="update", task_id=1, priority="urgent", notes="Must patch before merge")
            assert up_res.success is True
            assert "updated successfully" in up_res.content

