"""Measure production lines of code for the NexusOps admin portal.

Counts physical lines in application, template, and static sources.
Excludes tests, virtualenvs, git metadata, caches, local data, and this
measurement helper's own commentary is still counted if it lives under app/.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

PRODUCTION_ROOTS = (
    ROOT / "app",
    ROOT / "templates",
    ROOT / "static",
    ROOT / "wsgi.py",
)

SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    "htmlcov",
    "var",
    "dist",
    "node_modules",
}

PRODUCTION_SUFFIXES = {".py", ".html", ".css", ".js"}


def iter_files() -> list[Path]:
    files: list[Path] = []
    for root in PRODUCTION_ROOTS:
        if root.is_file():
            files.append(root)
            continue
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in SKIP_DIR_NAMES for part in path.parts):
                continue
            if path.suffix.lower() in PRODUCTION_SUFFIXES:
                files.append(path)
    return sorted(files)


def count_file(path: Path) -> dict[str, int]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    blank = sum(1 for line in lines if not line.strip())
    return {
        "total": len(lines),
        "blank": blank,
        "nonblank": len(lines) - blank,
    }


def measure() -> dict:
    files = iter_files()
    by_suffix: dict[str, int] = {}
    total = 0
    nonblank = 0
    details = []
    for path in files:
        stats = count_file(path)
        total += stats["total"]
        nonblank += stats["nonblank"]
        suffix = path.suffix.lower() or "none"
        by_suffix[suffix] = by_suffix.get(suffix, 0) + stats["total"]
        details.append(
            {
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "lines": stats["total"],
            }
        )
    return {
        "production_loc": total,
        "production_nonblank": nonblank,
        "file_count": len(files),
        "by_suffix": by_suffix,
        "meets_50000": total >= 50_000,
        "files": details,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Count production LOC")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = measure()
    if args.json:
        printable = dict(result)
        printable.pop("files", None)
        print(json.dumps(printable, indent=2))
        return
    print(f"production_loc={result['production_loc']}")
    print(f"production_nonblank={result['production_nonblank']}")
    print(f"file_count={result['file_count']}")
    print(f"meets_50000={result['meets_50000']}")
    for suffix, count in sorted(result["by_suffix"].items()):
        print(f"  {suffix}: {count}")


if __name__ == "__main__":
    main()
