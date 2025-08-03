import streamlit as st
import pandas as pd
import sqlite3
from sqlite3 import Error
import io
import os
from datetime import datetime
import altair as alt

# --- Database Functions ---

def create_connection(db_file):
    """Create a database connection to a SQLite database."""
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        return conn
    except Error as e:
        st.error(f"Error connecting to database: {e}")
    return conn

def create_table(conn):
    """Create the ratecons table if it doesn't exist."""
    try:
        sql_create_ratecons_table = """CREATE TABLE IF NOT EXISTS ratecons (
                                        id INTEGER PRIMARY KEY,
                                        load_number TEXT NOT NULL,
                                        pickup_date TEXT NOT NULL,
                                        delivery_date TEXT NOT NULL,
                                        rate REAL NOT NULL,
                                        carrier_name TEXT,
                                        carrier_mc TEXT,
                                        carrier_phone TEXT,
                                        carrier_email TEXT,
                                        shipper_name TEXT,
                                        shipper_address TEXT,
                                        consignee_name TEXT,
                                        consignee_address TEXT,
                                        notes TEXT,
                                        status TEXT DEFAULT 'Booked'
                                    );"""
        c = conn.cursor()
        c.execute(sql_create_ratecons_table)
    except Error as e:
        st.error(f"Error creating table: {e}")

def add_ratecon(conn, ratecon):
    """Add a new rate confirmation."""
    sql = ''' INSERT INTO ratecons(load_number, pickup_date, delivery_date, rate, carrier_name, carrier_mc, carrier_phone, carrier_email, shipper_name, shipper_address, consignee_name, consignee_address, notes)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) '''
    cur = conn.cursor()
    cur.execute(sql, ratecon)
    conn.commit()
    return cur.lastrowid

def update_ratecon(conn, ratecon_data):
    """Update an existing rate confirmation."""
    sql = ''' UPDATE ratecons
              SET load_number = ? ,
                  pickup_date = ? ,
                  delivery_date = ? ,
                  rate = ? ,
                  carrier_name = ? ,
                  carrier_mc = ? ,
                  carrier_phone = ? ,
                  carrier_email = ?,
                  shipper_name = ?,
                  shipper_address = ?,
                  consignee_name = ?,
                  consignee_address = ?,
                  notes = ?,
                  status = ?
              WHERE id = ?'''
    cur = conn.cursor()
    cur.execute(sql, ratecon_data)
    conn.commit()

def delete_ratecon(conn, id):
    """Delete a rate confirmation by id."""
    sql = 'DELETE FROM ratecons WHERE id = ?'
    cur = conn.cursor()
    cur.execute(sql, (id,))
    conn.commit()

def get_all_ratecons(conn):
    """Query all rows in the ratecons table."""
    cur = conn.cursor()
    cur.execute("SELECT * FROM ratecons")
    rows = cur.fetchall()
    return rows

def get_ratecon_by_id(conn, id):
    """Query a single rate confirmation by id."""
    cur = conn.cursor()
    cur.execute("SELECT * FROM ratecons WHERE id=?", (id,))
    row = cur.fetchone()
    return row

# --- Helper Functions ---
def get_column_names(conn):
    """Get column names from the ratecons table."""
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(ratecons)")
    return [info[1] for info in cur.fetchall()]

@st.cache_data
def convert_df_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="RateCons")
    processed_data = output.getvalue()
    return processed_data


# --- Main Application ---
def main():
    st.set_page_config(page_title="RateCon Tracker", layout="wide")
    st.title("🚚 Rate Confirmation Tracker")
    st.write("A simple tool to manage your freight load rate confirmations.")

    database = "ratecon_tracker.db"
    conn = create_connection(database)

    if conn is not None:
        create_table(conn)
    else:
        st.error("Error! cannot create the database connection.")
        return

    menu = ["View All", "Add New", "Update/Delete", "Analytics"]
    choice = st.sidebar.selectbox("Menu", menu)

    if choice == "View All":
        st.subheader("All Rate Confirmations")
        ratecon_data = get_all_ratecons(conn)
        column_names = get_column_names(conn)

        if ratecon_data:
            df = pd.DataFrame(ratecon_data, columns=column_names)

            # Filtering UI
            st.sidebar.header("Filter Loads:")
            status_filter = st.sidebar.multiselect("Filter by Status:", options=df['status'].unique(), default=df['status'].unique())
            carrier_filter = st.sidebar.text_input("Filter by Carrier Name:")
            load_number_filter = st.sidebar.text_input("Filter by Load Number:")

            # Apply filters
            filtered_df = df[df['status'].isin(status_filter)]
            if carrier_filter:
                filtered_df = filtered_df[filtered_df['carrier_name'].str.contains(carrier_filter, case=False, na=False)]
            if load_number_filter:
                filtered_df = filtered_df[filtered_df['load_number'].str.contains(load_number_filter, case=False, na=False)]

            st.dataframe(filtered_df, use_container_width=True)

            # Export to Excel
            excel_data = convert_df_to_excel(filtered_df)
            st.download_button(
                label="📥 Export to Excel",
                data=excel_data,
                file_name="ratecons.xlsx",
                mime="application/vnd.ms-excel"
            )

        else:
            st.info("No rate confirmations found. Add one from the 'Add New' menu.")

    elif choice == "Add New":
        st.subheader("Add a New Rate Confirmation")
        with st.form("add_form"):
            col1, col2 = st.columns(2)
            with col1:
                load_number = st.text_input("Load Number / Pro #")
                pickup_date = st.date_input("Pickup Date")
                delivery_date = st.date_input("Delivery Date")
                rate = st.number_input("Rate ($)", min_value=0.0, format="%.2f")
            with col2:
                carrier_name = st.text_input("Carrier Name")
                carrier_mc = st.text_input("Carrier MC#")
                carrier_phone = st.text_input("Carrier Phone")
                carrier_email = st.text_input("Carrier Email")

            st.subheader("Stop Information")
            shipper_name = st.text_input("Shipper Name")
            shipper_address = st.text_area("Shipper Address")
            consignee_name = st.text_input("Consignee Name")
            consignee_address = st.text_area("Consignee Address")

            notes = st.text_area("Notes")

            submitted = st.form_submit_button("Add RateCon")
            if submitted:
                if not all([load_number, pickup_date, delivery_date, rate]):
                    st.warning("Please fill in all required fields (Load Number, Dates, Rate).")
                else:
                    ratecon = (load_number, str(pickup_date), str(delivery_date), rate, carrier_name,
                               carrier_mc, carrier_phone, carrier_email, shipper_name, shipper_address,
                               consignee_name, consignee_address, notes)
                    add_ratecon(conn, ratecon)
                    st.success("Successfully added new rate confirmation!")
                    st.balloons()


    elif choice == "Update/Delete":
        st.subheader("Update or Delete a Rate Confirmation")
        ratecon_data = get_all_ratecons(conn)
        column_names = get_column_names(conn)

        if not ratecon_data:
            st.warning("No rate confirmations to update or delete.")
            return

        df = pd.DataFrame(ratecon_data, columns=column_names)
        load_list = df['load_number'].tolist()
        selected_load = st.selectbox("Select a Load Number to manage", load_list)

        if selected_load:
            ratecon_id = df[df['load_number'] == selected_load]['id'].iloc[0]
            ratecon_details = get_ratecon_by_id(conn, ratecon_id)

            if ratecon_details:
                with st.form("update_form"):
                    # Unpack details
                    (id, load_number, pickup_date, delivery_date, rate, carrier_name, carrier_mc,
                     carrier_phone, carrier_email, shipper_name, shipper_address, consignee_name,
                     consignee_address, notes, status) = ratecon_details

                    pickup_date_obj = datetime.strptime(pickup_date, '%Y-%m-%d').date()
                    delivery_date_obj = datetime.strptime(delivery_date, '%Y-%m-%d').date()
                    
                    st.subheader(f"Editing Load: {load_number}")

                    col1, col2 = st.columns(2)
                    with col1:
                        new_load_number = st.text_input("Load Number / Pro #", load_number)
                        new_pickup_date = st.date_input("Pickup Date", pickup_date_obj)
                        new_delivery_date = st.date_input("Delivery Date", delivery_date_obj)
                        new_rate = st.number_input("Rate ($)", value=rate, format="%.2f")
                        new_status = st.selectbox("Status", ["Booked", "In Transit", "Delivered", "Invoiced", "Paid", "Cancelled"], index=["Booked", "In Transit", "Delivered", "Invoiced", "Paid", "Cancelled"].index(status))

                    with col2:
                        new_carrier_name = st.text_input("Carrier Name", carrier_name)
                        new_carrier_mc = st.text_input("Carrier MC#", carrier_mc)
                        new_carrier_phone = st.text_input("Carrier Phone", carrier_phone)
                        new_carrier_email = st.text_input("Carrier Email", carrier_email)
                    
                    st.subheader("Stop Information")
                    new_shipper_name = st.text_input("Shipper Name", shipper_name)
                    new_shipper_address = st.text_area("Shipper Address", shipper_address)
                    new_consignee_name = st.text_input("Consignee Name", consignee_name)
                    new_consignee_address = st.text_area("Consignee Address", consignee_address)

                    new_notes = st.text_area("Notes", notes)

                    update_button = st.form_submit_button("Update RateCon")
                    if update_button:
                        updated_data = (new_load_number, str(new_pickup_date), str(new_delivery_date),
                                        new_rate, new_carrier_name, new_carrier_mc, new_carrier_phone,
                                        new_carrier_email, new_shipper_name, new_shipper_address,
                                        new_consignee_name, new_consignee_address, new_notes, new_status, ratecon_id)
                        update_ratecon(conn, updated_data)
                        st.success(f"Successfully updated Load {new_load_number}.")

                if st.button("Delete RateCon", type="primary"):
                    delete_ratecon(conn, ratecon_id)
                    st.warning(f"Deleted Load {selected_load}.")
                    st.experimental_rerun() # To refresh the page and remove the deleted item's form


    elif choice == "Analytics":
        st.subheader("Load Analytics")
        ratecon_data = get_all_ratecons(conn)
        column_names = get_column_names(conn)

        if not ratecon_data:
            st.warning("No data to analyze.")
            return

        df = pd.DataFrame(ratecon_data, columns=column_names)
        df['rate'] = pd.to_numeric(df['rate'])

        # Total Revenue
        total_revenue = df['rate'].sum()
        st.metric(label="Total Revenue from All Loads", value=f"${total_revenue:,.2f}")

        # Loads by Status
        st.subheader("Loads by Status")
        status_counts = df['status'].value_counts().reset_index()
        status_counts.columns = ['Status', 'Count']
        chart = alt.Chart(status_counts).mark_bar().encode(
            x=alt.X('Status', sort=None),
            y='Count',
            tooltip=['Status', 'Count']
        ).properties(
            title='Count of Loads per Status'
        )
        st.altair_chart(chart, use_container_width=True)

        # Revenue by Carrier
        st.subheader("Total Revenue by Carrier")
        carrier_revenue = df.groupby('carrier_name')['rate'].sum().sort_values(ascending=False).reset_index()
        carrier_revenue.columns = ['Carrier', 'Total Revenue']

        if not carrier_revenue.empty:
            chart = alt.Chart(carrier_revenue).mark_bar().encode(
                x=alt.X('Total Revenue:Q', title='Total Revenue ($)'),
                y=alt.Y('Carrier:N', sort='-x'),
                tooltip=['Carrier', 'Total Revenue']
            ).properties(
                title='Top Carriers by Revenue'
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("No carrier data available for this chart.")


    conn.close()

if __name__ == '__main__':
    main()
