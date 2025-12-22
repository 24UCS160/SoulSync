import streamlit as st
from soulsync.db import SessionLocal
from soulsync.services.stats import get_stats
from soulsync.ui.theme import load_css

load_css()

if "user" not in st.session_state:
    st.warning("Please log in first.")
    st.stop()

st.title("Dashboard 📊")

db = SessionLocal()
stats = get_stats(st.session_state.user["id"], db)
db.close()

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

st.subheader("Recent Activity")
st.write("Complete missions to level up!")
