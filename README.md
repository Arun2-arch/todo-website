# Todo List (Flask + vanilla JS)

## Run locally (VS Code)
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py                    # http://127.0.0.1:5000
```
In VS Code: select the `.venv` interpreter (Ctrl+Shift+P → "Python: Select Interpreter"), then press F5.

## Push to GitHub
```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin main
```

## Deploy to Vercel
1. Go to vercel.com → Add New → Project → import the GitHub repo.
2. Leave defaults (Vercel auto-detects Flask via `app.py`; no vercel.json needed) → Deploy.
3. Every push to `main` redeploys automatically.

CLI alternative: `npm i -g vercel && vercel`.

## Persistent storage (Neon Postgres)
Without `DATABASE_URL`, todos are saved to `data/todos.json` (fine locally, but
Vercel's filesystem is ephemeral). To persist on Vercel:
1. Vercel dashboard -> your project -> Storage -> **Neon** (Postgres) -> Create, connect to the project.
2. Vercel adds `DATABASE_URL` (and `POSTGRES_URL`) automatically.
3. Redeploy (Deployments -> ... -> Redeploy). The `todos` table is created on first request.

To use Neon locally too, set the variable before running:
```bash
export DATABASE_URL="postgresql://user:pass@host/db?sslmode=require"   # Windows PowerShell: $env:DATABASE_URL="..."
python app.py
```
