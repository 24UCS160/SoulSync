# SoulSync MVP

This is a Streamlit-based Student Life RPG.

## Setup

1.  **Dependencies**: Installed via `packager_tool` (Streamlit, SQLAlchemy, Requests).
2.  **Run**: `streamlit run app.py --server.port 3000 --server.address 0.0.0.0`
    *   (In Replit, the `.replit` file should handle this, or run manually in Shell).

## Configuration

*   **Database**: Defaults to `sqlite:///soulsync.db`. Set `DATABASE_URL` for Postgres.
*   **AI**: Set `GOOGLE_API_KEY` for Gemini integration. Defaults to fallback mode if missing.

## Features

*   **Dashboard**: View RPG stats.
*   **Missions**: Daily tasks based on journal inputs.
*   **Journal**: Daily check-in.
*   **Your Voice**: Supportive chat (Gemini or Fallback).
