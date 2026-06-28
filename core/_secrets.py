"""
core._secrets — framework-neutral secret loading.

Reads keys from .streamlit/secrets.toml (so the existing Streamlit setup keeps
working) and falls back to environment variables (so the same code runs under a
plain API server / cron with no Streamlit). No streamlit import.
"""
import os

_CACHE = {}


def get_secret(name, default=None):
    """Return a secret by name: env var first, then .streamlit/secrets.toml."""
    if name in os.environ:
        return os.environ[name]
    if name in _CACHE:
        return _CACHE[name]
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        ".streamlit", "secrets.toml")
    val = None
    if os.path.exists(path):
        try:
            import tomllib
            with open(path, "rb") as fh:
                val = tomllib.load(fh).get(name)
        except Exception:
            with open(path, encoding="utf-8") as fh:  # minimal KEY = "value" fallback
                for ln in fh:
                    if ln.strip().startswith(name):
                        parts = ln.split("=", 1)
                        if len(parts) == 2:
                            val = parts[1].strip().strip('"').strip("'")
                            break
    _CACHE[name] = val if val is not None else default
    return _CACHE[name]
