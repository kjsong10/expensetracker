# How authentication works

This is a mechanical, step-by-step walkthrough of the login flow. For *why* it's built this way (Authlib vs. hand-rolled, cookie vs. JWT, etc.), see [docs/ARCHITECTURE.md §3.7](ARCHITECTURE.md#37-authentication--multi-tenancy). This document is about *what actually happens*, in order, so it doubles as a debugging reference if the flow ever misbehaves.

## The pieces involved

- **`api/auth.py`** — configures the Google OAuth client (`oauth`) and defines `get_current_user`, the dependency every protected endpoint uses.
- **`api/routers/auth.py`** — the four `/auth/*` endpoints that drive the flow.
- **`SessionMiddleware`** ([api/main.py](../api/main.py)) — Starlette middleware that reads/writes a signed cookie called `session` on every request, exposing its contents as a plain dict at `request.session`.
- **`frontend/src/components/LoginButton.jsx`** and **`App.jsx`** — the only frontend pieces that know about auth at all.

## Step by step: signing in

1. **You click "Sign in with Google"** ([LoginButton.jsx](../frontend/src/components/LoginButton.jsx)). This is a plain `<a href="http://localhost:8000/auth/login">`, not a `fetch()` call — the whole point of the next few steps is a chain of full-page browser redirects, which only works as an actual navigation.

2. **`GET /auth/login`** ([routers/auth.py](../api/routers/auth.py)) calls `oauth.google.authorize_redirect(request, redirect_uri)`. Authlib:
   - generates a random `state` value (CSRF protection — proves the callback in step 4 corresponds to a request *this* browser actually initiated) and a random `nonce` (replay protection for the ID token in step 5),
   - stores both, plus the intended `redirect_uri`, in `request.session` (the cookie — nothing server-side yet),
   - responds with `302 Found`, `Location: https://accounts.google.com/o/oauth2/v2/auth?...&client_id=...&redirect_uri=http://localhost:8000/auth/callback&scope=openid+email+profile&state=...&nonce=...`.

3. **Your browser follows the redirect to Google.** You see Google's real consent screen, sign in (or Google recognizes an existing session), and approve. This step happens entirely on Google's servers — this app never sees your Google password, only whatever Google decides to hand back.

4. **Google redirects back to `GET /auth/callback?code=...&state=...`**. Authlib's `authorize_access_token(request)`:
   - checks the returned `state` matches what was stashed in the session cookie in step 2 — if it doesn't, the request is rejected (this is what stops an attacker from tricking your browser into completing *their* login flow),
   - exchanges the authorization `code` for tokens by calling Google's token endpoint server-to-server (this app's `GOOGLE_CLIENT_SECRET` is used here, and only here — it never touches the browser),
   - receives an **ID token** (a signed JWT asserting who you are) and validates it: signature against Google's published public keys, `iss` is really `accounts.google.com`, `aud` matches our `GOOGLE_CLIENT_ID`, `exp` hasn't passed, and the `nonce` claim matches what was stashed in step 2.
   - The validated claims come back as `token["userinfo"]` — a dict with (at minimum) `sub` (Google's permanent, unique ID for that account — *not* the email, since a user could change their email later), `email`, and `name`.

5. **Look up or create the `User` row** ([routers/auth.py](../api/routers/auth.py)):
   ```python
   user = session.exec(
       select(User).where(User.oauth_provider == "google", User.oauth_subject == subject)
   ).first()
   if user is None:
       user = User(display_name=name, email=email, oauth_provider="google", oauth_subject=subject)
   ```
   The lookup key is `(oauth_provider, oauth_subject)` — Google's `sub`, not the email — because emails can change or be reused across accounts in ways a stable account ID can't. First-ever login for a given Google account creates the row right here; every later login just finds it again.

6. **The session is set**: `request.session["user_id"] = user.id`. `SessionMiddleware` serializes the whole session dict, signs it with `SESSION_SECRET_KEY`, and sends it back as a `Set-Cookie: session=<signed-value>; HttpOnly; SameSite=Lax; Path=/`.

7. **Redirect to the frontend**: `RedirectResponse(FRONTEND_URL)` sends the browser to `http://localhost:5173`. The cookie set in step 6 is now attached to the browser for the API's origin and will be sent automatically on every subsequent request to `localhost:8000` — no frontend code ever handles a token.

8. **The frontend loads and calls `GET /auth/me`** ([App.jsx](../frontend/src/App.jsx), on mount). The browser attaches the session cookie automatically. `get_current_user` (see below) resolves it to the `User` row, `/auth/me` returns `{id, display_name, email}`, and the app renders the dashboard instead of the sign-in screen.

## What's actually in the cookie

Just one key: `{"user_id": 7}` (plus whatever transient `state`/`nonce` Authlib stashes mid-flow, cleared once the flow completes). It's **signed, not encrypted** — anyone can base64-decode the cookie and read `user_id` in plain text, but they cannot *change* it, because any tampering invalidates the signature and `itsdangerous` rejects the cookie outright. The security property is "the browser can't forge or edit this," not "the browser can't see it" — there's nothing secret in it worth hiding (no password, no token, just an integer).

## How protected endpoints enforce this

Every endpoint that should only see one user's data takes `current_user: User = Depends(get_current_user)`:

```python
def get_current_user(request: Request, session: Session = Depends(get_session)) -> User:
    user_id = request.session.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
```

No cookie, tampered cookie, or a cookie naming a deleted user → `401` before the route body ever runs. This is what changed from the pre-OAuth version of this app: `user_id` used to be a value the *client* supplied (a query param or request field), trusted at face value. Now it's a value the *server* derives from a cryptographically-verified cookie — a client can no longer just say "I'm user 12" and have it believed. `GET /transactions/list`, `POST /transactions/create`, `GET /transactions/{id}`, and all three `/plaid/*` endpoints all use `current_user.id` for every read and write; none of them accept a `user_id` from the request anymore.

## Logging out

`POST /auth/logout` calls `request.session.clear()`, which tells `SessionMiddleware` to send back an expired cookie — the browser deletes it, and the next request has no session at all. **What this does not do**: rotate `SESSION_SECRET_KEY` or invalidate the cookie on the server side. If someone had already copied the cookie value before you logged out (e.g. via a browser extension with cookie access, or a compromised machine), that copy remains valid — signed cookies aren't tracked anywhere server-side to be revoked individually. This is a deliberate, named trade-off (see [docs/ARCHITECTURE.md §6](ARCHITECTURE.md#6-known-limitations--next-steps)): fixing it means adding a server-side session table (store an opaque session ID in the cookie instead of the data itself, look it up on every request, delete the row on logout) — real added complexity this app doesn't need yet, since nothing else in it has a "log out one specific device" story either.

## Local setup

1. Go to [console.cloud.google.com](https://console.cloud.google.com) → APIs & Services → Credentials.
2. Create Credentials → OAuth client ID → Application type: **Web application**.
3. Under **Authorized redirect URIs**, add exactly `http://localhost:8000/auth/callback` — this must match what `GET /auth/login` sends Google byte-for-byte, or Google rejects the request with a `redirect_uri_mismatch` error.
4. Copy the generated Client ID and Client Secret into `.env`:
   ```
   GOOGLE_CLIENT_ID=...
   GOOGLE_CLIENT_SECRET=...
   ```
5. Generate a session-signing secret and add it too — any long random string works:
   ```bash
   openssl rand -hex 32
   ```
   ```
   SESSION_SECRET_KEY=<paste the output here>
   ```
6. `FRONTEND_URL=http://localhost:5173` should already be set (default) — this is where step 7 above redirects to.
7. If your Google Cloud project's OAuth consent screen is in "Testing" mode (the default for a new project), only accounts you've explicitly added as test users can complete login — add your own Google account under **Audience → Test users** in the consent screen settings, or publish the app if you want anyone to be able to sign in.
