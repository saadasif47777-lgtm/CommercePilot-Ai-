# Vercel backend startup

An HTTP 500 means the server could not complete a request. A log beginning
`could not import "api/index.py"` means the Python application failed to load;
all API sections can fail together while the static website still displays.
Expand the log and read the final exception to identify the exact cause.

## Dependency installation

Runtime packages are defined in the root `requirements.txt`. Python is selected
by `.python-version`. Keep pytest settings in `pytest.ini` and Ruff settings in
`ruff.toml`. A tooling-only `pyproject.toml` can take precedence over
`requirements.txt` in Vercel's Python installer and leave required packages out
of the function. If migrating to a Python project manifest in future, migrate
the complete runtime dependencies too.

The GitHub workflow now installs only `requirements.txt` in a fresh virtual
environment and imports the actual `api/index.py` entry point. It runs the real
production startup with disposable PostgreSQL, checks health, projects,
integration status and advisor session creation, and loads both advisor prompts.
The placeholder AI key is only for startup validation; this is not a live model
test. The existing suite separately tests business workflows and browser flows.

## Production configuration and verification

Set `APP_MODE=production`, a real `LLM_API_KEY` and `LLM_MODEL`, persistent
PostgreSQL `DATABASE_URL`, and `CREDENTIAL_ENCRYPTION_KEY` in Vercel. Keep these
values out of source control and screenshots. Missing required configuration or
an unreachable database must be corrected in Vercel; do not enable demo mode or
ephemeral SQLite to conceal a startup failure.

After a production deployment completes, use an authorized browser or Vercel
connection to check `/api/health`, `/api/projects`, `/api/integrations/status`,
then open AI Assistant and create a conversation. Send a real question to verify
the configured model separately. Test connected Shopify and Meta accounts only
with their owner-approved credentials. Deployment success alone does not prove
the runtime or external accounts work. Vercel Authentication can block an
unauthenticated tester before requests reach the application.
