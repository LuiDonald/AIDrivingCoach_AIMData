# AIM Analyzer - AI Driving Coach

AI-powered motorsport telemetry analyzer for AIM SOLO and SOLO DL data loggers. Upload your track data and get instant coaching recommendations to find more lap time.

## Features

- **File Upload**: Support for AIM native `.xrk`, `.xrz`, and exported `.csv` files
- **Lap Analysis**: Speed traces, g-g diagrams, corner-by-corner breakdown
- **Theoretical Best Lap**: Stitches fastest segments to show recoverable time
- **Consistency Scoring**: Identifies where you're inconsistent lap-to-lap
- **AI Coaching**: GPT-4o powered recommendations prioritized by time gain
- **Chat Interface**: Ask natural-language questions about your driving data
- **Photo Analysis**: Snap tire and car photos for AI-detected wear patterns and aero config
- **Weather Integration**: Auto-fetches conditions based on GPS location and session time
- **Mobile-First PWA**: Designed for trackside use on phones and tablets

## Quick Start

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your OpenAI API key
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## Environment Variables

### Backend (`backend/.env`)

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key for AI coaching and photo analysis | Yes (for AI features) |
| `OPENWEATHER_API_KEY` | OpenWeatherMap API key | No (weather auto-fill) |
| `DATABASE_URL` | SQLite connection string | No (has default) |

## Tech Stack

- **Backend**: Python, FastAPI, libxrk, pandas, numpy, scipy, SQLAlchemy
- **Frontend**: Next.js, React, TypeScript, Tailwind CSS, Recharts
- **AI**: OpenAI GPT-4o (Chat Completions + Vision + Function Calling)
- **Database**: SQLite (dev), PostgreSQL (prod)
