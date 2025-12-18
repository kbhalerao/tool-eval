"""
Simple exploration tools for agentic file navigation.
3 tools: list, read, grep. That's it.
"""

import os
import re
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional

from .registry import tool_registry

ALLOWED_BASE = Path("/Users/kaustubh/Documents/code/tool-test")


class ListArgs(BaseModel):
    """List directory contents."""
    path: str = Field(description="Directory path (e.g., 'results', 'results/')")


class ReadArgs(BaseModel):
    """Read a file."""
    path: str = Field(description="File path (e.g., 'results/granite-t6.jsonl')")
    lines: int = Field(default=20, description="Max lines to read")


class GrepArgs(BaseModel):
    """Search for pattern in file(s)."""
    pattern: str = Field(description="Text or regex to search for")
    path: str = Field(description="File or directory to search")


@tool_registry.register(tier=7, description="List files in a directory")
def list_dir(args: ListArgs) -> dict:
    """List directory."""
    try:
        p = (ALLOWED_BASE / args.path).resolve()
        if not str(p).startswith(str(ALLOWED_BASE)):
            return {"error": "Access denied"}
        if not p.exists():
            return {"error": f"Not found: {args.path}"}

        files = []
        for f in sorted(p.iterdir()):
            files.append(f"{f.name}/" if f.is_dir() else f.name)

        return {"path": args.path, "files": files}
    except Exception as e:
        return {"error": str(e)}


@tool_registry.register(tier=7, description="Read file contents")
def read_file(args: ReadArgs) -> dict:
    """Read file."""
    try:
        p = (ALLOWED_BASE / args.path).resolve()
        if not str(p).startswith(str(ALLOWED_BASE)):
            return {"error": "Access denied"}
        if not p.exists():
            return {"error": f"Not found: {args.path}"}

        with open(p) as f:
            content = [line.rstrip() for line in f.readlines()[:args.lines]]

        return {"path": args.path, "lines": len(content), "content": content}
    except Exception as e:
        return {"error": str(e)}


@tool_registry.register(tier=7, description="Search for pattern in file(s)")
def grep(args: GrepArgs) -> dict:
    """Grep for pattern."""
    try:
        p = (ALLOWED_BASE / args.path).resolve()
        if not str(p).startswith(str(ALLOWED_BASE)):
            return {"error": "Access denied"}
        if not p.exists():
            return {"error": f"Not found: {args.path}"}

        regex = re.compile(args.pattern, re.IGNORECASE)
        matches = []

        files = [p] if p.is_file() else list(p.glob("*"))
        for fp in files:
            if not fp.is_file():
                continue
            try:
                with open(fp) as f:
                    for i, line in enumerate(f, 1):
                        if regex.search(line):
                            matches.append({
                                "file": fp.name,
                                "line": i,
                                "text": line.rstrip()[:200]
                            })
                            if len(matches) >= 20:
                                return {"pattern": args.pattern, "matches": matches, "truncated": True}
            except:
                continue

        return {"pattern": args.pattern, "matches": matches}
    except Exception as e:
        return {"error": str(e)}
