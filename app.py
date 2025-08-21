import streamlit as st
import pandas as pd
from io import StringIO
from datetime import datetime
from github import Github
import time
from datetime import datetime

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
st.title("🎟 Conference Participants Tracker")

df = load_data()

# --- Helper: get participant by ID ---
def get_participant(id_code):
    df_latest = load_data()  # always use the latest data
    return df_latest[df_latest["ID Code"].astype(str) == str(id_code)]


# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["🚌 Bus Check-in", "🍽 Food Collection", "🔑 Overrides", "📊 Dashboard"])

# Helper function: Check assigned day
def validate_action(participant_row, action_col):
    # Map each action to the relevant assigned columns
    action_to_columns = {
        'Bus Check-in': ['Assigned Day', 'Bus Check-in'],
        'Food Collection': ['Assigned Day', 'Food Collection'],
        'Override': ['Override'],
    }
    
    # Get the relevant columns for the action
    relevant_columns = action_to_columns.get(action_col, ['Assigned Day'])
    
    # Combine all relevant assigned dates into a single list, ignoring empty values
    assigned_days = []
    for col in relevant_columns:
        val = participant_row.get(col, "")
        if pd.notna(val) and val != "":
            # Handle comma-separated values in any cell
            assigned_days.extend([d.strip() for d in str(val).split(" ") if d.strip()])
    
    # Today's date
    today_day = datetime.today().strftime("%Y-%m-%d")
    
    # Check if action is already done
    already_done = participant_row.get(action_col, "No") == "Yes"
    
    # Validation logic
    if assigned_days and today_day not in assigned_days and action_col != "Override":
        return "invalid_day", f"❌ Not assigned for today ({today_day})."
    elif already_done:
        return "already", f"⚠️ Already recorded for {action_col}."
    else:
        return "ok", f"✅ Allowed to proceed with {action_col}."

# Persistent tab state
if "current_tab" not in st.session_state:
    st.session_state.current_tab = "Bus Check-in"

tabs = ["Bus Check-in", "Food Collection", "Overrides"]
selected_tab = st.radio("Select tab", tabs, index=tabs.index(st.session_state.current_tab))
st.session_state.current_tab = selected_tab

# Example participant row
participant_row = {"Assigned Day": "2025-08-21 2025-08-22", "Food Collection": "No"}

# Tab content
if selected_tab == "Food Collection":
    if st.button("Validate Food Collection"):
        status, msg = validate_action(participant_row, "Food Collection")
        st.success(msg)  # or st.warning/st.error depending on status

# --- Toast helper ---
def auto_dismiss_message_once(key, message, msg_type="success"):
    if key not in st.session_state:
        st.session_state[key] = True  # mark as shown
        if msg_type == "success":
            st.toast(f"{message}", icon="✅")
        elif msg_type == "error":
            st.toast(f"{message}", icon="❌")
        elif msg_type == "warning":
            st.toast(f"{message}", icon="⚠️")
        elif msg_type == "info":
            st.toast(f"{message}", icon="ℹ️")

# --- Action Handler Helper ---
def handle_action(tab, header, activity, button_label, field_name, df_field, timestamp_field):
    with tab:
        st.header(header)
        id_code = st.text_input(f"Enter Participant ID({activity}):").strip()

        if id_code:
            participant_row = get_participant(id_code)

            if not participant_row.empty:
                participant = participant_row.iloc[0]
                participant_name = participant["Name"]

                # Unique key per participant/action for session_state
                toast_key = f"{activity}_{id_code}"

                # Info toast (found participant)
                if toast_key + "_info" not in st.session_state:
                    st.session_state[toast_key + "_info"] = True
                    auto_dismiss_message(
                        f"👤 Found: {participant_name} (Assigned: {participant.get('Assigned Day', 'N/A')})",
                        "info"
                    )

                # Validate action
                status, msg = validate_action(participant, activity)
                if status == "invalid_day":
                    if toast_key + "_error" not in st.session_state:
                        st.session_state[toast_key + "_error"] = True
                        auto_dismiss_message(f"You are not assigned for today ({datetime.today().strftime('%Y-%m-%d')}).", "error")
                elif status == "already":
                    if toast_key + "_warn" not in st.session_state:
                        st.session_state[toast_key + "_warn"] = True
                        auto_dismiss_message(f"This action has already been recorded for {activity}.", "warning")

                else:
                    # Button for valid action
                    if st.button(button_label):
                        df = load_data()
                        df.loc[df["ID Code"].astype(str) == id_code, df_field] = "Yes"
                        df.loc[df["ID Code"].astype(str) == id_code, timestamp_field] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        if save_data(df, f"{activity} for {participant_name}"):
                            load_data.clear()
                            if toast_key + "_success" not in st.session_state:
                                st.session_state[toast_key + "_success"] = True
                                auto_dismiss_message(f"{participant_name}'s {button_label} has been successfully recorded.", "success")

            else:
                # Participant not found
                toast_key = f"{activity}_{id_code}_notfound"
                if toast_key not in st.session_state:
                    st.session_state[toast_key] = True
                    auto_dismiss_message("Participant not found.", "error")


# --- Bus Check-in Tab ---
handle_action(
    tab1, "🚌 Bus Check-in", "Bus Check-in",
    "Check-in for Bus", "Bus Check-in", "Bus Check-in", "Bus Timestamp"
)

# --- Food Collection Tab ---
handle_action(
    tab2, "🍽 Food Collection", "Food Collection",
    "Collect Food", "Food Collection", "Food Collection", "Food Timestamp"
)

# --- Overrides Tab ---
handle_action(
    tab3, "🔑 Overrides", "Override",
    "Apply Override", "Override", "Override", "Override Timestamp"
)

            
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





