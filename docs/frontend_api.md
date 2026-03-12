## Municipal Services — Frontend Integration Guide

This document helps frontend engineers integrate with the backend in this repository. It lists the available HTTP endpoints, expected request/response shapes, authentication, database collections, environment variables, and quick run instructions.

Base URL (local)
- http://localhost:3000

Prefix notes
- All primary routes are mounted under `/api` in `main.py`:
  - Auth: `/api/auth`
  - Users: `/api/users`
  - Grievances (user + admin): `/api/grievances`

## Authentication
- The app uses JWT tokens. The token is issued by `/api/auth/verify-otp` and must be sent on protected endpoints using the HTTP Authorization header:

  Authorization: Bearer <token>

- The signing secret env var is `JWT_SECRET` (or `jwt_secret` in `app/config.py` via `pydantic_settings`). Tokens contain payload { "id": "<user_id>", "exp": <expiry> }.

## Environment variables (important)
- MONGO_URI / mongo_uri — MongoDB connection string
- JWT_SECRET / jwt_secret — JWT signing secret
- redis_host, redis_port, redis_password — Redis connection (used for OTP storage)
- TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, twilio_phone_number — Twilio credentials
- CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET — Cloudinary credentials
- GEMINI_API_KEY, BASE_URL, BASE_API_URL — optional for AI services

The project uses `app/config.py` and `.env` file convention. See `main.py` for startup initialization.

## How to run locally (quick)
1. Create & activate venv (PowerShell):

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Create a `.env` file in the repo root and set the variables listed above.

4. Start the app:

```powershell
# from repo root
uvicorn main:app --host 0.0.0.0 --port 3000 --reload
```

## Database
- MongoDB (using `motor` async driver) — the DB init is in `app/database/database.py`.
- Collections used:
  - `users`
  - `grievances`
  - `document_records`

Important indexes (created on startup): `mobile` (users), `grievance_id` (grievances), `user_id`, `status`, `category`, `created_at`.

### Grievance document (fields)
- `grievance_id` (string, unique)
- `title`, `description`, `category` (enum), `status` (enum)
- `priority` (enum), `location`, `address`, `landmark`, `ward_number`, `pin_code`
- `user_id`, `user_mobile`, `anonymous` (bool)
- `attachments` (list of URLs)
- `admin_notes`, `assigned_to`, `estimated_resolution_date`, `actual_resolution_date`
- `created_at`, `updated_at`, `status_history` (list)

### User document (fields)
- `_id` (ObjectId unique id)
- `mobile` (string, unique)
- `verified` (bool)
- optional: `name`, `email`, `profile_photo`, `age`, `gender`, `location`

## Endpoints (grouped)

Notes for each endpoint shown as: METHOD PATH — auth? — brief description — request shape — response shape.

### Auth

- POST /api/auth/send-otp — public
  - Request JSON: { "mobile": "+911234567890" }
  - Response: { "message": "OTP sent successfully" }

- POST /api/auth/resend-otp — public
  - Request JSON: { "mobile": "+911234567890" }
  - Response: { "message": "OTP resent successfully" }

- POST /api/auth/verify-otp — public
  - Request JSON: { "mobile": "+911234567890", "otp": "123456" }
  - Response: { "token": "<jwt>", "user": { "_id": "..", "mobile": ".." } }

Authentication contract
- After verify, include `Authorization: Bearer <token>` in requests to protected endpoints.

### User

- PUT /api/users/update-profile — protected
  - Body JSON: any subset of ProfileUpdateModel, e.g. { "name": "Asha", "email":"asha@example.com" }
  - Response: { "message": "Profile updated successfully", "user": { ... } }

- GET /api/users/me — protected
  - Response: { "message": "User found", "user": { "_id": "..", "mobile": "..", "verified": true, ... } }

- POST /api/users/documents/upload-document — protected (controller expects form-data)
  - Form fields: `user_id` (string), `notes` (string, optional), `file` (file)
  - Response: { "message": "document uploaded", "record": { ... } }

Note: The current route `app/routes/user_routes.py` maps `/documents/upload-document` as a GET to `upload_document_record`. That seems to be an accidental mismatch because the controller expects a file upload (POST with form-data). Recommendation: change the route to `router.post('/documents/upload-document')` to match the controller.

### Grievances (user-facing)

- GET /api/grievances/categories — public
  - Response: { "message": "Categories retrieved successfully", "categories": [ {value,label}, ... ] }

- GET /api/grievances/track/{grievance_id} — public
  - Response: { "message": "Grievance status retrieved successfully", "grievance": { ... } }

- POST /api/grievances/create — protected
  - Body JSON (GrievanceCreateModel):
    {
      "title": "Overflowing drain",
      "description": "Drain overflowing near market",
      "category": "drainage",
      "location": "Sector 5",
      "address": "...",
      "priority": "medium",
      "anonymous": false
    }
  - Response: 201 Created { "message": "Grievance created successfully", "grievance": { ... } }

- GET /api/grievances/my-grievances — protected
  - Query params: status (optional), category (optional), limit (default 10), skip (default 0)
  - Response: { "message": "Grievances retrieved successfully", "grievances": [...], "total_count": N, "page": X, "per_page": Y }

- GET /api/grievances/{grievance_id} — protected
  - Response: { "message": "Grievance retrieved successfully", "grievance": { ... } }

- PUT /api/grievances/{grievance_id} — protected
  - Body JSON (GrievanceUpdateModel): subset of fields to update
  - Response: { "message": "Grievance updated successfully", "grievance": { ... } }

- POST /api/grievances/{grievance_id}/upload-attachment — protected
  - Form-data: `file` (binary file)
  - Response: { "message": "Attachment uploaded successfully", "attachment_url": "https://..." }

- DELETE /api/grievances/{grievance_id} — protected
  - Only allowed when grievance status == SUBMITTED
  - Response: { "message": "Grievance deleted successfully" }

### Grievances Admin (AI-agent / admin)

All admin endpoints are mounted under the same `/api/grievances` prefix (see `app/routes/grievance_admin_routes.py`). These are intended for internal/AI use but are HTTP endpoints you can call.

- GET /api/grievances/admin/all — protected/admin
  - Query params: status, category, priority, limit (50), skip (0)
  - Response: { "success": true, "grievances": [...], "total_count": N, ... }

- PUT /api/grievances/admin/{grievance_id}/status — protected/admin
  - Query params: `status` (enum), `admin_notes` (optional), `estimated_resolution_date` (ISO string optional)
  - Response: { "success": true, "message": "Grievance status updated successfully", "grievance": {...} }

- PUT /api/grievances/admin/{grievance_id}/assign — protected/admin
  - Query param: `assigned_to` (string)
  - Response: { "success": true, "message": "Grievance assigned successfully", "grievance": {...} }

- GET /api/grievances/admin/stats — protected/admin
  - Response: { "success": true, "stats": { total_grievances, pending_grievances, resolved_grievances, recent_grievances, detailed_stats } }

- GET /api/grievances/admin/search?q=term&limit=20 — protected/admin
  - Response: { "success": true, "grievances": [...], "count": N }

- GET /api/grievances/admin/overdue — protected/admin
  - Response: { "success": true, "overdue_grievances": [...], "count": N }

### Twilio / Voice / WhatsApp webhooks

- POST /whatsapp (mounted in `app/routes/twilio_routes.py` without `/api` prefix in router)
  - This handles Twilio webhook POSTs (form-data). Twilio sends fields like `From`, `To`, `Body`, `NumMedia`, `MediaUrl0`, etc.
  - Response: TwiML XML or empty text depending on flow.

- POST /voice — Twilio voice webhook (create greeting TwiML)
- POST /voice/process — Twilio speech processing callback
- GET /voice/twiml?message=... — generate simple TwiML
- POST /send-whatsapp — admin/testing endpoint (Form `to_number`, `message`)
- POST /make-call — admin/testing (Form `to_number`, `message`)
- GET /config — returns Twilio webhook URLs if configured

> Note: Twilio endpoints live in `app/routes/twilio_routes.py` and are not prefixed under `/api` in `main.py`. If you need them under `/api`, the route setup must be adjusted.

### Voice chat web endpoints (web client)

- POST /voice (in `voice_chat_routes`) — accepts `multipart/form-data` with an `audio_file` and optional `session_id`.
  - Response JSON includes base64 `audio_response` and `session_id`.

- POST /text — accepts JSON: { "message": "..", "language": "en", "session_id": ".." }

- GET /test/speech — returns example TTS audio (base64)

- Sessions management endpoints: GET /sessions, GET /sessions/{session_id}, DELETE /sessions/{session_id}, POST /sessions/cleanup

## Request/Response examples

Create grievance (example):

POST /api/grievances/create
Body JSON:
```json
{
  "title": "Overflowing drain",
  "description": "Overflowing drain near central market",
  "category": "drainage",
  "location": "Central Market",
  "priority": "high",
  "anonymous": false
}
```

Success response (201):
```json
{
  "message": "Grievance created successfully",
  "grievance": {
    "_id": "653a...",
    "grievance_id": "DR-2025-0001",
    "title": "Overflowing drain",
    "status": "submitted",
    "category": "drainage",
    "user_id": "64f...",
    "created_at": "2025-11-03T12:34:56.789Z",
    "attachments": []
  }
}
```

Error responses
- Consistently uses FastAPI exceptions; typical shape for 4xx/5xx responses is JSON with `detail` or custom `error` fields.

## Notes, gotchas & recommended fixes
- `app/routes/user_routes.py` maps `/documents/upload-document` to a GET but the controller expects a POST with form-data. Update to `router.post(...)`.
- Twilio routes are mounted without `/api` prefix — be aware when configuring external webhooks.
- Some admin endpoints do not enforce admin-only middleware at route level — ensure protected access when needed.

## Quick cURL examples

- Verify OTP (example):

```bash
curl -X POST http://localhost:3000/api/auth/verify-otp \
  -H "Content-Type: application/json" \
  -d '{"mobile":"+911234567890","otp":"123456"}'
```

- Get categories (public):

```bash
curl http://localhost:3000/api/grievances/categories
```

- Create grievance (authenticated):

```bash
curl -X POST http://localhost:3000/api/grievances/create \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"title":"Test","description":"desc here","category":"roads","location":"Area 1"}'
```

## Next steps for frontend integration
1. Decide on auth UX (OTP via SMS) and store token in a secure storage (e.g., HttpOnly cookie or secure local storage depending on web/native app strategy).
2. Confirm whether Twilio webhooks should be accessible from the same API domain or separately.
3. Update any mismatched routes (noted above) before heavy integration.

If you want, I can also produce a Postman collection / OpenAPI spec trimmed to only the endpoints you need (or update controllers to add explicit response models to improve generated OpenAPI docs).
