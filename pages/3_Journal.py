import streamlit as st
from soulsync.db import SessionLocal
from soulsync.services.journal import add_entry
from soulsync.services.missions import generate_daily_missions
from soulsync.ui.theme import load_css

load_css()

if "user" not in st.session_state:
    st.warning("Please log in first.")
    st.stop()

st.title("Daily Journal 📔")

with st.form("journal_form"):
    st.subheader("How are you today?")
    mood = st.slider("Mood (1-10)", 1, 10, 7)
    
    st.subheader("Health Check")
    col1, col2 = st.columns(2)
    sleep = col1.number_input("Sleep (hours)", 0.0, 24.0, 7.0)
    water = col2.number_input("Water (cups)", 0, 20, 5)
    
    col3, col4 = st.columns(2)
    study = col3.number_input("Study (mins)", 0, 600, 30)
    move = col4.number_input("Movement (mins)", 0, 600, 15)
    
    st.subheader("Reflection")
    text = st.text_area("What's on your mind?")
    good_thing = st.text_input("One good thing today")
    
    submitted = st.form_submit_button("Check In")
    
    if submitted:
        metrics = {
            "sleep_hours": sleep,
            "water_cups": water,
            "study_minutes": study,
            "movement_minutes": move,
            "good_thing": good_thing
        }
        
        db = SessionLocal()
        add_entry(st.session_state.user["id"], text, mood, metrics, db)
        
        # Generate missions
        generate_daily_missions(st.session_state.user["id"], metrics, db)
        
        db.close()
        st.success("Entry saved! Missions generated.")
