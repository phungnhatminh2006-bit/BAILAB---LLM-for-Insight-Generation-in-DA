# **BAILAB SOTA -- LLM for Insight Generation in DA**
This project reconstructs and extends the framework proposed in the paper:

**“An LLM-Based Approach for Insight Generation in Data Analysis”**

The goal is to build a cost-efficient, modular, and scalable pipeline that automatically generates actionable insights from structured databases using Large Language Models (LLMs).

Unlike traditional data analysis workflows, this system:
- Eliminates manual exploration
- Works on multi-table databases
- Produces human-readable insights (≤ 3 sentences)
- Balances insightfulness and correctness

## Core Idea
Instead of directly generating insights from data, the system follows a multi-step reasoning pipeline:
- Generate high-level analytical questions
- Decompose into SQL-executable subquestions
- Execute queries via an agent
- Aggregate results into natural language insights

## Architecture:

<img width="1192" height="507" alt="image" src="https://github.com/user-attachments/assets/a6c72fca-a2f8-486d-95f9-07adcd717dec" />

**Structured Reasoning Pipeline**

The architecture follows a multi-step reasoning process:
`
LLM → Questions → SQL → Answers → Insight
`
- Decomposes complex analysis into smaller tasks
- Mimics human analytical workflows
- Produces deeper and more meaningful insights than direct LLM generation

**Proposed Architecture:**

<img width="1176" height="520" alt="image" src="https://github.com/user-attachments/assets/a2b1ea5a-876d-42ea-8d33-75b3c852d6a5" />

**1 - High-Level Generator (HL-G)**
- Input: Short DB description
- Output: Big question (abstract, exploratory)
  
**2 - Low-Level Generator (LL-G)**
- Input: High-level question + Full schema + data info
- Output: Sub-question, SQL-able

**3 - Query Agent**
- Generate SQL: Question → SQL
- Execute Query: SQL → Result Table
- Verbalize: Table → text
- LLM filter: eliminate noise before summarize

**4 - Summarization**
- Aggregate
- Generate Insight
- Hallucination Detector
- Reflection loop: a sub-process within Summarization, with goal to refine the insight

## Project Structure
```text
.
├── data/                  # Sample databases
├── prompts/               # Prompt templates
├── pipeline/
│   ├── hypothesis.py
│   ├── query_agent.py
│   ├── summarizer.py
│   └── reflection.py
├── evaluation/
│   ├── insightfulness.py
│   └── correctness.py
├── main.py
└── README.md
```

## Evaluation
**1 - Correctness:**
Correctness measures whether an insight is factually supported by the data. 
Each insight is decomposed into a set of claims $𝐶𝑖$, where each claim has a truth value $𝑇𝑉(𝐶𝑖)∈{0,1}$

$$
\text{Correctness}(I) = \frac{1}{n} \sum_{i=1}^{n} TV(C_i)
$$

**2 - Insightful:** Insightfulness evaluates the quality and usefulness of an insight for a user $𝑈$.
It is defined as a weighted combination of subjective metrics such as: actionability, relevance, novelty

$$
\text{Insightfulness}(I, U) =
\frac{\sum_{i=0}^{n} w_i \cdot M_i(I, U)}{\sum_{i=0}^{n} w_i}
$$

**3 - Objective Function:** The final objective balances both correctness and insightfulness using a weighted harmonic mean:

$$
O = \max \left( \frac{1}{\frac{\alpha}{\text{Insightfulness}} + \frac{1 - \alpha}{\text{Correctness}}} \right)
$$

where $𝛼∈[0,1]$ controls the trade-off between the two metrics $(default: 𝛼=0.5)$



## Limitation:
- The pipeline requires multiple LLM calls (question generation, SQL generation, summarization, reflection), leading to increased cost and latency. This project choose free API tokens from Github, a free solution, but with trade-offs including rate limits, limited scalability, and potential instability in production environments.
- Performance may degrade when handling complex or large databases due to schema size and context limitations.
- Insight quality is measured using human judgment or preference-based ranking, making it difficult to standardize and reproduce.
- Although mitigation mechanisms exist, some incorrect or unsupported claims may still remain in the final insights.

