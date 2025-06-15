import streamlit as st
import pandas as pd
import duckdb
from datetime import datetime
from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM
import torch

# --- تنظیمات اولیه ---
st.set_page_config(
    page_title="سیستم هوشمند تحلیل مالی",
    page_icon="💳",
    layout="wide"
)

# --- بارگذاری مدل زبان طبیعی ---
@st.cache_resource
def load_nlp_model():
    try:
        # استفاده از مدل سبک‌وزن فارسی
        model_name = "HooshvareLab/bert-fa-base-uncased"
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
        return pipeline("text2text-generation", model=model, tokenizer=tokenizer)
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

def natural_language_query(query):
    """تبدیل پرس‌وجوی طبیعی به SQL"""
    try:
        # الگوی پیش‌فرض برای مدل
        prompt = f"""
        جدول تراکنش‌ها با ستون‌های: id, date, amount, category, description
        این پرس‌وجو را به SQL تبدیل کن: {query}
        فقط کد SQL را برگردان بدون توضیح.
        """
        
        # تولید SQL با مدل زبانی
        generated = nlp_pipe(prompt, max_length=128)
        sql = generated[0]['generated_text'].strip()
        
        # اجرای کوئری
        result = st.session_state.db.execute(sql).fetchdf()
        return result, sql
    except Exception as e:
        return None, f"خطا: {str(e)}"

# --- رابط کاربری ---
st.title("💳 تحلیلگر هوشمند مالی با پرس‌وجوی طبیعی")

tab1, tab2, tab3 = st.tabs(["ثبت تراکنش", "تحلیل سنتی", "پرس‌وجوی هوشمند"])

with tab1:
    # فرم ثبت تراکنش (مشابه قبل)

with tab2:
    # تحلیل‌های سنتی (مشابه قبل)

with tab3:
    st.header("پرس‌وجوی هوشمند")
    st.markdown("""
    **مثال‌های پرس‌وجو:**
    - کل هزینه‌های من چقدر است؟
    - پرخرج‌ترین دسته‌بندی کدام است؟
    - تراکنش‌های ماه جاری را نشان بده
    """)
    
    user_query = st.text_input("سوال خود را به زبان فارسی وارد کنید:")
    
    if st.button("اجرای پرس‌وجو") and user_query:
        with st.spinner("در حال پردازش..."):
            result, sql = natural_language_query(user_query)
            
            if result is not None:
                st.success("نتایج پرس‌وجو:")
                st.dataframe(result)
                
                with st.expander("مشاهده کوئری SQL تولید شده"):
                    st.code(sql, language='sql')
            else:
                st.error(sql)  # نمایش خطا
