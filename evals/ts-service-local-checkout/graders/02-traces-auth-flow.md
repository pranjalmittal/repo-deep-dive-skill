---
type: llm
focus: trace
weight: 1
---

The auth explanation traces the real flow with file references: the Authorization header accepts both `Token` and `Bearer` (src/app/routes/auth/auth.ts), express-jwt `auth.required`/`auth.optional` middleware populates `req.auth.user.id`, tokens are signed in token.utils.ts with a 60d expiry, and passwords are hashed/compared with bcryptjs in auth.service.ts.
