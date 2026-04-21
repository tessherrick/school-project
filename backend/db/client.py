"""Supabase client factories.

- service_client(): admin access, bypasses RLS. Use for migrations and seeding.
- anon_client(): backend runtime reads/writes on behalf of users. RLS-aware.
"""
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")


@lru_cache(maxsize=1)
def service_client() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


@lru_cache(maxsize=1)
def anon_client() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_ANON_KEY"]
    return create_client(url, key)
