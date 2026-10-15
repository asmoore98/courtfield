"""Runtime settings, read from environment variables."""
import os

# "dev" enables the sample accounts and relaxed CORS. Anything else is production.
ENV = os.environ.get("COURTFIELD_ENV", "dev")
IS_DEV = ENV == "dev"

# Public address of the app, used to build invite links, e.g. https://app.courtfield.com
# Render sets RENDER_EXTERNAL_URL automatically; PUBLIC_URL overrides it (e.g. a custom domain).
PUBLIC_URL = (os.environ.get("PUBLIC_URL") or os.environ.get("RENDER_EXTERNAL_URL") or "http://localhost:8000").rstrip("/")

SESSION_DAYS = int(os.environ.get("SESSION_DAYS", "90"))  # crews shouldn't re-sign-in every week
INVITE_DAYS = int(os.environ.get("INVITE_DAYS", "7"))
