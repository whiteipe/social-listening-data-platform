import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()


class Settings:
    gcp_project = os.environ.get("GCP_PROJECT", "")
    bq_dataset = os.environ.get("BQ_DATASET", "social_listening_data_platform")
    bq_location = os.environ.get("BQ_LOCATION", "US")
    salt = os.environ.get("AUTHOR_HASH_SALT", "")
    meta_graph_version = os.environ.get("META_GRAPH_VERSION", "v21.0")
    meta_token = os.environ.get("META_ACCESS_TOKEN", "")
    ig_user_id = os.environ.get("IG_USER_ID", "")
    youtube_key = os.environ.get("YOUTUBE_API_KEY", "")
    youtube_channel = os.environ.get("YOUTUBE_CHANNEL_ID", "")
    reddit_id = os.environ.get("REDDIT_CLIENT_ID", "")
    reddit_secret = os.environ.get("REDDIT_CLIENT_SECRET", "")
    x_token = os.environ.get("X_BEARER_TOKEN", "")
    slack_webhook = os.environ.get("SLACK_WEBHOOK_URL", "")
    sentiment_backend = os.environ.get("SENTIMENT_BACKEND", "hf")
    llm_model = os.environ.get("LLM_MODEL", "claude-haiku-5-5")


settings = Settings()


def _cfg(path: str = "config/queries.yaml") -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def load_queries() -> dict[str, list[str]]:
    return _cfg()["query_groups"]


def load_hashtags() -> dict[str, list[str]]:
    return _cfg()["hashtags"]


def load_trends() -> tuple[list[str], str]:
    c = _cfg()
    return c["trends_terms"], c["geo"]


def load_locale() -> tuple[str, str]:
    """(país ISO-3166, idioma ISO-639-1) das marcas, ex.: ("BR", "pt")."""
    c = _cfg()
    return c.get("region", "BR"), c.get("language", "pt")
