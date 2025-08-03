import streamlit as st
import pandas as pd
import pdfplumber
from datetime import datetime
from io import BytesIO
import re
import plotly.express as px
from dataclasses import dataclass
import logging
import gspread
from gspread_dataframe import set_with_dataframe

# --- Logging Configuration ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# --- App Configuration DataClass ---
@dataclass
class Config:
    SHEET_NAME = "RateConTrackerData"
    WORKSHEET_NAME = "Sheet1"
    DEFAULT_CUSTOMER = "Covenant"
    DRAYAGE_RATE = 400
    CHASSIS_RATE = 35
    MAX_FILE_SIZE = 200 * 1024 * 1024  # 200MB
    COLUMNS = [
        "Date Added",
        "Customer",
        "Reference #",
        "Equipment",
        "Container #",
        "Rate",
        "File",
        "Status",
        "Notes",
    ]


config = Config()

# --- Streamlit Page Setup ---
st.set_page_config(
    page_title="RateCon Tracker", layout="wide", initial_sidebar_state="expanded"
)

# --- Adaptive Light/Dark Mode CSS Styling ---
st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    /* --- THEME VARIABLES --- */
    :root {
        /* Light Mode (Default) */
        --app-bg: #f0f2f6;
        --app-text: #31333F;
        --card-bg: #ffffff;
        --card-border: #e6eaf1;
        --heading-text: #09090b;
        --subtle-text: #626773;
        --accent-color: #008374; /* A more standard green */
        --accent-text: #ffffff;
        --danger-color: #d94444;
        --plotly-template: 'plotly_white';
    }

    @media (prefers-color-scheme: dark) {
        :root {
            /* Dark Mode Overrides */
            --app-bg: #020617;
            --app-text: #e2e8f0;
            --card-bg: #0f172a;
            --card-border: #1e293b;
            --heading-text: #f8fafc;
            --subtle-text: #94a3b8;
            --accent-color: #00f5d4;
            --accent-text: #020617;
            --danger-color: #ef4444;
            --plotly-template: 'plotly_dark';
        }
    }

    /* --- General App Styling --- */
    .main { 
        background-color: var(--app-bg);
        color: var(--app-text);
        font-family: 'Inter', sans-serif; 
    }
    h1, h2, h3 { 
        color: var(--heading-text);
        font-weight: 600; 
    }
    
    /* --- Custom "Card" Container Styling --- */
    [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlock"] {
        background-color: var(--card-bg);
        border: 1px solid var(--card-border);
        border-radius: 12px;
        padding: 2rem;
        margin-bottom: 2rem;
    }

    /* --- Tab Navigation Styling --- */
    .stButton>button {
        background-color: transparent;
        color: var(--subtle-text);
        border: 1px solid transparent;
        border-radius: 8px;
        padding: 0.6rem 1.2rem;
        font-weight: 500;
        font-size: 1rem;
        transition: color 0.2s, background-color 0.2s;
    }
    .stButton>button:hover {
        background-color: var(--card-border);
        color: var(--heading-text);
        transform: none;
        border: 1px solid var(--card-border);
    }
    .stButton>button:disabled { 
        background-color: transparent; 
        color: #475569;
    }

    /* --- Action Button Styling --- */
    .stButton>button[type="submit"] { /* For primary buttons */
        background-color: var(--accent-color);
        color: var(--accent-text);
        font-weight: 700;
        border: none; 
    }
    .stButton>button[type="submit"]:hover { 
        filter: brightness(1.1);
        transform: scale(1.02); 
    }
    
    /* --- Metric Styling --- */
    .metric-container {
        display: flex;
        flex-direction: column;
    }
    .metric-label {
        font-size: 0.9rem;
        color: var(--subtle-text);
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 600;
        color: var(--heading-text);
    }
</style>
""",
    unsafe_allow_html=True,
)


# --- Core Data Functions ---
@st.cache_resource
def connect_to_sheet():
    try:
        creds = st.secrets["gcp_service_account"]
        gc = gspread.service_account_from_dict(creds)
        return gc.open(config.SHEET_NAME)
    except Exception as e:
        st.error(f"Failed to connect to Google Sheets. Check secrets.toml. Error: {e}")
        return None


@st.cache_data(ttl=60)
def load_log():
    try:
        spreadsheet = connect_to_sheet()
        if spreadsheet:
            worksheet = spreadsheet.worksheet(config.WORKSHEET_NAME)
            df = pd.DataFrame(worksheet.get_all_records())
            for col in config.COLUMNS:
                if col not in df.columns:
                    df[col] = pd.NA
            return df[config.COLUMNS]
        return pd.DataFrame(columns=config.COLUMNS)
    except Exception as e:
        st.error(f"Error loading data from Google Sheet: {e}")
        return pd.DataFrame(columns=config.COLUMNS)


def update_sheet(df):
    try:
        spreadsheet = connect_to_sheet()
        if spreadsheet:
            worksheet = spreadsheet.worksheet(config.WORKSHEET_NAME)
            worksheet.clear()
            set_with_dataframe(worksheet, df)
            logger.info("Google Sheet updated.")
            st.cache_data.clear()
    except Exception as e:
        st.error(f"Failed to update Google Sheet: {e}")


def append_to_sheet(new_records_df):
    try:
        spreadsheet = connect_to_sheet()
        if spreadsheet:
            worksheet = spreadsheet.worksheet(config.WORKSHEET_NAME)
            worksheet.append_rows(
                new_records_df.values.tolist(), value_input_option="USER_ENTERED"
            )
            logger.info(f"Appended {len(new_records_df)} records.")
            st.cache_data.clear()
    except Exception as e:
        st.error(f"Failed to append to Google Sheet: {e}")


# --- Helper Functions ---
def extract_data_from_pdf(pdf_bytes):
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            text = "\n".join(
                p.extract_text() for p in pdf.pages if p.extract_text() or ""
            )
        ref_patterns, rate_patterns, equip_patterns, container_patterns = (
            [
                r"Route #\s*(\S+)",
                r"Reference #\s*(\S+)",
                r"Pro #\s*(\S+)",
                r"Load #\s*(\S+)",
                r"Job #\s*(\S+)",
            ],
            [
                r"Total Rate:\s*\$?([\d,]+\.?\d{0,2})",
                r"Total Cost\s*\$?([\d,]+\.?\d{0,2})",
                r"Amount:\s*\$?([\d,]+\.?\d{0,2})",
                r"Rate:\s*\$?([\d,]+\.?\d{0,2})",
            ],
            [
                r"Equipment:\s*([^\n]+)",
                r"Trailer Type:\s*([^\n]+)",
                r"Equipment Type:\s*([^\n]+)",
            ],
            [
                r"Container #:\s*(\S+)",
                r"Container Number:\s*(\S+)",
                r"Container ID:\s*(\S+)",
            ],
        )

        def find_match(patterns, text):
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    return match.group(1).strip()
            return None

        ref, rate, equip, container = (
            find_match(ref_patterns, text),
            find_match(rate_patterns, text),
            find_match(equip_patterns, text),
            find_match(container_patterns, text),
        )
        return (
            ref if ref else "Unknown",
            rate.replace(",", "") if rate else "0.00",
            equip if equip else "None",
            container if container else "",
        )
    except Exception as e:
        logger.error(f"PDF extraction error: {e}")
        return "Unknown", "0.00", "None", ""


@st.cache_data
def process_dataframe(df):
    if df.empty:
        return df
    df_proc = df.copy()
    df_proc["Parsed Rate"] = pd.to_numeric(
        df_proc["Rate"].astype(str).str.replace("[$,]", "", regex=True), errors="coerce"
    ).fillna(0)
    df_proc["Chassis Count"] = (
        (df_proc["Parsed Rate"] - config.DRAYAGE_RATE) / config.CHASSIS_RATE
    ).apply(lambda x: max(round(x), 0))
    df_proc["Expected Rate"] = (
        config.DRAYAGE_RATE + df_proc["Chassis Count"] * config.CHASSIS_RATE
    )
    df_proc["Mismatch"] = df_proc["Parsed Rate"] != df_proc["Expected Rate"]
    return df_proc


@st.cache_data
def convert_df_to_csv(df):
    return df.to_csv(index=False).encode("utf-8")


@st.cache_data
def convert_df_to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="RateCons")
    return output.getvalue()


# --- UI Rendering Functions ---
def render_metrics(df):
    if df.empty:
        st.info("No data available to display metrics.")
        return
    df_proc = process_dataframe(df)
    total_loads, total_revenue = len(df_proc), df_proc["Parsed Rate"].sum()
    avg_rate_per_load = total_revenue / total_loads if total_loads > 0 else 0
    drayage_revenue, chassis_revenue = (
        total_loads * config.DRAYAGE_RATE,
        df_proc["Chassis Count"].sum() * config.CHASSIS_RATE,
    )
    mismatched_revenue, total_chassis_units, mismatched_count = (
        df_proc[df_proc["Mismatch"]]["Parsed Rate"].sum(),
        df_proc["Chassis Count"].sum(),
        df_proc["Mismatch"].sum(),
    )
    avg_chassis_per_load = total_chassis_units / total_loads if total_loads > 0 else 0

    def metric_display(label, value, help_text=None):
        st.markdown(
            f'<div class="metric-container"><div class="metric-label">{label} {f"<span title={repr(help_text)}>ⓘ</span>" if help_text else ""}</div><div class="metric-value">{value}</div></div>',
            unsafe_allow_html=True,
        )

    st.subheader("Key Performance Indicators")
    cols1 = st.columns(3)
    with cols1[0]:
        metric_display("Total Loads", f"{total_loads:,}")
    with cols1[1]:
        metric_display("Total Revenue", f"${total_revenue:,.2f}")
    with cols1[2]:
        metric_display("Average Rate / Load", f"${avg_rate_per_load:,.2f}")
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("Revenue Breakdown")
    cols2 = st.columns(3)
    with cols2[0]:
        metric_display("Total Drayage Revenue", f"${drayage_revenue:,.2f}")
    with cols2[1]:
        metric_display("Total Chassis Revenue", f"${chassis_revenue:,.2f}")
    with cols2[2]:
        metric_display(
            "Non-Standard Revenue",
            f"${mismatched_revenue:,.2f}",
            "Revenue from loads where rate != Drayage + Chassis model.",
        )

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("Operational & Quality Statistics")
    cols3 = st.columns(3)
    with cols3[0]:
        metric_display("Total Chassis Units Billed", f"{total_chassis_units:,}")
    with cols3[1]:
        metric_display("Avg. Chassis Days / Load", f"{avg_chassis_per_load:.1f}")
    with cols3[2]:
        metric_display(
            "Mismatched Rates",
            mismatched_count,
            "Count of loads needing review due to non-standard rates.",
        )


def render_charts(df):
    if df.empty:
        return
    df_proc = process_dataframe(df)
    
    # Get the current theme for plotly
    plotly_template = "plotly_dark" if "dark" in st.get_option("theme.base") else "plotly_white"
    accent_color = "#00f5d4" if "dark" in st.get_option("theme.base") else "#008374"

    col1, col2 = st.columns(2)
    with col1:
        chassis_dist = df_proc["Chassis Count"].value_counts().sort_index()
        if not chassis_dist.empty:
            fig = px.bar(
                chassis_dist,
                title="Loads by Chassis Count",
                labels={"index": "Chassis Count", "value": "Number of Loads"},
                color_discrete_sequence=[accent_color],
                template=plotly_template,
            )
            st.plotly_chart(fig, use_container_width=True)
    with col2:
        equip_dist = df_proc["Equipment"].value_counts().nlargest(10)
        if not equip_dist.empty:
            fig = px.bar(
                equip_dist,
                title="Top 10 Loads by Equipment Type",
                labels={"index": "Equipment Type", "value": "Number of Loads"},
                color_discrete_sequence=[accent_color],
                template=plotly_template,
            )
            st.plotly_chart(fig, use_container_width=True)


def render_data_table(df):
    if df.empty:
        return
    df_proc = process_dataframe(df)
    display_cols = [
        "Date Added",
        "Customer",
        "Reference #",
        "Equipment",
        "Container #",
        "Rate",
        "Chassis Count",
        "Status",
        "Notes",
    ]
    st.dataframe(
        df_proc[display_cols].style.apply(
            lambda row: (
                ["background-color: #450a0a"] * len(row)
                if row.get("Mismatch")
                else [""] * len(row)
            ),
            axis=1,
        ),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Rate": st.column_config.NumberColumn(format="$%.2f"),
            "Date Added": st.column_config.DateColumn("Date"),
        },
    )


# --- Callback Functions ---
def run_file_processing(uploaded_files):
    if not uploaded_files:
        st.warning("Please upload files before processing.")
        return
        
    existing_df = load_log()
    new_records, skipped_files = [], []
    existing_refs, existing_files = (
        set(existing_df["Reference #"].astype(str)),
        set(existing_df["File"].astype(str)),
    ) if not existing_df.empty else (set(), set())

    progress_bar_placeholder = st.empty()
    progress_bar = progress_bar_placeholder.progress(0, text="Initializing...")
    
    for i, file in enumerate(uploaded_files):
        progress_bar.progress(
            (i + 1) / len(uploaded_files), text=f"Processing: {file.name}"
        )
        if file.name in existing_files:
            skipped_files.append({"file": file.name, "reason": "Duplicate filename."})
            continue
        ref, rate, equip, container = extract_data_from_pdf(file.getvalue())
        if ref == "Unknown":
            skipped_files.append({"file": file.name, "reason": "Unsupported Format."})
            continue
        if ref in existing_refs:
            skipped_files.append(
                {"file": file.name, "reason": f"Duplicate Reference # {ref}"}
            )
            continue
        new_records.append(
            {
                "Date Added": datetime.now().strftime("%Y-%m-%d"),
                "Customer": config.DEFAULT_CUSTOMER,
                "Reference #": ref,
                "Equipment": equip,
                "Container #": container,
                "Rate": rate,
                "File": file.name,
                "Status": "Active",
                "Notes": "",
            }
        )
        existing_refs.add(ref)
    
    progress_bar_placeholder.empty()
    st.session_state.processed_records = new_records
    st.session_state.skipped_files = skipped_files
    st.session_state.processing_complete = True
    st.session_state.needs_rerun = True


def run_save_records():
    new_records = st.session_state.get("processed_records", [])
    if new_records:
        append_to_sheet(pd.DataFrame(new_records))
        st.toast(f"✅ Success! Added {len(new_records)} new records to the log.", icon="🎉")
        
        st.session_state.processing_complete = False
        st.sess
