import os


def database_url() -> str:
    return os.environ["DATABASE_URL"]


def admin_token() -> str:
    return os.environ["ADMIN_TOKEN"]


MAX_FILE_BYTES = int(os.environ.get("MAX_FILE_BYTES", 1_000_000))
MAX_BUNDLE_BYTES = int(os.environ.get("MAX_BUNDLE_BYTES", 5_000_000))
MAX_FILES = int(os.environ.get("MAX_FILES", 200))
