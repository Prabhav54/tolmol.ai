# Vercel entrypoint: the Python runtime serves the ASGI `app` exported from this module.
from api.main import app  # noqa: F401
