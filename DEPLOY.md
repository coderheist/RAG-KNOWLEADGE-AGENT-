# Deploying: Vercel (frontend) + Render (backend)

1. **Qdrant Cloud**: create a free cluster at cloud.qdrant.io. Copy its URL (`https://….cloud.qdrant.io:6333`) and an API key.
2. **Render**: New → Blueprint → select this repo. It reads `render.yaml` and creates the API and Postgres.
   Fill the prompted values: `GOOGLE_API_KEY`, `QDRANT_URL`, `QDRANT_API_KEY`, and `CORS_ORIGINS` (set it after step 3).
   When it is live, `https://<service>.onrender.com/health` should return OK.
3. **Vercel**: Add New → Project → import this repo (root directory = repo root). Add the environment variable
   `BACKEND_URL=https://<service>.onrender.com` (no trailing slash), then Deploy.
4. Back on Render, set `CORS_ORIGINS=["https://<your-app>.vercel.app"]` and redeploy.

Notes: uploads through Vercel's proxy are limited to about 4.5 MB, and long streamed answers can hit its time limit.
If either bites, add `NEXT_PUBLIC_API_URL=https://<service>.onrender.com` on Vercel and redeploy; the browser then
calls Render directly (this is why CORS must list the Vercel domain). The app has no login, so keep the URL private.
