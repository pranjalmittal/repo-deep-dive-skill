---
type: llm
focus: trace
weight: 1
---

The output explains that unit tests in src/tests mock Prisma with jest-mock-extended (src/tests/prisma-mock.ts) so no database is needed, distinct from the e2e tests in e2e/ that need a running server.
