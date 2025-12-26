import streamlit as st
from datetime import datetime
from soulsync.db import SessionLocal
from soulsync.models import Mission, PlanRun
from soulsync.services.missions import (
    get_todays_missions,
    complete_mission,
    build_planner_context,
    generate_ai_plan_json,
    validate_plan,
    preview_plan,
    assign_plan_creating_daily_missions,
    # --- 3F-1: swaps + time context ---
    compute_time_context,
    get_pending_missions,
    propose_swaps,
    validate_swap_plan,
    apply_swaps,
)
from soulsync.services.streak import (
    check_and_handle_streak_break,
    reset_shields_if_new_week,
    complete_recovery_mission,
)
from soulsync.ui.theme import load_css

load_css()

if "user" not in st.session_state:
    st.warning("Please log in first.")
    st.stop()

st.title("Today's Missions 🎯")

db = SessionLocal()
try:
    user_id = st.session_state.user["id"]
    today = datetime.now().strftime("%Y-%m-%d")

    # Weekly shield reset (existing)
    reset_shields_if_new_week(user_id, db)

    # ------------------------------------------------------------
    # 3F-1: Time remaining banner (bedtime cutoff + midnight window)
    # ------------------------------------------------------------
    time_ctx = compute_time_context(user_id, db)
    mins_to_bed = time_ctx.get("effective_mins_to_bedtime", 0)
    mins_to_mid = time_ctx.get("effective_mins_to_midnight", 0)

    st.info(
        f"⏳ Until bedtime cutoff: **{mins_to_bed} min**  •  "
        f"🌙 Wind-down until midnight: **{mins_to_mid} min**"
    )

    missions = get_todays_missions(user_id, db)

    # -------------------------
    # Display existing missions
    # -------------------------
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

            recovery_badge = "🛡️ Recovery" if getattr(mission, "is_recovery", False) else ""

            with st.container():
                why_text = ""
                try:
                    if mission.geo_rule_json:
                        why_text = mission.geo_rule_json.get("why", "") or ""
                except Exception:
                    why_text = ""

                st.markdown(
                    f"""
                    <div class="ss-card">
                        <span class="ss-chip">{mission.type}</span>
                        <span class="ss-chip">+{mission.xp_reward} XP</span>
                        {f'<span class="ss-chip">{recovery_badge}</span>' if recovery_badge else ''}
                        <h3>{mission.title}</h3>
                        <p><i>{why_text}</i></p>
                        {f'<p>Duration: {mission.duration_minutes} mins</p>' if getattr(mission, "duration_minutes", None) else ''}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                if assign.status == "pending":
                    if st.button("Complete", key=f"btn_complete_{assign.id}"):
                        if getattr(mission, "is_recovery", False):
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

    # -----------------------------------------
    # 3F-1: AI Swap UI (preview + apply swaps)
    # -----------------------------------------
    st.subheader("🔁 AI Swaps (up to 3)")
    st.write("Use AI to intelligently swap up to 3 **pending** missions based on your Journal + Your Voice context.")

    # Optional context pushed from Journal/Voice pages (3F-2/3F-3 later)
    journal_signals = st.session_state.get("latest_journal_signals", None)
    voice_intent = st.session_state.get("latest_voice_intent", None)

    pending = get_pending_missions(user_id, today, db)

    if not pending:
        st.caption("No pending missions available to swap.")
    else:
        col_s1, col_s2 = st.columns([1, 1])

        with col_s1:
            if st.button("Suggest swaps", type="secondary", key="btn_suggest_swaps"):
                swap_json = propose_swaps(
                    user_id=user_id,
                    date_str=today,
                    minutes_cap=st.session_state.get("minutes_cap_slider", 60),
                    db=db,
                    journal_signals_json=journal_signals,
                    voice_intent_summary=voice_intent,
                )
                st.session_state["swap_preview"] = swap_json

        with col_s2:
            if st.button("Clear swap preview", key="btn_clear_swaps"):
                st.session_state.pop("swap_preview", None)
                st.rerun()

        swap_preview = st.session_state.get("swap_preview")
        if swap_preview:
            st.markdown("### Swap Preview")

            swap_count = swap_preview.get("swap_count", 0)
            if swap_count == 0:
                st.warning(swap_preview.get("no_swap_reason", "No swaps suggested."))
            else:
                replacements = (swap_preview.get("replacements") or [])[:swap_count]
                for idx, repl in enumerate(replacements, start=1):
                    old_title = repl.get("replace_title", "")
                    nm = repl.get("new_mission", {}) or {}

                    st.markdown(f"**{idx}. Replace:** {old_title}")
                    st.markdown(
                        f"➡️ **New:** {nm.get('title','')} "
                        f"({nm.get('type','')}, {nm.get('difficulty','')}, {nm.get('duration_minutes',0)} mins, +{nm.get('xp_reward',0)} XP)"
                    )
                    if repl.get("reason"):
                        st.caption(f"Reason: {repl.get('reason')}")
                    if nm.get("why_this"):
                        st.caption(f"Why this: {nm.get('why_this')}")

            # Validate before applying swaps
            ok, errs = validate_swap_plan(swap_preview, pending, time_ctx)
            if not ok:
                st.error("Swap plan invalid:")
                for e in errs:
                    st.write(f"- {e}")

            apply_disabled = (not ok) or (swap_preview.get("swap_count", 0) == 0)
            if st.button("Apply swaps", type="primary", disabled=apply_disabled, key="btn_apply_swaps"):
                apply_swaps(
                    user_id=user_id,
                    date_str=today,
                    swap_json=swap_preview,
                    db=db,
                    source="missions_page",
                )
                st.success("Swaps applied ✅")
                st.session_state.pop("swap_preview", None)
                st.rerun()

    st.divider()

    # -----------------------
    # Smart AI Planner (existing)
    # -----------------------
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

    if st.session_state.get("show_regen_confirm"):
        st.warning("Regenerate will replace today's plan. Continue?")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Yes, regenerate", key="btn_regen_yes"):
                if assigned_plan:
                    assigned_plan.status = "superseded"
                    db.commit()
                st.session_state.show_regen_confirm = False
                st.session_state.force_regenerate = True
                st.rerun()
        with c2:
            if st.button("Cancel", key="btn_regen_cancel"):
                st.session_state.show_regen_confirm = False
                st.rerun()

    if st.button("Generate AI Plan", key="btn_generate_plan"):
        try:
            # Build context (optionally include journal/voice context if present)
            context = build_planner_context(
                user_id,
                today,
                minutes_cap,
                db,
                journal_signals_json=journal_signals,
                voice_intent_summary=(voice_intent.get("intent_summary") if isinstance(voice_intent, dict) else None),
            )

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
                    plan_run, _ = preview_plan(
                        user_id, today, "missions_page", plan_json,
                        time_context, minutes_cap, db
                    )

                    st.session_state.preview_plan_run_id = plan_run.id
                    st.session_state.show_plan_preview = True
                    st.rerun()
        except Exception as e:
            st.error(f"Error generating plan: {str(e)[:200]}")

    # Show plan preview if available
    if st.session_state.get("show_plan_preview") and st.session_state.get("preview_plan_run_id"):
        plan_run = db.query(PlanRun).filter(PlanRun.id == st.session_state.preview_plan_run_id).first()

        if not plan_run:
            st.session_state.show_plan_preview = False
            st.session_state.preview_plan_run_id = None
            st.rerun()

        plan_json = (plan_run.meta_json or {}).get("plan_json", {})

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

            st.markdown(
                f"""
                **{title}** ({m_type})  
                Duration: {duration} mins | XP: +{xp}  
                *{why}*  
                """
            )

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
                    st.session_state.preview_plan_run_id = None
                    st.rerun()
                else:
                    st.warning("Plan already assigned (idempotent).")

        with col_cancel:
            if st.button("Cancel", key="btn_cancel_preview"):
                st.session_state.show_plan_preview = False
                st.session_state.preview_plan_run_id = None
                st.rerun()

finally:
    db.close()
