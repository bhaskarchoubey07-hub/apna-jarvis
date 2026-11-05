"""Unit tests for the work_briefing tool."""

from __future__ import annotations

import tempfile
from pathlib import Path

from openjarvis.core.registry import ToolRegistry
from openjarvis.tools.work_briefing import WorkBriefingTool


class TestWorkBriefingTool:
    def test_registered(self):
        assert ToolRegistry.contains("work_briefing")
        tool_cls = ToolRegistry.get("work_briefing")
        assert tool_cls is WorkBriefingTool

    def test_daily_briefing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = WorkBriefingTool(storage_dir=Path(tmpdir))
            res = tool.execute(action="daily_briefing")
            assert res.success is True
            assert "OpenJarvis Briefing" in res.content
            assert "Work & Tasks Overview:" in res.content

    def test_standup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = WorkBriefingTool(storage_dir=Path(tmpdir))
            res = tool.execute(action="standup")
            assert res.success is True
            assert "Daily Standup Report" in res.content
            assert "1. What was completed recently:" in res.content
            assert "2. What is planned for today:" in res.content
            assert "3. Blockers & High-Priority Attention:" in res.content

    def test_quick_notes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tool = WorkBriefingTool(storage_dir=Path(tmpdir))
            add_res = tool.execute(action="quick_note", note="Remember to check the deployment script", tag="ops")
            assert add_res.success is True
            assert "Saved quick note" in add_res.content

            list_res = tool.execute(action="list_notes")
            assert list_res.success is True
            assert "Remember to check the deployment script" in list_res.content
