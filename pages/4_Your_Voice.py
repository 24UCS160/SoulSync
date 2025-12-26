import streamlit as st
from datetime import datetime
from soulsync.db import SessionLocal
from soulsync.services.voice import get_ai_response
from soulsync.services.moderation import check_safety
from soulsync.models import VoiceMessage, JournalEntry
from soulsync.ui.theme import load_css

# 3F-3: voice intent extractor (Step 3B)
try:
    from soulsync.services.voice_intent import extract_voice_intent_summary
except Exception:
    extract_voice_intent_summary = None

load_css()

if "user" not in st.session_state:
    st.warning("Please log in first.")
    st.stop()

st.title("Your Voice 💭")
st.caption("Optimistic, but honest. A thinking tool — not a diary. Planning happens only when you click a tool button.")

# Defaults
st.session_state.setdefault("voice_mode", "Cheer me on")
st.session_state.setdefault("latest_voice_intent", None)
st.session_state.setdefault("open_swaps_on_missions", False)

user_id = st.session_state.user["id"]
user_tz = st.session_state.user.get("timezone")

# Mode selector
col1, col2 = st.columns([3, 1])
with col1:
    st.subheader("Chat")
with col2:
    st.session_state.voice_mode = st.selectbox(
        "Mode",
        ["Cheer me on", "Help me plan", "Reflect with me", "Study buddy"],
        index=["Cheer me on", "Help me plan", "Reflect with me", "Study buddy"].index(st.session_state.voice_mode)
        if st.session_state.voice_mode in ["Cheer me on", "Help me plan", "Reflect with me", "Study buddy"]
        else 0,
        key="voice_mode_select",
    )

db = SessionLocal()
try:
    # Load history (oldest -> newest)
    history = (
        db.query(VoiceMessage)
        .filter(VoiceMessage.user_id == user_id)
        .order_by(VoiceMessage.created_at)
        .all()
    )

    # ---------------------------
    # 3F-3 Tool Buttons (Plan/Swap)
    # ---------------------------
    st.markdown("### Tools")
    tool_col1, tool_col2 = st.columns(2)

    def _build_voice_intent_from_recent(history_rows) -> dict:
        """Extract intent summary from the last 1–3 user messages."""
        recent_user_msgs = [m.text for m in history_rows if m.role == "user"][-3:]

        # Fallback if no user messages yet
        if not recent_user_msgs:
            return {
                "intent_summary": "No specific intent yet.",
                "priority": "other",
                "constraints": [],
            }

        if extract_voice_intent_summary is None:
            # Safe deterministic fallback
            return {
                "intent_summary": recent_user_msgs[-1][:140],
                "priority": "other",
                "constraints": [],
            }

        # Use the extractor service
        try:
            intent = extract_voice_intent_summary(recent_user_msgs, user_timezone=user_tz)
            if not isinstance(intent, dict):
                raise ValueError("Intent extractor did not return dict")
            # Ensure keys
            intent.setdefault("intent_summary", recent_user_msgs[-1][:140])
            intent.setdefault("priority", "other")
            intent.setdefault("constraints", [])
            return intent
        except Exception:
            return {
                "intent_summary": recent_user_msgs[-1][:140],
                "priority": "other",
                "constraints": [],
            }

    with tool_col1:
        if st.button("Build today’s plan from this chat ⚡", key="btn_voice_plan_tool"):
            st.session_state["latest_voice_intent"] = _build_voice_intent_from_recent(history)
            st.session_state["open_swaps_on_missions"] = False
            # Navigate to Missions page
            try:
                st.switch_page("pages/2_Missions.py")
            except Exception:
                st.info("Go to the Missions page to generate your AI plan.")

    with tool_col2:
        if st.button("Swap up to 3 missions based on this chat 🔁", key="btn_voice_swap_tool"):
            st.session_state["latest_voice_intent"] = _build_voice_intent_from_recent(history)
            st.session_state["open_swaps_on_missions"] = True
            # Navigate to Missions page
            try:
                st.switch_page("pages/2_Missions.py")
            except Exception:
                st.info("Go to the Missions page to suggest/apply swaps.")

    # Show current extracted intent (if any)
    if st.session_state.get("latest_voice_intent"):
        vi = st.session_state["latest_voice_intent"]
        st.caption(f"🧭 Intent summary saved for planning: **{vi.get('intent_summary','')}**")

    st.divider()

    # ---------------------------
    # Render chat history
    # ---------------------------
    for msg in history:
        cls = "ss-bubble-user" if msg.role == "user" else "ss-bubble-assistant"
        st.markdown(
            f'<div class="{cls}">{msg.text}</div><div style="clear: both;"></div>',
            unsafe_allow_html=True,
        )

    st.write("")

    # -----------------------------------
    # Permission gate check (private memory)
    # -----------------------------------
    has_private = False
    recent_entries = (
        db.query(JournalEntry)
        .filter(JournalEntry.user_id == user_id)
        .order_by(JournalEntry.created_at.desc())
        .limit(3)
        .all()
    )

    for entry in recent_entries:
        tags = []
        try:
            tags = entry.tags.split(",") if entry.tags else []
            tags = [t.strip().lower() for t in tags]
        except Exception:
            tags = []
        if "private" in tags or "sensitive" in tags:
            has_private = True
            break

    if has_private and "private_memory_approved" not in st.session_state:
        st.info("I found something you wrote that might help. Use it?")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Yes, use it", key="btn_private_yes"):
                st.session_state.private_memory_approved = True
                st.rerun()
        with c2:
            if st.button("No, keep it private", key="btn_private_no"):
                st.session_state.private_memory_approved = False
                st.rerun()

    # ---------------------------
    # Chat input
    # ---------------------------
    user_input = st.chat_input("What's on your mind?")

    if user_input:
        safe, warning = check_safety(user_input)
        if not safe:
            st.error(warning)
        else:
            # Save user message to DB
            umsg = VoiceMessage(
                user_id=user_id,
                role="user",
                text=user_input,
                created_at=datetime.utcnow(),
            )
            db.add(umsg)
            db.commit()

            # Build a light context (the voice service can do the rest)
            context = f"User mode: {st.session_state.voice_mode}. User is a student."

            # Get AI response
            response, has_private_used = get_ai_response(
                user_id,
                user_input,
                context,
                db,
                mode=st.session_state.voice_mode,
            )

            # If your get_ai_response already stores assistant messages in DB, this may duplicate.
            # To avoid duplication, only store if response exists AND last assistant message isn't identical.
            if response:
                last_assistant = (
                    db.query(VoiceMessage)
                    .filter(VoiceMessage.user_id == user_id, VoiceMessage.role == "assistant")
                    .order_by(VoiceMessage.created_at.desc())
                    .first()
                )
                if not last_assistant or (last_assistant.text or "").strip() != (response or "").strip():
                    amsg = VoiceMessage(
                        user_id=user_id,
                        role="assistant",
                        text=response,
                        created_at=datetime.utcnow(),
                    )
                    db.add(amsg)
                    db.commit()

            st.rerun()

finally:
    db.close()
