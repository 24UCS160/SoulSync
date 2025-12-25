import os

# Get DATABASE_URL, but validate it; fallback to SQLite if invalid
_raw_db_url = os.getenv("DATABASE_URL", "sqlite:///soulsync.db")

# If DATABASE_URL looks malformed, use SQLite instead
if _raw_db_url and not _raw_db_url.startswith(("sqlite://", "postgresql://", "postgres://")):
    print(f"⚠️ Invalid DATABASE_URL detected. Using SQLite fallback.")
    DATABASE_URL = "sqlite:///soulsync.db"
else:
    DATABASE_URL = _raw_db_url

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL_ID = os.getenv("GEMINI_MODEL_ID", "gemini-2.0-flash")

def get_diagnostics():
    return {
        "Database": "SQLite (Default)" if "sqlite" in DATABASE_URL else "Postgres",
        "Google API Key": "Configured" if GOOGLE_API_KEY else "Missing (Fallback Mode)",
        "Model": GEMINI_MODEL_ID
    }
