"""Desktop & System Automation tool — operate your environment conversationally.

Provides safe access to system clipboard, hardware vitals, disk space, and
quick application/folder launching across Windows, macOS, and Linux.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Any, Dict, Optional

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec


def _get_clipboard_text() -> str:
    """Read text from the system clipboard across platforms."""
    system = platform.system()
    if system == "Windows":
        try:
            cmd = ["powershell", "-NoProfile", "-Command", "Get-Clipboard"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            return res.stdout.rstrip("\r\n")
        except Exception:
            return ""
    elif system == "Darwin":
        try:
            res = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=5)
            return res.stdout
        except Exception:
            return ""
    else:
        # Linux
        for binary, args in [("wl-paste", []), ("xclip", ["-selection", "clipboard", "-o"]), ("xsel", ["--clipboard", "--output"])]:
            if shutil.which(binary):
                try:
                    res = subprocess.run([binary] + args, capture_output=True, text=True, timeout=5)
                    return res.stdout
                except Exception:
                    pass
    return ""


def _set_clipboard_text(text: str) -> bool:
    """Write text to the system clipboard across platforms."""
    system = platform.system()
    if system == "Windows":
        try:
            proc = subprocess.Popen(
                ["powershell", "-NoProfile", "-Command", "$input | Set-Clipboard"],
                stdin=subprocess.PIPE,
                text=True,
            )
            proc.communicate(input=text, timeout=5)
            return proc.returncode == 0
        except Exception:
            return False
    elif system == "Darwin":
        try:
            proc = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE, text=True)
            proc.communicate(input=text, timeout=5)
            return proc.returncode == 0
        except Exception:
            return False
    else:
        # Linux
        for binary, args in [("wl-copy", []), ("xclip", ["-selection", "clipboard"]), ("xsel", ["--clipboard", "--input"])]:
            if shutil.which(binary):
                try:
                    proc = subprocess.Popen([binary] + args, stdin=subprocess.PIPE, text=True)
                    proc.communicate(input=text, timeout=5)
                    return proc.returncode == 0
                except Exception:
                    pass
    return False


@ToolRegistry.register("desktop_automation")
class DesktopAutomationTool(BaseTool):
    """System, desktop, and workspace automation tool."""

    tool_id = "desktop_automation"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="desktop_automation",
            description=(
                "Desktop and system automation. Actions: "
                "'clipboard_get' (read current clipboard text), "
                "'clipboard_set' (copy text to clipboard), "
                "'system_vitals' (check CPU, RAM, disk space, battery), "
                "'open_path' (open a local directory or file in default file manager), "
                "'open_url' (open a web URL in default browser)."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [
                            "clipboard_get",
                            "clipboard_set",
                            "system_vitals",
                            "open_path",
                            "open_url",
                        ],
                        "description": "Desktop automation action to execute.",
                    },
                    "text": {
                        "type": "string",
                        "description": "Text content to copy for 'clipboard_set'.",
                    },
                    "path": {
                        "type": "string",
                        "description": "Local file or directory path to open for 'open_path'.",
                    },
                    "url": {
                        "type": "string",
                        "description": "Web URL (http/https) to open for 'open_url'.",
                    },
                },
                "required": ["action"],
            },
            category="system",
        )

    def execute(self, **params: Any) -> ToolResult:
        action = str(params.get("action", "")).strip().lower()
        if not action:
            return ToolResult(
                tool_name="desktop_automation",
                content="Error: 'action' parameter is required.",
                success=False,
            )

        if action == "clipboard_get":
            content = _get_clipboard_text()
            if not content:
                return ToolResult(
                    tool_name="desktop_automation",
                    content="Clipboard is empty or could not be accessed.",
                    success=True,
                    metadata={"content": ""},
                )
            preview = content if len(content) <= 3000 else content[:3000] + "... (truncated)"
            return ToolResult(
                tool_name="desktop_automation",
                content=f"Clipboard content ({len(content)} chars):\n{preview}",
                success=True,
                metadata={"full_content": content, "length": len(content)},
            )

        elif action == "clipboard_set":
            text = params.get("text")
            if text is None:
                return ToolResult(
                    tool_name="desktop_automation",
                    content="Error: 'text' parameter is required for clipboard_set.",
                    success=False,
                )
            text_str = str(text)
            ok = _set_clipboard_text(text_str)
            if ok:
                return ToolResult(
                    tool_name="desktop_automation",
                    content=f"Copied {len(text_str)} characters to system clipboard successfully.",
                    success=True,
                )
            return ToolResult(
                tool_name="desktop_automation",
                content="Failed to set clipboard content (platform utility unavailable).",
                success=False,
            )

        elif action == "system_vitals":
            vitals: Dict[str, Any] = {
                "os": f"{platform.system()} {platform.release()}",
                "python": platform.python_version(),
                "machine": platform.machine(),
            }
            lines = [
                "=== System Health & Vitals ===",
                f"OS: {vitals['os']} ({vitals['machine']})",
                f"Python: {vitals['python']}",
            ]

            # Try psutil if available
            try:
                import psutil  # type: ignore

                cpu_count = psutil.cpu_count(logical=True)
                cpu_pct = psutil.cpu_percent(interval=0.1)
                mem = psutil.virtual_memory()
                vitals["cpu_percent"] = cpu_pct
                vitals["cpu_cores"] = cpu_count
                vitals["ram_total_gb"] = round(mem.total / (1024**3), 1)
                vitals["ram_available_gb"] = round(mem.available / (1024**3), 1)
                vitals["ram_used_percent"] = mem.percent

                lines.append(f"CPU: {cpu_pct}% load ({cpu_count} logical cores)")
                lines.append(
                    f"Memory (RAM): {vitals['ram_available_gb']} GB available / {vitals['ram_total_gb']} GB total ({mem.percent}% used)"
                )

                # Disk usage
                cwd = Path.cwd()
                disk = psutil.disk_usage(str(cwd))
                vitals["disk_free_gb"] = round(disk.free / (1024**3), 1)
                vitals["disk_total_gb"] = round(disk.total / (1024**3), 1)
                vitals["disk_used_percent"] = disk.percent
                lines.append(
                    f"Disk ({cwd.anchor or '/'}): {vitals['disk_free_gb']} GB free / {vitals['disk_total_gb']} GB total ({disk.percent}% used)"
                )

                # Battery if exists
                if hasattr(psutil, "sensors_battery"):
                    battery = psutil.sensors_battery()
                    if battery:
                        vitals["battery_percent"] = battery.percent
                        vitals["power_plugged"] = battery.power_plugged
                        plug_str = "Plugged in" if battery.power_plugged else "On battery"
                        lines.append(f"Battery: {battery.percent}% ({plug_str})")
            except Exception:
                # Fallback to shutil.disk_usage
                try:
                    usage = shutil.disk_usage(Path.cwd())
                    free_gb = round(usage.free / (1024**3), 1)
                    total_gb = round(usage.total / (1024**3), 1)
                    lines.append(f"Disk: {free_gb} GB free / {total_gb} GB total")
                except Exception:
                    pass

            return ToolResult(
                tool_name="desktop_automation",
                content="\n".join(lines),
                success=True,
                metadata=vitals,
            )

        elif action == "open_path":
            path_str = str(params.get("path", "")).strip()
            if not path_str:
                return ToolResult(
                    tool_name="desktop_automation",
                    content="Error: 'path' parameter is required for open_path.",
                    success=False,
                )
            target = Path(path_str).expanduser().resolve()
            if not target.exists():
                return ToolResult(
                    tool_name="desktop_automation",
                    content=f"Error: Path does not exist: {path_str}",
                    success=False,
                )

            system = platform.system()
            try:
                if system == "Windows":
                    os.startfile(str(target))  # type: ignore[attr-defined]
                elif system == "Darwin":
                    subprocess.run(["open", str(target)], check=True, timeout=5)
                else:
                    subprocess.run(["xdg-open", str(target)], check=True, timeout=5)
                return ToolResult(
                    tool_name="desktop_automation",
                    content=f"Opened successfully in default application: {target}",
                    success=True,
                )
            except Exception as exc:
                return ToolResult(
                    tool_name="desktop_automation",
                    content=f"Error opening {path_str}: {exc}",
                    success=False,
                )

        elif action == "open_url":
            url = str(params.get("url", "")).strip()
            if not url or not (url.startswith("http://") or url.startswith("https://")):
                return ToolResult(
                    tool_name="desktop_automation",
                    content="Error: A valid URL starting with http:// or https:// is required.",
                    success=False,
                )
            try:
                webbrowser.open(url)
                return ToolResult(
                    tool_name="desktop_automation",
                    content=f"Opened URL in default web browser: {url}",
                    success=True,
                )
            except Exception as exc:
                return ToolResult(
                    tool_name="desktop_automation",
                    content=f"Error opening browser URL: {exc}",
                    success=False,
                )

        return ToolResult(
            tool_name="desktop_automation",
            content=f"Unknown action: '{action}'. Allowed: clipboard_get, clipboard_set, system_vitals, open_path, open_url",
            success=False,
        )

