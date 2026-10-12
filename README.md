# NgenoAI 🇳🇦 — Namibia-focused AI Learning Platform

**Learn Namibia. Understand More. Achieve More.**

NgenoAI is a responsive educational platform for Namibian secondary-school learners (including NSSCO/NSSCAS) and university learners. It includes accounts, learner profiles, AI tutoring, subject spaces, quizzes, study mode, translation, browser voice tools, AI image generation, progress tracking, notes and a university workspace.

This package now includes **Progressive Web App (PWA) support** so learners can install NgenoAI from a supported mobile or desktop browser and launch it from their home screen. It is still a web application backed by Flask; it is not a native Android/iOS package.

## Run in PyCharm / VS Code

1. Extract this ZIP and open the `NgenoAI_Pro` folder.
2. Create and activate a Python virtual environment (recommended).
3. Install dependencies:

   ```bash
   python -m pip install -r requirements.txt
   ```

4. Copy `.env.example` to `.env`, then add your API key and a strong secret key. Never put secret keys in HTML or JavaScript.
5. Start the app:

   ```bash
   python app.py
   ```

6. Open `http://127.0.0.1:5000`. Create an account or sign in.

## Install NgenoAI on a phone

- Deploy the app to a host that serves it over **HTTPS** (localhost is also permitted for development).
- Open the deployed NgenoAI site in a supported browser.
- **Android/Chrome:** open the browser menu and select **Install app** or **Add to Home screen**. The in-app **＋ Install** button appears when the browser exposes its install prompt.
- **iPhone/iPad/Safari:** tap **Share** → **Add to Home Screen**.
- Launch NgenoAI using the new home-screen icon.

## What works offline?

The service worker caches the app shell and core static files and can reopen a cached shell during a network interruption. **AI chat, sign-in, profile syncing, saved progress, translation, and image generation still require the server and/or external API services to be reachable.** API responses and private learner data are not intentionally cached by the service worker.

## Environment and safety notes

- The first run creates `ngenoai.db` automatically. The database is intentionally not bundled in this ZIP.
- Browser speech recognition/text-to-speech depends on browser support and permissions.
- The local password-reset interface is not a working email delivery system until an email provider is configured.
- Uploaded files are stored locally under `static/uploads`; for public deployment, add access control, malware scanning, object storage and stronger privacy controls.
- Set `FLASK_DEBUG=false` and use a strong `NGENO_SECRET_KEY` in deployment.
- AI-generated quiz questions are practice questions, not official past papers.
- Translation quality varies by language pair; NgenoAI should flag uncertainty.
- Use HTTPS for public hosting and review security settings before accepting real learner accounts.

## PWA files added

- `static/manifest.json` — NgenoAI app name, display mode, theme and icons.
- `static/sw.js` — cache shell and offline navigation fallback.
- `static/icons/ngenoai-192.png` and `static/icons/ngenoai-512.png` — home-screen icons.
- `/sw.js` Flask route — serves the service worker at the site root so it can control the app scope.
