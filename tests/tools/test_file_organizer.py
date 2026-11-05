"""Unit tests for the file_organizer tool."""

from __future__ import annotations

import tempfile
from pathlib import Path

from openjarvis.core.registry import ToolRegistry
from openjarvis.tools.file_organizer import FileOrganizerTool


class TestFileOrganizerTool:
    def test_registered(self):
        assert ToolRegistry.contains("file_organizer")
        tool_cls = ToolRegistry.get("file_organizer")
        assert tool_cls is FileOrganizerTool

    def test_organize_dry_run_and_execution(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            doc_file = base / "report.pdf"
            doc_file.write_text("dummy pdf", encoding="utf-8")
            img_file = base / "chart.png"
            img_file.write_text("dummy png", encoding="utf-8")

            tool = FileOrganizerTool()

            # Dry run test
            preview = tool.execute(action="organize", directory=str(base), dry_run=True)
            assert preview.success is True
            assert "PREVIEW:" in preview.content
            assert "report.pdf -> Documents/" in preview.content
            assert "chart.png -> Images/" in preview.content
            assert doc_file.exists()

            # Real execution
            run_res = tool.execute(action="organize", directory=str(base), dry_run=False)
            assert run_res.success is True
            assert (base / "Documents" / "report.pdf").exists()
            assert (base / "Images" / "chart.png").exists()

    def test_find_duplicates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            f1 = base / "file1.txt"
            f2 = base / "file2.txt"
            f1.write_text("Identical duplicate content 12345", encoding="utf-8")
            f2.write_text("Identical duplicate content 12345", encoding="utf-8")

            tool = FileOrganizerTool()
            res = tool.execute(action="find_duplicates", directory=str(base))
            assert res.success is True
            assert "duplicate" in res.content.lower()
            assert "file1.txt" in res.content
            assert "file2.txt" in res.content

    def test_clean_temp(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            junk = base / "debug.log"
            junk.write_text("junk log", encoding="utf-8")

            tool = FileOrganizerTool()
            res = tool.execute(action="clean_temp", directory=str(base), dry_run=False)
            assert res.success is True
            assert not junk.exists()

