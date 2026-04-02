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
            "model": "openai/gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}]
        })
    )

    result = response.json()

    if "choices" not in result:
        print("API ERROR:", result)
        return ""

    return result["choices"][0]["message"]["content"]


# ===== 3. CLEAN SQL =====
def clean_sql(text):

    if "SELECT" in text:
        text = text[text.find("SELECT"):]

    text = text.replace("```sql", "")
    text = text.replace("```", "")

    return text.strip()


# ===== 4. DATABASE =====
conn = sqlite3.connect("data.db")


# ===== 5. GENERATE QUESTIONS (FIXED) =====
def generate_questions():

    prompt = """
    You are analyzing a dataset:

    students(
        school TEXT,
        sat_score INTEGER,
        frpm_percent REAL
    )

   Generate 3 analytical questions focusing on:
    - relationships
    - comparisons
    - patterns

    Avoid simple descriptive questions like max or average only.
    """

    result = call_llm(prompt)

    questions = result.split("\n")

    return [q.strip("- ").strip() for q in questions if q.strip()]


# ===== 6. FILTER VALID QUESTIONS =====
def is_valid_question(q):

    allowed = ["school", "sat", "frpm"]

    return any(word in q.lower() for word in allowed)


# ===== 7. GENERATE SQL =====
def generate_sql(question):

    # ❗ FIX: nếu hỏi correlation → dùng query đơn giản
    if "correlation" in question.lower():
        return "SELECT frpm_percent, sat_score FROM students"

    prompt = f"""
    You are a SQLite expert.

    Table schema:
    students(
        school TEXT,
        sat_score INTEGER,
        frpm_percent REAL
    )

    Return ONLY SQL query.

    Question:
    {question}
    """

    return clean_sql(call_llm(prompt))


# ===== 8. RUN SQL =====
def run_sql(sql):

    try:
        df = pd.read_sql_query(sql, conn)
        return df
    except Exception as e:
        print("SQL ERROR:", e)
        return None


# ===== 9. EXPLAIN =====
def explain(df):

    prompt = f"""
    Explain this data carefully.

    If the result is unclear or invalid, say so.

    Data:
    {df.to_string()}
    """

    return call_llm(prompt)


# ===== 10. FINAL INSIGHT =====
def generate_final_insight(explanations):

    prompt = f"""
    Based on the following findings:

    {explanations}

    Generate a concise and accurate overall insight (2-3 sentences).

    Focus on patterns in the data.
    Do NOT assume incorrect results.
    """

    return call_llm(prompt)


# ===== RUN PIPELINE =====

# Step 1
questions = generate_questions()

# Step 2: filter
questions = [q for q in questions if is_valid_question(q)]

print("\nGenerated Questions:")
for q in questions:
    print("-", q)

all_explanations = []

# Step 3
for q in questions:

    print("\nProcessing:", q)

    sql = generate_sql(q)
    print("SQL:", sql)

    if "SELECT" not in sql:
        print("Invalid SQL, skipping...")
        continue

    df = run_sql(sql)

    # ❗ FIX: skip invalid results
    if df is None or df.empty or df.isnull().values.any():
        print("Invalid result, skipping...")
        continue

    print("Result:\n", df)

    exp = explain(df)
    print("Explanation:", exp)

    all_explanations.append(exp)


# Step 4
final_insight = generate_final_insight(all_explanations)

print("\nFINAL INSIGHT:\n", final_insight)