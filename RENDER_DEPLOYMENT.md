# Java APEX on Render (one Docker web service)

The root Dockerfile builds React and serves it through FastAPI. MongoDB Atlas
remains external. Local `.env` files are excluded from the image. No separate
static site or `VITE_API_URL` is needed for this deployment.

## Render settings

1. Push these changes to the GitHub branch you intend to deploy.
2. Create a Web Service from that repository and select Docker.
3. Leave Root Directory blank. Set Dockerfile Path to `./Dockerfile` and
   Docker Build Context to `.`. Leave Docker Command blank.
4. Select Free for a demo and use `/health` for the health check.
5. Configure the environment below, then deploy. Replace the URL placeholders
   with the actual assigned Render service URL and redeploy if necessary.
6. In Atlas Network Access, allow the outbound IP ranges shown by Render under
   Connect / Outbound. Check runtime logs for a successful MongoDB connection.

## Required environment

Enter these in Render, never in a committed secret file:

```dotenv
ENVIRONMENT=production
AUTH_PROVIDER=mongodb
PERSISTENCE_BACKEND=mongodb
ENABLE_MONGODB=true
MONGODB_URI=<Atlas connection string with database credentials>
MONGODB_DATABASE=java_apex
JWT_SECRET_KEY=<random secret>
FRONTEND_URL=https://<service>.onrender.com
BACKEND_URL=https://<service>.onrender.com
CORS_ORIGINS=https://<service>.onrender.com
```

Generate a JWT secret locally with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

For publishing migrations set `GITHUB_TARGET_OWNER` and `GITHUB_TARGET_TOKEN`.
Set `GITHUB_TOKEN` if server-side source repository credentials are needed.
For AI features configure `LLM_1` (Hugging Face) and/or `LLM_2` (Groq), with
models available to the account. Localhost Ollama on your laptop is not
reachable from Render. Do not import Windows tool paths from local settings.

For quality scans configure `FOSSA_API_KEY`, `SONAR_TOKEN`, `SONAR_HOST_URL`,
and `SONAR_ORGANIZATION` as required by your provider. The image installs the
scanner executables but does not supply accounts or credentials. The existing
Python migration fallback remains available when the separate engine JAR is absent.

For OAuth, configure provider credentials and register:

- `https://<service>.onrender.com/api/auth/google/callback`
- `https://<service>.onrender.com/api/auth/github/callback`

## Checks

Optional local Docker validation from the repository root:

```powershell
docker build -t java-apex-render .
```

On Render verify `/health`, `/docs`, the home page, and direct navigation and
refresh on `/signin` and `/report`. Verify login and database operations too:
`/health` is only a liveness probe. Run one small migration and inspect build
and proposed-test results; a successful deployment is not a passed migration.

## Free service limits

The Free service sleeps after 15 minutes without incoming traffic. Local job
files disappear on restart, redeploy or spin-down; Atlas does not preserve
those files. Free services cannot attach disks. Download reports before they
are lost. Running jobs are interrupted when the service stops.

The 512 MB demo instance may not have enough memory for Maven/Gradle plus
browser tests. Limit testing to one small job; full migration workloads may
require paid compute. Do not rely on SMTP ports 25/465/587 on Free services.

References: https://render.com/docs/free and https://render.com/docs/docker
