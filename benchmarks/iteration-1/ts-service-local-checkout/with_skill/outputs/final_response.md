I've written an onboarding guide to `REPO_GUIDE.md` at the repo root. It's a new untracked file and I haven't committed it. I only read the code: I didn't install, build or run anything, so the commands it lists come from the repo's own scripts and README.

**What this is:** a TypeScript JSON API built on Express 4, Prisma 4 and PostgreSQL. It implements the RealWorld "Conduit" spec, a Medium-style blog backend with users, articles, comments, tags, favorites and follows. Each endpoint follows the same path: an Express router file checks the JWT, a service file validates input and queries Prisma directly, and a mapper builds the JSON response.

**How it fits together**
- **Structure:** `src/main.ts` sets up the middleware and one global error handler, and `src/app/routes/routes.ts` mounts four feature folders (`auth`, `article`, `profile`, `tag`) under `/api`. Each folder has a `*.controller.ts` for routes, a `*.service.ts` for logic and Prisma calls, and mappers. There's no repository layer, no dependency injection and no background jobs.
- **Auth:**
  - Register and login hash passwords with bcrypt and return a token signed with `JWT_SECRET`. The token carries only `{ user: { id } }` and lasts 60 days (`src/app/routes/auth/token.utils.ts`).
  - Routes use `auth.required` or `auth.optional` from `express-jwt` (`src/app/routes/auth/auth.ts`). Clients send either `Token <jwt>` or `Bearer <jwt>`, and the user id ends up in `req.auth.user.id`.
  - There are no roles. The only permission check is "do you own this article or comment", written inside the services.
- **Data:** `src/prisma/schema.prisma` defines four tables (User, Article, Comment, Tag) plus three automatic join tables for tags, favorites and follows. The SQL migrations are in `src/prisma/migrations/`.
- **Errors:** services throw `HttpException(status, body)` and `main.ts` turns it into the response. Any other error becomes a 500 that includes the raw error message.

**Running and testing locally**
1. Start your own Postgres. The repo has no docker-compose.
2. Create a `.env` at the repo root with `DATABASE_URL` and `JWT_SECRET`.
3. Run `npm install`, then `npx prisma generate`, `npx prisma migrate deploy` and `npx prisma db seed`.
4. Start the server with `npx nx serve api`. It listens on port 3000.
5. Run the unit tests with `npm test`. They mock Prisma using `src/tests/prisma-mock.ts`, so they don't need a database.

The e2e suite is an unedited Nx placeholder that will fail as it stands, and the repo has no CI config.

**Things that will bite you (details and line numbers in the guide)**
1. **Data leak:** `POST` and `DELETE /api/articles/:slug/favorite` send back the full user rows of everyone who favorited the article, including email and password hash (`src/app/routes/article/article.service.ts:597-603`). This is the first thing I'd fix.
2. **Default JWT secret:** if `JWT_SECRET` isn't set, the service quietly uses `'superSecret'`, which means anyone can forge tokens.
3. **Hidden content:** the article list, tags and comments only show content from seeded "demo" users or from the person asking. If you test with two fresh accounts, neither will see the other's posts.
4. **Tags wiped on edit:** a `PUT /articles/:slug` request without `tagList` deletes all of the article's tags.

**Where to start reading:** `src/main.ts`, then `src/app/routes/auth/auth.ts` with `auth.service.ts`, then `src/app/routes/article/article.service.ts`.

Guide: `benchmarks/iteration-1/ts-service-local-checkout/with_skill/work/realworld-api/REPO_GUIDE.md`

**Assumptions:**
- This checkout is your team's service. It's actually the public upstream `gothinkster` example, with no internal CI, CODEOWNERS or deploy config, so your team's real pipeline and hosting aren't covered. I've listed those under Open questions in the guide.
- Some local history is missing (the clone has gaps), so the guide has no per-file history.

From here I can run the test suite and confirm the local setup works, fix the favorite data leak with a test, or trace another flow in more depth.
