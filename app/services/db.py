from functools import lru_cache

from supabase import Client, create_client

from app.config import get_config


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    config = get_config()
    return create_client(config["supabase"]["url"], config["supabase"]["key"])
