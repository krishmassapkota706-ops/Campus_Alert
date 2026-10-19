# ReportSDState API

Base URL: `http://<host>:5000/api/v1`. All bodies are JSON.

**Auth:** protected endpoints need `Authorization: Bearer <access_token>`. Access tokens last 15 minutes; use the refresh token with `POST /auth/refresh` to get a new one.

**Errors** always look like this (see `README.md`):

```json
{ "error": { "code": "validation_error", "message": "Some fields are invalid.", "fields": { "email": "Use your SDSU school email (@jacks.sdstate.edu)." } } }
```

| Status | `code` | Meaning |
|---|---|---|
| 401 | `unauthorized`, `invalid_token`, `token_expired`, `token_revoked`, `invalid_credentials` | Not signed in, or token no longer valid |
| 403 | `forbidden`, `email_not_verified` | Signed in but not allowed |
| 404 | `not_found` | |
| 409 | `conflict` | Duplicate (for example, email already registered) |
| 422 | `validation_error` | Field errors in `fields` |
| 429 | `too_many_requests` | Rate limit hit; retry later |
| 503 | `email_unavailable` | Email provider down; nothing was saved |

## Health

### `GET /health`
`200 {"status": "ok", "environment": "development"}`

## Auth

Rate limits per IP: register, resend, forgot-password = 5/min and 20/hour; others = 10/min and 100/hour.

### `POST /auth/register`
```json
{ "email": "jack@jacks.sdstate.edu", "password": "Jackrabbits2026", "name": "Jack Rabbit" }
```
- Email must be `@jacks.sdstate.edu`. Password: 10–128 characters, at least one letter and one number.
- Emails a 6-digit code. The account can't sign in until it's verified.
- `201 {"user": User, "message": "..."}` · `409` duplicate · `422` invalid fields · `503` email couldn't be sent (nothing saved)

### `POST /auth/verify-email`
```json
{ "email": "jack@jacks.sdstate.edu", "code": "123456" }
```
`200 Tokens + {"user": User}` · `400 invalid_code` (wrong, expired, used, or 5 wrong attempts)

### `POST /auth/resend-verification`
`{ "email": "..." }` → always `202`. Sends a new code only if the account exists and is unverified; earlier codes stop working.

### `POST /auth/login`
`{ "email": "...", "password": "..." }` → `200 Tokens + {"user": User}` · `401 invalid_credentials` · `403 email_not_verified`

### `POST /auth/refresh` 🔒 refresh token
Send the **refresh** token in the `Authorization` header. → `200 {"access_token", "token_type", "expires_in"}`

### `POST /auth/logout` 🔒
Revokes the token sent and its refresh token. → `204`

### `POST /auth/forgot-password`
`{ "email": "..." }` → always `202`. Emails a reset code if the account exists.

### `POST /auth/reset-password`
```json
{ "email": "...", "code": "123456", "new_password": "BrandNewPass99" }
```
`200` · `400 invalid_code`. Signs out every existing session for that account.

## Me (profile)

### `GET /me` 🔒
`200 User`

### `PATCH /me` 🔒
Send only the fields you're changing:
```json
{ "name": "Jack R.", "phone": "(605) 555-0142" }
```
Phone numbers are normalized to E.164 (`+16055550142`); send `"phone": null` to remove it. Email and role can't be changed. → `200 User` · `422`

### `POST /me/password` 🔒
```json
{ "current_password": "...", "new_password": "..." }
```
`200 Tokens`. Other sessions are signed out, so store the new tokens on this device. · `422` wrong current password or weak new password

## Emergency contacts

Each user can save up to 5. Another user's contact returns `404`.

### `GET /contacts` 🔒
`200 {"contacts": [Contact, ...]}`

### `POST /contacts` 🔒
```json
{ "name": "Mom", "phone": "605-555-0199", "relationship": "Parent" }
```
`relationship` is optional. → `201 Contact` · `409 contact_limit` · `422` invalid phone

### `GET /contacts/<id>` 🔒
`200 Contact` · `404`

### `PATCH /contacts/<id>` 🔒
Any of `name`, `phone`, `relationship`. → `200 Contact` · `404` · `422`

### `DELETE /contacts/<id>` 🔒
`204` · `404`

## Shapes

**Tokens**
```json
{ "access_token": "...", "refresh_token": "...", "token_type": "Bearer", "expires_in": 900 }
```

**Contact**
```json
{ "id": 3, "name": "Mom", "phone": "+16055550199", "relationship": "Parent" }
```

**User**
```json
{ "id": 1, "email": "jack@jacks.sdstate.edu", "name": "Jack Rabbit", "phone": null, "role": "student", "email_verified": true, "created_at": "2026-10-19T15:04:05.123456Z" }
```
