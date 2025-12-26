import streamlit as st
from soulsync.db import SessionLocal
from soulsync.services.journal import add_entry
from soulsync.services.missions import generate_daily_missions
from soulsync.ui.theme import load_css

# 3F-2: journal signals extraction (if you created this module in Step 3A)
# If it doesn't exist yet, we'll fall back gracefully.
try:
    from soulsync.services.journal_signals import extract_journal_signals
except Exception:
    extract_journal_signals = None

load_css()

if "user" not in st.session_state:
    st.warning("Please log in first.")
    st.stop()

st.title("Daily Journal 📔")
st.caption("This is your private log. It doesn’t judge you. ✅")

# We'll keep a place to store post-submit actions
st.session_state.setdefault("latest_journal_signals", None)
st.session_state.setdefault("go_to_missions", False)
st.session_state.setdefault("open_swaps_on_missions", False)

with st.form("journal_form"):
    st.subheader("How are you today?")

    # Keep your original 1–10 mood slider
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
        "good_thing": good_thing,
    }

    user_id = st.session_state.user["id"]
    db = SessionLocal()
    try:
        # 1) Save Journal entry
        add_entry(user_id, text, mood, metrics, db)

        # 2) Extract and store Journal Signals (3F-2)
        #    Purpose: structured signals for planning/swaps (NOT coaching).
        #    Store in session_state so Missions page can use it immediately.
        mood_label = (
            "happy" if mood >= 8 else
            "neutral" if mood >= 5 else
            "sad"
        )

        if extract_journal_signals is not None:
            signals = extract_journal_signals(
                journal_text=text or "",
                mood_label=mood_label,
                tags=None,
                user_timezone=st.session_state.user.get("timezone"),
            )
        else:
            # Graceful fallback if journal_signals module isn't available yet
            signals = {
                "mood": "neutral",
                "energy": 3,
                "focus": 3,
                "stress": 2,
                "wins": [good_thing] if good_thing else [],
                "blockers": [],
                "needs": [],
                "intent": "Have a better day tomorrow.",
                "privacy_tags": [],
                "safety_flag": False,
                "safety_reason": "",
            }

        st.session_state["latest_journal_signals"] = signals

        # 3) Keep legacy mission generation (basic mode) for backward compatibility
        #    This ensures the app still works even if AI plan isn't generated today.
        generate_daily_missions(user_id, metrics, db)

    finally:
        db.close()

    st.success("Entry saved! ✅ Signals updated for planning.")

    # Show signals summary (small + non-judgmental)
    if st.session_state["latest_journal_signals"]:
        s = st.session_state["latest_journal_signals"]
        st.markdown("### Signals detected (for planning)")
        c1, c2, c3 = st.columns(3)
        c1.metric("Energy", s.get("energy", 3))
        c2.metric("Focus", s.get("focus", 3))
        c3.metric("Stress", s.get("stress", 2))

    st.divider()

    st.subheader("What do you want to do next?")
    st.write("You can use these signals to generate a plan or swap today’s pending missions.")

    colA, colB = st.columns(2)

    with colA:
        if st.button("Generate today’s AI plan ⚡", key="btn_journal_to_plan"):
            st.session_state["go_to_missions"] = True
            st.session_state["open_swaps_on_missions"] = False
            # Navigate to Missions page (Streamlit multipage)
            try:
                st.switch_page("pages/2_Missions.py")
            except Exception:
                st.info("Go to the Missions page to generate your AI plan.")

    with colB:
        if st.button("Suggest swaps (up to 3) 🔁", key="btn_journal_to_swaps"):
            st.session_state["go_to_missions"] = True
            st.session_state["open_swaps_on_missions"] = True
            # Navigate to Missions page (Streamlit multipage)
            try:
                st.switch_page("pages/2_Missions.py")
            except Exception:
                st.info("Go to the Missions page to suggest/apply swaps.")
