"""
Final Verification Test Sweep
=============================
Runs a comprehensive sweep of the compliance checker on diverse edge cases.
"""

from compliance_checker import check_compliance

TEST_CASES = [
    # --- Compliant Scenarios (Should be False) ---
    ("We process payment information solely to complete the user's transaction.", False),
    ("We check IP addresses briefly to prevent DDoS attacks and fraud.", False),
    ("We offer a loyalty program where users get discounts in exchange for an email address.", False),
    
    # --- Heuristic Non-Compliant Scenarios (Should be True) ---
    ("We sell personal data of 15-year-old users to third parties.", True),
    ("Our data broker website has no do not sell link anywhere.", True),
    ("Users must waive ccpa rights in our contract before using the site.", True),
    
    # --- LLM Non-Compliant Scenarios (Should be True) ---
    ("We share users' precise geolocation with third-party advertisers without telling them.", True),
    ("We charge a 20% fee to process consumer deletion requests.", True),
    ("If a user opts out of data selling, we throttle their app speed to 2G.", True),
    
    # --- Ambiguous Scenario (Expected True based on strictness) ---
    ("We sell customer biometric data without consent.", True)
]

def main():
    print("======================================================")
    print("FINAL ACCURACY SWEEP")
    print("======================================================")
    
    passed = 0
    
    for i, (prompt, expected_harmful) in enumerate(TEST_CASES, 1):
        print(f"\n[Case {i}] {prompt}")
        print(f"Expected Harmful: {expected_harmful}")
        
        result = check_compliance(prompt)
        actual_harmful = result.get("harmful", False)
        
        print(f"Actual Harmful:   {actual_harmful}  (Sections: {result.get('articles', [])})")
        
        if actual_harmful == expected_harmful:
            print("Status: ✅ PASS")
            passed += 1
        else:
            print("Status: ❌ FAIL")
            
        print("-" * 54)
        
    print(f"\nSummary: {passed}/{len(TEST_CASES)} tests passed.")

if __name__ == "__main__":
    main()
