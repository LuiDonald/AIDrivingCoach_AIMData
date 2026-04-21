# AIM Analyzer - AI Driving Coach

AI-powered motorsport telemetry analyzer. Upload your track data and get instant coaching recommendations to find more lap time. Your data is processed in-memory and never stored — close the tab and it's gone.

## Features

- **Multi-Format Support**: AIM native `.xrk`/`.xrz`, Porsche Track Precision `.csv`, and exported AIM `.csv` files
- **Multi-File Comparison**: Upload multiple sessions and compare laps across different files
- **Lap Analysis**: Speed traces, g-g diagrams, corner-by-corner breakdown
- **Theoretical Best Lap**: Combines fastest sectors across all laps with turn-based labels
- **Sector Hover Highlighting**: Hover over a sector in the breakdown to see it highlighted on the track map
- **Known Track Database**: Correct corner numbering and names for NJMP Thunderbolt, Watkins Glen, VIR, Road America (auto-detected via GPS)
- **Consistency Scoring**: Identifies where you're inconsistent lap-to-lap
- **AI Coaching**: GPT-5.4 powered recommendations prioritized by time gain
- **Chat Interface**: Ask natural-language questions about your driving data
- **Weather Integration**: Auto-fetches historical conditions from Open-Meteo based on GPS location and session time — includes grip assessment
- **Stateless & Ephemeral**: No database, no accounts, no server-side storage. Data lives in-memory with a 30-minute TTL

## Quick Start

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Optionally add your OpenAI API key to .env (users can also provide their own in the UI)
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### Docker

```bash
docker-compose up --build
```

## Environment Variables

### Backend (`backend/.env`)

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | Server-side fallback OpenAI API key. Users can provide their own key in the UI via Settings | No |
| `CORS_ORIGINS` | Allowed CORS origins (JSON array, defaults to `["http://localhost:3000"]`) | No |

## Tech Stack

- **Backend**: Python, FastAPI, libxrk, pandas, numpy, scipy
- **Frontend**: Next.js, React, TypeScript, Tailwind CSS, Recharts
- **AI**: OpenAI GPT-5.4 (Chat Completions + Function Calling)
- **Weather**: Open-Meteo (free, no API key required)
- **Deployment**: Docker, Vercel (frontend), Railway/Fly.io (backend)
