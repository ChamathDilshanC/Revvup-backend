# RevvUp Backend

FastAPI REST API for the **RevvUp** multi-showroom marketplace — optimized for **Vercel Serverless**, backed by **Supabase** (Postgres, Auth, Storage).

## Architecture

```
revvup-backend/
├── api/index.py              # Vercel ASGI entry (handler = app)
├── app/
│   ├── main.py               # FastAPI app, CORS, routers
│   ├── api/
│   │   ├── auth.py           # Register / login / owner email confirm
│   │   ├── bikes.py          # Public catalog (all showrooms)
│   │   ├── owner_bikes.py    # Owner-isolated CRUD
│   │   ├── showrooms.py      # Public showroom list + owner profile
│   │   └── admin.py          # Approve / reject owners
│   ├── models/               # Pydantic schemas
│   └── core/                 # Config, security, email, Supabase
├── vercel.json
└── requirements.txt
```

## Roles

| API `role` | Description |
| ---------- | ----------- |
| `client` | Buyer — public read only |
| `showroom_owner` | Vendor — CRUD on own `owner_id` bikes after `status=active` |
| `admin` | Platform — approve owners, manage any bike |

Register body uses `role`: `"client"` or `"showroom_owner"` (alias concept: **owner** in product docs).

## API endpoints

### Auth (public)

| Method | Path | Description |
| ------ | ---- | ----------- |
| `POST` | `/api/v1/auth/register` | Register client or showroom owner |
| `POST` | `/api/v1/auth/login` | Supabase password sign-in → JWT |
| `GET` | `/api/v1/auth/me` | Current profile 🔒 |
| `GET` | `/api/v1/auth/confirm` | Email approve/reject link (HTML) |

### Bikes — public catalog (clients)

| Method | Path | Description |
| ------ | ---- | ----------- |
| `GET` | `/api/v1/bikes` | All bikes from **all** showrooms |
| `GET` | `/api/v1/bikes/{id}` | Detail: top speed, weight, engine cc, HP, year |

### Owner bikes — protected (showroom inventory)

Requires `Authorization: Bearer <access_token>` and **active** `showroom_owner` (or admin).

| Method | Path | Description |
| ------ | ---- | ----------- |
| `GET` | `/api/v1/owner/bikes` | List **only this showroom's** bikes |
| `POST` | `/api/v1/owner/bikes` | Add bike (`owner_id` set server-side) |
| `PUT` | `/api/v1/owner/bikes/{id}` | Full update (own bikes only) |
| `PATCH` | `/api/v1/owner/bikes/{id}` | Partial update |
| `DELETE` | `/api/v1/owner/bikes/{id}` | Delete own listing |
| `POST` | `/api/v1/owner/bikes/{id}/image` | Upload image → Supabase Storage |

### Showrooms

| Method | Path | Description |
| ------ | ---- | ----------- |
| `GET` | `/api/v1/showrooms` | Active showroom directory (public) |
| `GET` | `/api/v1/showrooms/{profile_id}` | Public showroom profile |
| `GET` | `/api/v1/owner/showroom/me` | Own profile 🔒 |
| `PATCH` | `/api/v1/owner/showroom/me` | Update showroom name, address, phone 🔒 |

### Admin 🔒

| Method | Path |
| ------ | ---- |
| `GET` | `/api/v1/admin/owners/pending` |
| `POST` | `/api/v1/admin/owners/{id}/approve` |
| `POST` | `/api/v1/admin/owners/{id}/reject` |

## Environment

Copy `.env.example` → `.env`. Production: set variables in **Vercel** dashboard.

```env
SUPABASE_URL=
SUPABASE_SERVICE_KEY=
APP_BASE_URL=https://revvup-backend.vercel.app
DEVELOPER_EMAIL=
SMTP_HOST=smtp.gmail.com
...
```

## Local run

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Docs: http://localhost:8000/api/docs

## Deploy (Vercel)

```bash
vercel --prod
```

Include `APP_BASE_URL` for approval email links. Logo is embedded in `app/core/email_logo_b64.py` for serverless.

## Data model (simplified)

- `profiles` — user, role, status, showroom fields
- `bikes` — listing with `owner_id` → showroom isolation

## Parent repo

Submodule of [revvup-app](https://github.com/ChamathDilshanC/revvup-app).
