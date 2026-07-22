"""Apply versioned SahelWatch PostgreSQL migrations exactly once."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))


def main() -> None:
    database_url = os.getenv("DATABASE_ADMIN_URL") or os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("Set DATABASE_ADMIN_URL or DATABASE_URL in backend/.env")

    try:
        import psycopg
    except ImportError as exc:
        raise SystemExit(
            "PostgreSQL driver could not load. Install the pinned binary driver with "
            "`python -m pip install \"psycopg[binary]==3.3.4\"`. "
            f"Original error: {exc}"
        ) from exc

    migrations = sorted(Path(__file__).with_name("migrations").glob("[0-9][0-9][0-9]_*.sql"))
    with psycopg.connect(database_url, connect_timeout=15) as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS public.schema_migrations (
                   version text PRIMARY KEY,
                   applied_at timestamptz NOT NULL DEFAULT now()
               )"""
        )
        applied = {
            row[0] for row in connection.execute("SELECT version FROM public.schema_migrations").fetchall()
        }
        for path in migrations:
            if path.name in applied:
                print(f"skip  {path.name}")
                continue
            # Migration files are repository-controlled, not user input.
            connection.execute(path.read_text(encoding="utf-8"), prepare=False)
            connection.execute(
                "INSERT INTO public.schema_migrations (version) VALUES (%s)", (path.name,)
            )
            print(f"apply {path.name}")
    print("Database migrations complete")


if __name__ == "__main__":
    main()
