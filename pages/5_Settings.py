import streamlit as st
from soulsync.config import get_diagnostics
from soulsync.db import SessionLocal
from soulsync.services.story_service import get_unlocked_stories
from soulsync.ui.theme import load_css

load_css()
st.title("Settings ⚙️")

db = SessionLocal()

st.subheader("Diagnostics")
diag = get_diagnostics()
st.json(diag)

st.subheader("Storybook 📚")
stories = get_unlocked_stories(st.session_state.user["id"], db) if "user" in st.session_state else []
if stories:
    for story in stories:
        with st.expander(f"{story.title} ({story.week_start_date})"):
            st.markdown(story.content_md)
else:
    st.write("No stories unlocked yet. Keep completing missions!")

if "user" in st.session_state and st.button("Logout"):
    del st.session_state.user
    st.rerun()

db.close()
