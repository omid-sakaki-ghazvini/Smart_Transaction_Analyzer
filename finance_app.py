import streamlit as st
import pandas as pd
import duckdb
from datetime import datetime
from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
import torch

# --- Initial Settings ---
st.set_page_config(
    page_title="Smart Financial Analyzer",
    page_icon="💳",
    layout="wide"
)

# --- NLP Model ---
@st.cache_resource
def load_nlp_model():
    try:
        # For English queries, use a model fine-tuned for text classification in English
        model_name = "distilbert-base-uncased-finetuned-sst-2-english"
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSequenceClassification.from_pretrained(model_name)
        return pipeline(
            "text-classification",
            model=model,
            tokenizer=tokenizer,
            device=0 if torch.cuda.is_available() else -1
        )
    except Exception as e:
        st.error(f"Error loading model: {str(e)}")
        return None

nlp_pipe = load_nlp_model()

# --- Database ---
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
    # Sample data
    sample_data = [
        (1, '2023-01-15', 150000, 'Food', 'Restaurant'),
        (2, '2023-01-20', 250000, 'Transport', 'Taxi'),
        (3, '2023-02-05', 3000000, 'Housing', 'Rent')
    ]
    for data in sample_data:
        conn.execute("INSERT OR IGNORE INTO transactions VALUES (?, ?, ?, ?, ?)", data)
    return conn

if 'db' not in st.session_state:
    st.session_state.db = init_db()

# --- Main Functions ---
def add_transaction(date, amount, category, description):
    try:
        st.session_state.db.execute("""
        INSERT INTO transactions VALUES (
            (SELECT COALESCE(MAX(id), 0) + 1 FROM transactions),
            ?, ?, ?, ?
        )""", [str(date), float(amount), category, description])
        return True
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return False

def natural_language_to_sql(query):
    """
    Convert an English natural language query to SQL using simple pattern matching.
    For a full solution, connect an English-to-SQL model or expand this function.
    """
    try:
        # Simple rule-based matching for demonstration
        q = query.lower()
        if "total" in q and ("cost" in q or "expense" in q or "spend" in q):
            sql = "SELECT SUM(amount) AS total FROM transactions"
        elif "food" in q:
            sql = "SELECT SUM(amount) AS food_total FROM transactions WHERE category='Food'"
        elif "recent" in q or "last" in q or "latest" in q:
            sql = "SELECT * FROM transactions ORDER BY date DESC LIMIT 5"
        elif "category" in q or "distribution" in q:
            sql = """
            SELECT category, SUM(amount) AS total 
            FROM transactions 
            GROUP BY category 
            ORDER BY total DESC
            """
        else:
            # Default: show everything
            sql = "SELECT * FROM transactions ORDER BY date DESC LIMIT 10"
        df = st.session_state.db.execute(sql).fetchdf()
        return df, sql
    except Exception as e:
        return None, f"Error: {str(e)}"

# --- User Interface ---
st.title("💳 Smart Financial Analyzer")

tab1, tab2, tab3 = st.tabs(["Add Transaction", "Traditional Analysis", "Smart Query"])

with tab1:
    st.header("Add New Transaction")
    with st.form("transaction_form"):
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("Date", datetime.now())
            amount = st.number_input("Amount (Rial)", min_value=1000, step=1000)
        with col2:
            category = st.selectbox(
                "Category",
                ["Food", "Transport", "Housing", "Fun", "Shopping", "Other"]
            )
            description = st.text_input("Description (optional)")
        submitted = st.form_submit_button("Add Transaction")
        if submitted:
            if add_transaction(date, amount, category, description):
                st.success("Transaction added successfully.")

with tab2:
    st.header("Traditional Analysis")
    analysis_type = st.selectbox(
        "Analysis Type",
        ["Total Expenses", "Expense Distribution", "Recent Transactions"]
    )

    if analysis_type == "Total Expenses":
        df = st.session_state.db.execute("SELECT SUM(amount) AS 'Total Expenses' FROM transactions").fetchdf()
        st.dataframe(df, hide_index=True)
    elif analysis_type == "Expense Distribution":
        df = st.session_state.db.execute("""
        SELECT 
            category AS 'Category', 
            SUM(amount) AS 'Amount',
            ROUND(SUM(amount)*100/(SELECT SUM(amount) FROM transactions), 1) AS 'Percent'
        FROM transactions 
        GROUP BY category 
        ORDER BY SUM(amount) DESC
        """).fetchdf()
        st.dataframe(df, hide_index=True)
        st.bar_chart(df.set_index('Category')['Amount'])
    elif analysis_type == "Recent Transactions":
        df = st.session_state.db.execute("SELECT * FROM transactions ORDER BY date DESC LIMIT 10").fetchdf()
        st.dataframe(df, hide_index=True)

with tab3:
    st.header("Smart Query")
    st.markdown("""
    **Sample queries:**
    - What is my total expense?
    - How much did I spend on food?
    - Show my recent transactions
    - What is my expense distribution by category?
    """)
    user_query = st.text_input("Enter your question in English:")
    if st.button("Run Query") and user_query:
        with st.spinner("Processing your query..."):
            result, sql = natural_language_to_sql(user_query)
            if result is not None:
                st.success("Results:")
                st.dataframe(result)
                with st.expander("Show SQL Query"):
                    st.code(sql, language='sql')
            else:
                st.error(sql)
