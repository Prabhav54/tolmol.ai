import os

# Offline tests: never touch real keys or a real database from a local .env.
os.environ["GOOGLE_API_KEY"] = ""
os.environ["GEMINI_API_KEY"] = ""
os.environ["AUTO_INIT_DB"] = "false"
