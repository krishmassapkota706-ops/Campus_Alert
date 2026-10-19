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

## Reports

Categories: `maintenance` (dorm / facilities), `crime` (non-emergency), `emergency` (quick report after SOS), `other`. There is **no health category**: health and mental-health help is redirect-only (see Resources). Statuses: `submitted`, `in_review`, `resolved`.

The reporter is stored encrypted. Students can only see their own reports.

### `POST /reports` 🔒
```json
{ "category": "maintenance", "location": "Hansen Hall 214", "details": "Heater not working" }
```
`location` up to 200 characters, `details` up to 1000.
→ `201 {"report": Report, "message": "Report received. Your reference ID is RPT-7K2Q9M."}` · `422`

Only show a confirmation after this returns `201`.

### `GET /reports` 🔒
Your own reports, newest first. Query: `category`, `page` (default 1), `per_page` (default 20, max 100).
→ `200 {"reports": [Report, ...], "page": 1, "per_page": 20, "total": 2}`

### `GET /reports/<reference_id>` 🔒
`200 Report` · `404` (not found or not yours)

## Resources (public)

No sign-in needed, so crisis info stays reachable even when signed out.

### `GET /resources`
Query: `category` (`emergency`, `crisis`, `health`, `safety`, `housing`, `campus`), `q` (searches name and description).
→ `200 {"resources": [Resource, ...], "categories": [...]}`

Show `phone` on screen but **dial `dial_number`**. In demo mode it's the test number.

## Emergency

### `GET /emergency/config` (public)
```json
{
  "demo_mode": true,
  "notice": "ReportSDState does not replace 911. ...",
  "demo_notice": "Demo mode: call buttons dial a test number, ...",
  "campus_police": { "name": "SDSU University Police", "phone": "+16056885117", "dial_number": "+16055550100" },
  "emergency_services": { "name": "Emergency Services", "phone": "911", "dial_number": "+16055550100" },
  "crisis_line": { "name": "988 Suicide & Crisis Lifeline", "phone": "988", "dial_number": "+16055550100" },
  "sos_hold_seconds": 2
}
```
Show `notice` on the emergency screen (US-09), and `demo_notice` when it isn't null.

### `POST /emergency/events` 🔒
Call this when an emergency call button is used. It returns the number to dial.
```json
{ "action": "call_campus_police" }
```
`action`: `call_campus_police`, `call_911`, `call_crisis_line`, or `call_contact` (also needs `"contact_id"`). No location or free text is stored.
→ `201 {"event": {"id", "action", "simulated", "created_at"}, "dial_number": "+16055550100", "message": "..."}` · `404` contact not yours · `422`

If this request fails (offline, signed out), dial the `dial_number` from `/emergency/config` anyway. Never block an emergency call on the backend.

## Location sharing

### `POST /location/share` 🔒
Sends **one** text with the user's current location to one of their own emergency contacts.

Flow: user taps "Share location" → app asks for location permission (only now) → app shows the **recipient name and number** → user taps Send → app calls this endpoint.
```json
{ "contact_id": 3, "latitude": 44.31969, "longitude": -96.78428, "confirmed": true }
```
- `confirmed` must be JSON `true`. Anything else returns `422` and sends nothing. If the user cancels, don't call the endpoint at all.
- Coordinates are used for this one message and then thrown away. They're never stored or logged.
- Demo mode simulates the text (`"status": "simulated"`) and sends nothing real.
- Rate limit: 5 per minute, 20 per hour, per user.

→ `200 {"status": "sent" | "simulated", "recipient": {"id", "name", "phone"}, "message": "...", "stored": false}`
· `404` not your contact · `422` · `429`
· `503 sms_unavailable`: the live provider failed. `error.sms_link` is an `sms:` URI with the same message; open it so the phone's messaging app can send the text.

If location permission is denied, skip this call and keep the rest of the emergency screen working.

## Admin (maintainer role only)

Students get `403`.

### `GET /admin/reports` 🔒
All reports. Query: `category`, `status`, `page`, `per_page`. Same response shape as `GET /reports`.

### `GET /admin/reports/<reference_id>` 🔒
`200 Report + {"reporter": {"id", "name", "email", "phone"}}` (reporter is `null` if the account was deleted)

### `PATCH /admin/reports/<reference_id>` 🔒
`{ "status": "in_review" }` → `200 Report`

## Shapes

**Tokens**
```json
{ "access_token": "...", "refresh_token": "...", "token_type": "Bearer", "expires_in": 900 }
```

**Contact**
```json
{ "id": 3, "name": "Mom", "phone": "+16055550199", "relationship": "Parent" }
```

**Report**
```json
{ "id": 7, "reference_id": "RPT-7K2Q9M", "category": "maintenance", "status": "submitted", "location": "Hansen Hall 214", "details": "Heater not working", "created_at": "2026-10-19T15:04:05.123456Z" }
```

**Resource**
```json
{ "id": 2, "category": "emergency", "name": "SDSU University Police Department", "description": "...", "phone": "+16056885117", "sms": null, "url": "https://www.sdstate.edu/safety-security/university-police", "available_24_7": true, "verified_on": "2026-10-19", "dial_number": "+16055550100" }
```

**User**
```json
{ "id": 1, "email": "jack@jacks.sdstate.edu", "name": "Jack Rabbit", "phone": null, "role": "student", "email_verified": true, "created_at": "2026-10-19T15:04:05.123456Z" }
```
