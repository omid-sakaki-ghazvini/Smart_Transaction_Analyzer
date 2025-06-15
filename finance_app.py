import streamlit as st
import pandas as pd
import duckdb
from datetime import datetime
import sys

# بررسی نسخه پایتون
if sys.version_info >= (3, 13):
    st.warning("""
    ⚠️ Python 3.13 ممکن است مشکلات سازگاری داشته باشد.
    نسخه توصیه شده: پایتون 3.11
    """)

# تنظیمات اولیه صفحه
st.set_page_config(
    page_title="تحلیلگر هوشمند تراکنش‌های مالی",
    page_icon="💳",
    layout="wide"
)

# راه‌اندازی پایگاه داده
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

# مدیریت وضعیت برنامه
if 'db' not in st.session_state:
    st.session_state.db = init_db()

# توابع اصلی
def add_transaction(date, amount, category, description):
    try:
        datetime.strptime(str(date), '%Y-%m-%d')
        amount = float(amount)
        if amount <= 0:
            return "❌ مبلغ باید مثبت باشد"
            
        st.session_state.db.execute("""
        INSERT INTO transactions VALUES (
            (SELECT COALESCE(MAX(id), 0) + 1 FROM transactions),
            ?, ?, ?, ?
        )""", [str(date), amount, category, description])
        
        return "✅ تراکنش با موفقیت ثبت شد"
    except Exception as e:
        return f"❌ خطا: {str(e)}"

def get_transactions():
    return st.session_state.db.execute("""
    SELECT * FROM transactions ORDER BY date DESC
    """).fetchdf()

# رابط کاربری
st.title("💳 تحلیلگر هوشمند تراکنش‌های مالی")

tab1, tab2 = st.tabs(["ثبت تراکنش", "مدیریت و تحلیل"])

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
            result = add_transaction(date, amount, category, description)
            st.toast(result)

with tab2:
    st.header("مدیریت و تحلیل تراکنش‌ها")
    
    analysis_type = st.selectbox(
        "نوع تحلیل",
        ["نمایش همه تراکنش‌ها", "تحلیل دسته‌بندی", "خلاصه مالی"]
    )
    
    if analysis_type == "نمایش همه تراکنش‌ها":
        df = get_transactions()
        st.dataframe(df, use_container_width=True)
        
    elif analysis_type == "تحلیل دسته‌بندی":
        df = st.session_state.db.execute("""
        SELECT 
            category AS 'دسته‌بندی', 
            SUM(amount) AS 'مجموع',
            ROUND(SUM(amount)*100/(SELECT SUM(amount) FROM transactions), 1) AS 'درصد'
        FROM transactions 
        GROUP BY category 
        ORDER BY SUM(amount) DESC
        """).fetchdf()
        
        st.dataframe(df, use_container_width=True)
        st.bar_chart(df.set_index('دسته‌بندی')['مجموع'])
        
    elif analysis_type == "خلاصه مالی":
        col1, col2 = st.columns(2)
        with col1:
            st.metric("کل تراکنش‌ها", 
                     st.session_state.db.execute("SELECT COUNT(*) FROM transactions").fetchone()[0])
        with col2:
            st.metric("کل هزینه‌ها", 
                     f"{st.session_state.db.execute('SELECT SUM(amount) FROM transactions').fetchone()[0]:,} ریال")

# بخش مدیریت در سایدبار
with st.sidebar:
    st.header("مدیریت داده‌ها")
    
    if st.button("بارگذاری داده‌های نمونه"):
        st.session_state.db = init_db()
        st.toast("داده‌های نمونه بارگذاری شدند", icon="✅")
    
    if st.button("پاک کردن همه داده‌ها"):
        st.session_state.db.execute("DELETE FROM transactions")
        st.toast("همه داده‌ها پاک شدند", icon="⚠️")
    
    st.divider()
    
    # خروجی CSV
    st.header("گزارش‌گیری")
    if st.button("دانلود داده‌ها (CSV)"):
        df = get_transactions()
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="دانلود فایل CSV",
            data=csv,
            file_name='تراکنش‌های_مالی.csv',
            mime='text/csv'
        )
