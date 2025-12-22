import streamlit as st
from soulsync.config import get_diagnostics
from soulsync.ui.theme import load_css

load_css()
st.title("Settings ⚙️")

st.subheader("Diagnostics")
diag = get_diagnostics()
st.json(diag)

if st.button("Logout"):
    del st.session_state.user
    st.rerun()
