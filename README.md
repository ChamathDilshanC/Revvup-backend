# RevvUp Backend

Serverless **FastAPI** API for the RevvUp premium motorbike marketplace, deployed on **Vercel** via Python serverless functions and backed by **Supabase** (Postgres database, Auth, and Storage for images).

## Architecture

```
revvup-backend/
├── api/
│   └── index.py          # Vercel serverless entry (ASGI app export)
├── app/
│   ├── main.py           # FastAPI app, CORS, router registration
│   ├── core/
│   │   ├── config.py     # Env-driven settings (Supabase keys, SMTP, bucket)
│   │   ├── supabase_client.py  # Cached Supabase client factory
│   │   ├── security.py   # JWT verify + role guards (owner/admin)
│   │   └── email.py      # SMTP sender + HTML approval templates
│   ├── api/
│   │   ├── bikes.py      # Catalog CRUD + image upload (owner-protected)
│   │   ├── auth.py       # Role-based register, login, approval confirm
│   │   └── admin.py      # Approve/reject showroom owners
│   └── models/
│       ├── bike.py       # Bike Pydantic schemas
│       └── user.py       # Register/login/profile schemas
├── supabase_schema.sql   # DB tables, RLS, seed data, storage bucket
├── .env.example          # Required environment variables
├── vercel.json           # Vercel build & route config
└── requirements.txt
```

Vercel routes all traffic to `api/index.py`, which imports the FastAPI `app` from `app/main.py`. This pattern keeps business logic in `app/` while satisfying Vercel’s `api/` directory convention.

## Supabase Setup

1. Create a project at [supabase.com](https://supabase.com).
2. In **SQL Editor**, run the contents of [`supabase_schema.sql`](./supabase_schema.sql). This creates the `bikes` table, RLS policies, seed data, and the public `bike-images` storage bucket.
3. In **Project Settings → API**, copy your `Project URL`, `anon` key, and `service_role` key.
4. Copy `.env.example` to `.env` and fill in:

```env
SUPABASE_URL=https://<your-ref>.supabase.co
SUPABASE_ANON_KEY=<anon key>
SUPABASE_SERVICE_KEY=<service role key>   # SECRET — server only
SUPABASE_BUCKET=bike-images
```

> The **service role key** bypasses Row Level Security and is required for writes and image uploads. Never expose it to the mobile client.

## API Endpoints

Base URL (local): `http://localhost:8000`  
Production: `https://<your-project>.vercel.app`

| Method | Path | Description |
| ------ | ---- | ----------- |
| `GET` | `/api/health` | Health check (reports `supabase_configured`) |
| `GET` | `/api/v1/bikes` | Bike catalog (summary list) |
| `GET` | `/api/v1/bikes/{id}` | Full specs: top speed, weight, engine cc, horsepower |
| `POST` | `/api/v1/bikes` | Create a bike (JSON body) |
| `PATCH` | `/api/v1/bikes/{id}` | Partially update a bike |
| `DELETE` | `/api/v1/bikes/{id}` | Delete a bike |
| `POST` | `/api/v1/bikes/{id}/image` | Upload image (multipart `file`) → Supabase Storage 🔒 owner |
| `POST` | `/api/v1/auth/register` | Register as `client` or `showroom_owner` |
| `POST` | `/api/v1/auth/login` | Login via Supabase Auth (`email`, `password`) |
| `GET` | `/api/v1/auth/me` | Current user's profile 🔒 |
| `GET` | `/api/v1/auth/confirm` | Approve/reject link target (from the email) |
| `GET` | `/api/v1/admin/owners/pending` | List pending owners 🔒 admin |
| `GET` | `/api/v1/admin/owners` | List all showroom owners 🔒 admin |
| `POST` | `/api/v1/admin/owners/{id}/approve` | Approve an owner 🔒 admin |
| `POST` | `/api/v1/admin/owners/{id}/reject` | Reject an owner 🔒 admin |

🔒 = requires `Authorization: Bearer <access_token>`. Bike create/update/delete/image require an **active showroom owner or admin**.

Interactive docs: `/api/docs` (Swagger UI)

## Roles & Showroom-Owner Approval Flow

Registration asks for a `role`:

- **`client`** — activated immediately, can browse and log in right away.
- **`showroom_owner`** — created as **`pending`**. The backend emails the developer (`DEVELOPER_EMAIL`) a styled HTML email with **Approve** / **Reject** buttons. Those buttons hit `GET /api/v1/auth/confirm`. On **Approve** the account becomes **`active`** and gains CRUD capabilities over bikes (create, update, delete, upload images). Until approved, login is blocked with `403 Account is pending approval`.

```bash
# Register a showroom owner (triggers approval email to the developer)
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
        "email":"owner@moto.lk","password":"secret12","full_name":"Kasun P",
        "role":"showroom_owner","showroom_name":"Colombo Motors",
        "showroom_address":"Galle Rd, Colombo","phone":"+94 77 123 4567"
      }'
```

Admins can also approve from the app via `POST /api/v1/admin/owners/{id}/approve`. Promote a user to admin once in SQL (see the commented block at the bottom of `supabase_schema.sql`).

### Email setup (approval emails)

Set the `SMTP_*`, `DEVELOPER_EMAIL`, and `APP_BASE_URL` variables in `.env`. For Gmail, create an [App Password](https://myaccount.google.com/apppasswords) and use:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=dilshancolonne123@gmail.com
SMTP_PASSWORD=<16-char app password>
SMTP_USE_TLS=true
DEVELOPER_EMAIL=dilshancolonne123@gmail.com
APP_BASE_URL=http://localhost:8000
```

> If SMTP is left blank, registration still succeeds and the approval link is printed to the server console — handy for local testing.

### Example: Create a bike (requires an active owner/admin token)

```bash
curl -X POST http://localhost:8000/api/v1/bikes \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"name":"R1","brand":"Yamaha","price":18999,"engine_cc":998,"horsepower":200}'
```

### Example: Upload a bike image

```bash
curl -X POST http://localhost:8000/api/v1/bikes/<bike_id>/image \
  -H "Authorization: Bearer <access_token>" \
  -F "file=@/path/to/photo.jpg"
```

The response contains the bike with a public `image_url` pointing at Supabase Storage.

### Example: List bikes

```bash
curl https://your-deployment.vercel.app/api/v1/bikes
```

### Example: Bike details

```bash
curl https://your-deployment.vercel.app/api/v1/bikes/1
```

Response includes `top_speed_mph`, `weight_lbs`, `engine_cc`, `horsepower`, `year`.

### Example: Login

```bash
curl -X POST https://your-deployment.vercel.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"rider@revvup.com","password":"secret12"}'
```

## Local Development

```bash
cd revvup-backend
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Open [http://localhost:8000/api/docs](http://localhost:8000/api/docs).

## Deploy to Vercel

1. Install [Vercel CLI](https://vercel.com/docs/cli): `npm i -g vercel`
2. From `revvup-backend/`:

```bash
vercel
vercel --prod
```

Ensure `vercel.json` points `api/index.py` to `@vercel/python`. In the Vercel dashboard, set the environment variables from `.env.example` for **Production**, including:

- `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`, `SUPABASE_BUCKET`
- `SMTP_*`, `DEVELOPER_EMAIL`
- **`APP_BASE_URL=https://revvup-backend.vercel.app`** — approve/reject links in the owner email use this host (if left as `localhost`, the backend auto-uses `https://$VERCEL_URL` on Vercel after redeploy)

## Dependencies

- **FastAPI** — API framework
- **Uvicorn** — ASGI server (local dev)
- **Pydantic** — Request/response validation
- **Supabase** — Postgres database, Auth, and Storage client
- **python-multipart** — Multipart parsing for image uploads
- **Mangum** — Optional AWS Lambda adapter (reserved for future portability)

## Submodule Note

This repository is a **Git submodule** of [main-application](https://github.com/ChamathDilshanC/main-application).

## Security (Production)

Auth is handled by Supabase Auth (real JWTs, hashed passwords). Before going live:

- Keep `SUPABASE_SERVICE_KEY` server-side only — never ship it in the mobile app
- Restrict CORS `allow_origins` to your mobile app domains
- Add rate limiting on auth endpoints
- Tighten Row Level Security policies for any user-writable tables

## License

Proprietary — RevvUp © 2026
