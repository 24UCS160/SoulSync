import streamlit as st
from datetime import datetime
from soulsync.db import SessionLocal
from soulsync.services.missions import get_todays_missions, complete_mission
from soulsync.services.streak import check_and_handle_streak_break, reset_shields_if_new_week, complete_recovery_mission
from soulsync.services.planner_service import build_plan, apply_plan
from soulsync.models import Mission
from soulsync.ui.theme import load_css

load_css()

if "user" not in st.session_state:
    st.warning("Please log in first.")
    st.stop()

st.title("Today's Missions 🎯")

db = SessionLocal()
reset_shields_if_new_week(st.session_state.user["id"], db)

missions = get_todays_missions(st.session_state.user["id"], db)

if not missions:
    st.info("No missions yet! Check in with your Journal to generate them.")
else:
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("Today's Tasks")
    with col2:
        st.subheader("Planner")
    
    # Mission list
    for assign in missions:
        mission = db.query(Mission).filter(Mission.id == assign.mission_id).first()
        recovery_badge = "🛡️ Recovery" if mission.is_recovery else ""
        
        with st.container():
            st.markdown(f"""
            <div class="ss-card">
                <span class="ss-chip">{mission.type}</span>
                <span class="ss-chip">+{mission.xp_reward} XP</span>
                {f'<span class="ss-chip">{recovery_badge}</span>' if recovery_badge else ''}
                <h3>{mission.title}</h3>
                <p><i>{mission.geo_rule_json.get('why', '')}</i></p>
                {f'<p>Duration: {mission.duration_minutes} mins</p>' if mission.duration_minutes else ''}
            </div>
            """, unsafe_allow_html=True)
            
            if assign.status == "pending":
                if st.button("Complete", key=f"btn_{assign.id}"):
                    if mission.is_recovery:
                        complete_recovery_mission(assign.id, db)
                        st.success("Streak recovered! 🎉 +XP")
                    else:
                        complete_mission(assign.id, db)
                        st.success("Mission Complete! +XP")
                    st.rerun()
            else:
                st.write("✅ Completed")

st.divider()

st.subheader("Smart Planner ⏱️")
minutes_cap = st.slider("Daily minutes cap", 30, 180, 60)

if st.button("Build Plan"):
    today = datetime.now().strftime("%Y-%m-%d")
    plan = build_plan(st.session_state.user["id"], today, minutes_cap, db)
    if plan:
        st.success(f"Plan ready: {len(plan)} missions, {sum(d for _, _, d in plan)} mins total")
    else:
        st.info("All missions already assigned!")

db.close()
