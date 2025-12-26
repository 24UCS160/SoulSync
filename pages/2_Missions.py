import streamlit as st
from datetime import datetime
from soulsync.db import SessionLocal
from soulsync.models import Mission, PlanRun
from soulsync.services.missions import (
    get_todays_missions, complete_mission, build_planner_context, 
    generate_ai_plan_json, validate_plan, preview_plan, assign_plan_creating_daily_missions
)
from soulsync.services.streak import check_and_handle_streak_break, reset_shields_if_new_week, complete_recovery_mission
from soulsync.ui.theme import load_css

load_css()

if "user" not in st.session_state:
    st.warning("Please log in first.")
    st.stop()

st.title("Today's Missions 🎯")

db = SessionLocal()
reset_shields_if_new_week(st.session_state.user["id"], db)

user_id = st.session_state.user["id"]
today = datetime.now().strftime("%Y-%m-%d")

missions = get_todays_missions(user_id, db)

# Display existing missions
if missions:
    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("Today's Tasks")
    with col2:
        st.subheader("Planner")
    
    for assign in missions:
        mission = db.query(Mission).filter(Mission.id == assign.mission_id).first()
        if not mission:
            continue
        
        recovery_badge = "🛡️ Recovery" if mission.is_recovery else ""
        
        with st.container():
            st.markdown(f"""
            <div class="ss-card">
                <span class="ss-chip">{mission.type}</span>
                <span class="ss-chip">+{mission.xp_reward} XP</span>
                {f'<span class="ss-chip">{recovery_badge}</span>' if recovery_badge else ''}
                <h3>{mission.title}</h3>
                <p><i>{mission.geo_rule_json.get('why', '') if mission.geo_rule_json else ''}</i></p>
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
else:
    st.info("No missions yet! Generate a plan below to get started.")

st.divider()

st.subheader("Smart AI Planner ⚡")
st.write("Let AI generate your perfect daily mission plan.")

# AI Plan generator
col_cap, col_regen = st.columns([3, 1])

with col_cap:
    minutes_cap = st.slider("Daily minutes cap", 30, 180, 60, key="minutes_cap_slider")

# Check if there's an assigned plan already
assigned_plan = db.query(PlanRun).filter(
    PlanRun.user_id == user_id,
    PlanRun.date == today,
    PlanRun.kind == "full_plan",
    PlanRun.status == "assigned"
).first()

with col_regen:
    regen_disabled = assigned_plan is not None
    if st.button("Regenerate", disabled=regen_disabled, key="btn_regenerate"):
        st.session_state.show_regen_confirm = True

if "show_regen_confirm" in st.session_state and st.session_state.show_regen_confirm:
    st.warning("Regenerate will replace today's plan. Continue?")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Yes, regenerate"):
            if assigned_plan:
                assigned_plan.status = "superseded"
                db.commit()
            st.session_state.show_regen_confirm = False
            st.session_state.force_regenerate = True
            st.rerun()
    with col2:
        if st.button("Cancel"):
            st.session_state.show_regen_confirm = False
            st.rerun()

if st.button("Generate AI Plan", key="btn_generate_plan"):
    try:
        # Build context
        context = build_planner_context(user_id, today, minutes_cap, db)
        
        # Generate
        plan_json = generate_ai_plan_json(context)
        
        if not plan_json:
            st.error("AI planner failed. Please try again or use basic mode.")
        else:
            # Validate
            time_context = context.get("time_context", {})
            is_valid, errors = validate_plan(plan_json, minutes_cap, time_context)
            
            if not is_valid:
                st.error(f"Plan validation failed: {', '.join(errors[:3])}")
            else:
                # Preview
                plan_run, _ = preview_plan(user_id, today, "missions_page", plan_json, 
                                          time_context, minutes_cap, db)
                
                st.session_state.preview_plan_run = plan_run
                st.session_state.show_plan_preview = True
                st.rerun()
    except Exception as e:
        st.error(f"Error generating plan: {str(e)[:100]}")

# Show plan preview if available
if "show_plan_preview" in st.session_state and st.session_state.show_plan_preview:
    if "preview_plan_run" in st.session_state:
        plan_run = st.session_state.preview_plan_run
        plan_json = plan_run.meta_json.get("plan_json", {})
        
        st.subheader("📋 Plan Preview")
        
        total_mins = 0
        for mission in plan_json.get("missions", []):
            title = mission.get("title", "")
            m_type = mission.get("type", "")
            duration = mission.get("duration_minutes", 0)
            xp = mission.get("xp_reward", 0)
            why = mission.get("why_this", "")
            micro = mission.get("micro", {})
            
            total_mins += duration
            
            st.markdown(f"""
            **{title}** ({m_type})  
            Duration: {duration} mins | XP: +{xp}  
            *{why}*  
            """)
            
            if micro and micro.get("title"):
                st.caption(f"Micro: {micro['title']} ({micro.get('duration_minutes', 0)} mins)")
        
        st.info(f"Total: {total_mins} mins / {minutes_cap} mins cap")
        
        col_assign, col_cancel = st.columns(2)
        with col_assign:
            if st.button("Assign this plan", key="btn_assign"):
                success = assign_plan_creating_daily_missions(user_id, today, plan_run, db)
                if success:
                    st.success("✅ Plan assigned! Missions created.")
                    st.session_state.show_plan_preview = False
                    del st.session_state.preview_plan_run
                    st.rerun()
                else:
                    st.warning("Plan already assigned (idempotent).")
        
        with col_cancel:
            if st.button("Cancel", key="btn_cancel_preview"):
                st.session_state.show_plan_preview = False
                if "preview_plan_run" in st.session_state:
                    del st.session_state.preview_plan_run
                st.rerun()

db.close()
