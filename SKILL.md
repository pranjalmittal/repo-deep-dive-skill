---
name: repo-deep-dive
description: Thoroughly understand a code repository, from a local checkout or a GitHub URL, and write a durable REPO_GUIDE.md covering architecture, key flows traced end-to-end with file:line citations, data model, config, dev workflow, ownership/hotspots, gotchas and a reading order. Use this whenever someone wants to understand, explore, onboard onto, ramp up on, audit, or get an overview or architecture walkthrough of a repo, project or codebase. That includes casual asks like "what does this repo do", "I just joined this team, help me get up to speed", "explain how this project is structured", "walk me through github.com/org/repo", or "how does X work in this codebase" when answering means tracing across many files. Prefer this over ad-hoc exploration for any whole-repo understanding task.
license: MIT
compatibility: Agent Skills-compatible coding agent with file read/search, shell, and write capabilities. Requires git and Python 3.9+ (standard library only). The GitHub CLI (gh) is optional, for private repos and PR/issue context.
---

# Repo Deep Dive

This skill uses the Agent Skills format and is tool-vendor neutral. Use the host agent's
equivalent file-reading, search, shell, and file-writing tools for the steps below. If the
host doesn't support delegation, inspect independent components sequentially.

The goal is the mental model a senior engineer on the team carries in their head:
what the project is for, how it's shaped, what happens at runtime when its main
features are used, where you'd go to change something, and what will bite you.
A file inventory is not understanding. Being able to *predict* where code lives and
what it does is.

The output is a `REPO_GUIDE.md` the user can keep, share and re-read, plus a short
summary in chat.

## Principles

- **Code is the source of truth.** READMEs and wikis rot. Ground claims in code
  you've read and cite `path:line`. When docs and code disagree, report the
  disagreement in the guide, because it's one of the most useful things a newcomer can learn.
- **Separate what you verified from what you inferred.** Directory and file names
  suggest structure, but they're often misleading. Mark anything you haven't confirmed
  by reading code with *(inferred)*. A guide that's confidently wrong is worse than one
  with honest gaps.
- **Read, don't run.** Treat the repo as untrusted. Don't install dependencies,
  run build scripts, tests, git hooks or anything else the repo provides unless the
  user asks: package install scripts and Makefiles can execute arbitrary code.
  Only the bundled scripts and read-only `git` commands are needed.
- **Breadth first, then depth.** A cheap structural survey tells you where to
  spend expensive reading time. Then go deep where it matters: the core flows.
- **Spend effort where understanding comes from.** Tracing a real request
  through the code teaches more than summarizing twenty directories.

## Choose the scope

Match the depth to the ask:

| Ask | Do | Output |
|---|---|---|
| Understand / onboard / overview / "explain this repo" (default) | Full workflow below | `REPO_GUIDE.md` + chat summary |
| Quick tl;dr ("what is this, roughly?") | Steps 0–1, skim entry points | Short chat answer; offer the full guide |
| Focused question ("how does auth work here?") | Steps 0–1 lightly, then step 3 on that subsystem only | Chat answer with `path:line` citations; if a `REPO_GUIDE.md` exists, offer to add a section |

If the user named an area they care about (their team's service, a feature they'll
work on), weight the deep dives toward it, and say so in the guide.

## Workflow

### 0. Resolve the target

**Local path** (or the current directory): find the root with `git rev-parse --show-toplevel`.
If it's not a git repo, continue anyway. History-based sections just get skipped.

**GitHub URL**: parse `owner/repo`, plus an optional branch or subpath from
`/tree/<branch>/<path>` URLs. Clone into a fresh, empty directory under the
scratchpad (or `mktemp -d` if there's no scratchpad):

```bash
git clone --filter=blob:none [--branch <branch>] https://github.com/<owner>/<repo>.git <dir>/<owner>-<repo>
```

`--filter=blob:none` keeps full commit history (needed for hotspots and
ownership) while only downloading file contents for the checked-out tree. For
very large repos (the clone is slow, or the survey reports more than ~20k files),
`--depth 500` is a fine compromise. For private repos, use
`gh repo clone <owner>/<repo> <dir> -- --filter=blob:none` so the user's GitHub auth
is used. If a subpath was given, survey the whole repo but focus the deep dive there.

If `gh` is authenticated, also collect project context. It's cheap and often
reveals what's actively changing:

```bash
gh repo view <owner>/<repo> --json description,homepageUrl,repositoryTopics,stargazerCount,primaryLanguage,licenseInfo,pushedAt
gh pr list -R <owner>/<repo> --limit 15 --json number,title,author,updatedAt
gh issue list -R <owner>/<repo> --limit 15 --json number,title,labels
```

### 1. Survey (breadth)

Run the bundled survey script and save its output. It prints git metadata, language mix,
layout, build/CI/infra tooling, declared scripts, docs, candidate entry points,
tests, largest files, churn hotspots and TODO counts. It executes nothing from the repo.

```bash
python3 -I <skill-dir>/scripts/repo_survey.py <repo-root> > <scratch>/survey.md
```

Then read, in this order:
1. The README, repository instructions for this and other coding agents (for example
   `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.github/copilot-instructions.md`, and
   `.cursor/rules/`), plus `CONTRIBUTING*` / `ARCHITECTURE*` / ADRs if present.
   These state the authors' intent. Trust them less than code, but read them first.
2. The root manifests (`package.json`, `pyproject.toml`, `go.mod`, `pom.xml`, `Cargo.toml`, …)
   and workspace configs. Dependencies tell you the capabilities: web framework, ORM,
   queue client, auth library.
3. CI workflow files. They contain the real build, test and deploy commands.
4. `docker-compose*.yml` / `Dockerfile` if present. They show the runtime
   topology and what actually starts in production.

Now write down your working hypotheses: what kind of project this is (library, service,
CLI, web or mobile app, infra, monorepo), who consumes it, the main stack, and
the 2–4 flows that matter most. The next steps confirm or correct them.

For stack-specific places to look (Django settings, NestJS modules, Spring
beans, Go `cmd/`, Rails routes, monorepo workspace files, and so on), read the relevant
section of `references/ecosystem_hints.md`. It also has grep recipes for env vars, routes,
jobs, DB access and generated code.

### 2. Map the architecture

Establish, with citations:
- **Entry points**: confirm each candidate from the survey by opening it. Find
  where the process starts, or what a library exports as its public API.
- **Components and boundaries**: the main modules and packages, a one-sentence responsibility for
  each, and the dependency direction between them. Grep imports to check it; don't
  trust the folder names alone.
- **Layers**: interface (routes / CLI / handlers / UI) → domain logic → persistence and integrations.
  Note where the codebase breaks its own layering.
- **Data model**: schemas, migrations, ORM models, protobufs, core types.
- **Configuration**: config sources and precedence, the env vars that are read (grep them),
  feature flags, secrets handling.
- **Integrations**: databases, caches, queues, third-party APIs, other internal
  services, and where each client lives.

**Large repos and monorepos** (roughly more than 1,500 code files, or several
independent services or packages): build the package and service map yourself first.
If your coding-agent environment supports delegation, use parallel agents to inspect
major components, one per component, with a narrow brief: "For `<path>`, report its
purpose, public interface, key files, what it depends on and what depends on it,
notable patterns, and anything surprising. Cite `path:line` for every claim. Mark
anything you didn't confirm in code as inferred." If delegation isn't available,
inspect the components sequentially. Keep the cross-cutting synthesis (architecture,
flows that cross components) in the main analysis. If there are many independent
services and the user hasn't said which ones matter, give a map of all of them and
deep-dive on the shared core plus the most central one or two. Then offer to go deeper
on others.

### 3. Trace the key flows (depth)

This is the step that turns a directory summary into real understanding. Pick 2–4
flows that represent what the project is *for*. For example: the main API request, the core
CLI command, the primary background job, a library's central function, the page
that matters most. Follow each one through the actual call chain, file by file:

- Record each hop as `path:line` plus what happens there: validation, auth, business
  rules, persistence, side effects such as events, jobs and outbound calls.
- Note where control flow is indirect: middleware, decorators, DI containers,
  event buses, ORM callbacks, metaprogramming. That's where newcomers get lost, so
  name the mechanism explicitly.
- Where relevant, trace one write path and one failure path (how errors propagate,
  get mapped and get retried).

If a hop can't be resolved statically (a dynamic dispatch, a config-driven plugin), say
so rather than guessing.

### 4. Development workflow

Document how to set up, run, test, lint, build and release. Only list commands that exist in
the repo: manifest scripts, Makefile targets, CI steps, docs. Describe the
test layout and style (unit vs integration, fixtures and factories, what's mocked, how to
run a single test), and which CI checks gate a merge.

### 5. History, ownership and activity

Interpret what the survey shows rather than just pasting it:
- Hotspot files: a core file being churned means active development or a pain point,
  while churny CI or config files are mostly noise.
- Main contributors overall and per area (`git shortlog -sn -- <path>`), plus `CODEOWNERS`.
- Recent focus: themes in the last few months of commits, and open PRs and issues if available.
- Age and cadence: release tags, and whether the project is maintained or dormant.

### 6. Gotchas, risks and tech debt

Collect the things that would surprise a competent newcomer: hidden coupling (files
that must change together), generated code that shouldn't be hand-edited, magic
conventions, god files (the survey's largest-files list), TODO/FIXME clusters,
untested areas, deprecated paths still in use, doc/code drift, and security-sensitive
code (auth, payments, PII handling, crypto, deserialization).

### 7. Write the guide

Follow `references/guide_template.md`. Keep its section order, drop sections that truly
don't apply, and include at least one Mermaid architecture diagram. Write for a reader
who will open the files next to the guide. Specific beats exhaustive.

**Where to write it:**
- Local repo: `REPO_GUIDE.md` at the repo root. If that file already exists, read it first
  and update it rather than clobbering it. Mention that it's a new untracked file, and don't commit it.
- Cloned from a URL: `<current working directory>/<repo>-REPO_GUIDE.md`. The clone
  lives in scratch space and is easy to lose.
- A path the user names takes precedence over both.

**Verify before finishing.** Run the reference checker. It confirms every
`path` and `path:line` cited outside code fences exists and is in range:

```bash
python3 -I <skill-dir>/scripts/check_paths.py <guide.md> <repo-root>
```

Fix or remove any broken references it reports. Then reread the TL;DR and the
architecture section with fresh eyes: does each claim match what you saw in the code?

### 8. Summarize in chat

Keep it short, because the guide holds the detail:
- 2–3 sentences on what the project is and its core mechanism
- The mental model in a few bullets (the main components and how a request or command flows)
- Where to start reading (3 files)
- The full path to the guide
- An offer of natural next steps: a deeper dive on a component, tracing another flow, a
  "first task" walkthrough, or comparing against docs or tickets

## Quality bar

A strong guide lets a new engineer, without asking anyone:
- explain in two sentences what the project does and how,
- find the code for any main feature within a minute,
- follow one core flow from entry point to storage and back,
- set up, run and test it using only commands that really exist,
- know which areas are risky, generated, or owned by whom.

Before finishing, check the guide against that list. Where it falls short, either do the
missing work or record the gap under **Open questions**.
