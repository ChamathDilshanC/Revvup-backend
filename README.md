# RevvUp Backend

Serverless **FastAPI** API for the RevvUp premium motorbike marketplace, deployed on **Vercel** via Python serverless functions.

## Architecture

```
revvup-backend/
├── api/
│   └── index.py          # Vercel serverless entry (ASGI app export)
├── app/
│   ├── main.py           # FastAPI app, CORS, router registration
│   ├── api/
│   │   ├── bikes.py      # Catalog & detail endpoints
│   │   └── auth.py       # Login & register
│   └── models/
│       └── bike.py       # Pydantic schemas
├── vercel.json           # Vercel build & route config
└── requirements.txt
```

Vercel routes all traffic to `api/index.py`, which imports the FastAPI `app` from `app/main.py`. This pattern keeps business logic in `app/` while satisfying Vercel’s `api/` directory convention.

## API Endpoints (Mock)

Base URL (local): `http://localhost:8000`  
Production: `https://<your-project>.vercel.app`

| Method | Path | Description |
| ------ | ---- | ----------- |
| `GET` | `/api/health` | Health check |
| `GET` | `/api/v1/bikes` | Premium bike catalog (summary list) |
| `GET` | `/api/v1/bikes/{id}` | Full specs: top speed, weight, engine cc, horsepower |
| `POST` | `/api/v1/auth/login` | Mock login (`email`, `password`) |
| `POST` | `/api/v1/auth/register` | Mock register (`email`, `password`, `full_name`) |

Interactive docs: `/api/docs` (Swagger UI)

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

Ensure `vercel.json` points `api/index.py` to `@vercel/python`. Set environment variables in the Vercel dashboard as needed.

## Dependencies

- **FastAPI** — API framework
- **Uvicorn** — ASGI server (local dev)
- **Pydantic** — Request/response validation
- **Mangum** — Optional AWS Lambda adapter (reserved for future portability)

## Submodule Note

This repository is a **Git submodule** of [main-application](https://github.com/ChamathDilshanC/main-application).

## Security (Production)

Current auth endpoints return mock tokens. Before production:

- Hash passwords (bcrypt/argon2)
- Issue real JWTs with expiry
- Add rate limiting and input validation
- Restrict CORS `allow_origins` to your mobile app domains

## License

Proprietary — RevvUp © 2026
