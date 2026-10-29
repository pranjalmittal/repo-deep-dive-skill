# repo-deep-dive

A portable [Agent Skill](https://agentskills.io/) for coding agents that builds a thorough,
code-grounded understanding of a repository (a local checkout or a GitHub URL). It writes a
`REPO_GUIDE.md` that a new engineer can actually onboard from. The skill uses the standard
`SKILL.md` format and doesn't depend on a specific model or agent vendor.

Use it with any coding agent that supports Agent Skills. If your agent doesn't have a skill
loader, provide it with this repository's `SKILL.md` as instructions and keep the full
repository available so it can read the referenced scripts and guides. The agent needs to
read files, run Python 3 and Git commands, and write Markdown files.

It tries to give you the mental model a senior engineer on the team carries: what the project
is for, how it's shaped, what happens at runtime when its main features are used, where you'd
go to change something, and what will bite you. Every claim cites `path:line`, and the skill
verifies those references before it finishes.

## What you get

`REPO_GUIDE.md` contains:

- **TL;DR** and what the project is and who uses it
- **Tech stack** table and an annotated **repository map**
- **Architecture**: components, dependency direction, and a Mermaid diagram
- **Key flows** traced hop by hop through the real call chain, e.g. register → login → authenticated request
- **Data model**, **configuration and env vars**, **integrations**
- **Development workflow**, using only commands that exist in the repo
- **History and ownership**: hotspots, contributors, recent focus
- **Gotchas, risks and tech debt**
- **Where to start**: a reading order and good first tasks
- **Glossary** and **open questions**

You also get a short summary in chat. See [`examples/`](examples/) for a full guide the
skill generated for the [RealWorld Express + Prisma API](https://github.com/gothinkster/node-express-realworld-example-app).

The skill adjusts to the question:

| You ask | You get |
|---|---|
| "Help me understand this repo" / "I just joined this team" / "walk me through github.com/org/repo" | Full deep dive and `REPO_GUIDE.md` |
| "What is this repo, roughly?" | Quick chat summary, with an offer of the full guide |
| "How does auth work in this codebase?" | A focused trace with `path:line` citations, in chat |

## Install

Requirements: Bash and `git` for the installer, and Python 3.9+ (standard library only) for
the skill. The [GitHub CLI](https://cli.github.com/) is optional; it's used for private repos
and PR/issue context.

Run the installer without options to choose from its built-in list of common agents (Codex,
Claude Code, Cursor, and GitHub Copilot). It installs directly into the selected agent's
personal skill directory:

```bash
./install.sh
```

Pass `--agent` to install directly without the menu. Use `--scope project` to install in the
current repository's conventional project skill directory:

```bash
./install.sh --agent codex
./install.sh --agent codex --scope project
```

For an agent without a built-in path, the installer asks for the skill directory in an
interactive shell:

```bash
./install.sh --agent my-agent
```

Use `--dir PATH` to provide the skill directory directly; this works for any agent and skips
the prompt:

```bash
./install.sh --dir /path/to/agent/skills/repo-deep-dive
```

To link the current checkout for temporary use or local development, add `--link`. Edits then
show up immediately in the installed skill:

```bash
./install.sh --agent codex --link
```

Remove the link when you no longer need it; this leaves the checkout intact:

```bash
rm /path/to/agent/skills/repo-deep-dive
```

If the destination already contains a clone of this repository, the installer updates it with
a fast-forward-only pull. When run from a local checkout, it recognizes a link to that checkout
as already installed and refuses to overwrite unrelated directories or links.

To run the installer without first cloning this repository, specify a built-in agent or pass
`--dir` explicitly:

```bash
curl -fsSL https://raw.githubusercontent.com/pranjalmittal/repo-deep-dive/main/install.sh | bash -s -- --agent codex
```

Once installed, ask your agent something like *"help me understand this repo"*. If the agent
supports direct skill invocation, invoke `repo-deep-dive` by its name.

## How it works

1. **Resolve the target.** Use a local path, or clone a GitHub URL (`--filter=blob:none`, so
   history is kept but file contents are fetched lazily) into a scratch directory.
2. **Survey.** [`scripts/repo_survey.py`](scripts/repo_survey.py) produces a fast structural
   report: languages, layout, build, CI and infra tooling, scripts, docs, likely entry points,
   tests, largest files, churn hotspots, contributors and TODO counts.
3. **Map the architecture.** Entry points, components, layers, data model, config and
   integrations. Stack-specific hints live in [`references/ecosystem_hints.md`](references/ecosystem_hints.md).
   For large repos and monorepos, it uses parallel agents per component when the host supports
   delegation; otherwise it inspects components sequentially.
4. **Trace 2–4 key flows** end to end through the real call chain.
5. **Development workflow, history and ownership, gotchas.**
6. **Write the guide** from [`references/guide_template.md`](references/guide_template.md),
   then verify every cited path and line number with [`scripts/check_paths.py`](scripts/check_paths.py).

### Safety: it reads, it doesn't run

The skill treats every repo as untrusted. It does not install dependencies or run build
scripts, tests, hooks or anything else the repo ships, unless you ask it to. Package install
scripts and Makefiles can execute arbitrary code. The only things it runs are read-only `git`
commands and its own two scripts, which only read files.

## Using the scripts on their own

Both scripts are standalone and dependency-free:

```bash
# Structural survey of any checkout, as Markdown
python3 -I scripts/repo_survey.py path/to/repo > survey.md

# Check that every `path` / `path:line` cited in a Markdown doc exists (exits 1 if any are broken)
python3 -I scripts/check_paths.py path/to/GUIDE.md path/to/repo
```

`check_paths.py` works on any doc that cites code, such as design docs and onboarding wikis. It
ignores URL routes (`/api/tags`), code identifiers (`req.auth`), gitignored paths and fenced code
blocks.

## Repository layout

```
install.sh                  installs or links the skill for an agent
SKILL.md                    portable skill instructions and workflow
scripts/
  repo_survey.py            structural survey (read-only, stdlib only)
  check_paths.py            verifies path:line citations in a guide
references/
  guide_template.md         REPO_GUIDE.md structure
  ecosystem_hints.md        where things live per stack, plus grep recipes
evals/                      representative prompts and expected outcomes
benchmarks/                 with- vs. without-skill results, graded
examples/                   a sample generated guide
```

## Evaluating changes

`evals/` contains representative tasks and expected outcomes for checking the skill. Run them
with an evaluation harness available in your environment, or use them as manual review cases.

| Case | Tests |
|---|---|
| `ts-service-local-checkout` | Onboarding onto a local Express/Prisma API. It has 8 graded checks: auth flow traced, JWT secret risk flagged, accurate data model, only real commands, test setup, citations resolve, nothing executed |
| `onboard-flask-from-url` | Full deep dive from a GitHub URL (a Python library) |
| `focused-question-chi` | Focused-question mode on a Go library: routing, middleware and `Mount` |

The first benchmark ran one comparison per configuration, so treat its results as directional.
With the skill, the TypeScript case passed 8/8 checks versus 6/8 without it, with more verified
`file:line` citations. Outputs, grading evidence and notes are in [`benchmarks/`](benchmarks/).

## Contributing

Issues and PRs are welcome. Useful contributions:

- Ecosystem hints for stacks that aren't covered yet (`references/ecosystem_hints.md`)
- Better survey heuristics, such as entry-point detection or monorepo signals (`scripts/repo_survey.py`)
- New eval cases, especially monorepos and less common languages, with graders under `evals/<case>/graders/`

Keep `SKILL.md` under about 500 lines; put detail in `references/`.

## License

[MIT](LICENSE)
