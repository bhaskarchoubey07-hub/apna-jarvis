"""File Organizer & Workspace Cleaner tool — automated file management for OpenJarvis.

Allows users to organize messy folders (such as Downloads or Desktop), find large files,
detect exact duplicates by SHA-256 hash, and clean temp/cache files safely.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

_CATEGORIES: Dict[str, Set[str]] = {
    "Documents": {".pdf", ".docx", ".doc", ".txt", ".xlsx", ".xls", ".pptx", ".csv", ".md", ".rtf", ".epub"},
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".ico", ".tiff"},
    "Media": {".mp4", ".mkv", ".mov", ".avi", ".mp3", ".wav", ".flac", ".m4a", ".aac"},
    "Archives": {".zip", ".tar", ".gz", ".7z", ".rar", ".bz2", ".xz", ".iso"},
    "Code": {".py", ".rs", ".js", ".ts", ".html", ".css", ".json", ".yaml", ".toml", ".sql", ".sh", ".ps1"},
    "Installers": {".exe", ".msi", ".dmg", ".pkg", ".deb", ".rpm", ".apk"},
}

_TEMP_EXTENSIONS = {".tmp", ".temp", ".log", ".pyc", ".bak", ".swp"}
_TEMP_FILENAMES = {"thumbs.db", ".ds_store", "desktop.ini"}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


@ToolRegistry.register("file_organizer")
class FileOrganizerTool(BaseTool):
    """Automated file organizer, duplicate finder, and workspace cleaner."""

    tool_id = "file_organizer"

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="file_organizer",
            description=(
                "Smart file and workspace organizer. Actions: "
                "'organize' (sorts files by type into Documents, Images, Media, Archives, Code, Installers subfolders), "
                "'find_large' (find files exceeding min_size_mb), "
                "'find_duplicates' (find identical duplicate files by SHA-256 hash), "
                "'clean_temp' (detect/remove temp files and caches). "
                "Supports 'dry_run' (default: true) so you can preview changes safely."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["organize", "find_large", "find_duplicates", "clean_temp"],
                        "description": "File automation action to perform.",
                    },
                    "directory": {
                        "type": "string",
                        "description": "Target folder to inspect or organize (e.g. 'Downloads', current folder, or full path).",
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "If true (default), reports planned changes without moving or deleting anything.",
                    },
                    "min_size_mb": {
                        "type": "number",
                        "description": "Minimum size in MB for 'find_large' (default: 50).",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 20).",
                    },
                },
                "required": ["action"],
            },
            category="filesystem",
        )

    def execute(self, **params: Any) -> ToolResult:
        action = str(params.get("action", "")).strip().lower()
        if not action:
            return ToolResult(
                tool_name="file_organizer",
                content="Error: 'action' parameter is required.",
                success=False,
            )

        dir_str = str(params.get("directory", "")).strip() or "."
        target_dir = Path(dir_str).expanduser().resolve()
        if not target_dir.exists() or not target_dir.is_dir():
            return ToolResult(
                tool_name="file_organizer",
                content=f"Error: Target directory does not exist or is not a directory: {target_dir}",
                success=False,
            )

        dry_run = params.get("dry_run", True)
        if isinstance(dry_run, str):
            dry_run = dry_run.lower() in ("true", "1", "yes")

        if action == "organize":
            moves: List[Tuple[Path, Path, str]] = []
            for item in target_dir.iterdir():
                if item.is_file() and not item.name.startswith("."):
                    ext = item.suffix.lower()
                    matched_category = None
                    for cat_name, extensions in _CATEGORIES.items():
                        if ext in extensions:
                            matched_category = cat_name
                            break
                    if matched_category:
                        dest_folder = target_dir / matched_category
                        dest_file = dest_folder / item.name
                        moves.append((item, dest_file, matched_category))

            if not moves:
                return ToolResult(
                    tool_name="file_organizer",
                    content=f"No unorganized files found in '{target_dir}'.",
                    success=True,
                )

            lines = [
                f"{'PREVIEW: Files to organize' if dry_run else 'SUCCESS: Organized files'} in '{target_dir}':",
                f"Total matching files: {len(moves)}",
            ]
            for src, dest, cat in moves[:25]:
                lines.append(f"  * {src.name} -> {cat}/")
            if len(moves) > 25:
                lines.append(f"  ... and {len(moves) - 25} more file(s).")

            if dry_run:
                lines.append("\n(Dry run enabled. Pass dry_run=false to execute these moves.)")
            else:
                for src, dest, cat in moves:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    # Avoid overwrite if file exists with same name
                    final_dest = dest
                    counter = 1
                    while final_dest.exists() and final_dest != src:
                        final_dest = dest.parent / f"{dest.stem}_{counter}{dest.suffix}"
                        counter += 1
                    shutil.move(str(src), str(final_dest))

            return ToolResult(
                tool_name="file_organizer",
                content="\n".join(lines),
                success=True,
                metadata={"total_files": len(moves), "dry_run": dry_run},
            )

        elif action == "find_large":
            min_mb = float(params.get("min_size_mb", 50.0))
            min_bytes = int(min_mb * 1024 * 1024)
            limit = int(params.get("limit", 20))

            large_files: List[Tuple[Path, int]] = []
            for root, _, files in os.walk(target_dir):
                for f in files:
                    fp = Path(root) / f
                    try:
                        sz = fp.stat().st_size
                        if sz >= min_bytes:
                            large_files.append((fp, sz))
                    except (OSError, PermissionError):
                        continue

            large_files.sort(key=lambda x: x[1], reverse=True)
            if not large_files:
                return ToolResult(
                    tool_name="file_organizer",
                    content=f"No files larger than {min_mb} MB found in '{target_dir}'.",
                    success=True,
                    metadata={"count": 0},
                )

            lines = [f"Found {len(large_files)} file(s) larger than {min_mb} MB (showing top {min(limit, len(large_files))}):"]
            for fp, sz in large_files[:limit]:
                mb = round(sz / (1024 * 1024), 1)
                lines.append(f"  - {mb} MB: {fp.relative_to(target_dir)}")

            return ToolResult(
                tool_name="file_organizer",
                content="\n".join(lines),
                success=True,
                metadata={"count": len(large_files)},
            )

        elif action == "find_duplicates":
            # Group by size first for efficiency
            size_map: Dict[int, List[Path]] = {}
            for item in target_dir.iterdir():
                if item.is_file():
                    try:
                        sz = item.stat().st_size
                        if sz > 0:
                            size_map.setdefault(sz, []).append(item)
                    except (OSError, PermissionError):
                        continue

            duplicates: Dict[str, List[Path]] = {}
            wasted_bytes = 0
            for sz, paths in size_map.items():
                if len(paths) > 1:
                    hash_map: Dict[str, List[Path]] = {}
                    for p in paths:
                        try:
                            h = _sha256(p)
                            hash_map.setdefault(h, []).append(p)
                        except (OSError, PermissionError):
                            continue
                    for h, matched_paths in hash_map.items():
                        if len(matched_paths) > 1:
                            duplicates[h] = matched_paths
                            wasted_bytes += sz * (len(matched_paths) - 1)

            if not duplicates:
                return ToolResult(
                    tool_name="file_organizer",
                    content=f"No duplicate files found in '{target_dir}'.",
                    success=True,
                    metadata={"duplicate_sets": 0},
                )

            wasted_mb = round(wasted_bytes / (1024 * 1024), 2)
            lines = [
                f"Found {len(duplicates)} set(s) of exact duplicate files (potential space savings: {wasted_mb} MB):"
            ]
            for h, paths in list(duplicates.items())[:15]:
                lines.append(f"\nDuplicate group ({round(paths[0].stat().st_size / (1024*1024), 2)} MB each):")
                for p in paths:
                    lines.append(f"  * {p.name}")

            return ToolResult(
                tool_name="file_organizer",
                content="\n".join(lines),
                success=True,
                metadata={"duplicate_sets": len(duplicates), "wasted_bytes": wasted_bytes},
            )

        elif action == "clean_temp":
            temp_files: List[Path] = []
            for root, dirs, files in os.walk(target_dir):
                for f in files:
                    fp = Path(root) / f
                    if fp.suffix.lower() in _TEMP_EXTENSIONS or fp.name.lower() in _TEMP_FILENAMES:
                        temp_files.append(fp)

            if not temp_files:
                return ToolResult(
                    tool_name="file_organizer",
                    content=f"No temporary or cache files found in '{target_dir}'.",
                    success=True,
                )

            lines = [
                f"{'PREVIEW: Temp files to clean' if dry_run else 'SUCCESS: Cleaned temp files'} in '{target_dir}':",
                f"Found {len(temp_files)} file(s).",
            ]
            for tf in temp_files[:20]:
                lines.append(f"  - {tf.relative_to(target_dir)}")
            if len(temp_files) > 20:
                lines.append(f"  ... and {len(temp_files) - 20} more.")

            if dry_run:
                lines.append("\n(Dry run enabled. Pass dry_run=false to delete these files.)")
            else:
                deleted = 0
                for tf in temp_files:
                    try:
                        tf.unlink()
                        deleted += 1
                    except OSError:
                        pass
                lines.append(f"\nDeleted {deleted} temporary file(s).")

            return ToolResult(
                tool_name="file_organizer",
                content="\n".join(lines),
                success=True,
                metadata={"found": len(temp_files), "dry_run": dry_run},
            )

        return ToolResult(
            tool_name="file_organizer",
            content=f"Unknown action: '{action}'. Allowed: organize, find_large, find_duplicates, clean_temp",
            success=False,
        )

