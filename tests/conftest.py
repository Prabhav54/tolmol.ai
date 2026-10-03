import os

# Tests are offline: never pick up real keys or a real database from a local .env.
os.environ.setdefault("GOOGLE_API_KEY", "")
os.environ.setdefault("GEMINI_API_KEY", "")
os.environ.setdefault("AUTO_INIT_DB", "false")
