# realworld-api: onboarding guide

A guide to the Node/Express/Prisma implementation of the [RealWorld](https://github.com/gothinkster/realworld) ("Conduit") API spec. It's a Medium-style blogging backend with users, profiles, follows, articles, tags, comments and favorites.

Everything under "Verified" below was run on 2026-10-29 against a scratch copy of the checkout, using Node 24 and Postgres 16 in a container. File references are `path:line` relative to the repo root.

---

## 1. At a glance

| | |
|---|---|
| Runtime | Node.js, TypeScript 5.2, Express 4.18 |
| Build/task runner | Nx 17 (`project.json`), esbuild (unbundled CJS output to `dist/api`) |
| DB / ORM | PostgreSQL via Prisma 4.16 (`src/prisma/schema.prisma`) |
| Auth | Stateless JWT (HS256, 60-day expiry). `jsonwebtoken` signs, `express-jwt` verifies |
| Passwords | bcryptjs, cost 10 |
| Tests | Jest + ts-jest. Unit tests mock Prisma with `jest-mock-extended`. One e2e project with axios |
| Size | About 1,100 lines of app code in 25 files. No DI framework, no validation library, no logger |
| History | Forked from the 2017 anishkny/gothinkster repo and moved to Nx in Dec 2023/Jan 2024 (Gerome Grignon). The local `.git` is incomplete: some objects are missing, so `git show` on recent commits fails. |

---

## 2. Layout

```
src/
  main.ts                      Express app: middleware, static images, error handler, listen()
  app/
    models/http-exception.model.ts   HttpException(errorCode, message): the only error type
    routes/
      routes.ts                mounts all routers under /api
      auth/                    users, login, JWT middleware, token signing
        auth.controller.ts     POST /users, POST /users/login, GET/PUT /user
        auth.service.ts        createUser / login / getCurrentUser / updateUser
        auth.ts                express-jwt middlewares: auth.required, auth.optional
        token.utils.ts         generateToken(id)
        user-request.d.ts      augments Express.Request with req.auth.user.id
      profile/                 GET profile, follow/unfollow
      article/                 articles, feed, comments, favorites (the largest module)
        article.service.ts     652 lines, most of the business logic
        article.mapper.ts, author.mapper.ts   DB row to API shape
      tag/                     GET /tags (top 10)
  prisma/
    schema.prisma              data model (single source of truth)
    migrations/                4 SQL migrations (2021)
    prisma-client.ts           shared PrismaClient singleton
    seed.ts                    fake data generator (@ngneat/falso)
  tests/
    prisma-mock.ts             jest.mock of prisma-client using mockDeep<PrismaClient>()
    services/*.test.ts, utils/*.test.ts
  assets/images/               served statically at /images/*
e2e/                           separate Nx project "e2e" (jest + axios against a running server)
project.json                   Nx targets: build, serve, lint, test, docker-build
Dockerfile                     Nx-generated, runs dist/api
```

**Pattern:** each feature folder follows the same pattern: `*.controller.ts` (Express Router plus auth middleware), then `*.service.ts` (Prisma queries plus validation, throws `HttpException`), then `*.mapper.ts`/`*.utils.ts` (shapes the response). Controllers are thin try/catch wrappers that call `next(error)`.

### Request lifecycle

1. `src/main.ts:13-16`: `cors()` (all origins), `bodyParser.json()`, urlencoded, then `routes`.
2. `src/app/routes/routes.ts:7-13`: the tag, article, profile and auth routers are mounted under `/api`.
3. The route handler runs `auth.required` or `auth.optional` (`src/app/routes/auth/auth.ts`), then the service, then `res.json(...)`.
4. Errors go to the global handler at `src/main.ts:26-47`:
   - `UnauthorizedError` (from express-jwt) returns **401** `{status:'error', message:'missing authorization credentials'}` for any JWT problem: missing, malformed, expired or bad signature.
   - `HttpException` returns `err.errorCode` with `err.message` as the body (usually `{errors:{field:[...]}}`).
   - Anything else returns **500** with `err.message` as a JSON string. For Prisma errors this includes the query and the server file path (see Gotchas).
5. `GET /` returns `{status:'API is running on /api'}` (`src/main.ts:21`). `/images/*` serves `src/assets/images`.

### Endpoints

| Method | Path | Auth | Service fn |
|---|---|---|---|
| POST | /api/users | none | `createUser` (auth.service.ts:38) |
| POST | /api/users/login | none | `login` (auth.service.ts:84) |
| GET | /api/user | required | `getCurrentUser` (:131) |
| PUT | /api/user | required | `updateUser` (:151) |
| GET | /api/profiles/:username | optional | `getProfile` (profile.service.ts:5) |
| POST/DELETE | /api/profiles/:username/follow | required | `followUser` / `unfollowUser` |
| GET | /api/articles?tag&author&favorited&limit&offset | optional | `getArticles` (article.service.ts:69) |
| GET | /api/articles/feed | required | `getFeed` (:113) |
| POST | /api/articles | required | `createArticle` (:162) |
| GET/PUT/DELETE | /api/articles/:slug | opt / req / req | `getArticle` / `updateArticle` / `deleteArticle` |
| GET/POST | /api/articles/:slug/comments | opt / req | `getCommentsByArticle` / `addComment` |
| DELETE | /api/articles/:slug/comments/:id | required | `deleteComment` (:527) |
| POST/DELETE | /api/articles/:slug/favorite | required | `favoriteArticle` / `unfavoriteArticle` |
| GET | /api/tags | optional | `getTags` (tag.service.ts:4) |

Request and response bodies use the RealWorld envelope: `{ "user": {...} }`, `{ "article": {...} }`, `{ "comment": { "body": ... } }`.

---

## 3. How auth works

**Registration** (`auth.service.ts:38-82`): trims email, username and password and returns a 422 if any is blank. `checkUserUniqueness` makes two `findUnique` calls and returns a 422 `has already been taken` for each conflicting field. It then runs `bcrypt.hash(password, 10)`, creates the user, and returns the user plus a token. The controller forces `demo: false` (`auth.controller.ts:16`).

**Login** (`auth.service.ts:84-129`): `findUnique({email})`, then `bcrypt.compare`. On success it returns `{email, username, bio, image, token}`. Note that the response has **no `id`**, while register and `GET /user` do include `id`. On failure it returns a **403** `{"errors":{"email or password":["is invalid"]}}`. The same message covers an unknown email and a wrong password.

**Token** (`token.utils.ts:3-6`): `jwt.sign({ user: { id } }, JWT_SECRET || 'superSecret', { expiresIn: '60d' })`. The only claim is the user id. There are no roles, refresh tokens or revocation. Every `GET /user` and `PUT /user` call mints a fresh 60-day token.

**Verification** (`auth.ts`):
- `getTokenFromHeaders` accepts `Authorization: Token <jwt>` (the RealWorld convention) **or** `Bearer <jwt>`.
- `auth.required` is express-jwt with HS256. A missing or invalid token returns 401.
- `auth.optional` sets `credentialsRequired: false`. No header means anonymous. A **bad or expired token still returns 401**, even on public routes like `/api/tags` (verified).
- On success, express-jwt puts the decoded payload on `req.auth`, so handlers read `req.auth?.user?.id` (types are in `user-request.d.ts`).

**Authorization:** this is done ad hoc in the services:
- Article update and delete look up the author and return 403 if `author.id !== id` (`article.service.ts:310`, `:404`).
- Comment delete looks the comment up by `{id, author.id: userId}`, so someone else's comment gives a 404, not a 403 (`:528-547`). The `:slug` in the URL is ignored.

**Secret handling:** `JWT_SECRET` falls back to the hard-coded `'superSecret'` in three places (`auth.ts:16,21`, `token.utils.ts:4`). If the env var is missing in any environment, anyone can forge tokens for any user id. Consider failing fast at startup instead.

---

## 4. How data is stored

PostgreSQL, accessed only through Prisma. Schema: `src/prisma/schema.prisma`. Connection: `DATABASE_URL`.

```
User 1───* Article (authorId, onDelete: Cascade)
User 1───* Comment (authorId, Cascade)
Article 1───* Comment (articleId, Cascade)
Article *───* Tag            implicit join table _ArticleToTag
Article *───* User           "UserFavorites"  -> _UserFavorites
User    *───* User           "UserFollows"    -> _UserFollows (followedBy / following)
```

| Model | Notable fields |
|---|---|
| `User` | `email` and `username` unique. `password` is a bcrypt hash. `image` defaults to `https://api.realworld.io/images/smiley-cyrus.jpeg`. **`demo Boolean @default(false)`** |
| `Article` | `slug` unique. `createdAt` and `updatedAt` both `@default(now())`, **not** `@updatedAt`, so only `updateArticle` bumps `updatedAt` (manually, `article.service.ts:354`) |
| `Comment` | `body`, timestamps, FKs to article and author |
| `Tag` | `name` unique, created on demand with `connectOrCreate` |

- **Client:** `src/prisma/prisma-client.ts` exports one `PrismaClient`. It caches the client on `global` only when `NODE_ENV === 'development'`. Every service imports this default export, and that is the seam the unit tests mock.
- **Migrations:** `src/prisma/migrations/`, 4 of them, all from 2021: initial, implicit tags (dropped the explicit `ArticleTags` table), the default image URL change, and an index rename. Workflow: edit `schema.prisma`, run `npx prisma migrate dev --name <change>`, then commit the generated SQL. Production runs `npx prisma migrate deploy`.
- **Slugs:** `${slugify(title)}-${authorId}` (`article.service.ts:178`). Case is preserved (e.g. `Hello-World-25`), and the slug changes when the title changes.

### The `demo` flag: content visibility

This is the most surprising behaviour in the codebase. Article lists, tags and comments only show content written by **demo users (seeded) or by the caller**:

- `getArticles` (`article.service.ts:13-40`): `author: { OR: [{demo: true}, {id: me}] }`
- `getTags` (`tag.service.ts:5-24`): only tags used on demo or own articles
- `getCommentsByArticle` (`article.service.ts:417-431`): only comments by demo authors or by me

Verified: user B could not see user A's article in `GET /api/articles?author=A` (count 0). B **could** still fetch it by slug, and it **did** appear in B's `/articles/feed` after following A (the feed doesn't apply the filter). This looks like a deliberate choice for the public demo instance, so that strangers' posts don't appear. If this service is meant for real users, it is the first thing to raise with the team.

---

## 5. Running locally

Prerequisites: Node 18+ (verified on 24), and a Postgres instance (local or container).

```bash
# 1. Postgres (any runtime; podman and docker take the same flags)
docker run -d --name realworld-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=realworld \
  -p 5432:5432 postgres:16-alpine

# 2. .env at repo root (gitignored). Prisma CLI reads it automatically
cat > .env <<'EOF'
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/realworld?schema=public
JWT_SECRET=change-me-locally
NODE_ENV=development
EOF

# 3. Install, generate the client, migrate, seed
npm ci
npx prisma generate          # REQUIRED if your npm skips install scripts (npm 11 "allow-scripts" does)
npx prisma migrate deploy    # or `npx prisma migrate dev` while developing schema changes
npx prisma db seed           # see seed caveat below

# 4. Run (build + watch + restart, inspector on :9229)
npx nx serve api             # http://localhost:3000/api
```

> **Env caveat (verified):** the app itself does **not** use `dotenv`. `.env` works with `npx nx serve api` because **Nx** injects `.env` into the task's environment, and the Prisma CLI (`migrate`, `db seed`) reads it too. If you run the built output directly (`node dist/api/main.js`), nothing reads `.env`. You get `Environment variable not found: DATABASE_URL` on the first query, and `JWT_SECRET` silently falls back to `'superSecret'`. Export the variables in your shell or process manager in that case.

Production-style run: `npx nx build api`, then `node dist/api/main.js` (README deploy line: `npm ci && npx prisma migrate deploy && node dist/api/main.js`).

Quick smoke test:
```bash
curl -s -XPOST localhost:3000/api/users -H 'Content-Type: application/json' \
  -d '{"user":{"username":"me","email":"me@example.com","password":"pw"}}'
TOKEN=...   # from response.user.token
curl -s localhost:3000/api/user -H "Authorization: Token $TOKEN"
```

Other targets: `npx nx lint api`, `npx nx docker-build api` (build, then `docker build -t api`), `npx nx graph`.

---

## 6. Testing

| Kind | Command | What it is |
|---|---|---|
| Unit | `npx nx test api` (or `npm test`) | `src/tests/**`, Jest + ts-jest, no DB needed |
| Coverage | `npx nx test api --configuration=ci` | CI mode plus coverage into `coverage/api` |
| Single file | `npx jest -c jest.config.ts src/tests/services/article.service.test.ts` | |
| e2e | `npx nx e2e e2e` (server must already be running on HOST/PORT, default localhost:3000) | `e2e/src/server/server.spec.ts` |

**How mocking works:** `src/tests/prisma-mock.ts` calls `jest.mock('../prisma/prisma-client', () => ({ default: mockDeep<PrismaClient>() }))` and resets the mock before each test. In a test you write `prismaMock.user.findUnique.mockResolvedValue(...)` and then call the real service function. The tests cover services and mappers only. There are no controller or HTTP-level tests and no integration tests against a real DB.

**Current state (verified):** `nx test api` **fails**: 19 pass, 7 fail, 1 todo.
- All 7 failures are in `src/tests/services/auth.service.test.ts`. The cause is **import order**: line 2 imports `auth.service` (which loads the real Prisma client) *before* line 3 imports `../prisma-mock`. Because the `jest.mock` call lives inside `prisma-mock.ts` rather than in the test file, Jest doesn't hoist it, so the real client runs and fails on `DATABASE_URL`. The other test files import `prisma-mock` first and pass. **Fix:** move `import prismaMock from '../prisma-mock';` to the top. After that change, all 26 tests pass plus 1 todo (verified).
- `tag.service.test.ts` contains only a `test.todo`.
- The e2e spec expects `GET /` to return `{message:'Hello API'}` (Nx scaffold), but the app returns `{status:'API is running on /api'}`, so it fails. `global-setup.ts` also doesn't start the server or a DB.

**Lint:** `nx lint api` fails with 33 errors, mostly `no-explicit-any`, plus `@ts-ignore` and an unused var.

**CI:** there's no CI config in the tree. The README's Travis badge and the CircleCI history are leftovers from 2017.

---

## 7. Gotchas and known issues (ranked)

1. **Password hashes leak from the favorite and unfavorite endpoints.** `favoriteArticle` and `unfavoriteArticle` (`article.service.ts:562-652`) spread the raw Prisma row into the response, including `favoritedBy: true`, which is the full `User` rows. **Verified:** `POST /api/articles/:slug/favorite` returned `favoritedBy[].password` (the bcrypt hash) and `email` for every user who favorited, plus `id` and `authorId`. Fix: use `articleMapper`, like the other article endpoints do.
2. **`JWT_SECRET` falls back to `'superSecret'`** (see §3). Only `nx serve` loads `.env`. `node dist/api/main.js` does not (§5).
3. **Visibility filter on `demo`** (see §4) hides real users' content from each other.
4. **Error responses leak internals.** Unhandled Prisma errors return a 500 with the full query and server file path. Examples: favoriting an unknown slug, or commenting on an unknown slug (`addComment` doesn't 404, `:478-499`). `POST /comments` without a `comment` key returns a 500 `Cannot read properties of undefined (reading 'body')` (`article.controller.ts:175`).
5. **`PUT /articles/:slug` without `tagList` wipes all tags.** It always calls `disconnectArticlesTags` first (`article.service.ts:343`). Verified.
6. **`PUT /user`** has no uniqueness check, so a duplicate email or username becomes a Prisma P2002 error and a 500 instead of a 422. It also can't clear `bio` or `image`, because falsy values are skipped (`auth.service.ts:164-168`).
7. **Login response omits `id`**, unlike register and `GET /user`.
8. **Seed script is flaky and hides failures.** Articles are created in parallel with random tag words, so concurrent `connectOrCreate` calls on the same new tag hit `Unique constraint failed on (name)`. The `catch` only logs, so Prisma still prints "seed command has been executed". In my run it created 12 users and only 5 of the intended 144 articles. Re-running adds 12 more users each time.
9. **Over-fetching.** Every article query includes `favoritedBy: true` and `author.followedBy: true` (full user rows, hashes included) just to compute booleans and counts. Cost grows with popularity. `_count` is fetched but ignored by `articleMapper`.
10. **Docker image is probably incomplete (not verified).** The build output contains no `schema.prisma` or migrations, so `npm install` inside the image can't generate a real Prisma client, and nothing runs migrations. Check this before relying on `nx docker-build`.
11. **No input validation library, rate limiting, request logging, health endpoint or graceful shutdown.** `cors()` allows every origin.
12. **No pagination cap.** `limit` is passed straight to `take`.

---

## 8. Suggested reading order (about an hour)

1. `src/main.ts`, then `src/app/routes/routes.ts`: app wiring and error handling
2. `src/app/routes/auth/auth.ts`, `token.utils.ts`, `auth.service.ts`: auth end to end
3. `src/prisma/schema.prisma`, then `src/prisma/prisma-client.ts`
4. `src/app/routes/article/article.controller.ts`, then `article.service.ts` (`buildFindAllQuery`, `createArticle`, `updateArticle`), then `article.mapper.ts`
5. `src/app/routes/profile/*`, `src/app/routes/tag/*`: small, same pattern
6. `src/tests/prisma-mock.ts`, then `src/tests/services/profile.service.test.ts`: how to write a test
7. `project.json`, `package.json` (`prisma.seed`, `prisma.schema`), `Dockerfile`

## 9. Questions to ask the team

- Is the `demo` visibility filter intended for this deployment?
- Where does this actually run, and how are `DATABASE_URL` and `JWT_SECRET` injected (the built app has no dotenv)? Is the Docker image used?
- Is there CI outside the repo? Who owns the failing unit, e2e and lint checks?
- Any plan to upgrade Prisma 4 to 5 or 6, or Express 4 to 5?
