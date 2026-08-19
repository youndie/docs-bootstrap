"""Configuration for catalog-api.

Every key is read here and nowhere else, so this file is the list of knobs the
service actually has. Defaults are the values a development machine runs with.
"""
import os


class Config:
    def __init__(self, env=None):
        env = os.environ if env is None else env
        self.database_url = env.get(
            "CATALOG_DATABASE_URL", "postgresql://localhost/catalog"
        )
        # Number of books in one search page. Fixed for every caller.
        self.page_size = int(env.get("CATALOG_PAGE_SIZE", "25"))
        # Read, stored, and never consulted: nothing in the service lets a
        # caller ask for a larger page, so there is no upper bound to enforce.
        self.max_page_size = int(env.get("CATALOG_MAX_PAGE_SIZE", "100"))
        self.min_query_length = int(env.get("CATALOG_MIN_QUERY_LENGTH", "2"))
        # Shared secret expected in X-Service-Token on /internal/** routes.
        self.service_token = env.get("CATALOG_SERVICE_TOKEN", "dev-token")


CONFIG = Config()
