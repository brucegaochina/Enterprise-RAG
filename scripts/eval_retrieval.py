"""Retrieval evaluation: Hit@1, Hit@5 and MRR for vector, keyword and hybrid search
on a small golden set. Run against a server with the sample documents indexed:

    python scripts/eval_retrieval.py [--url http://localhost:8000]
"""

from __future__ import annotations

import argparse

import httpx

# (question, expected document filename prefix)
GOLDEN_SET = [
    ("Does my plan cover annual eye exams?", "02_health_benefits_guide"),
    ("How much does Helios pay for hearing aids?", "02_health_benefits_guide"),
    ("How many vacation days do I get after 4 years at the company?", "03_pto_and_holidays_policy"),
    ("What is the nightly hotel limit in San Francisco?", "04_travel_and_expense_policy"),
    ("Can I fly business class to Singapore?", "04_travel_and_expense_policy"),
    ("How much is the home office stipend?", "05_remote_and_hybrid_work_policy"),
    ("Is SMS allowed as a second factor for login?", "06_information_security_policy"),
    ("Can I paste customer data into ChatGPT?", "07_acceptable_use_policy"),
    ("What is the maximum value of gifts I can accept from a vendor?", "08_code_of_conduct"),
    ("Which trainings must new employees finish in their first month?", "09_new_hire_onboarding_guide"),
    ("What is the target bonus for a director?", "10_performance_review_process"),
    ("How does the 401k company match work?", "11_401k_retirement_plan"),
    ("How long is paid leave for a new father?", "12_parental_and_family_leave"),
    ("Which Wi-Fi should I use in the office?", "13_it_helpdesk_faq"),
    ("How long do we keep Slack messages?", "14_data_retention_and_privacy"),
    ("How many quotes do I need for a $20,000 purchase?", "15_procurement_and_vendor_policy"),
    ("RB-SEC-007 SEV2 response time", "16_security_incident_response_runbook"),
    ("HX-220 offline storage", "17_product_catalog_2026"),
    ("What service credit do we owe if uptime drops below 99%?", "18_customer_support_sla"),
    ("What was EMEA revenue in Q3?", "19_q3_2026_business_review"),
    ("Does Helios pay for my AWS certification exam?", "20_learning_and_development_program"),
    ("form COI-1", "08_code_of_conduct"),
]


def evaluate(client: httpx.Client, mode: str, top_k: int = 5) -> dict:
    hits1 = hits5 = 0
    rr_sum = 0.0
    misses = []
    for question, expected in GOLDEN_SET:
        resp = client.post("/api/search", json={"query": question, "mode": mode, "top_k": top_k})
        resp.raise_for_status()
        files = [r["filename"] for r in resp.json()["results"]]
        rank = next((i for i, f in enumerate(files, 1) if f.startswith(expected)), None)
        if rank == 1:
            hits1 += 1
        if rank:
            hits5 += 1
            rr_sum += 1 / rank
        else:
            misses.append(question)
    n = len(GOLDEN_SET)
    return {"mode": mode, "hit@1": hits1 / n, f"hit@{top_k}": hits5 / n, "mrr": rr_sum / n, "misses": misses}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    args = parser.parse_args()

    with httpx.Client(base_url=args.url, timeout=60) as client:
        health = client.get("/api/health").json()
        print(f"Embeddings: {health['embedding_model']} | {health['ready']} documents | {health['chunks']} chunks")
        print(f"Golden set: {len(GOLDEN_SET)} questions\n")
        print(f"{'mode':<10}{'Hit@1':>8}{'Hit@5':>8}{'MRR':>8}")
        results = [evaluate(client, mode) for mode in ("vector", "keyword", "hybrid")]
        for r in results:
            print(f"{r['mode']:<10}{r['hit@1']:>8.2f}{r['hit@5']:>8.2f}{r['mrr']:>8.2f}")
        for r in results:
            if r["misses"]:
                print(f"\n{r['mode']} misses (not in top 5):")
                for q in r["misses"]:
                    print(f"  - {q}")


if __name__ == "__main__":
    main()
