import streamlit as st
from datetime import datetime
from soulsync.db import SessionLocal
from soulsync.services.stats import get_stats
from soulsync.services.story_service import get_week_start, get_or_seed_story_for_week, compute_week_progress, evaluate_and_unlock
from soulsync.models import Profile
from soulsync.ui.theme import load_css

load_css()

if "user" not in st.session_state:
    st.warning("Please log in first.")
    st.stop()

st.title("Dashboard 📊")

db = SessionLocal()

# Stats display
stats = get_stats(st.session_state.user["id"], db)
cols = st.columns(len(stats) if stats else 1)
for i, stat in enumerate(stats):
    with cols[i]:
        st.markdown(f"""
        <div class="ss-card" style="text-align: center;">
            <h4>{stat.type}</h4>
            <h1>{stat.level}</h1>
            <p>XP: {stat.xp}</p>
        </div>
        """, unsafe_allow_html=True)

# Streak & Shields
profile = db.query(Profile).filter(Profile.user_id == st.session_state.user["id"]).first()
if profile:
    st.markdown(f"""
    <div class="ss-card">
        <h3>Streak: {profile.streak_count} 🔥</h3>
        <p>Shields: {profile.streak_shields_remaining} 🛡️</p>
    </div>
    """, unsafe_allow_html=True)

# This Week's Arc
today = datetime.now()
week_start = get_week_start(today)
story = get_or_seed_story_for_week(week_start, db)
progress = compute_week_progress(st.session_state.user["id"], week_start, db)

st.markdown(f"""
<div class="ss-card">
    <h3>This Week's Arc 📖</h3>
    <p><b>{story.title}</b></p>
    <p>Progress: {progress}/3</p>
    <div style="background-color: #E3F2FD; height: 10px; border-radius: 5px;">
        <div style="background-color: #22B8CF; height: 10px; border-radius: 5px; width: {progress*33.3}%;"></div>
    </div>
</div>
""", unsafe_allow_html=True)

@st.dialog("Story", width="medium", dismissible=True)
def show_story_dialog(story_md: str, user_id: int, week_start, db):
    st.markdown(story_md)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Mark as Read ✅", key="btn_mark_story_read"):
            evaluate_and_unlock(user_id, week_start, db)
            st.success("Story unlocked!")
            st.rerun()

    with col2:
        if st.button("Close", key="btn_close_story"):
            st.rerun()


if st.button("Read Story", key="btn_read_story"):
    show_story_dialog(story.content_md, st.session_state.user["id"], week_start, db)
db.close()
