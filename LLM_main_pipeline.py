import sqlite3
import pandas as pd
import requests
import time
import json

# ===== CONFIG =====
GITHUB_TOKEN = "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"
API_URL = "https://models.inference.ai.azure.com/chat/completions"
MODEL = "gpt-4o-mini"

# ===== LLM CALL =====
def call_llm(prompt, max_tokens=300):
    for _ in range(3):
        try:
            response = requests.post(
                API_URL,
                headers={
                    "Authorization": f"Bearer {GITHUB_TOKEN}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": 0
                }
            )

            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]
            else:
                print("API ERROR:", response.text)
                time.sleep(2)

        except Exception as e:
            print("REQUEST ERROR:", e)
            time.sleep(2)

    return ""

# ===== DATABASE =====
conn = sqlite3.connect("education_pro.db")

# =========================================================
# STEP 0 — DB UNDERSTANDING
# =========================================================
def get_db_context(conn):
    cursor = conn.cursor()
    tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()

    schema_text = ""

    for (t,) in tables:
        schema_text += f"\n=== Table: {t} ===\n"

        # Columns
        cols = cursor.execute(f"PRAGMA table_info({t});").fetchall()
        col_names = [c[1] for c in cols]

        schema_text += "Columns:\n"
        for c in cols:
            schema_text += f"- {c[1]} ({c[2]})\n"

        # Sample rows
        rows = cursor.execute(f"SELECT * FROM {t} LIMIT 3;").fetchall()

        schema_text += "\nSample rows:\n"
        for r in rows:
            schema_text += ", ".join([str(x) for x in r]) + "\n"

        schema_text += "\n"

    # ===== LLM generate description =====
    prompt = f"""
    You are a data analyst.

    Database schema:
    {schema_text}

    Task:
    1. Identify key variable types:
    - Socioeconomic variables
    - Performance variables
    - Resource or contextual variables

    2. Identify POSSIBLE INTERACTIONS:
    - How one variable might influence another differently under conditions

    3. Suggest 2–3 NON-OBVIOUS analytical directions.

    Rules:
    - Avoid listing columns
    - Focus on relationships and interactions
    - Keep concise

    Output format:
    - Variables:
    - Interactions:
    - Directions:
    """

    description = call_llm(prompt, 200)

    return schema_text, description

# =========================================================
# STEP 1 — HYPOTHESIS
# =========================================================

def generate_questions(context):
    prompt = f"""
    Context:
    {context}
    You are a senior data analyst.

    Generate analytical questions that MUST:
    1. Combine at least TWO variables (e.g., socioeconomic + funding)
    2. Explore INTERACTION EFFECTS:
   - How does X change under condition Y?
    3. Compare at least TWO groups
    4. Reveal NON-OBVIOUS patterns

    Avoid:
    - Simple correlations (e.g., "X vs Y")
    - Obvious trends

    Good examples:
    - "Does the impact of socioeconomic status on performance differ across schools with different funding levels?"
    - "Is the performance gap between groups smaller in high-resource environments?"

    Bad examples:
    - "How does X affect Y?"

    Output format:
    MAIN: one high-level interaction question
    SUB1: focuses on interaction (X under Y)
    SUB2: focuses on anomaly or contrast
    """

    text = call_llm(prompt, 250)

    main_q, sub_qs = None, []

    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("MAIN"):
            main_q = line.split(":", 1)[-1].strip()
        elif line.startswith("SUB"):
            sub_qs.append(line.split(":", 1)[-1].strip())

    if not main_q:
        main_q = "What affects student performance?"

    if len(sub_qs) < 2:
        sub_qs = [
            "How does socioeconomic status relate to performance?",
            "Are there differences across groups?"
        ]

    return main_q, sub_qs[:2]

# =========================================================
# STEP 2 — SQL AGENT
# =========================================================
def generate_sql(q):
    prompt = f"""
You are a SQL expert.

Database description:
{dinfo_text}

Database schema:
{schema_text}

Task:
Generate a SQL query to answer the question.

STRICT RULES:
1. MUST use at least ONE JOIN
2. MUST involve at least TWO variables
3. MUST include GROUP BY
4. MUST produce at least 2 groups for comparison
5. Prefer interaction segmentation (e.g., CASE WHEN)

Good pattern:
- Compare X across Y conditions
- Segment data into meaningful groups

Avoid:
- Simple averages without segmentation
- Using only one table
- Trivial queries

Return ONLY SQL.

Question:
{q}
"""

    text = call_llm(prompt, 200)

    if "SELECT" in text:
        sql = text[text.find("SELECT"):]
        if ";" in sql:
            sql = sql.split(";")[0] + ";"
        return sql.strip()

    return None

def sql_agent(q):
    sql = generate_sql(q)

    if sql is None:
        return None, None

    for _ in range(2):
        try:
            print("\nSQL:", sql)
            df = pd.read_sql_query(sql, conn)

            if len(df) < 2:
                print("Not enough data for comparison")
                return None, None

            print("Rows:", len(df))
            return sql, df

        except Exception as e:
            print("SQL ERROR:", e)
            return None, None

    return None, None

# =========================================================
# STEP 3 — ANALYZE + VERIFY
# =========================================================

def analyze_and_verify(df, question):
    if df is None or df.empty:
        return None

    sample = df.to_string(index=False)

    prompt = f"""
Data sample:
{sample}

Question:
{question}

You are an expert analyst.

Tasks:
1. Identify a NON-OBVIOUS pattern
2. Explain HOW the relationship changes across groups
3. Highlight any interaction effect or contrast
4. Include approximate numerical differences
5. Explain WHY this matters (implication)

Rules:
- Maximum 2 sentences
- Avoid obvious statements
- Focus on interaction, not just correlation

Bad:
"Group A has higher values than Group B"

Good:
"While Group A generally performs better, the gap narrows significantly under condition X, suggesting that Y mitigates the disadvantage."

Output:
INSIGHT: ...
VALID: YES or NO
"""
    text = call_llm(prompt, 250)

    if "YES" in text.upper():
        return text.strip()

    return None

# =========================================================
# STEP 4 — FINAL + RETRY LOOP (🔥 NEW)
# =========================================================

def generate_final_with_retry(main_q, insights, max_retry=2):

    if not insights:
        return "No strong evidence found from the data."

    feedback = ""

    for i in range(max_retry):

        prompt = f"""
        Main question:
        {main_q}

        Verified insights:
        {insights}

        Previous issue:
        {feedback}

        You are a senior data analyst.

        Generate ONE final insight that MUST:
        1. Combine multiple findings into a deeper conclusion
        2. Include a comparison (between groups or conditions)
        3. Include an implication (why this matters)
        4. Be non-obvious and analytical

        Rules:
        - ONLY use given insights
        - DO NOT introduce new claims
        - If evidence is limited, state limitation clearly
        - Maximum 2 sentences
        - Avoid obvious or trivial insights.
        - Include quantitative evidence when possible

        Bad example:
        "X increases when Y increases."

        Good example:
        "While X is generally higher when Y increases, the effect is significantly stronger in group A than group B, suggesting structural differences."

        Final insight:
        """

        final = call_llm(prompt, 200)

        # verify final
        check_prompt = f"""
        Final insight:
        {final}

        Source insights:
        {insights}

        Check:
        - Any new claim not in source?
        - Fully supported?

        Return ONLY VALID or INVALID
        """

        result = call_llm(check_prompt, 100)

        if "VALID" in result.upper():
            return final

        feedback = "Previous summary introduced unsupported claims."
        print(f"Retry summarization... ({i+1})")

    return "Final insight uncertain. Insights: " + str(insights)

# =========================================================
# RUN PIPELINE
# =========================================================

print("\n=== STEP 0 ===")
schema_text, dinfo_text = get_db_context(conn)
print("\n=== SCHEMA ===")
print(schema_text[:500])
print("\n=== DESCRIPTION ===")
print(dinfo_text)

print("\n=== STEP 1 ===")
main_q, sub_qs = generate_questions(dinfo_text)
print("MAIN:", main_q)
print("SUB:", sub_qs)

valid_insights = []

print("\n=== STEP 2 + 3 ===")
for q in sub_qs:
    sql, df = sql_agent(q)

    if df is None:
        continue

    result = analyze_and_verify(df, q)

    if result:
        print("VALID:", result)
        valid_insights.append(result)
    else:
        print("INVALID")

print("\n=== STEP 4 ===")
final = generate_final_with_retry(main_q, valid_insights)

print("\nFINAL INSIGHT:\n", final)

import json

output_data = {
    "main_question": main_q,
    "sub_questions": sub_qs,
    "sql_results_summary": [],
    "verified_insights": [],
    "final_insight": final,
    "metadata": {
        "num_valid_insights": len(valid_insights),
        "model": MODEL
    }
}

# extract insight text
for ins in valid_insights:
    output_data["verified_insights"].append({
        "text": ins,
        "valid": True
    })

# save file
with open("pipeline_output.json", "w", encoding="utf-8") as f:
    json.dump(output_data, f, indent=4, ensure_ascii=False)