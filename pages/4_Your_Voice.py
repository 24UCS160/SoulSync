import streamlit as st
from soulsync.db import SessionLocal
from soulsync.services.voice import get_ai_response
from soulsync.services.moderation import check_safety
from soulsync.models import VoiceMessage
from soulsync.ui.theme import load_css

load_css()

if "user" not in st.session_state:
    st.warning("Please log in first.")
    st.stop()

st.title("Your Voice 💭")

db = SessionLocal()
history = db.query(VoiceMessage).filter(VoiceMessage.user_id == st.session_state.user["id"]).order_by(VoiceMessage.created_at).all()

for msg in history:
    cls = "ss-bubble-user" if msg.role == "user" else "ss-bubble-assistant"
    # Clean float clearing
    st.markdown(f'<div class="{cls}">{msg.text}</div><div style="clear: both;"></div>', unsafe_allow_html=True)

st.write("") # Spacer

user_input = st.chat_input("What's on your mind?")

if user_input:
    # Moderation
    safe, warning = check_safety(user_input)
    if not safe:
        st.error(warning)
    else:
        # Get AI response
        context = "User is a student."
        response = get_ai_response(st.session_state.user["id"], user_input, context, db)
        
        st.rerun()

db.close()
