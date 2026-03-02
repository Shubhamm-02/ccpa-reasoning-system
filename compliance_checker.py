"""
CCPA Compliance Checker
=========================================
Core compliance layer that acts as the entry point for legal reasoning.

It applies a lightweight, rule-based heuristic layer to catch obvious
CCPA violations directly before falling back to the LLM-based reasoning
engine. This saves expensive LLM inference time on clear-cut cases.

Usage:
    python compliance_checker.py
    from compliance_checker import check_compliance
"""

from reasoning import analyze_prompt, retriever


# ---------------------------------------------------------------------------
# Pre-defined heuristic rules
# Maps specific toxic phrases to the CCPA sections they likely violate.
# ---------------------------------------------------------------------------
HEURISTICS = {
    # Existing rules
    "sell data without consent": ["Section 1798.120", "Section 1798.135"],
    "without notifying users": ["Section 1798.130", "Section 1798.100"],
    "ignore deletion request": ["Section 1798.105"],
    "deny opt-out": ["Section 1798.120", "Section 1798.135"],
    "charge higher price for privacy users": ["Section 1798.125"],
    
    # New high-confidence rules
    "sell personal data of 14-year-old": ["Section 1798.120"],
    "sell personal data of 15-year-old": ["Section 1798.120"],
    "sell personal data of 16-year-old without opt in": ["Section 1798.120"],
    "waive ccpa rights in contract": ["Section 1798.192"],
    "no do not sell link": ["Section 1798.135"],
    "retain data forever": ["Section 1798.100"],
}


def check_compliance(prompt: str) -> dict:
    """
    Check if a business practice complies with the CCPA.

    Uses a fast rule-based check first. If unambiguous keywords are found,
    it verifies them against the semantic retrieval results. Otherwise,
    it falls back to the full LLM reasoning engine.

    Parameters
    ----------
    prompt : str
        Description of the business practice.

    Returns
    -------
    dict
        {"harmful": bool, "articles": list}
    """
    try:
        lower_prompt = prompt.lower()

        # Step 1: Lightweight rule-based check
        for phrase, target_sections in HEURISTICS.items():
            if phrase in lower_prompt:
                # We found a toxic phrase. Let's see if the semantic retrieve
                # actually brings up the relevant sections to confirm context.
                # (Re-uses the globally loaded retriever from reasoning.py)
                retrieved = retriever.retrieve_sections(prompt, top_k=5)
                retrieved_titles = {name for name, _ in retrieved}

                # Find the intersection between hardcoded targets and retrieved context
                matched_articles = [
                    sec for sec in target_sections if sec in retrieved_titles
                ]

                # If the heuristic matches AND the retrieval system agrees it's
                # in context, short-circuit the LLM and return immediately.
                if matched_articles:
                    return {
                        "harmful": True,
                        "articles": matched_articles
                    }

        # Step 2: Fallback to LLM reasoning
        response = analyze_prompt(prompt)

        # Step 3: Ensure strict format
        if not isinstance(response, dict):
            return {"harmful": False, "articles": []}
            
        harmful = bool(response.get("harmful", False))
        articles = response.get("articles", [])
        
        if not isinstance(articles, list):
            articles = []

        return {
            "harmful": harmful,
            "articles": articles
        }

    except Exception as e:
        # Step 4: Graceful failure
        print(f"Compliance check failed: {e}")
        return {"harmful": False, "articles": []}


# ---------------------------------------------------------------------------
# CLI test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    test_cases = [
        # 1. Harmful case (should hit the heuristic: "without notifying users")
        "We sell customer data without notifying users directly.",
        
        # 2. Safe case (should bypass heuristic, go to LLM, and return safe)
        "We use a consumer's billing address solely to ship the product they ordered."
    ]

    print("=" * 60)
    print("TESTING COMPLIANCE CHECKER")
    print("=" * 60)

    for i, test_prompt in enumerate(test_cases, 1):
        print(f"\n[Scenario {i}]")
        print(f"Prompt: \"{test_prompt}\"")
        res = check_compliance(test_prompt)
        print(f"Result: {res}")
        print("-" * 60)
