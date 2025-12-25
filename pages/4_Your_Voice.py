import streamlit as st
from soulsync.db import SessionLocal
from soulsync.services.voice import get_ai_response, check_private_memory_permission
from soulsync.services.moderation import check_safety
from soulsync.models import VoiceMessage, JournalEntry
from soulsync.ui.theme import load_css

load_css()

if "user" not in st.session_state:
    st.warning("Please log in first.")
    st.stop()

st.title("Your Voice 💭")

if "voice_mode" not in st.session_state:
    st.session_state.voice_mode = "Cheer me on"

col1, col2 = st.columns([3, 1])
with col1:
    st.subheader("Chat")
with col2:
    st.session_state.voice_mode = st.selectbox(
        "Mode",
        ["Cheer me on", "Help me plan", "Reflect with me", "Study buddy"],
        key="voice_mode_select"
    )

db = SessionLocal()
history = db.query(VoiceMessage).filter(VoiceMessage.user_id == st.session_state.user["id"]).order_by(VoiceMessage.created_at).all()

for msg in history:
    cls = "ss-bubble-user" if msg.role == "user" else "ss-bubble-assistant"
    st.markdown(f'<div class="{cls}">{msg.text}</div><div style="clear: both;"></div>', unsafe_allow_html=True)

st.write("")

# Permission gate check
has_private = False
recent_entries = db.query(JournalEntry).filter(
    JournalEntry.user_id == st.session_state.user["id"]
).order_by(JournalEntry.created_at.desc()).limit(3).all()

for entry in recent_entries:
    tags = entry.tags.split(",") if entry.tags else []
    if "private" in tags or "sensitive" in tags:
        has_private = True
        break

if has_private and "private_memory_approved" not in st.session_state:
    st.info("I found something you wrote that might help. Use it?")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Yes, use it"):
            st.session_state.private_memory_approved = True
    with col2:
        if st.button("No, keep it private"):
            st.session_state.private_memory_approved = False

user_input = st.chat_input("What's on your mind?")

if user_input:
    safe, warning = check_safety(user_input)
    if not safe:
        st.error(warning)
    else:
        context = f"User mode: {st.session_state.voice_mode}. User is a student."
        response, has_private_used = get_ai_response(
            st.session_state.user["id"],
            user_input,
            context,
            db,
            mode=st.session_state.voice_mode
        )
        st.rerun()

db.close()
