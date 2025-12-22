import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///soulsync.db")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL_ID = os.getenv("GEMINI_MODEL_ID", "gemini-2.0-flash")

# Diagnostics (safe to print)
def get_diagnostics():
    return {
        "Database": "SQLite (Default)" if "sqlite" in DATABASE_URL else "Postgres",
        "Google API Key": "Configured" if GOOGLE_API_KEY else "Missing (Fallback Mode)",
        "Model": GEMINI_MODEL_ID
    }
