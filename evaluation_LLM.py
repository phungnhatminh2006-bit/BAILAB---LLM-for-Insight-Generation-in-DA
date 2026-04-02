import json
import re
import requests
from typing import List, Dict

# ===== CONFIG =====
GITHUB_TOKEN = "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"
API_URL = "https://models.inference.ai.azure.com/chat/completions"
MODEL = "gpt-4o-mini"  

# ===== LLM CALL =====
def call_llm(prompt, max_tokens=200):
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
            return ""

    except Exception as e:
        print("REQUEST ERROR:", e)
        return ""


# =========================================================
# ===== CORRECTNESS (CLAIM-BASED) =========================
# =========================================================

def split_into_claims(text: str):
    parts = re.split(r'[.;]|\band\b', text)
    return [p.strip() for p in parts if len(p.strip()) > 5]


def score_claim(claim: str) -> float:
    claim = claim.lower()
    score = 0.0

    # numeric evidence
    if re.search(r"\d+(\.\d+)?", claim):
        score += 0.3

    # comparison
    if any(k in claim for k in ["higher", "lower", "greater", "less", "more than"]):
        score += 0.25

    # reasoning
    if any(k in claim for k in ["suggests", "indicates", "implies", "due to"]):
        score += 0.2

    # interaction / condition
    if any(k in claim for k in ["while", "whereas", "under", "among", "in"]):
        score += 0.15

    # length
    if 8 <= len(claim.split()) <= 30:
        score += 0.1

    return min(score, 1.0)


def compute_correctness(verified_insights: List[Dict]) -> float:
    if not verified_insights:
        return 0.0

    all_scores = []

    for ins in verified_insights:
        text = ins.get("text", "")
        claims = split_into_claims(text)

        if not claims:
            continue

        claim_scores = [score_claim(c) for c in claims]
        insight_score = sum(claim_scores) / len(claim_scores)
        all_scores.append(insight_score)

    if not all_scores:
        return 0.0

    return sum(all_scores) / len(all_scores)


# =========================================================
# ===== INSIGHTFULNESS (LLM JUDGE) =========================
# =========================================================

def llm_judge_once(insight: str, question: str, supporting=None) -> float:

    support_text = ""
    if supporting:
        support_text = "\nSupporting insights:\n" + "\n".join(
            [s.get("text", "") for s in supporting]
        )

    prompt = f"""
You are an expert evaluator of data insights.

Main question:
{question}

Insight:
{insight}
{support_text}

Evaluate the insight based on:

1. Non-obviousness:
Is it surprising or just a basic trend?

2. Depth:
Does it involve multiple variables or interaction effects?

3. Usefulness:
Does it provide meaningful or actionable implications?

4. Evidence:
Does it include quantitative or comparative support?

Scoring:
Each criterion from 0 to 1.
Final score = average.

Output STRICTLY:
score: X.X
reason: short explanation
"""

    response = call_llm(prompt, 150)

    try:
        score_line = [l for l in response.split("\n") if "score" in l.lower()][0]
        score = float(score_line.split(":")[1].strip())
        return max(0.0, min(score, 1.0))
    except:
        return 0.0


def compute_insightfulness(data: Dict, num_judges: int = 3) -> float:
    insight = data.get("final_insight", "")
    question = data.get("main_question", "")
    supporting = data.get("verified_insights", [])

    if not insight:
        return 0.0

    scores = []

    for _ in range(num_judges):
        s = llm_judge_once(insight, question, supporting)
        if s > 0:
            scores.append(s)

    if not scores:
        return 0.0

    return sum(scores) / len(scores)


# =========================================================
# ===== OBJECTIVE =========================================
# =========================================================

def compute_objective(insightfulness: float, correctness: float, alpha: float = 0.5) -> float:
    if insightfulness == 0 or correctness == 0:
        return 0.0

    return 1.0 / (
        (alpha / insightfulness) +
        ((1 - alpha) / correctness)
    )


# =========================================================
# ===== MAIN ==============================================
# =========================================================

def evaluate(json_path: str, alpha: float = 0.5) -> Dict:
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    correctness = compute_correctness(data.get("verified_insights", []))
    insightfulness = compute_insightfulness(data)
    objective = compute_objective(insightfulness, correctness, alpha)

    return {
        "correctness": round(correctness, 4),
        "insightfulness": round(insightfulness, 4),
        "objective_score": round(objective, 4)
    }


# =========================================================
# ===== RUN ===============================================
# =========================================================

if __name__ == "__main__":
    result = evaluate("pipeline_output.json")

    print("=== EVALUATION RESULT ===")
    print(f"Correctness     : {result['correctness']}")
    print(f"Insightfulness  : {result['insightfulness']}")
    print(f"Final Objective : {result['objective_score']}")