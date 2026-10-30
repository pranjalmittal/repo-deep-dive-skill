# REPO_GUIDE.md template

Use this structure for the guide. Drop sections that genuinely don't apply (a pure
library has no deployment story; a static site has no data model) rather than
padding them — but say so in one line if a reader would expect it ("No database;
all state is in-memory per request."). Keep section order so guides across repos
feel familiar.

Citation style: `path/to/file.ext:LINE` or `path/to/file.ext:START-END`, relative
to the repo root. Mark inferences with *(inferred)* — anything not confirmed by
reading the code itself.

---

```markdown
# <Project name> — Repo Guide

> Generated <YYYY-MM-DD> from `<remote or path>` at commit `<short sha>` (<branch>).
> Claims cite `file:line`. *(inferred)* = deduced from names/structure, not confirmed in code.

## TL;DR
3–5 sentences: what this is, what problem it solves, the core mechanism in one
sentence, and the single most important thing to know before touching it.

## What it is and who uses it
- Kind of project: library / service / CLI / web app / mobile app / infra / monorepo of …
- Users or consumers (end users, other services, developers importing it)
- Maturity and activity (age, release cadence, how active the last ~year has been)

## Tech stack
| Concern | Choice | Where it's configured |
|---|---|---|
| Language/runtime | | |
| Framework | | |
| Storage | | |
| Messaging / jobs | | |
| Build / packaging | | |
| Testing | | |
| CI/CD / deploy | | |

## Repository map
Annotated tree of the directories and files that matter — not every file.
Say what each one is *for*, and mark generated or vendored areas you shouldn't edit by hand.

    src/
      api/          HTTP handlers; thin, delegate to services/
      services/     business logic — start here
      db/           models + migrations (migrations are generated: don't hand-edit)
    scripts/        one-off ops scripts, not part of the runtime

## Architecture
- Components and their single-sentence responsibilities
- Dependency direction (who imports whom; which layers must not depend on which)
- Runtime topology if it's a deployed system (processes, workers, DBs, queues)

Include a Mermaid diagram (GitHub renders it). Prefer a few accurate boxes over
many speculative ones:

    ```mermaid
    flowchart LR
      Client --> API[api/ handlers] --> Svc[services/] --> DB[(Postgres)]
      Svc --> Queue[[jobs queue]] --> Worker[worker/]
    ```

## Key flows
For each of the 2–4 most important flows, a numbered hop-by-hop trace:

### <Flow name, e.g. "Creating an order (POST /orders)">
1. Route registered — `src/api/routes.ts:41`
2. Validation — `src/api/orders.ts:18-52` (zod schema `OrderInput`)
3. Business logic — `src/services/orders.ts:77` `createOrder()`; computes totals, reserves stock
4. Persistence — `src/db/orders.ts:30` inside a transaction
5. Side effects — enqueues `order.created` → `src/worker/notify.ts:12`
- Errors: <how failures surface — exceptions mapped where, retries, idempotency>

## Data model
Core entities, their relationships, and where they're defined (schema files,
ORM models, migrations, protobufs, core types). A small ER-style Mermaid diagram
helps when there are more than ~4 entities.

## Configuration and environment
- Config sources and precedence (files, env vars, flags, remote config)
- Table of important env vars / settings: name, purpose, default, where it's read
- Feature flags, secrets handling, per-environment differences

## External dependencies and integrations
Databases, caches, queues, third-party APIs, other internal services — what each
is used for and where the client code lives. Key libraries that shape the code
(ORM, DI container, state management) belong here too.

## Development workflow
Only commands that actually exist in the repo (manifests, Makefile, CI, docs).
- Setup / install
- Run locally
- Test (layout, how to run one test, fixtures/factories, what's mocked)
- Lint / format / type-check
- CI: which workflows run on PRs and what gates a merge
- Release / deploy

## Conventions and patterns
Naming, error handling, logging, dependency injection, code generation,
module boundaries, "the way things are done here". Point to an exemplary file
that demonstrates the house style.

## History and ownership
- Hotspots (most-changed files) and what that suggests
- Owners / main contributors per area (CODEOWNERS, git history)
- Recent focus (last few months of commits, open PRs/issues if GitHub is available)

## Gotchas, risks and tech debt
Things that would surprise a competent newcomer: magic, hidden coupling, files
you must update together, generated code, flaky tests, deprecated paths still in use,
TODO/FIXME clusters, missing test coverage, places where docs and code disagree,
security-sensitive areas.

## Where to start
- Reading order: 5–8 files, in order, with one line on why each
- Good first tasks / experiments to build intuition (e.g. "add a field to X and follow the compiler errors")

## Glossary
Domain and project-specific terms, with where they appear in code.

## Open questions
What couldn't be determined from the code alone, and who/what might answer it.
```
