import streamlit as st
from soulsync.db import SessionLocal
from soulsync.services.missions import get_todays_missions, complete_mission
from soulsync.models import Mission
from soulsync.ui.theme import load_css

load_css()

if "user" not in st.session_state:
    st.warning("Please log in first.")
    st.stop()

st.title("Today's Missions 🎯")

db = SessionLocal()
missions = get_todays_missions(st.session_state.user["id"], db)

if not missions:
    st.info("No missions yet! Check in with your Journal to generate them.")
else:
    for assign in missions:
        mission = db.query(Mission).filter(Mission.id == assign.mission_id).first()
        with st.container():
            st.markdown(f"""
            <div class="ss-card">
                <span class="ss-chip">{mission.type}</span>
                <span class="ss-chip">+{mission.xp_reward} XP</span>
                <h3>{mission.title}</h3>
                <p><i>{mission.geo_rule_json.get('why', '')}</i></p>
            </div>
            """, unsafe_allow_html=True)
            if assign.status == "pending":
                if st.button("Complete", key=f"btn_{assign.id}"):
                    complete_mission(assign.id, db)
                    st.success("Mission Complete! +XP")
                    st.rerun()
            else:
                st.write("✅ Completed")

db.close()
