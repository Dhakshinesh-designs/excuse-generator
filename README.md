# Sicko-Excuse Generator and Support Assistant

## Assessment submission

- **Individual task title:** Responsive Excuse Generator with FAQ-Grounded AI Support Assistant
- **Live website (HTTPS):** Not deployed yet — add the production HTTPS URL after deployment.
- **GitHub repository:** https://github.com/Dhakshinesh-designs/excuse-generator
- **Proposed improvement:** Add authenticated ticket-status tracking so students can follow up on support requests.
- **Assessment task sheet:** [Software Development submission sheet](https://docs.google.com/spreadsheets/d/1gac3qN_sFgbBQR7utv6N-66-C8szNq3-F6L7NQsbx78/edit?usp=sharing)

## Features

- Responsive excuse generator, FAQ, error-code guide, and About pages.
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

1. Choose a Django-compatible host with HTTPS, persistent PostgreSQL, and MongoDB service/connection string.
2. Push this repository to GitHub and add the production HTTPS URL to this README and the assessment task sheet.
3. Configure the environment variables above in the hosting dashboard; do not put credentials in source or commit history.
4. Run `python manage.py migrate` as a release step, then collect static files with `python manage.py collectstatic --noinput`.
5. Set the deployed host in `DJANGO_ALLOWED_HOSTS`, the HTTPS origin in `DJANGO_CSRF_TRUSTED_ORIGINS`, and enable `DJANGO_SECURE_SSL_REDIRECT`. Set HSTS only after confirming HTTPS works for the domain.
6. Visit `/health/`, check the generator and chat, test a narrow mobile viewport, and request a random nonexistent path to confirm the branded 404 page.
7. Copy the final task title, HTTPS website URL, and GitHub URL into the assessment spreadsheet.
