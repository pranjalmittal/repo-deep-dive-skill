---
type: llm
focus: trace
weight: 1
---

Run instructions use only commands that exist in the repo (e.g. npm install, npx prisma generate, npx prisma migrate deploy, npx nx serve api, npx prisma db seed, npx nx test) and invent no nonexistent npm scripts such as `npm run dev`.
