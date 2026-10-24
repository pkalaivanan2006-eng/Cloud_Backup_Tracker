# Cloud Backup Tracker — Netlify + Render

This is a split deployment starter: `frontend/` is static HTML/CSS/JS for Netlify; `backend/` is a Flask JSON API for Render.

## Deploy backend first
1. Push this folder to a GitHub repository.
2. Render Dashboard → New → Web Service → connect the repository.
3. Set Root Directory to `backend`.
4. Build command: `pip install -r requirements.txt`
5. Start command: `gunicorn app:app`
6. Add environment variables:
   - `SECRET_KEY`: a long random secret
   - `FRONTEND_ORIGIN`: your exact Netlify URL, after frontend deploy (temporarily `*` for initial smoke test only)
   - `DATABASE_PATH`: `/var/data/cloud_backup_tracker.db`
   - `STORAGE_PATH`: `/var/data/backup_storage`
7. For durable SQLite and uploads, attach a persistent disk mounted at `/var/data`. Check current Render plan/disk costs and limits; without persistent storage, local database/files may be lost on restart or redeploy.
8. Deploy. Test `https://YOUR-SERVICE.onrender.com/api/health`.

## Deploy frontend on Netlify
1. In `frontend/app.js`, replace `https://YOUR-BACKEND-NAME.onrender.com` with the actual Render URL.
2. Push changes to GitHub.
3. Netlify → Add new project → Import an existing project → choose repository.
4. Base directory: `frontend`. Build command: leave blank. Publish directory: `.`.
5. Deploy and copy the Netlify URL.
6. Set Render's `FRONTEND_ORIGIN` to that exact Netlify URL and redeploy the backend.

## Notes
- This is a college-project prototype. Don't upload private or sensitive files.
- The frontend uses a bearer token saved in browser localStorage. A production service should receive a security review, rate limiting, strong secrets, and proper managed database/object storage.
- File upload maximum is 100 MB per request.
