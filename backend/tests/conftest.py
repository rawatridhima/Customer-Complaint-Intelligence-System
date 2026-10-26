"""Root test configuration. Runs before any test module imports the app.

Integration tests must never touch the development database: they create
complaints, and the migration test drops every table. So the tests always use
a separate database, "<your database>_test" (for example cis_test), created
automatically on first use. Set TEST_DATABASE_URL to choose another one.

This has to happen here, before app.core.config is imported anywhere, because
the settings object reads DATABASE_URL once at import time.
"""

import os

from sqlalchemy.engine import make_url

DEFAULT_URL = "postgresql+psycopg://cis:cis_password@db:5432/cis"


def _test_database_url() -> str:
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        return explicit
    url = make_url(os.environ.get("DATABASE_URL") or _from_dotenv() or DEFAULT_URL)
    name = url.database or "cis"
    if not name.endswith("_test"):
        url = url.set(database=f"{name}_test")
    return url.render_as_string(hide_password=False)


def _from_dotenv() -> str | None:
    """DATABASE_URL from backend/.env or the project .env, when not exported."""
    here = os.path.dirname(__file__)
    for path in (os.path.join(here, "..", ".env"), os.path.join(here, "..", "..", ".env")):
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("DATABASE_URL="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
        except OSError:
            continue
    return None


os.environ["DATABASE_URL"] = _test_database_url()
