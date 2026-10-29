This is a small Express + Prisma + Postgres API (about 1,100 lines of TypeScript) that implements the RealWorld "Conduit" blogging spec. Before writing anything up, I installed it in a scratch copy, ran it against a throwaway Postgres, and ran the tests, linter and endpoints. Your checkout is untouched. The full guide, with `file:line` references, is in **ONBOARDING_GUIDE.md**.

**Three things to know first:**
- **Password hashes leak.** `POST /api/articles/:slug/favorite` (and unfavorite) returns the bcrypt hash and email of every user who favorited the article. I confirmed it by calling the endpoint. It's in `src/app/routes/article/article.service.ts:562-652`, which returns the raw database row instead of going through the mapper the other endpoints use.
- **Real users can't see each other's content.** Article lists, tags and comments only show posts by seeded "demo" users or by the caller. Another user's article is still reachable by its URL and shows up in a follower's feed. That fits a public demo; if real users depend on this service, ask the team about it first.
- **The unit tests fail on a clean checkout: 7 of 27.** All 7 are in `src/tests/services/auth.service.test.ts`, which imports the service before `../prisma-mock`, so the real database client loads instead of the mock. Moving that import to the top makes 26 pass (the 27th is a placeholder). The e2e test and lint (33 errors) also fail, and there's no CI config in the repo.

**Structure**
- `src/main.ts` sets up the app: open CORS, JSON body parsing, routes under `/api`, and one global error handler.
- There are four feature folders under `src/app/routes/`: `auth`, `profile`, `article` and `tag`. Each has a thin `*.controller.ts` (routes plus the auth check), a `*.service.ts` holding the database queries and validation, and a mapper that shapes the response.
- Errors are thrown as `HttpException(status, body)` and turned into responses in `main.ts`. Any other error becomes a 500 with the raw error message, which for database errors includes internal details.

**Auth**
- Login is stateless JWT, HS256 with a 60-day expiry. The token only carries `{ user: { id } }`. There are no roles, refresh tokens or revocation.
- Signing is in `auth/token.utils.ts`; checking is in `auth/auth.ts` (the `express-jwt` library) as two variants, `auth.required` and `auth.optional`.
- The header can be `Authorization: Token <jwt>` or `Bearer <jwt>`. Handlers read the user id from `req.auth.user.id`.
- A bad or expired token gets a 401 even on public routes.
- Passwords are hashed with bcrypt.
- Permission checks are written inline in the services: only the author can edit or delete an article or comment.
- If `JWT_SECRET` isn't set, the code silently falls back to `'superSecret'`, which means anyone could forge tokens.

**Data**
- Postgres through Prisma. The schema is `src/prisma/schema.prisma`; migrations are in `src/prisma/migrations` (four, all from 2021).
- There are four tables: User, Article, Comment, Tag. Tags, favorites and follows are many-to-many links. Deleting a user or article deletes its children.
- Article slugs are the title plus the author id, e.g. `Hello-World-25`.
- `updatedAt` is only set by hand when an article is updated.
- One shared database client lives in `src/prisma/prisma-client.ts`; it's what the tests mock.

**Run locally**
```bash
docker run -d --name realworld-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=realworld -p 5432:5432 postgres:16-alpine
# .env at repo root (gitignored):
#   DATABASE_URL=postgresql://postgres:postgres@localhost:5432/realworld?schema=public
#   JWT_SECRET=change-me
npm ci
npx prisma generate        # needed if npm skips install scripts (npm 11 does by default)
npx prisma migrate deploy
npx prisma db seed         # flaky, see below
npx nx serve api           # http://localhost:3000/api, auto-reload, debugger on :9229
```
`nx serve` reads `.env` for you; the app itself doesn't. If you run the build directly (`node dist/api/main.js`), you have to export the variables yourself. Otherwise the first query fails because the database URL is missing, and the JWT secret falls back to the default.

**Test**
- Unit tests: `npx nx test api`. They need no database because the client is mocked.
- Single file: `npx jest -c jest.config.ts <file>`.
- e2e: `npx nx e2e e2e`. Start the server yourself first. It currently fails because it expects `{message:'Hello API'}` from `GET /`.
- The tests only cover services and mappers. Nothing tests the HTTP routes or a real database.

**Other issues I confirmed**
- Updating an article without `tagList` deletes all its tags.
- Commenting on an article that doesn't exist, or posting without a `comment` field, returns a 500 instead of a 404 or 422.
- `PUT /user` with an email or username that's already taken returns a 500 instead of a 422.
- The login response has no `id`, unlike register and `GET /user`.
- The seed script fails partway on a tag-name clash (in my run, 5 of 144 articles were created) but still prints success.

Files are in benchmarks/iteration-1/ts-service-local-checkout/without_skill/outputs:
- ONBOARDING_GUIDE.md

I can also turn the guide into a shareable page for the team.
