import streamlit as st
import pandas as pd
import duckdb
from datetime import datetime

st.set_page_config(
    page_title="تحلیلگر هوشمند مالی",
    page_icon="💳",
    layout="wide"
)

def init_db():
    conn = duckdb.connect(database=':memory:')
    conn.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY,
        date DATE,
        amount DECIMAL(12, 2),
        category VARCHAR(50),
        description TEXT
    )""")
    sample_data = [
        (1, '2023-01-15', 150000, 'غذا', 'رستوران'),
        (2, '2023-01-20', 250000, 'حمل و نقل', 'تاکسی'),
        (3, '2023-02-05', 3000000, 'مسکن', 'اجاره')
    ]
    for data in sample_data:
        conn.execute("INSERT OR IGNORE INTO transactions VALUES (?, ?, ?, ?, ?)", data)
    return conn

if 'db' not in st.session_state:
    st.session_state.db = init_db()

def add_transaction(date, amount, category, description):
    try:
        st.session_state.db.execute("""
        INSERT INTO transactions VALUES (
            (SELECT COALESCE(MAX(id), 0) + 1 FROM transactions),
            ?, ?, ?, ?
        )""", [str(date), float(amount), category, description])
        return True
    except Exception as e:
        st.error(f"خطا: {str(e)}")
        return False

st.title("💳 تحلیلگر هوشمند مالی")

tab1, tab2 = st.tabs(["ثبت تراکنش", "تحلیل"])

with tab1:
    st.header("ثبت تراکنش جدید")
    with st.form("transaction_form"):
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("تاریخ", datetime.now())
            amount = st.number_input("مبلغ (ریال)", min_value=1000, step=1000)
        with col2:
            category = st.selectbox(
                "دسته‌بندی",
                ["غذا", "حمل و نقل", "مسکن", "تفریح", "خرید", "سایر"]
            )
            description = st.text_input("توضیحات (اختیاری)")
        submitted = st.form_submit_button("ثبت تراکنش")
        if submitted:
            if add_transaction(date, amount, category, description):
                st.success("تراکنش با موفقیت ثبت شد.")

with tab2:
    st.header("تحلیل تراکنش‌ها")
    analysis_type = st.selectbox(
        "نوع تحلیل",
        ["کل هزینه‌ها", "توزیع هزینه‌ها", "تراکنش‌های اخیر"]
    )

    if analysis_type == "کل هزینه‌ها":
        df = st.session_state.db.execute("SELECT SUM(amount) AS 'مجموع هزینه‌ها' FROM transactions").fetchdf()
        st.dataframe(df, hide_index=True)
    elif analysis_type == "توزیع هزینه‌ها":
        df = st.session_state.db.execute("""
        SELECT 
            category AS 'دسته', 
            SUM(amount) AS 'مبلغ',
            ROUND(SUM(amount)*100/(SELECT SUM(amount) FROM transactions), 1) AS 'درصد'
        FROM transactions 
        GROUP BY category 
        ORDER BY SUM(amount) DESC
        """).fetchdf()
        st.dataframe(df, hide_index=True)
        st.bar_chart(df.set_index('دسته')['مبلغ'])
    elif analysis_type == "تراکنش‌های اخیر":
        df = st.session_state.db.execute("SELECT * FROM transactions ORDER BY date DESC LIMIT 10").fetchdf()
        st.dataframe(df, hide_index=True)
