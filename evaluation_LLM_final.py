import json
import random
import requests
from typing import List, Dict
import numpy as np

# ===== CONFIG =====
GITHUB_TOKEN = "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"
API_URL = "https://models.inference.ai.azure.com/chat/completions"
MODEL = "gpt-4o-mini"

K_FACTOR = 16
NUM_MATCHES = 20
BOOTSTRAP_RUNS = 5

TOTAL_CALLS = 0

# ADD: cache
COMPARE_CACHE = {}


# =========================================================
# LLM CALL (SAFE + TIMEOUT)
# =========================================================
def call_llm(prompt, max_tokens=50):
    global TOTAL_CALLS
    TOTAL_CALLS += 1

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
                "temperature": 0.0
            },
            timeout=10 
        )

        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"].strip()
    except:
        pass

    return ""


# =========================================================
# COMPARE (CACHED)
# =========================================================
def compare_insights_cached(a_id, b_id, insight_a, insight_b):

    key = tuple(sorted([a_id, b_id]))

    # 🔥 nếu đã có thì dùng lại
    if key in COMPARE_CACHE:
        return COMPARE_CACHE[key]

    prompt = f"""
You are an expert evaluator.

Insight A:
{insight_a}

Insight B:
{insight_b}

Which insight is MORE insightful?

Answer strictly: A or B
"""

    res = call_llm(prompt).strip().upper()

    if res == "A":
        result = 1
    elif res == "B":
        result = 0
    else:
        result = random.choice([0, 1])

    COMPARE_CACHE[key] = result
    return result


# =========================================================
# CORRECTNESS (giữ nguyên)
# =========================================================
def evaluate_correctness(insight: str) -> float:
    prompt = f"""
Evaluate whether the following insight is FACTUALLY CORRECT.

Insight:
{insight}

Score from 0 to 1.
Return ONLY a number.
"""

    res = call_llm(prompt, max_tokens=10)

    try:
        return max(0, min(1, float(res)))
    except:
        return 0.5


# =========================================================
# ELO CORE
# =========================================================
def elo_expected(ra, rb):
    return 1 / (1 + 10 ** ((rb - ra) / 400))


def elo_update(ra, rb, sa):
    ea = elo_expected(ra, rb)
    ra_new = ra + K_FACTOR * (sa - ea)
    rb_new = rb + K_FACTOR * ((1 - sa) - (1 - ea))
    return ra_new, rb_new


# =========================================================
# RUN ELO USING CACHE
# =========================================================
def run_elo(candidates):

    ratings = {c["id"]: 1000 for c in candidates}

    n = len(candidates)

    matches = [
        tuple(random.sample(range(n), 2))
        for _ in range(NUM_MATCHES)
    ]

    for i, j in matches:
        A = candidates[i]
        B = candidates[j]

        result = compare_insights_cached(
            A["id"], B["id"], A["insight"], B["insight"]
        )

        ra, rb = ratings[A["id"]], ratings[B["id"]]
        new_a, new_b = elo_update(ra, rb, result)

        ratings[A["id"]] = new_a
        ratings[B["id"]] = new_b

    return ratings


# =========================================================
# BOOTSTRAP (NO EXTRA CALLS)
# =========================================================
def bootstrap_elo(candidates):
    all_results = []

    for _ in range(BOOTSTRAP_RUNS):
        ratings = run_elo(candidates)
        all_results.append(ratings)

    return all_results


def summarize_bootstrap(all_results):
    summary = {}

    for k in all_results[0].keys():
        scores = [r[k] for r in all_results]

        summary[k] = {
            "mean": round(np.mean(scores), 2),
            "std": round(np.std(scores), 2)
        }

    return summary

# =========================================================
# MAIN
# =========================================================
def main():
    with open("pipeline_output_multi.json", "r", encoding="utf-8") as f:
        candidates = json.load(f)["candidates"]

    # ===== ELO =====
    all_results = bootstrap_elo(candidates)
    summary = summarize_bootstrap(all_results)

    # ===== CORRECTNESS =====
    correctness = {
        c["id"]: evaluate_correctness(c["insight"])
        for c in candidates
    }

    # format ranking (giống paper)
    ranking = sorted(
        [
            {
                "id": k,
                "elo_mean": summary[k]["mean"],
                "elo_std": summary[k]["std"],
                "correctness": round(correctness[k], 3)
            }
            for k in summary
        ],
        key=lambda x: x["elo_mean"],
        reverse=True
    )

    # ===== SAVE JSON =====
    output = {
        "elo_summary": summary,
        "correctness": correctness,
        "ranking": ranking,
        "total_calls": TOTAL_CALLS
    }

    with open("elo_results.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4, ensure_ascii=False)

    # ===== PRINT =====
    print("\n=== FINAL RANKING ===")
    for r in ranking:
        print(f"{r['id']} | Elo={r['elo_mean']} ± {r['elo_std']} | Corr={r['correctness']}")

    print(f"\nTOTAL CALLS: {TOTAL_CALLS}")


if __name__ == "__main__":
    main()