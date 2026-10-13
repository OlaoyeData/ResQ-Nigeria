# Put the ResQ demo on Vercel

This repository has a Vite frontend and a FastAPI backend. Deploy them as two Vercel projects connected to the same Git repository. The homepage phone preview works by itself; incident reports, tracking, and the command centre need the API and a persistent database.

## 1. Push the project to Git

Push this repository to a private or public GitHub, GitLab, or Bitbucket repository. Do not commit `.env`, API keys, database passwords, or a production JWT secret.

## 2. Create a persistent PostgreSQL database

Create a PostgreSQL database with a provider supported by your Vercel account, such as Neon or Supabase. Copy its connection string. Keep it private. SQLite is fine locally, but Vercel serverless storage is not a persistent database for this application.

## 3. Deploy the API project

In Vercel, import the repository as a project and set **Root Directory** to `backend`. Leave the Python/FastAPI framework detection enabled. Vercel should detect `backend/app/main.py` and install `backend/requirements.txt`.

Add these project environment variables for the Production environment:

| Variable | Value |
| --- | --- |
| `APP_ENV` | `demo` |
| `DATABASE_URL` | Your PostgreSQL connection string |
| `JWT_SECRET` | A long, unique random secret |
| `AI_PROVIDER` | `mock` |
| `NIPOST_PROVIDER` | `mock` |
| `WHATSAPP_PROVIDER` | `mock` |
| `CORS_ORIGINS` | `https://<your-frontend-domain>` |

Keep the WhatsApp and NIPOST provider settings in mock mode for this portfolio demo. Mock mode does not contact WhatsApp, NIPOST, or real responders. Deploy the API and note its Vercel domain, for example `https://resq-api-yourname.vercel.app`.

## 4. Create the schema and seed the demo records

From PowerShell in the repository, point the backend at the hosted database and run the migrations and seed script. Replace the placeholder with the private connection string from your database provider:

```powershell
cd backend
$env:DATABASE_URL = "<your-private-postgresql-connection-string>"
$env:RESQ_DEMO_OPERATOR_PASSWORD = "<a-new-private-demo-password>"
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m app.seed
Remove-Item Env:DATABASE_URL
Remove-Item Env:RESQ_DEMO_OPERATOR_PASSWORD
```

If your virtual environment is not at `backend/.venv`, use the Python executable from the environment where you installed `backend/requirements.txt`. The seed script creates clearly marked demo incidents and response units. Run it once for a fresh database; it is safe to rerun to fill in missing demo data. Keep the operator password private; do not place it in the repository or share it in the public project description.

The seed script uses the local demo password only when `RESQ_DEMO_OPERATOR_PASSWORD` is not set. For the hosted database, set a new private value as shown above before seeding so the known local demo password cannot be used to sign in.

## 5. Deploy the frontend project

Import the same Git repository again as a second Vercel project and set **Root Directory** to `frontend`. Vercel should detect Vite. Set:

| Setting | Value |
| --- | --- |
| Build command | `npm run build` |
| Output directory | `dist` |
| Environment variable | `VITE_API_URL=https://<your-api-domain>` |

Use the API domain from step 3, with no trailing slash. The included `frontend/vercel.json` sends client-side routes back to the Vite app. Redeploy after setting the environment variable because Vite embeds it during the build.

## 6. Set the final API origin and redeploy

Copy the frontend's Production domain into the API project's `CORS_ORIGINS` value. Redeploy the API after changing that variable. Open the frontend domain and check the interactive phone preview, `/report`, `/track`, and `/operator`.

## Demo limits

The homepage phone is an interactive browser simulation. It classifies the text with simple local rules, accepts the synthetic postcode `FC 02 A09 DB 09`, and displays an illustrative nearest demo unit. It does not send a WhatsApp message or dispatch a real team. API submissions are stored in the shared demo database, so remove personal details and clear the database when you no longer want to keep those submissions. This deployment is a portfolio demonstration, not an emergency service.
