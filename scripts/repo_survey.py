#!/usr/bin/env python3
"""Fast, read-only structural survey of a code repository.

Prints a Markdown report covering: git metadata, language mix, top-level
layout, build/CI/infra tooling, declared scripts, docs, likely entry points,
tests, largest files, churn hotspots and TODO density.

It never executes anything from the target repo (only `git` read commands),
so it is safe to run on freshly cloned, untrusted code.

Usage:
    python3 -I repo_survey.py <repo_path> [--max-files 50000] [--hotspot-days 365]
"""

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

SKIP_DIRS = {
    ".git", "node_modules", "vendor", "dist", "build", "target", "out", ".next",
    ".nuxt", ".venv", "venv", "env", "__pycache__", ".mypy_cache", ".pytest_cache",
    ".tox", ".gradle", ".idea", ".vscode", "coverage", ".terraform", "bower_components",
    "Pods", ".dart_tool", ".cache", "tmp", "log", "logs", ".bundle", "site-packages",
}

LANG_BY_EXT = {
    ".py": "Python", ".js": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".jsx": "JavaScript (JSX)", ".ts": "TypeScript", ".tsx": "TypeScript (TSX)",
    ".go": "Go", ".rs": "Rust", ".java": "Java", ".kt": "Kotlin", ".kts": "Kotlin",
    ".scala": "Scala", ".rb": "Ruby", ".php": "PHP", ".cs": "C#", ".fs": "F#",
    ".c": "C", ".h": "C/C++ header", ".cc": "C++", ".cpp": "C++", ".hpp": "C++",
    ".m": "Objective-C", ".mm": "Objective-C++", ".swift": "Swift", ".dart": "Dart",
    ".ex": "Elixir", ".exs": "Elixir", ".erl": "Erlang", ".clj": "Clojure",
    ".hs": "Haskell", ".ml": "OCaml", ".lua": "Lua", ".r": "R", ".jl": "Julia",
    ".sh": "Shell", ".bash": "Shell", ".zsh": "Shell", ".ps1": "PowerShell",
    ".sql": "SQL", ".proto": "Protobuf", ".graphql": "GraphQL", ".gql": "GraphQL",
    ".vue": "Vue", ".svelte": "Svelte", ".html": "HTML", ".erb": "ERB",
    ".css": "CSS", ".scss": "SCSS", ".less": "Less",
    ".tf": "Terraform", ".hcl": "HCL", ".yaml": "YAML", ".yml": "YAML",
    ".json": "JSON", ".toml": "TOML", ".xml": "XML", ".md": "Markdown", ".rst": "reST",
    ".ipynb": "Jupyter",
}
# Languages that are config/docs rather than application code.
NON_CODE = {"YAML", "JSON", "TOML", "XML", "Markdown", "reST", "HTML", "CSS", "SCSS", "Less"}

# (glob-ish filename or relative path, label)
TOOLING_MARKERS = [
    ("package.json", "Node.js package"), ("pnpm-workspace.yaml", "pnpm workspace (monorepo)"),
    ("lerna.json", "Lerna monorepo"), ("nx.json", "Nx monorepo"), ("turbo.json", "Turborepo"),
    ("yarn.lock", "Yarn lockfile"), ("package-lock.json", "npm lockfile"), ("pnpm-lock.yaml", "pnpm lockfile"),
    ("bun.lockb", "Bun lockfile"), ("deno.json", "Deno"), ("tsconfig.json", "TypeScript config"),
    ("pyproject.toml", "Python project (pyproject)"), ("setup.py", "Python setup.py"),
    ("setup.cfg", "Python setup.cfg"), ("requirements.txt", "pip requirements"),
    ("Pipfile", "Pipenv"), ("poetry.lock", "Poetry lockfile"), ("uv.lock", "uv lockfile"),
    ("manage.py", "Django project"), ("go.mod", "Go module"), ("go.work", "Go workspace"),
    ("Cargo.toml", "Rust crate/workspace"), ("pom.xml", "Maven"), ("build.gradle", "Gradle"),
    ("build.gradle.kts", "Gradle (Kotlin DSL)"), ("settings.gradle", "Gradle multi-project"),
    ("Gemfile", "Ruby Bundler"), ("config/routes.rb", "Rails app"), ("composer.json", "PHP Composer"),
    ("mix.exs", "Elixir Mix"), ("pubspec.yaml", "Dart/Flutter"), ("Package.swift", "Swift package"),
    ("CMakeLists.txt", "CMake"), ("Makefile", "Makefile"), ("justfile", "just"), ("Taskfile.yml", "Taskfile"),
    ("BUILD.bazel", "Bazel"), ("WORKSPACE", "Bazel workspace"), ("MODULE.bazel", "Bazel module"),
    ("Dockerfile", "Docker image"), ("docker-compose.yml", "Docker Compose"),
    ("docker-compose.yaml", "Docker Compose"), ("compose.yaml", "Docker Compose"),
    ("Procfile", "Procfile (Heroku-style)"), ("serverless.yml", "Serverless Framework"),
    ("vercel.json", "Vercel"), ("netlify.toml", "Netlify"), ("fly.toml", "Fly.io"),
    ("app.yaml", "App Engine / app config"), ("Chart.yaml", "Helm chart"), ("skaffold.yaml", "Skaffold"),
    ("kustomization.yaml", "Kustomize"), (".github/workflows", "GitHub Actions"),
    (".gitlab-ci.yml", "GitLab CI"), ("Jenkinsfile", "Jenkins"), (".circleci", "CircleCI"),
    ("azure-pipelines.yml", "Azure Pipelines"), (".buildkite", "Buildkite"), (".travis.yml", "Travis CI"),
    (".pre-commit-config.yaml", "pre-commit hooks"), (".env.example", "env var template"),
    (".env.sample", "env var template"), ("openapi.yaml", "OpenAPI spec"), ("openapi.json", "OpenAPI spec"),
    ("swagger.yaml", "Swagger spec"), ("swagger.json", "Swagger spec"), ("schema.prisma", "Prisma schema"),
    ("alembic.ini", "Alembic migrations"), ("flyway.conf", "Flyway migrations"),
    ("CODEOWNERS", "CODEOWNERS"), (".github/CODEOWNERS", "CODEOWNERS"),
]

DOC_PATTERNS = re.compile(
    r"^(readme|contributing|architecture|design|hacking|development|developing|setup|install|"
    r"security|changelog|changes|history|claude|agents|copilot-instructions|glossary|faq|runbook)"
    r"(\.[a-z]+)?$",
    re.I,
)
DOC_DIRS = {"docs", "doc", "documentation", "adr", "adrs", "decisions", "rfcs", "rfc", "wiki", "design"}

ENTRY_NAMES = re.compile(
    r"^(main|index|app|server|cli|__main__|manage|wsgi|asgi|program|startup|bootstrap|application|"
    r"lambda_function|handler|worker|cmd)\.(py|js|mjs|cjs|ts|tsx|go|rs|java|kt|rb|php|cs|ex|exs|swift|dart)$",
    re.I,
)
TEST_DIR = re.compile(r"(^|/)(tests?|spec|specs|__tests__|e2e|integration|test_.*|.*_test)(/|$)", re.I)
TEST_FILE = re.compile(r"(^test_.*\.py$|.*_test\.(py|go|rb|exs)$|.*\.(test|spec)\.[jt]sx?$|.*Tests?\.(java|kt|cs|swift)$|.*_spec\.rb$)")
TODO_RE = re.compile(rb"\b(TODO|FIXME|HACK|XXX)\b")
NOT_ENTRY = re.compile(r"(^|/)(tests?|spec|__tests__|e2e|examples?|samples?|fixtures?|testdata|docs?)(/|$)", re.I)


def run_git(repo, *args, timeout=60):
    try:
        res = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True, text=True, timeout=timeout,
        )
        return res.stdout.strip() if res.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def walk(repo, max_files):
    """Yield (relative_path, size) for files, skipping vendored/generated dirs."""
    count = 0
    for root, dirs, files in os.walk(repo):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.endswith(".egg-info"))
        for name in files:
            p = Path(root, name)
            try:
                if p.is_symlink():
                    continue
                size = p.stat().st_size
            except OSError:
                continue
            yield p.relative_to(repo).as_posix(), size
            count += 1
            if count >= max_files:
                return


def count_lines(path, limit=2_000_000):
    try:
        with open(path, "rb") as fh:
            data = fh.read(limit)
    except OSError:
        return 0, 0
    if b"\0" in data[:4096]:
        return 0, 0  # binary
    return data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0), len(TODO_RE.findall(data))


def section(title):
    print(f"\n## {title}\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo")
    ap.add_argument("--max-files", type=int, default=50_000)
    ap.add_argument("--hotspot-days", type=int, default=365)
    args = ap.parse_args()

    repo = Path(args.repo).expanduser().resolve()
    if not repo.is_dir():
        sys.exit(f"Not a directory: {repo}")

    print(f"# Repo survey: `{repo.name}`\n")
    print(f"Path: `{repo}`")

    # ---- Git metadata -------------------------------------------------------
    is_git = bool(run_git(repo, "rev-parse", "--is-inside-work-tree"))
    if is_git:
        section("Git")
        remote = run_git(repo, "remote", "get-url", "origin")
        branch = run_git(repo, "rev-parse", "--abbrev-ref", "HEAD")
        last = run_git(repo, "log", "-1", "--format=%h %ad %an: %s", "--date=short")
        first = run_git(repo, "log", "--reverse", "--format=%ad", "--date=short", "--max-parents=0")
        total = run_git(repo, "rev-list", "--count", "HEAD")
        shallow = run_git(repo, "rev-parse", "--is-shallow-repository") == "true"
        tags = run_git(repo, "tag", "--sort=-creatordate").splitlines()[:5]
        print(f"- Remote: {remote or '(none)'}")
        print(f"- Branch: {branch}  |  Commits: {total}{' (shallow clone — history truncated)' if shallow else ''}")
        print(f"- First commit: {first.splitlines()[0] if first else '?'}  |  Last: {last}")
        if tags:
            print(f"- Recent tags: {', '.join(tags)}")
        authors = run_git(repo, "shortlog", "-sn", "--no-merges", f"--since={args.hotspot_days} days ago", "HEAD")
        if authors:
            print(f"\nActive contributors (last {args.hotspot_days}d, by commits):")
            for line in authors.splitlines()[:10]:
                print(f"- {line.strip()}")
        recent = run_git(repo, "log", "-15", "--format=%h %ad %s", "--date=short", "--no-merges")
        if recent:
            print("\nRecent commits:")
            print("```")
            print(recent)
            print("```")

    # ---- File walk ----------------------------------------------------------
    files = list(walk(repo, args.max_files))
    truncated = len(files) >= args.max_files
    lang_files, lang_lines = Counter(), Counter()
    top_dir_files = Counter()
    todo_total, todo_by_dir = 0, Counter()
    largest = []
    entry_points, doc_files, test_files = [], [], 0
    test_dirs = set()
    ext_unknown = Counter()

    for rel, size in files:
        name = rel.rsplit("/", 1)[-1]
        top = rel.split("/", 1)[0] if "/" in rel else "(root)"
        top_dir_files[top] += 1
        ext = os.path.splitext(name)[1].lower()
        lang = LANG_BY_EXT.get(ext)
        if name == "Dockerfile" or name.startswith("Dockerfile."):
            lang = "Dockerfile"
        if lang:
            lang_files[lang] += 1
            if size < 2_000_000:
                lines, todos = count_lines(repo / rel)
                lang_lines[lang] += lines
                if lang not in NON_CODE:
                    todo_total += todos
                    if todos:
                        todo_by_dir[top] += todos
                    largest.append((lines, rel))
        elif ext:
            ext_unknown[ext] += 1
        parts = rel.lower().split("/")
        if DOC_PATTERNS.match(name) or (len(parts) > 1 and parts[0] in DOC_DIRS and ext in {".md", ".rst", ".adoc", ".txt"}):
            doc_files.append(rel)
        if not NOT_ENTRY.search(rel):
            if ENTRY_NAMES.match(name) and rel.count("/") <= 3:
                entry_points.append(rel)
            if rel.startswith(("bin/", "cmd/")) and rel.count("/") <= 2:
                entry_points.append(rel)
        if TEST_FILE.match(name) or TEST_DIR.search(rel.rsplit("/", 1)[0] if "/" in rel else ""):
            test_files += 1
            m = TEST_DIR.search(rel)
            if m:
                test_dirs.add(rel[: m.end()].rstrip("/"))

    section("Size & languages")
    code_files = sum(v for k, v in lang_files.items() if k not in NON_CODE)
    code_lines = sum(v for k, v in lang_lines.items() if k not in NON_CODE)
    print(f"Files scanned: {len(files)}{' (TRUNCATED at --max-files)' if truncated else ''}  |  "
          f"Code files: {code_files}  |  Code lines: {code_lines:,}\n")
    print("| Language | Files | Lines |\n|---|---:|---:|")
    for lang, n in lang_files.most_common(15):
        print(f"| {lang} | {n} | {lang_lines[lang]:,} |")

    section("Top-level layout (files per entry, vendored/build dirs skipped)")
    for top, n in sorted(top_dir_files.items(), key=lambda kv: (-kv[1], kv[0]))[:30]:
        kind = "dir" if top != "(root)" and (repo / top).is_dir() else ""
        print(f"- `{top}{'/' if kind else ''}` — {n} files")

    # Second level for the biggest dirs gives a feel for module boundaries.
    sub = defaultdict(Counter)
    for rel, _ in files:
        parts = rel.split("/")
        if len(parts) >= 3:
            sub[parts[0]][parts[1]] += 1
    big = [t for t, _ in top_dir_files.most_common(6) if t in sub]
    if big:
        print("\nSecond level of the largest dirs:")
        for t in big:
            kids = ", ".join(f"{k} ({v})" for k, v in sub[t].most_common(12))
            print(f"- `{t}/`: {kids}")

    section("Build, runtime & infra tooling detected")
    found = []
    for marker, label in TOOLING_MARKERS:
        if (repo / marker).exists():
            found.append(f"- {label} — `{marker}`")
    # Nested manifests hint at a monorepo / polyglot repo.
    nested = Counter()
    for rel, _ in files:
        name = rel.rsplit("/", 1)[-1]
        if "/" in rel and name in {"package.json", "pyproject.toml", "go.mod", "Cargo.toml", "pom.xml",
                                   "build.gradle", "build.gradle.kts", "Gemfile", "Dockerfile", "setup.py"}:
            nested[name] += 1
    print("\n".join(found) if found else "(no common markers at root)")
    if nested:
        print("\nNested manifests (monorepo / multi-service signal): " +
              ", ".join(f"{k} ×{v}" for k, v in nested.most_common()))
    wf = repo / ".github" / "workflows"
    if wf.is_dir():
        names = sorted(p.name for p in wf.iterdir() if p.suffix in {".yml", ".yaml"})
        print(f"\nGitHub workflows: {', '.join(names)}")

    section("Declared scripts / tasks")
    pkg = repo / "package.json"
    if pkg.is_file():
        try:
            data = json.loads(pkg.read_text(errors="replace"))
            print(f"package.json name: `{data.get('name')}`  version: `{data.get('version')}`")
            for k in ("main", "module", "bin", "workspaces", "engines"):
                if k in data:
                    print(f"- {k}: `{json.dumps(data[k])[:200]}`")
            scripts = data.get("scripts") or {}
            if scripts:
                print("\nnpm scripts:")
                for k, v in list(scripts.items())[:25]:
                    print(f"- `{k}`: `{str(v)[:140]}`")
            deps = list((data.get("dependencies") or {}).keys())
            if deps:
                print(f"\nRuntime deps ({len(deps)}): {', '.join(deps[:40])}")
        except (ValueError, OSError):
            print("package.json present but not parseable")
    pyproj = repo / "pyproject.toml"
    if pyproj.is_file():
        text = pyproj.read_text(errors="replace")
        for header in ("[project.scripts]", "[tool.poetry.scripts]"):
            if header in text:
                block = text.split(header, 1)[1].split("\n[", 1)[0].strip()
                print(f"\n{header}:\n```\n{block[:800]}\n```")
        m = re.search(r"(?ms)^dependencies\s*=\s*\[(.*?)\]", text)
        if m:
            deps = re.findall(r"[\"']([A-Za-z0-9_.\-\[\]]+)", m.group(1))
            print(f"\nPython deps ({len(deps)}): {', '.join(deps[:40])}")
    for mk in ("Makefile", "makefile", "justfile"):
        p = repo / mk
        if p.is_file():
            targets = re.findall(r"(?m)^([A-Za-z0-9][\w.\-]*)\s*:(?!=)", p.read_text(errors="replace"))
            if targets:
                print(f"\n{mk} targets: {', '.join(dict.fromkeys(targets).keys())}")
    gomod = repo / "go.mod"
    if gomod.is_file():
        first_line = gomod.read_text(errors="replace").splitlines()[0]
        print(f"\ngo.mod: `{first_line}`")

    section("Documentation found")
    if doc_files:
        ordered = sorted(doc_files, key=lambda s: (s.count("/"), s))
        for d in ordered[:25]:
            print(f"- `{d}`")
        rest = ordered[25:]
        if rest:
            by_dir = Counter(r.rsplit("/", 1)[0] if "/" in r else "(root)" for r in rest)
            print(f"- … and {len(rest)} more: " + ", ".join(f"`{d}/` ×{n}" for d, n in by_dir.most_common(10)))
    else:
        print("(no README/docs found — expect to infer intent from code)")

    section("Likely entry points (heuristic — confirm by reading)")
    eps = sorted(set(entry_points), key=lambda s: (s.count("/"), s))
    print("\n".join(f"- `{e}`" for e in eps[:30]) if eps else "(none matched; check manifests' main/bin/scripts)")

    section("Tests")
    print(f"Test files (heuristic): {test_files}")
    if test_dirs:
        roots = sorted({d for d in test_dirs if not any(d != o and d.startswith(o + "/") for o in test_dirs)})
        print("Test roots: " + ", ".join(f"`{d}`" for d in roots[:20]))

    section("Largest code files (often the core — or the tech debt)")
    for lines, rel in sorted(largest, reverse=True)[:15]:
        print(f"- `{rel}` — {lines:,} lines")

    if is_git:
        section(f"Churn hotspots (most-changed files, last {args.hotspot_days}d)")
        log = run_git(repo, "log", f"--since={args.hotspot_days} days ago", "--no-merges",
                      "--name-only", "--format=", timeout=120)
        churn = Counter(l for l in log.splitlines() if l and not any(
            seg in SKIP_DIRS for seg in l.split("/")) and not l.endswith((".lock", "-lock.json", ".lockb")))
        if churn:
            for path, n in churn.most_common(15):
                print(f"- `{path}` — {n} commits")
        else:
            print("(no commits in window, or shallow clone)")

    section("TODO / FIXME / HACK markers in code")
    print(f"Total: {todo_total}")
    if todo_by_dir:
        print("By top-level dir: " + ", ".join(f"`{d}` {n}" for d, n in todo_by_dir.most_common(10)))

    if ext_unknown:
        section("Other file types (unmapped extensions)")
        print(", ".join(f"{e} ×{n}" for e, n in ext_unknown.most_common(15)))


if __name__ == "__main__":
    main()
