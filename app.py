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

# --- Bus Check-in Tab ---
with tab1:
    st.header("🚌 Bus Check-in")
    id_code = st.text_input("Enter Participant ID (Bus):").strip()
    if id_code:
        participant_row = get_participant(id_code)
        if not participant_row.empty:
            participant_name = participant_row.iloc[0]["Name"]
            st.success(f"👤 Found: {participant_name}")
            if st.button("Check-in for Bus"):
                df = load_data()
                df.loc[df["ID Code"].astype(str) == id_code, "Bus Check-in"] = "Yes"
                df.loc[df["ID Code"].astype(str) == id_code, "Bus Timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if save_data(df, f"Bus check-in for {participant_name}"):
                    load_data.clear()
                    st.success(f"✅ {participant_name} checked in for Bus")
        else:
            st.error("❌ Participant not found.")

# --- Food Collection Tab ---
with tab2:
    st.header("🍽 Food Collection")
    id_code = st.text_input("Enter Participant ID (Food):").strip()
    if id_code:
        participant_row = get_participant(id_code)
        if not participant_row.empty:
            participant_name = participant_row.iloc[0]["Name"]
            st.success(f"👤 Found: {participant_name}")
            if st.button("Collect Food"):
                df = load_data()
                df.loc[df["ID Code"].astype(str) == id_code, "Food Collection"] = "Yes"
                df.loc[df["ID Code"].astype(str) == id_code, "Food Timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if save_data(df, f"Food collection for {participant_name}"):
                    load_data.clear()
                    st.success(f"✅ {participant_name} collected Food")
        else:
            st.error("❌ Participant not found.")

# --- Overrides Tab ---
with tab3:
    st.header("🔑 Overrides")
    id_code = st.text_input("Enter Participant ID (Override):").strip()
    if id_code:
        participant_row = get_participant(id_code)
        if not participant_row.empty:
            participant_name = participant_row.iloc[0]["Name"]
            st.success(f"👤 Found: {participant_name}")
            if st.button("Apply Override"):
                df = load_data()
                df.loc[df["ID Code"].astype(str) == id_code, "Override"] = "Yes"
                df.loc[df["ID Code"].astype(str) == id_code, "Override Timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if save_data(df, f"Override for {participant_name}"):
                    load_data.clear()
                    st.success(f"✅ Override applied for {participant_name}")
        else:
            st.error("❌ Participant not found.")

# --- Dashboard Tab ---
with tab4:
    st.header("📊 Dashboard")
    st.dataframe(load_data())

    bus_count = (df.get("Bus Check-in", pd.Series(dtype=str)) == "Yes").sum()
    food_count = (df.get("Food Collection", pd.Series(dtype=str)) == "Yes").sum()
    override_count = (df.get("Override", pd.Series(dtype=str)) == "Yes").sum()

    col1, col2, col3 = st.columns(3)
    col1.metric("Bus Check-ins", int(bus_count))
    col2.metric("Food Collections", int(food_count))
    col3.metric("Overrides", int(override_count))



