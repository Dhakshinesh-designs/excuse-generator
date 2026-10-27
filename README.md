# Sicko-Excuse Generator and Support Assistant

## Assessment submission

- **Individual task title:** Responsive Excuse Generator with FAQ-Grounded AI Support Assistant
- **Live website (HTTPS):** Not deployed yet — add the production HTTPS URL after deployment.
- **GitHub repository:** https://github.com/Dhakshinesh-designs/excuse-generator
- **Proposed improvement:** Add authenticated ticket-status tracking so students can follow up on support requests.
- **Assessment task sheet:** [Software Development submission sheet](https://docs.google.com/spreadsheets/d/1gac3qN_sFgbBQR7utv6N-66-C8szNq3-F6L7NQsbx78/edit?usp=sharing)

## Features

- Responsive excuse generator, FAQ, error-code guide, and About pages.
- The generator's situation and optional private note are never echoed into its excuse text.
- Shared assistant chat widget on every page, including custom 404 and 500 pages.
- Ten FAQs, eight required HTTP error explanations, and one site-specific error code seeded into SQL.
- Support tickets stored in the SQL database and manageable in Django admin.
- Optional Gemini assistant responses grounded in the SQL FAQ/error data. Without a Gemini key, FAQ matching remains available.
- MongoDB persistence for chat logs and assistant feedback when `MONGODB_URI` is configured.
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

The local website is available at `http://127.0.0.1:8000/`. SQLite is used when `DATABASE_URL` is empty. The assessment pages and local FAQ assistant work without Gemini or MongoDB. Configure MongoDB before relying on persistent chat logs and feedback; configure `GEMINI_API_KEY` to enable generated responses.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `DJANGO_SECRET_KEY` | Secret key; generate a new private value for deployment. |
| `DJANGO_DEBUG` | Set to `False` in deployment. |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated host names served by Django. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Comma-separated HTTPS origins used by the deployed site. |
| `DJANGO_SECURE_SSL_REDIRECT` | Set to `True` when HTTPS is terminated by the hosting platform. |
| `DJANGO_SECURE_HSTS_SECONDS` | Enable HSTS only after HTTPS is confirmed working for the production domain. |
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
- `/health/` — SQL/MongoDB/assistant health JSON
- `/api/assistant/` — FAQ/error assistant and support-ticket creation
- `/api/assistant/feedback/` — MongoDB-backed answer feedback
- `/api/inspiration/` — third-party inspiration with timeout and fallback

Custom 404/500 templates are enabled when `DJANGO_DEBUG=False`. To verify the 404 page locally, open `/this-page-does-not-exist/`.

## Deployment checklist

### Vercel

1. Import `https://github.com/Dhakshinesh-designs/excuse-generator` into your Vercel account. Vercel detects Django from `manage.py` and uses `myproject.wsgi:application`; Python dependencies are read from `requirements.txt`.
2. Connect a persistent PostgreSQL integration and set its `DATABASE_URL`. Do not use the local SQLite database for production; Vercel functions do not provide persistent local-disk storage.
3. Configure `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`, `DJANGO_ALLOWED_HOSTS=.vercel.app`, and `DJANGO_SECURE_SSL_REDIRECT=True` in Vercel's project environment variables.
4. Provision MongoDB (for example, MongoDB Atlas) and set `MONGODB_URI` and `MONGODB_DATABASE`. Set `GEMINI_API_KEY` to enable generative answers. Add secrets in Vercel only; never commit them.
5. Deploy once to obtain the production hostname, then set `DJANGO_CSRF_TRUSTED_ORIGINS` to the exact HTTPS origin, such as `https://your-project.vercel.app`, and redeploy.
6. Link the Vercel project locally, pull its production environment to the ignored `.env.local` file with the Vercel CLI, and run `python manage.py migrate` to create tables and seed the FAQ/error catalog. Vercel automatically collects and serves static files from `STATIC_ROOT`.
7. Check `/health/`, try the assistant, verify a narrow mobile viewport, and request a random nonexistent URL to confirm the custom 404. Set HSTS only after HTTPS is confirmed for the domain; include subdomains only if all of them support HTTPS.
8. Replace the live-link placeholder above and enter the task title, HTTPS URL, and GitHub URL in the assessment spreadsheet.
