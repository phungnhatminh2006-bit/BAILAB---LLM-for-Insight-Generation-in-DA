import sqlite3
import pandas as pd
import requests
import json


# ===== 1. API KEY =====
API_KEY = "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"


# ===== 2. CALL OPENROUTER =====
def call_llm(prompt):

    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        data=json.dumps({
            "model": "openai/gpt-4o-mini",   # ⭐ mạnh và ổn định
            "messages": [
                {"role": "user", "content": prompt}
            ]
        })
    )

    result = response.json()

    return result["choices"][0]["message"]["content"]


# ===== 3. CLEAN SQL =====
def clean_sql(text):

    if "SELECT" in text:
        text = text[text.find("SELECT"):]

    text = text.replace("```sql", "")
    text = text.replace("```", "")

    return text.strip()


# ===== 4. CONNECT DATABASE =====
conn = sqlite3.connect("data.db")


# ===== 5. QUESTION =====
question = "What is the relationship between FRPM and SAT scores?"
print("Question:", question)


# ===== 6. GENERATE SQL =====
def generate_sql(question):

    prompt = f"""
    You are a SQLite expert.

    Table schema:
    students(
        school TEXT,
        sat_score INTEGER,
        frpm_percent REAL
    )

    Generate ONLY valid SQLite SQL.

    Rules:
    - Only SQL
    - No explanation
    - Use only given columns

    Question:
    {question}
    """

    sql = call_llm(prompt)

    return clean_sql(sql)


# ===== 7. RUN SQL =====
def run_sql(sql):

    try:
        df = pd.read_sql_query(sql, conn)
        return df
    except Exception as e:
        print("SQL ERROR:", e)
        return None


# ===== 8. EXPLAIN RESULT =====
def explain(df):

    prompt = f"""
    Explain the following data:

    {df.to_string()}

    Keep it short.
    """

    return call_llm(prompt)


# ===== 9. GENERATE INSIGHT =====
def generate_insight(text):

    prompt = f"""
    Generate a short insight (max 2 sentences):

    {text}
    """

    return call_llm(prompt)


# ===== RUN PIPELINE =====

sql = generate_sql(question)
print("\nSQL:\n", sql)

df = run_sql(sql)

if df is not None:
    print("\nResult:\n", df)

    explanation = explain(df)
    print("\nExplanation:\n", explanation)

    insight = generate_insight(explanation)
    print("\nInsight:\n", insight)

else:
    print("Query failed")