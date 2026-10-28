# Weather-Aware Truck Routing

React + Django app that recommends the safest of 3 truck routes based on forecast weather at each checkpoint's ETA, load weight and travel time. See [docs/problem.md](docs/problem.md).

## Run locally

Backend (http://127.0.0.1:8000):

```bash
cd backend
cp ../.env.example .env   # then fill in keys
uv run python manage.py migrate
uv run python manage.py runserver
```

Frontend (http://localhost:5173, proxies `/api` to the backend):

```bash
cd frontend
pnpm install
pnpm dev
```

Tests:

```bash
cd backend && uv run pytest
```
