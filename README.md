# AI-Powered Adaptive Study Planner

AI-driven study planning system that transforms course syllabi into topic graphs using GPT + sentence embedding similarity, then generates personalized daily schedules with difficulty-aware and dependency-aware planning.

## Tech Stack
- Backend: FastAPI + Python
- AI Pipeline: OpenAI GPT API + SentenceTransformers
- Storage: Supabase (with in-memory fallback for local dev)
- Frontend: React (Vite)

## Features
- Syllabus ingestion and topic extraction with GPT
- Topic graph creation using dependency edges + embedding similarity edges
- Personalized daily schedules based on:
  - topic difficulty
  - estimated effort
  - prerequisite dependencies
  - study-time budget per day
- Adaptive replanning triggered from progress updates
- Real-time progress tracking API and reminder generation endpoint
- React dashboard for end-to-end workflow

## Repository Layout
```text
backend/
  app/
    api/routes.py
    core/config.py
    db/{supabase_client.py,repository.py}
    schemas/planner.py
    services/{gpt_service.py,embedding_service.py,topic_graph_service.py,planner_service.py,reminder_service.py}
  tests/test_planner.py
frontend/
  src/
    api/client.js
    components/*
    pages/DashboardPage.jsx
    styles/main.css
```

## Backend Setup
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Backend URL: `http://localhost:8000`

## Frontend Setup
```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Frontend URL: `http://localhost:5173`

## API Endpoints
- `GET /api/v1/health`
- `POST /api/v1/syllabus/ingest`
- `POST /api/v1/progress`
- `POST /api/v1/plan/replan`
- `GET /api/v1/plan/{user_id}/{course_id}`
- `GET /api/v1/progress/{user_id}/{course_id}`
- `GET /api/v1/reminders/{user_id}/{course_id}`

## Example Ingest Payload
```json
{
  "user_id": "student-001",
  "course_id": "cs-grad-601",
  "course_title": "Advanced Computer Science Seminar",
  "syllabus_text": "Week 1: Intro...\nWeek 2: Foundations...\n...",
  "start_date": "2026-03-01",
  "end_date": "2026-03-21",
  "daily_study_minutes": 120
}
```

## Supabase Tables (Suggested)
Apply [`supabase/schema.sql`](supabase/schema.sql) to create persistence tables:
- `courses`
- `topics`
- `topic_edges`
- `study_plan_items`
- `progress_events`

The backend gracefully falls back to in-memory storage if Supabase credentials are not configured.

## Tests
```bash
cd backend
pytest
```
