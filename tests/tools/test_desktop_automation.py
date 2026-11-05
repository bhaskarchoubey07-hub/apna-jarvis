"""Unit tests for the desktop_automation tool."""

from __future__ import annotations

from openjarvis.core.registry import ToolRegistry
from openjarvis.tools.desktop_automation import DesktopAutomationTool


class TestDesktopAutomationTool:
    def test_registered(self):
        assert ToolRegistry.contains("desktop_automation")
        tool_cls = ToolRegistry.get("desktop_automation")
        assert tool_cls is DesktopAutomationTool

    def test_spec(self):
        tool = DesktopAutomationTool()
        assert tool.spec.name == "desktop_automation"
        assert "clipboard_get" in tool.spec.parameters["properties"]["action"]["enum"]
        assert "system_vitals" in tool.spec.parameters["properties"]["action"]["enum"]

    def test_system_vitals(self):
        tool = DesktopAutomationTool()
        res = tool.execute(action="system_vitals")
        assert res.success is True
        assert "System Health & Vitals" in res.content
        assert "OS:" in res.content

    def test_open_url_validation(self):
        tool = DesktopAutomationTool()
        # Invalid URL
        res = tool.execute(action="open_url", url="ftp://bad-url")
        assert res.success is False
        assert "valid URL starting with http" in res.content

    def test_open_path_nonexistent(self):
        tool = DesktopAutomationTool()
        res = tool.execute(action="open_path", path="non_existent_folder_xyz_12345")
        assert res.success is False
        assert "does not exist" in res.content

