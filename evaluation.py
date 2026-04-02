import json
import re
from typing import List, Dict

# ===== CORRECTNESS =======
def split_into_claims(text: str):
    """
    Split insight into smaller claims (sentences or clauses)
    """
    # split theo dấu chấm + ; + and
    parts = re.split(r'[.;]|\band\b', text)
    claims = [p.strip() for p in parts if len(p.strip()) > 5]
    return claims


def score_claim(claim: str) -> float:
    """
    Heuristic scoring for each claim
    """
    claim = claim.lower()
    score = 0.0

    # 1. Có quantitative evidence
    if re.search(r"\d+(\.\d+)?", claim):
        score += 0.3

    # 2. Có comparison
    if any(k in claim for k in ["higher", "lower", "greater", "less", "more than"]):
        score += 0.25

    # 3. Có relationship / reasoning
    if any(k in claim for k in ["suggests", "indicates", "implies", "due to"]):
        score += 0.2

    # 4. Có condition / interaction
    if any(k in claim for k in ["while", "whereas", "under", "in", "among"]):
        score += 0.15

    # 5. Length hợp lý
    length = len(claim.split())
    if 8 <= length <= 30:
        score += 0.1

    return min(score, 1.0)


def compute_correctness(verified_insights):
    """
    Claim-based correctness scoring
    """
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

# ===== INSIGHTFULNESS ====
def score_relevance(insight: str, question: str) -> float:
    """
    Simple keyword overlap
    """
    insight_words = set(insight.lower().split())
    question_words = set(question.lower().split())

    overlap = insight_words.intersection(question_words)
    return len(overlap) / (len(question_words) + 1e-6)


def score_specificity(insight: str) -> float:
    """
    Detect presence of quantitative / relational patterns
    """
    patterns = [
        r"increase|decrease|correlate|relationship",
        r"higher|lower|more|less",
        r"\d+%",  # percentage
    ]

    score = sum(bool(re.search(p, insight.lower())) for p in patterns)
    return score / len(patterns)


def score_actionability(insight: str) -> float:
    """
    Detect if insight suggests implication / decision
    """
    keywords = [
        "suggests", "indicates", "implies",
        "need to", "should", "recommend"
    ]
    count = sum(k in insight.lower() for k in keywords)
    return min(count / len(keywords), 1.0)


def score_coherence(insight: str) -> float:
    """
    Penalize too short / too long / messy text
    """
    length = len(insight.split())

    if length < 10:
        return 0.3
    elif length < 40:
        return 1.0
    elif length < 80:
        return 0.7
    else:
        return 0.5


def compute_insightfulness(data: Dict) -> float:
    """
    Weighted combination of proxy metrics
    """
    insight = data.get("final_insight", "")
    main_q = data.get("main_question", "")

    if not insight:
        return 0.0

    relevance = score_relevance(insight, main_q)
    specificity = score_specificity(insight)
    actionability = score_actionability(insight)
    coherence = score_coherence(insight)

    # weights (can tune)
    weights = {
        "relevance": 0.3,
        "specificity": 0.25,
        "actionability": 0.25,
        "coherence": 0.2,
    }

    insightfulness = (
        weights["relevance"] * relevance +
        weights["specificity"] * specificity +
        weights["actionability"] * actionability +
        weights["coherence"] * coherence
    )

    return insightfulness

# ===== OBJECTIVE =========
def compute_objective(insightfulness: float, correctness: float, alpha: float = 0.5) -> float:
    """
    Harmonic mean (paper)
    """
    if insightfulness == 0 or correctness == 0:
        return 0.0

    return 1.0 / (
        (alpha / insightfulness) +
        ((1 - alpha) / correctness)
    )


# ===== MAIN PIPELINE =====
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

# ===== RUN ===============
if __name__ == "__main__":
    result = evaluate("pipeline_output.json")

    print("=== EVALUATION RESULT ===")
    print(f"Correctness     : {result['correctness']}")
    print(f"Insightfulness  : {result['insightfulness']}")
    print(f"Final Objective : {result['objective_score']}")