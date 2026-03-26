import sqlite3
import pandas as pd
import requests
import json

API_KEY = "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"


# ===== CALL LLM =====
def call_llm(prompt):

    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        data=json.dumps({
            "model": "openai/gpt-4o-mini",
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}]
        })
    )

    result = response.json()

    if "choices" not in result:
        print("API ERROR:", result)
        return ""

    return result["choices"][0]["message"]["content"]


# ===== CLEAN SQL =====
def clean_sql(text):

    if "SELECT" in text:
        text = text[text.find("SELECT"):]

    text = text.replace("```sql", "")
    text = text.replace("```", "")

    return text.strip()


# ===== DATABASE =====
conn = sqlite3.connect("data.db")


# ===== STEP 1: HIGH-LEVEL QUESTION =====
def generate_high_level_question():

    prompt = """
    Generate ONE high-level analytical question.

    Database:
    - students(student_id, school_id, sat_score, frpm_percent, gender)
    - schools(school_id, location, funding_per_student)
    - performance(school_id, graduation_rate, dropout_rate)

    IMPORTANT:
    - frpm_percent is between 0 and 1 (NOT 0–100)

    Focus on:
    - socioeconomic inequality
    - performance differences

    Keep it concise.
    """

    return call_llm(prompt)


# ===== STEP 2: SUB-QUESTIONS =====
def generate_sub_questions(high_q):

    prompt = f"""
    Break this into EXACTLY 3 sub-questions:

    {high_q}

    Rules:
    - Use ONLY columns from database
    - Use relationships between tables (JOIN when needed)
    - Avoid simple questions like max/count
    - Focus on relationships and comparisons

    Keep them short.
    """

    result = call_llm(prompt)

    return [q.strip("- ").strip() for q in result.split("\n") if q.strip()]


# ===== FILTER =====
def is_valid(q):

    banned = ["threshold", "time", "% range"]

    if any(b in q.lower() for b in banned):
        return False

    return True


# ===== STEP 3: GENERATE SQL =====
def generate_sql(q):

    prompt = f"""
    You are a SQLite expert.

    Database schema:
    students(student_id, school_id, sat_score, frpm_percent, gender)
    schools(school_id, location, funding_per_student)
    performance(school_id, graduation_rate, dropout_rate)

    IMPORTANT:
    - frpm_percent is between 0 and 1
    - Use JOIN when needed

    Return ONLY SQL query.

    Question:
    {q}
    """

    return clean_sql(call_llm(prompt))


# ===== RUN SQL =====
def run_sql(sql):

    try:
        return pd.read_sql_query(sql, conn)
    except Exception as e:
        print("SQL ERROR:", e)
        return None


# ===== EXPLAIN =====
def explain(df):

    prompt = f"""
    Explain this data.

    Focus on:
    - patterns
    - relationships
    - key insights

    Data:
    {df.to_string()}
    """

    return call_llm(prompt)


# ===== FINAL INSIGHT =====
def final_insight(high_q, exps):

    prompt = f"""
    High-level question:
    {high_q}

    Findings:
    {exps}

    Generate a strong final insight (2-3 sentences).

    Include:
    - key pattern
    - implication
    - limitation
    """

    return call_llm(prompt)


# ===== RUN PIPELINE =====

# 1️⃣ High-level
high_q = generate_high_level_question()
print("\nHIGH-LEVEL QUESTION:\n", high_q)

# 2️⃣ Sub-questions
sub_qs = generate_sub_questions(high_q)
sub_qs = [q for q in sub_qs if is_valid(q)]

print("\nSUB-QUESTIONS:")
for q in sub_qs:
    print("-", q)

all_exp = []

# 3️⃣ Loop
for q in sub_qs:

    print("\nProcessing:", q)

    sql = generate_sql(q)
    print("SQL:", sql)

    if "SELECT" not in sql:
        print("Invalid SQL, skipping...")
        continue

    df = run_sql(sql)

    # fallback thông minh
    if df is None or df.empty:
        print("Fallback to safe query...")
        df = run_sql("""
            SELECT frpm_percent, sat_score
            FROM students
        """)

    print("Result:\n", df)

    exp = explain(df)
    print("Explanation:", exp)

    all_exp.append(exp)


# 4️⃣ Final Insight
final = final_insight(high_q, all_exp)

print("\nFINAL INSIGHT:\n", final)