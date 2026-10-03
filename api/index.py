# Vercel entrypoint: the Python runtime serves the ASGI `app` exported from this module.
from tolmol.main import app  # noqa: F401
