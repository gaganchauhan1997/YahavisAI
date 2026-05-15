"""
YAHAVIS — skills/code_writer.py
Generate, save, and open code files in the default editor.
"""

import asyncio
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

log = logging.getLogger("yahavis.code_writer")

EXTENSION_MAP = {
    "python": ".py", "py": ".py",
    "javascript": ".js", "js": ".js",
    "typescript": ".ts", "ts": ".ts",
    "jsx": ".jsx", "tsx": ".tsx",
    "react": ".jsx",
    "html": ".html", "css": ".css",
    "java": ".java", "cpp": ".cpp", "c": ".c",
    "go": ".go", "rust": ".rs",
    "bash": ".sh", "shell": ".sh",
    "sql": ".sql", "json": ".json",
    "markdown": ".md", "md": ".md",
    "yaml": ".yml", "toml": ".toml",
}

CODE_SYSTEM_PROMPT = """You are an expert programmer. Write clean, well-commented,
production-ready code. Include necessary imports, error handling, and docstrings.
No explanations — output ONLY the code. No markdown fences."""


class CodeWriter:
    """Generate code using YAHAVIS brain and save to disk."""

    OUTPUT_DIR = Path("~/Documents/YAHAVIS_Code").expanduser()

    def __init__(self):
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    async def generate(
        self,
        description: str,
        language: str = "python",
        brain=None,
        save_path: Optional[str] = None,
    ) -> str:
        """Generate code for the given description and language."""
        ext = EXTENSION_MAP.get(language.lower(), ".txt")
        prompt = (
            f"Write complete, working {language} code for:\n{description}\n\n"
            f"Requirements:\n"
            f"- Include all imports\n"
            f"- Add helpful comments\n"
            f"- Handle common edge cases\n"
            f"- Follow {language} best practices\n"
            f"Output ONLY the code, no explanation:"
        )

        if brain:
            code = await brain.think(
                prompt,
                extra_system=CODE_SYSTEM_PROMPT,
                use_context=False,
            )
        else:
            code = f"# {description}\n# TODO: Implement this\n"

        # Clean code fences if LLM added them
        code = self._clean_code_fences(code)

        # Save to file
        if not save_path:
            import time
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            safe_name = "".join(c if c.isalnum() else "_" for c in description[:30])
            save_path = str(self.OUTPUT_DIR / f"yahavis_{safe_name}_{timestamp}{ext}")

        Path(save_path).write_text(code, encoding="utf-8")
        log.info(f"Code saved: {save_path}")

        self.save_and_open(code, filename=save_path)
        return code

    def save_and_open(self, content: str, filename: str = "yahavis_code.txt"):
        """Save content to a file and open it in the default editor."""
        path = Path(filename).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        log.info(f"Opening: {path}")
        try:
            if sys.platform == "win32":
                # Try VS Code first, fall back to notepad
                try:
                    subprocess.Popen(["code", str(path)])
                except FileNotFoundError:
                    os.startfile(str(path))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as e:
            log.warning(f"Could not open file: {e}")
        return str(path)

    def _clean_code_fences(self, code: str) -> str:
        """Remove markdown code fences if LLM added them."""
        lines = code.strip().split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines)

    async def explain_code(self, code: str, brain=None) -> str:
        """Explain what a piece of code does."""
        if not brain:
            return "Brain not available for code explanation."
        prompt = (
            f"Explain this code concisely in plain English:\n\n{code}\n\n"
            f"Focus on: what it does, key functions, potential issues."
        )
        return await brain.think(prompt, use_context=False)

    async def debug_code(self, code: str, error: str = "", brain=None) -> str:
        """Debug code and suggest fixes."""
        if not brain:
            return "Brain not available for debugging."
        prompt = (
            f"Debug this code and provide the fixed version:\n\n{code}\n\n"
            + (f"Error message:\n{error}\n\n" if error else "")
            + f"Output: brief explanation of the bug + complete fixed code."
        )
        return await brain.think(prompt, use_context=False)
