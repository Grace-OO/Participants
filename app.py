import streamlit as st
import pandas as pd
from io import StringIO
from datetime import datetime
from github import Github
import time

# --- GitHub Setup ---
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
REPO_NAME = st.secrets["GITHUB_REPO"]  # e.g., "your-username/your-repo"
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
st.title("🎟 Conference Participant Tracker")

df = load_data()

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["🚌 Bus Check-in", "🍽 Food Collection", "🔑 Overrides", "📊 Dashboard"])

# --- Helper function: participant lookup ---
def get_participant(id_code):
    return df[df["ID Code"].astype(str) == id_code]

# --- Timeout helper ---
def show_timed_message(key: str, msg: str, msg_type: str = "success", timeout: int = 3):
    """Stores message in session state with timestamp and type."""
    st.session_state[key] = {"msg": msg, "type": msg_type, "time": time.time(), "timeout": timeout}

def render_timed_message(key: str):
    """Renders the message if within timeout."""
    if key in st.session_state and st.session_state[key]:
        data = st.session_state[key]
        if time.time() - data["time"] < data["timeout"]:
            if data["type"] == "success":
                st.success(data["msg"])
            elif data["type"] == "error":
                st.error(data["msg"])
            elif data["type"] == "info":
                st.info(data["msg"])
            elif data["type"] == "warning":
                st.warning(data["msg"])
        else:
            st.session_state[key] = None  # clear after timeout


# Helper function: Check assigned day
def validate_action(participant_row, action_col):
    # Assigned days may be a list (comma-separated string)
    assigned_days = str(participant_row.get("Assigned Day", "")).split(",")
    assigned_days = [d.strip() for d in assigned_days if d.strip()]

    today_day = datetime.today().strftime("%Y-%m-%d")

    already_done = participant_row.get(action_col, "No") == "Yes"

    if assigned_days and today_day not in assigned_days and action_col != "Override":
        return "invalid_day", f"❌ Not assigned for today ({today_day})."
    elif already_done:
        return "already", f"⚠️ Already recorded for {action_col}."
    else:
        return "ok", f"✅ Allowed to proceed with {action_col}."


# --- Bus Check-in Tab ---
with tab1:
    st.header("🚌 Bus Check-in")
    id_code = st.text_input("Enter Participant ID (Bus):").strip()

    if id_code:
        participant_row = get_participant(id_code)

        if not participant_row.empty:
            participant = participant_row.iloc[0]
            participant_name = participant["Name"]

            st.success(f"👤 Found: {participant_name} (Assigned: {participant.get('Assigned Day', 'N/A')})")

            status, msg = validate_action(participant, "Bus Check-in")
            if status == "invalid_day":
                show_timed_message("bus_msg", msg, "error")   # 🔹 use timed message
            elif status == "already":
                show_timed_message("bus_msg", msg, "warning") # 🔹 use timed message
            else:
                if st.button("Check-in for Bus"):
                    df = load_data()
                    df.loc[df["ID Code"].astype(str) == id_code, "Bus Check-in"] = "Yes"
                    df.loc[df["ID Code"].astype(str) == id_code, "Bus Timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    if save_data(df, f"Bus check-in for {participant_name}"):
                        load_data.clear()
                        show_timed_message("bus_msg", f"✅ {participant_name} checked in for Bus")  # 🔹 timed

            # 🔹 Always render message (if still active)
            render_timed_message("bus_msg")

        else:
            show_timed_message("bus_msg", "❌ Participant not found.", "error")
            render_timed_message("bus_msg")

# --- Food Collection Tab ---
with tab2:
    st.header("🍽 Food Collection")
    id_code = st.text_input("Enter Participant ID (Food):").strip()

    if id_code:
        participant_row = get_participant(id_code)

        if not participant_row.empty:
            participant = participant_row.iloc[0]
            participant_name = participant["Name"]

            st.success(f"👤 Found: {participant_name} (Assigned: {participant.get('Assigned Day', 'N/A')})")

            status, msg = validate_action(participant, "Food Collection")
            if status == "invalid_day":
                show_timed_message("food_msg", msg, "error", timeout=3)
            elif status == "already":
                show_timed_message("food_msg", msg, "warning", timeout=3)
            else:
                if st.button("Collect Food"):
                    df = load_data()
                    df.loc[df["ID Code"].astype(str) == id_code, "Food Collection"] = "Yes"
                    df.loc[df["ID Code"].astype(str) == id_code, "Food Timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    if save_data(df, f"Food collection for {participant_name}"):
                        load_data.clear()
                        show_timed_message("food_msg", f"✅ {participant_name} collected Food", "success", timeout=3)

            render_timed_message("food_msg")  # 🔹 Always render message

        else:
            show_timed_message("food_msg", "❌ Participant not found.", "error", timeout=3)
            render_timed_message("food_msg")


# --- Overrides Tab ---
with tab3:
    st.header("🔑 Overrides")
    id_code = st.text_input("Enter Participant ID (Override):").strip()

    if id_code:
        participant_row = get_participant(id_code)

        if not participant_row.empty:
            participant = participant_row.iloc[0]
            participant_name = participant["Name"]

            st.success(f"👤 Found: {participant_name}")

            status, msg = validate_action(participant, "Override")
            if status == "already":
                show_timed_message("override_msg", msg, "warning", timeout=3)
            else:
                if st.button("Apply Override"):
                    df = load_data()
                    df.loc[df["ID Code"].astype(str) == id_code, "Override"] = "Yes"
                    df.loc[df["ID Code"].astype(str) == id_code, "Override Timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    if save_data(df, f"Override for {participant_name}"):
                        load_data.clear()
                        show_timed_message("override_msg", f"✅ Override applied for {participant_name}", "success", timeout=3)

            render_timed_message("override_msg")  # 🔹 Always render message

        else:
            show_timed_message("override_msg", "❌ Participant not found.", "error", timeout=3)
            render_timed_message("override_msg")

            
# --- Dashboard Tab ---
with tab4:
    st.header("📊 Dashboard")
    df_latest = load_data()
    st.dataframe(df_latest)

    # Add download button
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






