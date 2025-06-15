import streamlit as st
import pandas as pd
import duckdb
from datetime import datetime
import sqlite3
import os

# تنظیمات صفحه
st.set_page_config(
    page_title="مدیریت مالی هوشمند",
    page_icon="💳",
    layout="wide"
)

# 1. راه‌اندازی پایگاه داده
def init_db():
    conn = duckdb.connect(database=':memory:')
    
    conn.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY,
        date DATE,
        amount DECIMAL(12, 2),
        category VARCHAR(50),
        description TEXT
    )
    """)
    
    # داده‌های نمونه
    sample_data = [
        (1, '2023-01-15', 150000, 'غذا', 'رستوران'),
        (2, '2023-01-20', 250000, 'حمل و نقل', 'تاکسی'),
        (3, '2023-02-05', 3000000, 'مسکن', 'اجاره')
    ]
    
    for data in sample_data:
        conn.execute("""
        INSERT OR IGNORE INTO transactions VALUES (?, ?, ?, ?, ?)
        """, data)
    
    return conn

# 2. مدیریت وضعیت (State)
if 'db' not in st.session_state:
    st.session_state.db = init_db()

# 3. توابع اصلی
def add_transaction(date, amount, category, description):
    try:
        datetime.strptime(date, '%Y-%m-%d')
        amount = float(amount)
        if amount <= 0:
            return "❌ مبلغ باید مثبت باشد"
            
        st.session_state.db.execute("""
        INSERT INTO transactions VALUES (
            (SELECT COALESCE(MAX(id), 0) + 1 FROM transactions),
            ?, ?, ?, ?
        )""", [date, amount, category, description])
        
        return "✅ تراکنش ثبت شد"
    except Exception as e:
        return f"❌ خطا: {str(e)}"

def run_query(sql):
    try:
        return st.session_state.db.execute(sql).fetchdf()
    except Exception as e:
        st.error(f"خطا در اجرای پرس‌وجو: {e}")
        return pd.DataFrame()

# 4. رابط کاربری Streamlit
st.title("💳 سیستم مدیریت مالی هوشمند")

tab1, tab2 = st.tabs(["ثبت تراکنش", "تحلیل مالی"])

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
            result = add_transaction(
                date.strftime('%Y-%m-%d'),
                amount,
                category,
                description
            )
            st.success(result)

with tab2:
    st.header("تحلیل تراکنش‌ها")
    
    analysis_type = st.selectbox(
        "نوع تحلیل",
        ["کل هزینه‌ها", "توزیع هزینه‌ها", "تراکنش‌های اخیر"]
    )
    
    if analysis_type == "کل هزینه‌ها":
        df = run_query("SELECT SUM(amount) AS 'مجموع هزینه‌ها' FROM transactions")
        st.dataframe(df, hide_index=True)
        
    elif analysis_type == "توزیع هزینه‌ها":
        df = run_query("""
        SELECT 
            category AS 'دسته', 
            SUM(amount) AS 'مبلغ',
            ROUND(SUM(amount)*100/(SELECT SUM(amount) FROM transactions), 1) AS 'درصد'
        FROM transactions 
        GROUP BY category 
        ORDER BY SUM(amount) DESC
        """)
        st.dataframe(df, hide_index=True)
        st.bar_chart(df.set_index('دسته')['مبلغ'])
        
    elif analysis_type == "تراکنش‌های اخیر":
        df = run_query("SELECT * FROM transactions ORDER BY date DESC LIMIT 10")
        st.dataframe(df, hide_index=True)

# 5. بخش مدیریت داده‌ها
st.sidebar.header("مدیریت داده‌ها")
if st.sidebar.button("بارگذاری داده‌های نمونه"):
    st.session_state.db = init_db()
    st.sidebar.success("داده‌های نمونه بارگذاری شدند")

if st.sidebar.button("پاک کردن همه داده‌ها"):
    st.session_state.db.execute("DELETE FROM transactions")
    st.sidebar.warning("همه داده‌ها پاک شدند")

# دانلود خروجی
st.sidebar.header("گزارش‌گیری")
if st.sidebar.button("دانلود همه تراکنش‌ها"):
    df = run_query("SELECT * FROM transactions ORDER BY date DESC")
    csv = df.to_csv(index=False).encode('utf-8-sig')
    st.sidebar.download_button(
        label="دانلود به صورت CSV",
        data=csv,
        file_name='transactions.csv',
        mime='text/csv'
    )
