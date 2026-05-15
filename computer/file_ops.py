"""
YAHAVIS — computer/file_ops.py
File system operations: search, open, move, copy, delete, create.
"""

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

import send2trash

log = logging.getLogger("yahavis.file_ops")


class FileOps:
    """Safe file system operations for YAHAVIS."""

    def search(
        self,
        folder: str = "~/Downloads",
        extension: Optional[str] = None,
        query: Optional[str] = None,
        recursive: bool = True,
    ) -> List[Path]:
        """Search for files matching extension and/or name query."""
        folder_path = Path(folder).expanduser()
        if not folder_path.exists():
            log.warning(f"Folder not found: {folder_path}")
            return []

        pattern = f"**/*" if recursive else "*"
        if extension:
            ext = extension if extension.startswith(".") else f".{extension}"
            pattern = f"**/*{ext}" if recursive else f"*{ext}"

        results = list(folder_path.glob(pattern))

        if query:
            query_lower = query.lower()
            results = [f for f in results if query_lower in f.name.lower()]

        log.info(f"Found {len(results)} files in {folder_path}")
        return sorted(results, key=lambda p: p.stat().st_mtime, reverse=True)

    def open_file(self, path: str):
        """Open a file with the default system application."""
        p = Path(path).expanduser()
        if not p.exists():
            raise FileNotFoundError(f"File not found: {p}")
        log.info(f"Opening: {p}")
        if sys.platform == "win32":
            os.startfile(str(p))
        elif sys.platform == "darwin":
            subprocess.run(["open", str(p)])
        else:
            subprocess.run(["xdg-open", str(p)])

    def open_folder(self, path: str):
        """Open a folder in File Explorer / Finder."""
        p = Path(path).expanduser()
        if sys.platform == "win32":
            subprocess.run(["explorer", str(p)])
        elif sys.platform == "darwin":
            subprocess.run(["open", str(p)])
        else:
            subprocess.run(["xdg-open", str(p)])

    def copy(self, src: str, dst: str) -> Path:
        src_p, dst_p = Path(src).expanduser(), Path(dst).expanduser()
        if src_p.is_file():
            result = shutil.copy2(str(src_p), str(dst_p))
        else:
            result = shutil.copytree(str(src_p), str(dst_p))
        log.info(f"Copied: {src_p} → {dst_p}")
        return Path(result)

    def move(self, src: str, dst: str) -> Path:
        src_p = Path(src).expanduser()
        dst_p = Path(dst).expanduser()
        result = shutil.move(str(src_p), str(dst_p))
        log.info(f"Moved: {src_p} → {dst_p}")
        return Path(result)

    def delete(self, path: str, permanent: bool = False):
        """Delete a file or folder. Moves to trash by default (safe)."""
        p = Path(path).expanduser()
        if permanent:
            if p.is_file():
                p.unlink()
            else:
                shutil.rmtree(str(p))
            log.info(f"Permanently deleted: {p}")
        else:
            send2trash.send2trash(str(p))
            log.info(f"Moved to trash: {p}")

    def create_file(self, path: str, content: str = "") -> Path:
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        log.info(f"Created file: {p}")
        return p

    def create_folder(self, path: str) -> Path:
        p = Path(path).expanduser()
        p.mkdir(parents=True, exist_ok=True)
        log.info(f"Created folder: {p}")
        return p

    def read_file(self, path: str) -> str:
        p = Path(path).expanduser()
        return p.read_text(encoding="utf-8", errors="replace")

    def write_file(self, path: str, content: str):
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    def get_info(self, path: str) -> dict:
        p = Path(path).expanduser()
        stat = p.stat()
        return {
            "name": p.name,
            "path": str(p.absolute()),
            "size_bytes": stat.st_size,
            "size_human": self._human_size(stat.st_size),
            "modified": stat.st_mtime,
            "is_file": p.is_file(),
            "is_dir": p.is_dir(),
            "extension": p.suffix,
        }

    def list_directory(self, path: str = "~") -> list:
        p = Path(path).expanduser()
        return sorted(
            [{"name": f.name, "is_dir": f.is_dir(), "size": f.stat().st_size}
             for f in p.iterdir()],
            key=lambda x: (not x["is_dir"], x["name"].lower()),
        )

    def _human_size(self, size: int) -> str:
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"
