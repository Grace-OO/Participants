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
st.title("🎟 Conference Check-in System (ID Based)")

df = load_data()

# Participant lookup by ID
id_code = st.text_input("Enter Participant ID Code:").strip()

if id_code:
    participant_row = df[df["ID Code"].astype(str) == id_code]

    if not participant_row.empty:
        participant_name = participant_row.iloc[0]["Name"]
        st.success(f"👤 Participant Found: {participant_name}")

        # Prevent rapid double-clicks
        if "busy" not in st.session_state:
            st.session_state.busy = False

        col1, col2, col3 = st.columns(3)
        disable_actions = st.session_state.busy

        # --- Bus Check-in ---
        if col1.button("🚌 Bus Check-in", disabled=disable_actions):
            st.session_state.busy = True
            df = load_data()
            df.loc[df["ID Code"].astype(str) == id_code, "Bus Check-in"] = "Yes"
            df.loc[df["ID Code"].astype(str) == id_code, "Bus Timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if save_data(df, f"Bus check-in for {participant_name}"):
                load_data.clear()
                st.success(f"✅ {participant_name} checked in for Bus")
            st.session_state.busy = False

        # --- Food Check-in ---
        if col2.button("🍽 Food Collection", disabled=disable_actions):
            st.session_state.busy = True
            df = load_data()
            df.loc[df["ID Code"].astype(str) == id_code, "Food Collection"] = "Yes"
            df.loc[df["ID Code"].astype(str) == id_code, "Food Timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if save_data(df, f"Food collection for {participant_name}"):
                load_data.clear()
                st.success(f"✅ {participant_name} has collected Food")
            st.session_state.busy = False

        # --- Override ---
        if col3.button("🔑 Override", disabled=disable_actions):
            st.session_state.busy = True
            df = load_data()
            df.loc[df["ID Code"].astype(str) == id_code, "Override"] = "Yes"
            df.loc[df["ID Code"].astype(str) == id_code, "Override Timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if save_data(df, f"Override for {participant_name}"):
                load_data.clear()
                st.success(f"✅ Override applied for {participant_name}")
            st.session_state.busy = False
    else:
        st.error("❌ No participant found with that ID code.")

# --- Dashboard ---
st.subheader("📊 Check-in Dashboard")
st.dataframe(load_data())

bus_count = (df.get("Bus Check-in") == "Yes").sum()
food_count = (df.get("Food Check-in") == "Yes").sum()
st.metric("Bus Check-ins", int(bus_count))
st.metric("Food Check-ins", int(food_count))
