#!/usr/bin/env python3
"""Verify that file references cited in a Markdown guide exist in the repo.

Scans inline code spans (`like/this.py` or `src/app.ts:42` or `lib/x.rb:10-20`)
outside fenced code blocks, and checks that each referenced path exists under
the repo root and that cited line numbers are within the file's length.

Usage:
    python3 -I check_paths.py <guide.md> <repo_root>

Exit code 1 if any reference is broken, so it can gate "done".
"""

import re
import subprocess
import sys
from pathlib import Path

SPAN = re.compile(r"`([^`\n]+)`")
REF = re.compile(r"^(?P<path>[\w.\-@+/\[\]()]+?)(?::(?P<start>\d+)(?:[-–](?P<end>\d+))?)?$")
FENCE = re.compile(r"^\s*(```|~~~)")


FILE_EXTS = {
    "py", "pyi", "js", "mjs", "cjs", "jsx", "ts", "tsx", "go", "rs", "java", "kt", "kts", "scala",
    "rb", "php", "cs", "fs", "c", "h", "cc", "cpp", "hpp", "m", "mm", "swift", "dart", "ex", "exs",
    "erl", "clj", "hs", "ml", "lua", "r", "jl", "sh", "bash", "zsh", "ps1", "sql", "proto", "graphql",
    "gql", "vue", "svelte", "html", "erb", "css", "scss", "less", "tf", "hcl", "yaml", "yml", "json",
    "toml", "xml", "md", "rst", "txt", "ini", "cfg", "conf", "lock", "gradle", "prisma", "mod", "sum",
    "ipynb", "csv", "env", "dockerfile", "mk", "bazel", "bzl", "properties", "plist", "pbxproj",
}


def looks_like_path(token, root):
    """Heuristic: is this inline-code span a repo file reference (vs. a URL route or identifier)?"""
    if token.startswith(("http://", "https://", "/", "~", "-", "$", "@", "<")) or " " in token:
        return False  # URLs, URL routes like /api/tags, absolute paths, flags, placeholders
    ext = token.rsplit(".", 1)[-1].lower() if "." in token.rsplit("/", 1)[-1] else ""
    if ext in FILE_EXTS:
        return True
    # Extensionless (dirs, Makefile, `req.auth`-style identifiers): only check when it's
    # anchored in an existing top-level entry, e.g. `src/app/routes/`.
    first = token.split("/", 1)[0]
    return "/" in token and bool(first) and (root / first).exists()


def git_ignored(root, rel):
    """Cited paths like `dist/api` or `.env` are legitimately absent when gitignored."""
    try:
        return subprocess.run(["git", "-C", str(root), "check-ignore", "-q", "--no-index", rel],
                              capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    guide, root = Path(sys.argv[1]), Path(sys.argv[2]).resolve()
    in_fence = False
    checked, broken = 0, []
    line_cache = {}

    for lineno, line in enumerate(guide.read_text(errors="replace").splitlines(), 1):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for span in SPAN.findall(line):
            m = REF.match(span.strip())
            if not m or not looks_like_path(m.group("path"), root):
                continue
            rel = m.group("path").rstrip("/").removeprefix("./") or "."
            target = (root / rel).resolve()
            checked += 1
            if root not in target.parents and target != root:
                continue  # points outside the repo; not ours to judge
            if not target.exists():
                # Bare filenames (e.g. `package.json`) may legitimately refer to a nested one.
                if "/" not in rel and any(root.rglob(rel)):
                    continue
                if git_ignored(root, rel):
                    continue
                broken.append((lineno, span, "path not found"))
                continue
            if m.group("start") and target.is_file():
                if target not in line_cache:
                    line_cache[target] = target.read_bytes().count(b"\n") + 1
                last = int(m.group("end") or m.group("start"))
                if last > line_cache[target]:
                    broken.append((lineno, span, f"line {last} > file length {line_cache[target]}"))

    print(f"Checked {checked} path references in {guide.name}.")
    for lineno, span, why in broken:
        print(f"  guide line {lineno}: `{span}` — {why}")
    if broken:
        print(f"{len(broken)} broken reference(s). Fix or remove them before finishing.")
        sys.exit(1)
    print("All references resolve.")


if __name__ == "__main__":
    main()
