from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("gcontext-ai")
except PackageNotFoundError:  # running from a checkout without an install
    __version__ = "unknown"
