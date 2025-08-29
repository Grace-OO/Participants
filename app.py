import streamlit as st
import pandas as pd
from io import StringIO
from github import Github
import base64
import requests
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
    url = f"https://api.github.com/repos/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    content = r.json()
    csv_content = base64.b64decode(content["content"]).decode("utf-8")
    return pd.read_csv(StringIO(csv_content))

# --- Helper: save CSV to GitHub with retry ---
def save_data(df, commit_msg="Update check-in"):
    new_csv = df.to_csv(index=False)
    url = f"https://api.github.com/repos/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}

    retries = 4
    for attempt in range(retries):
        try:
            # Get file SHA (needed for update)
            r = requests.get(url, headers=headers)
            r.raise_for_status()
            sha = r.json()["sha"]

            update_data = {
                "message": commit_msg,
                "content": base64.b64encode(new_csv.encode()).decode(),
                "sha": sha,
                "branch": "main"  # change if your default branch is not main
            }

            r = requests.put(url, headers=headers, json=update_data)

            if r.status_code in (200, 201):
                return True
            else:
                raise Exception(r.json())

        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1.5)  # wait before retry
            else:
                st.error(f"❌ Failed to save after {retries} attempts: {e}")
                return False

# --- Streamlit UI ---
st.header("🎟 Conference Participants Tracker")

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
        

# --- Get participant by ID ---
def get_participant(id_code):
    df_latest = load_data()
    return df_latest[
        df_latest["ID Code"].astype(str).str.strip().str.lower()
        == str(id_code).strip().lower()
    ]


# Define timezone
LOCAL_TZ = timezone(timedelta(hours=1))

def handle_action(tab, header, activity, button_label, df_field, timestamp_field):
    with tab:

        # Keep a session key for the input
        if f"{activity}_id" not in st.session_state:
            st.session_state[f"{activity}_id"] = ""

        id_code = st.text_input(
            f"Enter Participant ID ({activity}):",
            value=st.session_state[f"{activity}_id"],   # shadow state drives the widget
            key=f"{activity}_input",
            placeholder="Type ID...",
            label_visibility="visible"
        ).strip().lower()
        
        st.session_state[f"{activity}_id"] = id_code.strip() 

        submit = st.button("Enter", key=f"{activity}_submit")

        st.subheader(header)

        # --- Allow either keyboard enter (id_code filled) OR button press ---
        if not id_code:  
            return
        if not submit and not st.session_state[f"{activity}_id"]:  
            return

        # Works with keyboard Enter OR button click
        participant_row = get_participant(id_code)
        if participant_row.empty:
            toast_key = f"{activity}_{id_code}_notfound"
            auto_dismiss_message(toast_key, "Participant not found.", "error")
            return

        participant = participant_row.iloc[0]
        participant_name = participant["Name"]
        toast_key = f"{activity}_{id_code}"
        

        # Validate
        if participant[df_field] == "Yes":
            auto_dismiss_message(
            toast_key + "_warn",
            f"{participant_name} has already been recorded for {activity}.",
            "warning"
            )
            else:
    # Auto-log immediately with correct timezone
            df = load_data()
            mask = df["ID Code"].astype(str).str.strip().str.lower() == id_code.strip().lower()
            df.loc[mask, df_field] = "Yes"
            df.loc[mask, timestamp_field] = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S")
            if save_data(df, f"{activity} for {participant_name}"):
                load_data.clear()
                auto_dismiss_message(
                toast_key + "_success",
                f"✅ {participant_name}'s {button_label} has been recorded.",
                "success"
                )
                st.session_state[f"{activity}_id"] = ""   

        
        
# --- Mimic tabs using radio buttons ---
tabs = ["🚌 Bus Check-in", "📋 Conference Check-in", "🍽 Food Collection", "🚍 Return Trip", "📊 Dashboard"]

if "active_tab" not in st.session_state or st.session_state.active_tab not in tabs:
    st.session_state.active_tab = tabs[0]
    
# Radio buttons control session state automatically 
selected_tab = st.radio(
    "Select Section",
    options=tabs,
    key="active_tab",
    horizontal=True
)

# --- Always have the latest data available ---
df_latest = load_data()

# --- Display content based on selected tab ---
if selected_tab == "📋 Conference Check-in":
    handle_action(st.container(), "Conference Check-in", "Conference Check-in", "Check-in", "Conference Check-in", "Conference Timestamp")
elif selected_tab == "🚌 Bus Check-in":
    handle_action(st.container(), "Bus Check-in", "Bus Check-in", "Check-in", "Bus Check-in", "Bus Timestamp")
elif selected_tab == "🍽 Food Collection":
    handle_action(st.container(), "Food Collection", "Food Collection", "Collect Food", "Food Collection", "Food Timestamp")
elif selected_tab == "🚍 Return Trip":
    handle_action(st.container(), "Return Trip", "Return Trip", "Check-in", "Return Trip", "Return Timestamp")
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
conference_count = (df_latest.get("Conference Check-in", pd.Series(dtype=str)) == "Yes").sum()
food_count = (df_latest.get("Food Collection", pd.Series(dtype=str)) == "Yes").sum()
return_count = (df_latest.get("Return Trip", pd.Series(dtype=str)) == "Yes").sum()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Bus Check-ins", int(bus_count))
col2.metric("Conference Check-ins", int(conference_count))
col3.metric("Food Collections", int(food_count))
col4.metric("Return Trip", int(return_count))
