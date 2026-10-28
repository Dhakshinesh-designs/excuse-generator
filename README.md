# Sicko-Excuse Generator and Support Assistant

## Assessment submission

- **Individual task title:** Responsive Excuse Generator with FAQ-Grounded AI Support Assistant
- **Live website (HTTPS):** https://excuse-generator-murex-eight.vercel.app/
- **GitHub repository:** https://github.com/Dhakshinesh-designs/excuse-generator
- **Proposed improvement:** Add authenticated ticket-status tracking so students can follow up on support requests.
- **Assessment task sheet:** [Software Development submission sheet](https://docs.google.com/spreadsheets/d/1gac3qN_sFgbBQR7utv6N-66-C8szNq3-F6L7NQsbx78/edit?usp=sharing)

## Features

- Responsive excuse generator, FAQ, error-code guide, and About pages.
- The generator's situation and optional private note are never echoed into its excuse text.
- Shared assistant chat widget on every page, including custom 404 and 500 pages.
- Thirteen FAQs, eight required HTTP error explanations, and a site-specific error code seeded into SQL.
- FAQs are displayed on both the FAQ page and the landing page.
- Optional Django accounts use SQL-backed, hashed passwords; signed-in users can create, read, update, and delete their own MongoDB profile.
- Support tickets are stored in SQL, associated with signed-in users when available, and manageable in Django admin.
- Optional Gemini assistant responses grounded in the SQL FAQ/error data. Without a Gemini key, FAQ matching remains available.
- MongoDB persistence for user profiles, chat logs, and assistant feedback when `MONGODB_URI` is configured.
- Request logging to the application console and a `/health/` JSON health check.
- Excuse-inspiration API integration with a four-second timeout and local fallback.
- API keys and deployment configuration supplied through environment variables; no real key belongs in this repository.

## Run locally

Python 3.12 or newer is recommended.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py runserver
```

The local website is available at `http://127.0.0.1:8000/`. SQLite is used when `DATABASE_URL` is empty. The generator and FAQ assistant work without Gemini or MongoDB. MongoDB-backed profiles, chat logs, and feedback require `MONGODB_URI`; Gemini-generated grounded answers require `GEMINI_API_KEY`. The local `.env` file is ignored by Git.

## Get API credentials

Do not paste credentials into chat, source code, screenshots, or GitHub. Put local values directly in your ignored `.env` file. For deployment, enter the same values in the hosting provider's encrypted environment-variable settings; Vercel does not read your computer's `.env` file.

### MongoDB Atlas

1. Create a MongoDB Atlas account and project at <https://www.mongodb.com/products/platform/atlas-database>.
2. Create a cluster, then create a database user with a strong password. Keep the database username and password private.
3. Configure Atlas Network Access for your deployment. Prefer a private network integration or the provider's documented outbound IP ranges over unrestricted access.
4. In the cluster's **Connect → Drivers** flow, select Python and copy the connection URI. Replace the password placeholder with the database user's password, URL-encoding special characters.
5. Set `MONGODB_URI` to that URI and `MONGODB_DATABASE` to `excuse_generator` in `.env` locally and in the host's environment settings.

The app stores user profile documents in `user_profiles`, chat exchanges in `chat_logs`, and assistant feedback in `feedback`. Django handles login and securely hashes account passwords in SQL; MongoDB never receives account passwords. Profile operations are scoped to the logged-in account.

### Gemini

1. Sign in to Google AI Studio at <https://aistudio.google.com/app/apikey>.
2. Create an API key and copy it once.
3. Set `GEMINI_API_KEY` in `.env` locally and in the host's environment settings. The key is sent only in server-to-server requests. Without it, the SQL FAQ/error matcher continues to work.

### SQL database and Django settings

- For durable hosted FAQ and support-ticket data, connect PostgreSQL and set `DATABASE_URL` to its private connection URL. Locally, leave it empty to use SQLite.
- Set a unique random `DJANGO_SECRET_KEY` for production; do not reuse the example value.
- Set `DJANGO_ALLOWED_HOSTS` to `.vercel.app` (or your exact host names), with no URL scheme.
- Set `DJANGO_CSRF_TRUSTED_ORIGINS` to the exact HTTPS origin, for example `https://excuse-generator-murex-eight.vercel.app`.
- On Vercel, configure these in **Project Settings → Environment Variables** for Production (and Preview if used), then redeploy. Host-injected environment variables are necessary because the local `.env` file must not be committed.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `DJANGO_SECRET_KEY` | Secret key; generate a new private value for deployment. |
| `DJANGO_DEBUG` | Set to `False` in deployment. |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated host names served by Django. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Comma-separated HTTPS origins used by the deployed site. |
| `DJANGO_SECURE_SSL_REDIRECT` | Set to `True` when HTTPS is terminated by the hosting platform. |
| `DJANGO_SECURE_HSTS_SECONDS` | Enable HSTS only after HTTPS is confirmed working for the production domain. |
| `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS` | Include subdomains in HSTS only when each subdomain supports HTTPS. |
| `DJANGO_SECURE_HSTS_PRELOAD` | Enable HSTS preload only after reviewing the permanent browser preload requirements. |
| `DATABASE_URL` | PostgreSQL URL; leave empty to use SQLite locally. |
| `GEMINI_API_KEY` | Optional server-side key for FAQ-grounded Gemini answers. |
| `MONGODB_URI` | MongoDB connection URL for chat logs and feedback. |
| `MONGODB_DATABASE` | MongoDB database name. |

Never commit `.env`, provider credentials, or production database URLs. The checked-in `.env.example` contains placeholders only.

## Routes

- `/` — excuse generator and inspiration widget
- `/faq/` — database-backed FAQ list
- `/errors/` — HTTP error-code guide and site-specific `EGEN-001`
- `/about/` — project details
- `/accounts/register/`, `/accounts/login/`, `/accounts/profile/` — account registration, login, and MongoDB profile CRUD
- `/health/` — SQL/MongoDB/assistant health JSON
- `/api/assistant/` — FAQ/error assistant and support-ticket creation
- `/api/assistant/feedback/` — MongoDB-backed answer feedback
- `/api/inspiration/` — third-party inspiration with timeout and fallback

Custom 404/500 templates are enabled when `DJANGO_DEBUG=False`. To verify the 404 page locally, open `/this-page-does-not-exist/`.

## Deployment checklist

### Vercel

1. Import `https://github.com/Dhakshinesh-designs/excuse-generator` into Vercel. Vercel detects Django from `manage.py` and uses `myproject.wsgi:application`. Vercel uses `uv` for Python dependency installation and supports this project's `requirements.txt`; a `uv.lock` or `pyproject.toml` is not required.
2. Connect a persistent PostgreSQL integration and set `DATABASE_URL`. Vercel functions do not provide persistent local-disk storage, so SQLite is not suitable for production.
3. Configure `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`, `DJANGO_ALLOWED_HOSTS=.vercel.app`, `DJANGO_SECURE_SSL_REDIRECT=True`, and `DJANGO_CSRF_TRUSTED_ORIGINS=https://excuse-generator-murex-eight.vercel.app` in Vercel's environment settings.
4. Configure MongoDB Atlas and set `MONGODB_URI` and `MONGODB_DATABASE`; set `GEMINI_API_KEY` to enable generated responses. Never commit secrets.
5. Redeploy after changing environment variables. Run `python manage.py migrate` against the hosted PostgreSQL database to create tables and seed the FAQ/error catalog. Vercel automatically collects and serves static files from `STATIC_ROOT`.
6. Check `/health/`, register and sign in, test profile CRUD with MongoDB configured, try the assistant, verify a narrow mobile viewport, and request a random nonexistent URL to confirm the custom 404. Set HSTS only after HTTPS is confirmed.
7. Enter the task title, HTTPS URL, and GitHub URL in the assessment spreadsheet.
