import streamlit as st
import pandas as pd
from io import StringIO
from datetime import datetime
from github import Github
import time
from datetime import datetime, timezone, timedelta


# --- GitHub Setup ---
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
REPO_NAME = st.secrets["GITHUB_REPO"]  
FILE_PATH = "test_run.csv"

g = Github(GITHUB_TOKEN)
repo = g.get_repo(REPO_NAME)

# --- Helper: load CSV from GitHub ---
@st.cache_data(ttl=5)
def load_data():
    file_content = repo.get_contents(FILE_PATH)
    return pd.read_csv(StringIO(file_content.decoded_content.decode()))

# --- Helper: save CSV to GitHub with retry ---
def save_data(df, commit_msg="Update check-in"):
    csv_data = df.to_csv(index=False)
    retries = 3
    for attempt in range(retries):
        try:
            file_content = repo.get_contents(FILE_PATH)  # get fresh SHA
            repo.update_file(FILE_PATH, commit_msg, csv_data, file_content.sha)
            return True
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1.5)  # wait before retry
            else:
                st.error(f"❌ Failed to save after {retries} attempts: {e}")
                return False

# --- Streamlit UI ---
st.title("🎟 Conference Participants Tracker")

df = load_data()

# --- Toast helper (fires only once per key) ---
def auto_dismiss_message(key, message, msg_type="success"):
    if key not in st.session_state:
        st.session_state[key] = True
        if msg_type == "success":
            st.toast(f"{message}", icon="✅")
        elif msg_type == "error":
            st.toast(f"{message}", icon="❌")
        elif msg_type == "warning":
            st.toast(f"{message}", icon="⚠️")
        elif msg_type == "info":
            st.toast(f"{message}", icon="ℹ️")

# --- Get participant by ID ---
def get_participant(id_code):
    df_latest = load_data()
    return df_latest[df_latest["ID Code"].astype(str) == str(id_code)]

# --- Validation function ---
def validate_action(participant_row, action_col):
    action_to_columns = {
        'Bus Check-in': ['Assigned Day', 'Bus Check-in'],
        'Food Collection': ['Assigned Day', 'Food Collection'],
        'Override': ['Override'],
    }
    relevant_columns = action_to_columns.get(action_col, ['Assigned Day'])

    assigned_days = []
    for col in relevant_columns:
        val = participant_row.get(col, "")
        if pd.notna(val) and val != "":
            assigned_days.extend([d.strip() for d in str(val).split(" ") if d.strip()])

    today_day = datetime.today().strftime("%Y-%m-%d")
    already_done = participant_row.get(action_col, "No") == "Yes"

    if assigned_days and today_day not in assigned_days and action_col != "Override":
        return "invalid_day", f"You are not assigned for today ({today_day})."
    elif already_done:
        return "already", f"This action has already been recorded for {action_col}."
    else:
        return "ok", f"You may proceed with {action_col}."

# --- Action handler
# Define timezone
LOCAL_TZ = timezone(timedelta(hours=1))

def handle_action(tab, header, activity, button_label, df_field, timestamp_field):
    with tab:

        # Keep a session key for the input
        if f"{activity}_id" not in st.session_state:
            st.session_state[f"{activity}_id"] = ""

        id_code = st.text_input(
            f"Enter Participant ID ({activity}):",
            value=st.session_state[f"{activity}_id"],   # ✅ shadow state drives the widget
            key=f"{activity}_input",
            placeholder="Type ID...",
            label_visibility="visible"
        )
        st.session_state[f"{activity}_id"] = id_code.strip() 

        submit = st.button("Enter", key=f"{activity}_submit")

        st.header(header)

        # --- Allow either keyboard enter (id_code filled) OR button press ---
        if not id_code:  
            return
        if not submit and not st.session_state[f"{activity}_id"]:  
            return

        # ✅ At this point, works with keyboard Enter OR button click
        participant_row = get_participant(id_code)
        if participant_row.empty:
            toast_key = f"{activity}_{id_code}_notfound"
            auto_dismiss_message(toast_key, "Participant not found.", "error")
            return

        participant = participant_row.iloc[0]
        participant_name = participant["Name"]
        toast_key = f"{activity}_{id_code}"
        
        
        # Info toast
        auto_dismiss_message(
            toast_key + "_info",
            f"👤 Participant found: {participant_name} (Assigned: {participant.get('Assigned Day', 'N/A')})",
            "info"
        )

        # Validate
        status, msg = validate_action(participant, activity)
        if status == "invalid_day":
            auto_dismiss_message(toast_key + "_error", msg, "error")
        elif status == "already":
            auto_dismiss_message(toast_key + "_warn", msg, "warning")
        else:
            # ✅ Auto-log immediately with correct timezone
            df = load_data()
            df.loc[df["ID Code"].astype(str) == id_code, df_field] = "Yes"
            df.loc[df["ID Code"].astype(str) == id_code, timestamp_field] = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S")
            if save_data(df, f"{activity} for {participant_name}"):
                load_data.clear()
                auto_dismiss_message(
                    toast_key + "_success",
                    f"✅ {participant_name}'s {button_label} has been automatically recorded.",
                    "success"
                )
                st.session_state[f"{activity}_id"] = ""   #  only reset shadow state
               
    st.header(header)
# --- Mimic tabs using radio buttons ---
tabs = ["🚌 Bus Check-in", "🍽 Food Collection", "🔑 Overrides", "📊 Dashboard"]

# Initialize active tab safely
if "active_tab" not in st.session_state or st.session_state.active_tab not in tabs:
    st.session_state.active_tab = tabs[0]  # default to first tab
    
# Radio buttons control session state automatically
selected_tab = st.radio(
    "Select Section",
    options=tabs,
    key="active_tab",  # <--- this automatically syncs with st.session_state
    horizontal=True
)

# --- Display content based on selected tab ---
if selected_tab == "🚌 Bus Check-in":
    handle_action(st.container(), "Bus Check-in", "Bus Check-in", "Check-in", "Bus Check-in", "Bus Timestamp")
elif selected_tab == "🍽 Food Collection":
    handle_action(st.container(), "Food Collection", "Food Collection", "Collect Food", "Food Collection", "Food Timestamp")
elif selected_tab == "🔑 Overrides":
    handle_action(st.container(), "Overrides", "Override", "Apply Override", "Override", "Override Timestamp")
elif selected_tab == "📊 Dashboard":
    st.header("📊 Dashboard")
    df_latest = load_data()
    st.dataframe(df_latest)

    # Download button
    csv_data = df_latest.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Download CSV",
        data=csv_data,
        file_name="conference_checkins.csv",
        mime="text/csv",
    )

    # Metrics
    bus_count = (df_latest.get("Bus Check-in", pd.Series(dtype=str)) == "Yes").sum()
    food_count = (df_latest.get("Food Collection", pd.Series(dtype=str)) == "Yes").sum()
    override_count = (df_latest.get("Override", pd.Series(dtype=str)) == "Yes").sum()

    col1, col2, col3 = st.columns(3)
    col1.metric("Bus Check-ins", int(bus_count))
    col2.metric("Food Collections", int(food_count))
    col3.metric("Overrides", int(override_count))








