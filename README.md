# NgenoAI 🇳🇦 — Render-ready project

This package keeps the files in the exact folders Flask expects. The HTML template is in `templates/`; CSS and JavaScript are in `static/`.

## Run locally
1. Install Python 3.11 or 3.12.
2. Open a terminal in this folder.
3. Run `python -m venv .venv`
4. Activate it (Windows: `.venv\\Scripts\\activate`; macOS/Linux: `source .venv/bin/activate`).
5. Run `pip install -r requirements.txt`
6. Copy `.env.example` to `.env` and set a strong `NGENO_SECRET_KEY`.
7. Run `python -c "import app; app.init_db()"`
8. Run `python app.py` and open http://127.0.0.1:5000

## Deploy on Render
- Push the **contents of this folder** to the root of your GitHub repository (so `app.py`, `requirements.txt`, `templates/`, and `static/` are at repository root).
- Create a Render Web Service connected to that repository.
- Build command: `pip install -r requirements.txt`
- Start command: `python -c "import app; app.init_db()" && gunicorn app:app --bind 0.0.0.0:$PORT`
- Root Directory: leave blank if these files are at repository root.
- Add `OPENAI_API_KEY` in Render Environment only if you want to use the OpenAI-powered endpoints. Never commit secrets to GitHub.

## Important
- `NGENO_DEMO_MODE=true` enables the starter/demo behavior. Set it to `false` only after you have configured the required AI credentials and reviewed deployment/security settings.
- SQLite and uploaded files on a free Render web service may be lost when the instance is replaced. Use managed PostgreSQL and persistent object storage before real public use.
- Password reset email requires a configured email provider. Browser speech support depends on the visitor's browser and permissions.
