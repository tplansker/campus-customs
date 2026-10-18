# Campus Customs Online

Yale apparel shop with **Handsome Dan**, a PydanticAI shopping assistant (AI Foundations, HW4).
Live site: https://campus-customs-63et.onrender.com/

```
hw4/
├── AI_prompts.md          prompt log, one section per problem
├── requirements.txt       backend Python packages
├── .env.example           settings template (placeholders only)
├── frontend/              Vite + React + TypeScript app
├── backend/
│   ├── main.py            FastAPI app (run with uvicorn)
│   ├── agent.py           PydanticAI agent wiring
│   ├── models.py          Pydantic types
│   ├── tools.py           tools the agent can call
│   └── prompts/prompt.md  system prompt (voice + safety rules)
└── output/                harness.md, design.md, usability.md, app_check.html (+ images), audit_trail.json
```

## 1. Place the data pack (not in git)

Copy the course data pack into `hw4/data/` so it looks like this:

```
hw4/data/
├── campus_customs.db
└── products/          product images referenced by the catalogue
```

The backend reads the database from `hw4/data/campus_customs.db` and serves photos from `hw4/data/products/`.

## 2. Back end (FastAPI, port 8000)

```bash
cd hw4/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r ../requirements.txt
cp ../.env.example .env        # then fill in PORTKEY_API_KEY and SESSION_SECRET
uvicorn main:app --reload --port 8000
```

- `SESSION_SECRET`: any long random string, e.g. `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`.
- `PORTKEY_API_KEY`: needed only for the chat assistant; browsing, products, and login work without it.
- Leave `DATABASE_URL` empty to use the SQLite file in the data pack.
- Check it's running: http://localhost:8000/api/health → `{"status":"ok","database":"sqlite"}`

## 3. Front end (Vite + React, port 5173)

In a second terminal:

```bash
cd hw4/frontend
npm install
npm run dev
```

Open http://localhost:5173. The dev server forwards `/api` and `/media` to the backend on port 8000.
Test login (seed user in the data pack): `test@campuscustoms.yale.edu` / `password`.

## Deploy (optional, already live)

The live site runs on **Render** (one web service from `render.yaml` at the repo root, `rootDir: hw4`) with **Supabase Postgres**. The data pack isn't deployed: `backend/copy_to_supabase.py` copies the catalogue, inventory, seed users, and product photos into Supabase once, and the backend serves photos from Supabase when `data/products/` is missing. Secrets (`PORTKEY_API_KEY`, `DATABASE_URL`, `SESSION_SECRET`) are set in Render's environment, never in git. See `output/harness.md` §2.

## Documentation

- `output/harness.md`: how the whole system works (models, tools, safety, specs, how to run)
- `output/usability.md`, `output/design.md`, `output/app_check.html`, `output/audit_trail.json`
