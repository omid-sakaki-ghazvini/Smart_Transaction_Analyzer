import streamlit as st
import pandas as pd
import duckdb
from datetime import datetime
from transformers import pipeline
import torch

# تنظیمات اولیه
st.set_page_config(
    page_title="تحلیلگر مالی هوشمند",
    page_icon="💳",
    layout="wide"
)

# --- مدل پردازش زبان طبیعی ---
@st.cache_resource
def load_nlp_model():
    try:
        return pipeline(
            "text-generation",
            model="HooshvareLab/bert-fa-base-uncased",
            torch_dtype=torch.float16,
            device_map="auto"
        )
    except Exception as e:
        st.error(f"خطا در بارگذاری مدل: {str(e)}")
        return None

nlp_pipe = load_nlp_model()

# --- پایگاه داده ---
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
    
    # داده‌های نمونه
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

# --- توابع اصلی ---
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

def natural_language_to_sql(query):
    """تبدیل پرس‌وجوی طبیعی به SQL"""
    try:
        prompt = f"""
        شما یک مترجم پرس‌وجوی مالی به SQL هستید.
        جدول transactions دارای ستون‌های: id, date, amount, category, description
        
        این پرس‌وجو را به SQL تبدیل کن: {query}
        
        فقط کد SQL را برگردان بدون هیچ توضیحی.
        """
        
        # تولید SQL
        generated = nlp_pipe(prompt, max_length=200)
        sql = generated[0]['generated_text'].strip()
        
        # اجرای کوئری
        result = st.session_state.db.execute(sql).fetchdf()
        return result, sql
    except Exception as e:
        return None, f"خطا: {str(e)}"

# --- رابط کاربری ---
st.title("💳 تحلیلگر هوشمند مالی")

tab1, tab2, tab3 = st.tabs(["ثبت تراکنش", "تحلیل سنتی", "پرس‌وجوی هوشمند"])

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
                st.success("تراکنش با موفقیت ثبت شد")

with tab2:
    st.header("تحلیل سنتی")
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

with tab3:
    st.header("پرس‌وجوی هوشمند")
    st.markdown("""
    **نمونه پرس‌وجوها:**
    - کل هزینه‌های من چقدر است؟
    - پرخرج‌ترین دسته‌بندی کدام است؟
    - تراکنش‌های بالای ۱ میلیون تومان
    - مجموع هزینه‌های غذا در ماه گذشته
    """)
    
    user_query = st.text_input("سوال خود را به زبان فارسی وارد کنید:")
    
    if st.button("اجرای پرس‌وجو") and user_query:
        with st.spinner("در حال پردازش سوال..."):
            result, sql = natural_language_to_sql(user_query)
            
            if result is not None:
                st.success("نتایج:")
                st.dataframe(result)
                
                with st.expander("مشاهده کوئری SQL"):
                    st.code(sql, language='sql')
            else:
                st.error(sql)
