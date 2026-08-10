import os


def database_url() -> str:
    return os.environ["DATABASE_URL"]


def admin_token() -> str:
    return os.environ["ADMIN_TOKEN"]
