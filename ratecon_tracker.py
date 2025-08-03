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

# --- Streamlit Page Setup and Custom Styling ---
st.set_page_config(
    page_title="RateCon Tracker", layout="wide", initial_sidebar_state="expanded"
)

# --- AGGRESSIVE RESTYLE "CYBERSPACE GREEN" THEME ---
st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    /* --- Main Colors & Fonts --- */
    .main { 
        background-color: #020617; /* slate-950 */
        color: #e2e8f0; /* slate-200 */
        font-family: 'Inter', sans-serif; 
    }
    h1 { 
        color: #f8fafc; /* slate-50 */
        font-weight: 700; 
    }
    h2, h3 { 
        color: #f8fafc; /* slate-50 */
        font-weight: 600; 
    }
    
    /* --- Custom "Card" Container Styling --- */
    [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlock"] {
        background-color: #0f172a; /* slate-900 */
        border: 1px solid #1e293b; /* slate-800 */
        border-radius: 12px;
        padding: 2rem;
        margin-bottom: 2rem;
    }

    /* --- Custom Tab Navigation Styling --- */
    .stButton>button {
        background-color: transparent;
        color: #94a3b8; /* slate-400 */
        border: 1px solid transparent;
        border-radius: 8px;
        padding: 0.6rem 1.2rem;
        font-weight: 500;
        font-size: 1rem;
        transition: color 0.2s, background-color 0.2s;
    }
    .stButton>button:hover {
        background-color: #1e293b; /* slate-800 */
        color: #f8fafc; /* slate-50 */
        transform: none;
        border: 1px solid #334155;
    }
    .stButton>button:disabled { 
        background-color: transparent; 
        color: #475569; /* slate-600 */
    }

    /* --- Action Button Styling --- */
    .stButton>button.primary_action { 
        background-color: #00f5d4; /* Vibrant Green */
        color: #020617; /* Dark text for contrast */
        font-weight: 700;
        border: none; 
    }
    .stButton>button.primary_action:hover { 
        background-color: #00d9bc; 
        transform: scale(1.02); 
    }
    .stButton>button.danger_action { 
        background-color: #ef4444; /* red-500 */
        color: #f8fafc; 
        border: none; 
    }
    .stButton>button.danger_action:hover { 
        background-color: #dc2626; /* red-600 */
        transform: scale(1.02); 
    }
    
    /* --- Custom Metric Styling (inside cards) --- */
    .metric-container {
        display: flex;
        flex-direction: column;
    }
    .metric-label {
        font-size: 0.9rem;
        color: #94a3b8; /* slate-400 */
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 600;
        color: #f8fafc; /* slate-50 */
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
    df_proc, accent_color = process_dataframe(df), "#00f5d4"
    col1, col2 = st.columns(2)
    with col1:
        chassis_dist = df_proc["Chassis Count"].value_counts().sort_index()
        if not chassis_dist.empty:
            fig = px.bar(
                chassis_dist,
                title="Loads by Chassis Count",
                labels={"index": "Chassis Count", "value": "Number of Loads"},
                color_discrete_sequence=[accent_color],
                template="plotly_dark",
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
                template="plotly_dark",
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


def run_save_records():
    new_records = st.session_state.get("processed_records", [])
    if new_records:
        append_to_sheet(pd.DataFrame(new_records))
        st.toast(f"✅ Success! Added {len(new_records)} new records to the log.", icon="🎉")
        
        # Reset state after saving
        st.session_state.processing_complete = False
        st.session_state.processed_records = []
        st.session_state.skipped_files = []
        # This key change forces the file_uploader to reset
        st.session_state.uploader_key += 1
        st.rerun()


def run_delete_selected(refs_to_delete):
    if refs_to_delete:
        update_sheet(load_log()[~load_log()["Reference #"].isin(refs_to_delete)])
        st.toast(f"Deleted {len(refs_to_delete)} records.", icon="🗑️")
        st.rerun()


def run_delete_all():
    update_sheet(pd.DataFrame(columns=config.COLUMNS))
    st.toast("All records have been deleted.", icon="🚨")
    st.session_state.show_delete_all_confirm = False
    st.rerun()


def set_active_tab(tab_id):
    st.query_params["tab"] = tab_id


# --- Main Application Logic ---
def main():
    st.title("RateCon Tracker")

    # Initialize session state variables
    if "processing_complete" not in st.session_state:
        st.session_state.processing_complete = False
    if "processed_records" not in st.session_state:
        st.session_state.processed_records = []
    if "skipped_files" not in st.session_state:
        st.session_state.skipped_files = []
    if "show_delete_all_confirm" not in st.session_state:
        st.session_state.show_delete_all_confirm = False
    if "uploader_key" not in st.session_state:
        st.session_state.uploader_key = 0

    # Set active tab from URL query params
    active_tab = st.query_params.get("tab", "upload")

    # --- Tab Navigation ---
    tabs = {
        "upload": "📁 Upload",
        "dashboard": "📊 Dashboard",
        "manage": "⚙️ Manage Data",
    }
    cols = st.columns(len(tabs))
    for i, (tab_id, tab_name) in enumerate(tabs.items()):
        with cols[i]:
            st.button(
                tab_name,
                key=f"tab_{tab_id}",
                on_click=set_active_tab,
                args=(tab_id,),
                use_container_width=True,
            )

    # Highlight active tab
    st.markdown(
        f"""
        <style>
            button[kind="secondary"] {{
                background-color: {'#0f172a' if active_tab == 'upload' else 'transparent'};
            }}
        </style>
        """, unsafe_allow_html=True)


    df = load_log()

    # --- Main Content Area ---
    if active_tab == "upload":
        with st.container():
            st.header("Upload RateCon PDFs")
            
            uploaded_files = st.file_uploader(
                "Drag and drop PDF files here",
                type="pdf",
                accept_multiple_files=True,
                key=f"file_uploader_{st.session_state.uploader_key}",
                on_change=lambda: st.session_state.update(processing_complete=False)
            )

            st.button(
                "⚙️ Process Files",
                on_click=run_file_processing,
                args=(uploaded_files,),
                disabled=st.session_state.processing_complete or not uploaded_files,
                use_container_width=True,
                type="primary"
            )

            if st.session_state.processing_complete:
                st.header("Processing Complete")
                
                if st.session_state.processed_records:
                    st.button(
                        "💾 Save New Records to Log",
                        on_click=run_save_records,
                        use_container_width=True,
                        key="save_btn"
                    )

                if st.session_state.skipped_files:
                    st.subheader(f"⚠️ Skipped {len(st.session_state.skipped_files)} Files")
                    with st.expander("View details", expanded=True):
                        for item in st.session_state.skipped_files:
                            st.warning(f"**{item['file']}**: {item['reason']}")
                
                if st.session_state.processed_records:
                    st.subheader(f"✅ Found {len(st.session_state.processed_records)} New Records")
                    st.dataframe(
                        pd.DataFrame(st.session_state.processed_records),
                        use_container_width=True,
                    )
                else:
                    st.info("No new, valid records were found to be added.")

    elif active_tab == "dashboard":
        with st.container():
            render_metrics(df)
        with st.container():
            render_charts(df)
        with st.container():
            st.subheader("Full Data Log")
            render_data_table(df)
        if not df.empty:
            with st.container():
                st.subheader("Export Data")
                c1, c2, _ = st.columns([1, 1, 4])
                with c1:
                    export_format = st.selectbox(
                        "Format", ["Excel", "CSV"], label_visibility="collapsed"
                    )
                with c2:
                    file_name_base = f"ratecon_export_{datetime.now().strftime('%Y%m%d')}"
                    if export_format == "Excel":
                        label, data, mime, ext = "📥 Export to Excel", convert_df_to_excel(df), "application/vnd.ms-excel", "xlsx"
                    else:
                        label, data, mime, ext = "📥 Export to CSV", convert_df_to_csv(df), "text/csv", "csv"
                    
                    st.download_button(
                        label=label, data=data, file_name=f"{file_name_base}.{ext}", mime=mime
                    )

    elif active_tab == "manage":
        if df.empty:
            with st.container():
                st.info("No records to manage.")
        else:
            with st.container():
                st.subheader("Delete Individual Records")
                refs_to_delete = st.multiselect(
                    "Select by Reference #",
                    df["Reference #"].dropna().unique().tolist(),
                )
                st.button(
                    "Delete Selected",
                    on_click=run_delete_selected,
                    args=(refs_to_delete,),
                    use_container_width=True,
                    disabled=not refs_to_delete
                )
            with st.container():
                st.subheader("🚨 Danger Zone")
                if st.button("🗑️ Delete All Records", use_container_width=True, type="secondary"):
                    st.session_state.show_delete_all_confirm = True
                
                if st.session_state.show_delete_all_confirm:
                    st.error("Are you sure? This action is permanent and cannot be undone.")
                    c1, c2, _ = st.columns([1.5, 1, 4])
                    c1.button(
                        "✅ Yes, Delete Everything",
                        on_click=run_delete_all,
                        type="primary"
                    )
                    if c2.button("❌ Cancel"):
                        st.session_state.show_delete_all_confirm = False
                        st.rerun()


if __name__ == "__main__":
    main()
