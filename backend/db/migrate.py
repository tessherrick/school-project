"""Apply SQL migrations via a direct Postgres connection.

Supabase's REST API can't execute arbitrary DDL, so this uses psycopg against
the Postgres connection string. Grab the string from the Supabase dashboard:
  Project settings → Database → Connection string → "Transaction pooler" URI
  Paste your database password in place of [YOUR-PASSWORD]
  Add it to .env as SUPABASE_DB_URL

Run from the project root:
    python -m backend.db.migrate
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = REPO_ROOT / "migrations"

load_dotenv(dotenv_path=REPO_ROOT / ".env")


def main() -> int:
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        print("SUPABASE_DB_URL is not set in .env.\n")
        print("Two ways forward:\n")
        print("  A. Run it via Supabase SQL editor (fastest, no password juggling).")
        print(f"     Open the dashboard → SQL editor → paste the contents of:")
        print(f"     {MIGRATIONS_DIR}/001_initial_schema.sql\n")
        print("  B. Add SUPABASE_DB_URL to .env so this script can run it for you:")
        print("     Dashboard → Project settings → Database → Connection string")
        print('     Pick "Transaction pooler", replace [YOUR-PASSWORD], paste into .env.')
        return 1

    import psycopg

    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        print(f"No .sql files in {MIGRATIONS_DIR}")
        return 1

    print("Connecting to Postgres...")
    with psycopg.connect(db_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            for f in files:
                print(f"Applying {f.name}...")
                cur.execute(f.read_text())
                print(f"  ok: {f.name}")
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
