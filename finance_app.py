import re
from datetime import datetime
import streamlit as st
import duckdb
from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
import torch

# تنظیمات اولیه
st.set_page_config(
    page_title="تحلیلگر مالی هوشمند پیشرفته",
    page_icon="💳",
    layout="wide"
)

# --- مدل پردازش زبان طبیعی ---
@st.cache_resource
def load_nlp_model():
    try:
        model_name = "HooshvareLab/bert-fa-base-uncased"
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSequenceClassification.from_pretrained(model_name)
        
        return pipeline(
            "text-classification",
            model=model,
            tokenizer=tokenizer,
            device=0 if torch.cuda.is_available() else -1
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
        (3, '2023-02-05', 3000000, 'مسکن', 'اجاره'),
        (4, '2023-02-15', 500000, 'غذا', 'سفارش غذا'),
        (5, '2023-03-01', 1000000, 'تفریح', 'سینما')
    ]
    
    for data in sample_data:
        conn.execute("INSERT OR IGNORE INTO transactions VALUES (?, ?, ?, ?, ?)", data)
    
    return conn

if 'db' not in st.session_state:
    st.session_state.db = init_db()

# --- توابع کمکی ---
def extract_dates(query):
    """استخراج تاریخ از متن با استفاده از regex"""
    date_patterns = [
        (r"\d{4}-\d{2}-\d{2}", "%Y-%m-%d"),  # فرمت استاندارد
        (r"\d{2}/\d{2}/\d{4}", "%d/%m/%Y"),  # فرمت ایرانی
        (r"\d{4}/\d{2}/\d{2}", "%Y/%m/%d")   # فرمت جایگزین
    ]
    
    dates = []
    for pattern, date_format in date_patterns:
        matches = re.findall(pattern, query)
        for match in matches:
            try:
                dates.append(datetime.strptime(match, date_format).date())
            except:
                continue
    
    return sorted(dates) if dates else None

def get_category_from_query(query):
    """تشخیص دسته‌بندی از متن با ترکیب NLP و قوانین"""
    # تحلیل با مدل NLP
    nlp_result = nlp_pipe(query)[0]['label'] if nlp_pipe else None
    
    # قوانین دستی برای دسته‌بندی
    category_rules = {
        'غذا': ['غذا', 'رستوران', 'سفارش', 'پیتزا', 'کافه'],
        'حمل و نقل': ['تاکسی', 'اتوبوس', 'مترو', 'حمل', 'نقل'],
        'مسکن': ['مسکن', 'اجاره', 'خونه', 'خانه', 'آپارتمان'],
        'تفریح': ['تفریح', 'سینما', 'پارک', 'گردش', 'مسافرت']
    }
    
    query_lower = query.lower()
    for category, keywords in category_rules.items():
        if any(keyword in query_lower for keyword in keywords):
            return category
    
    return nlp_result if nlp_result else None

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

def hybrid_nlp_to_sql(query):
    """ترکیب NLP با قوانین دستی برای تبدیل پرس‌وجو به SQL"""
    try:
        # پیش‌پردازش پرس‌وجو
        query = query.strip().lower()
        
        # استخراج تاریخ‌ها (اگر وجود داشته باشند)
        dates = extract_dates(query)
        
        # تشخیص دسته‌بندی
        category = get_category_from_query(query)
        
        # الگوهای ترکیبی
        if dates and len(dates) >= 2:
            # پرس‌وجوهای محدوده تاریخی
            sql = f"""
            SELECT * FROM transactions 
            WHERE date BETWEEN '{dates[0]}' AND '{dates[1]}'
            ORDER BY date
            """
        elif "چند تا" in query or "تعداد" in query:
            # پرس‌وجوهای شمارشی
            if category:
                sql = f"SELECT COUNT(*) AS count FROM transactions WHERE category='{category}'"
            else:
                sql = "SELECT COUNT(*) AS count FROM transactions"
        elif "میانگین" in query or "متوسط" in query:
            # پرس‌وجوهای محاسباتی
            if category:
                sql = f"SELECT AVG(amount) AS average FROM transactions WHERE category='{category}'"
            else:
                sql = "SELECT AVG(amount) AS average FROM transactions"
        elif category:
            # پرس‌وجوهای مبتنی بر دسته‌بندی
            sql = f"""
            SELECT date, amount, description 
            FROM transactions 
            WHERE category='{category}'
            ORDER BY date DESC
            """
        elif "آخرین" in query or "اخیر" in query:
            # پرس‌وجوهای تراکنش‌های اخیر
            sql = "SELECT * FROM transactions ORDER BY date DESC LIMIT 5"
        elif "دسته" in query or "گروه" in query or "طبقه" in query:
            # پرس‌وجوهای گروه‌بندی
            sql = """
            SELECT category, SUM(amount) AS total, COUNT(*) AS count
            FROM transactions 
            GROUP BY category 
            ORDER BY total DESC
            """
        else:
            # پیش‌فرض - جمع کل
            sql = "SELECT SUM(amount) AS total FROM transactions"
        
        # اجرای کوئری
        df = st.session_state.db.execute(sql).fetchdf()
        return df, sql
        
    except Exception as e:
        return None, f"خطا در پردازش پرس‌وجو: {str(e)}"

# --- رابط کاربری ---
st.title("💳 تحلیلگر هوشمند مالی پیشرفته")

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
        ["کل هزینه‌ها", "توزیع هزینه‌ها", "تراکنش‌های اخیر", "میانگین هزینه‌ها"]
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
        
    elif analysis_type == "میانگین هزینه‌ها":
        df = st.session_state.db.execute("SELECT AVG(amount) AS 'میانگین هزینه‌ها' FROM transactions").fetchdf()
        st.dataframe(df, hide_index=True)

with tab3:
    st.header("پرس‌وجوی هوشمند (NLP)")
    
    user_query = st.text_input("سوال خود را به زبان فارسی وارد کنید:", key="query_input")
    
    if st.button("اجرای پرس‌وجو") and user_query:
        with st.spinner("در حال پردازش سوال..."):
            result, sql = hybrid_nlp_to_sql(user_query)
            
            if result is not None:
                st.success("نتایج پرس‌وجو:")
                st.dataframe(result)
                
                with st.expander("مشاهده کوئری SQL تولید شده"):
                    st.code(sql, language='sql')
            else:
                st.error(sql)


st.markdown("<br><hr><center>Made with ❤️ by <a href='https://omidsakaki.ir/'><strong>omid sakaki ghazvini</strong></a></center><hr>", unsafe_allow_html=True)
