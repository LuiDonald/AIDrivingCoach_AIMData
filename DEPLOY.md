# Deployment Guide

AIM Analyzer is a fully stateless application — no database, no file storage, no user accounts. Deploy it anywhere with minimal configuration.

## Architecture

```
User Browser  --->  Frontend (Next.js)  --->  Backend (FastAPI)
                                                  |
                                              OpenAI API
                                          (user's own key)
```

## Local (Docker Compose)

```bash
docker compose up --build
```

Frontend: http://localhost:3000  
Backend: http://localhost:8000

## Deploy Backend (Railway / Fly.io / Render)

The backend is a single stateless FastAPI container. No database or persistent storage needed.

### Railway

1. Push the `backend/` directory to a GitHub repo (or use the monorepo)
2. Create a new project on [railway.app](https://railway.app)
3. Connect the repo and set the root directory to `backend/`
4. Set environment variables:
   - `CORS_ORIGINS=["https://your-frontend-domain.vercel.app"]`
5. Railway auto-detects the Dockerfile and deploys

### Fly.io

```bash
cd backend
fly launch --no-deploy
fly secrets set CORS_ORIGINS='["https://your-frontend-domain.vercel.app"]'
fly deploy
```

### Environment Variables (Backend)

| Variable | Required | Description |
|----------|----------|-------------|
| `CORS_ORIGINS` | Yes | JSON array of allowed frontend origins |
| `OPENAI_API_KEY` | No | Server-side fallback key (users provide their own via header) |

## Deploy Frontend (Vercel)

1. Push the `frontend/` directory to GitHub
2. Import the project on [vercel.com](https://vercel.com)
3. Set environment variable:
   - `NEXT_PUBLIC_API_URL=https://your-backend.railway.app` (your backend URL)
4. Deploy

### Environment Variables (Frontend)

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_API_URL` | Yes | Backend API URL |

## Cost Estimate

- **Free tier**: Vercel free + Railway free = $0/month (with usage limits)
- **Light usage**: ~$5-10/month on paid tiers
- **No database costs** — the app is fully stateless
