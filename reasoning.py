"""
CCPA Constrained Legal Reasoning Module
=========================================
Uses a local Llama 3 8B (GGUF) model via llama-cpp-python to analyze
business practices against retrieved CCPA statute sections.

The model is loaded once at module level and reused across calls.

Usage:
    python reasoning.py                          # runs built-in test
    from reasoning import analyze_prompt         # use as a library
"""

import json
import re
from llama_cpp import Llama
from retrieval import CCPARetriever

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MODEL_PATH = "models/Meta-Llama-3-8B-Instruct-Q4_K_M.gguf"

# ---------------------------------------------------------------------------
# Module-level singletons — loaded once on first import
# ---------------------------------------------------------------------------
print("Loading Llama model (this may take a moment)...")
llm = Llama(
    model_path=MODEL_PATH,
    n_ctx=4096,       # context window large enough for legal text
    n_threads=4,      # adjust to your CPU core count
    verbose=False,
)
print("Llama model loaded.")

print("Initialising retriever...")
retriever = CCPARetriever()


# ---------------------------------------------------------------------------
# Core analysis function
# ---------------------------------------------------------------------------
def analyze_prompt(prompt: str) -> dict:
    """
    Analyse a business-practice description for CCPA compliance.

    Steps:
      1. Retrieve the top-5 most relevant CCPA sections.
      2. Build a strict instruction prompt with the retrieved text.
      3. Call the LLM with constrained decoding.
      4. Parse and validate the JSON output.
      5. Filter articles to only those actually retrieved.

    Parameters
    ----------
    prompt : str
        A plain-English description of a business practice.

    Returns
    -------
    dict
        {
          "harmful": bool,
          "articles": ["Section 1798.xxx", ...]
        }
    """

    # ── Step 1: Retrieve relevant sections ──────────────────────────────
    retrieved = retriever.retrieve_sections(prompt, top_k=5)
    valid_titles = {name for name, _ in retrieved}

    # Build the legal context block
    context_parts: list[str] = []
    for name, text in retrieved:
        # Truncate very long sections to stay within context window
        truncated = text[:2000] if len(text) > 2000 else text
        context_parts.append(f"### {name}\n{truncated}")

    legal_context = "\n\n".join(context_parts)

    # ── Step 2: Construct the instruction prompt ────────────────────────
    instruction = f"""[INST]
You are a CCPA compliance analyst. You will be given a business practice and relevant CCPA sections.

STRICT RULES:
- ONLY use the sections provided below. Do NOT invent section numbers.
- If the practice violates any provided section, set "harmful" to true and list the violated section titles in "articles".
- If you are unsure or the practice does not clearly violate any section, set "harmful" to false.
- Output ONLY valid JSON. No explanations, no extra text.

OUTPUT FORMAT (nothing else):
{{"harmful": true/false, "articles": ["Section 1798.xxx", ...]}}

BUSINESS PRACTICE:
{prompt}

RELEVANT CCPA SECTIONS:
{legal_context}

Respond with ONLY the JSON object.
[/INST]
"""

    # ── Step 3: Call the model ──────────────────────────────────────────
    try:
        response = llm(
            instruction,
            max_tokens=300,
            temperature=0.1,
            stop=["}"],          # stop right after the closing brace
            echo=False,
        )
        raw_output = response["choices"][0]["text"].strip() + "}"
    except Exception:
        return {"harmful": False, "articles": []}

    # ── Step 4: Parse the JSON output ───────────────────────────────────
    try:
        # Extract the first JSON object from the output
        match = re.search(r"\{.*\}", raw_output, re.DOTALL)
        if not match:
            return {"harmful": False, "articles": []}
        result = json.loads(match.group())
    except (json.JSONDecodeError, ValueError):
        return {"harmful": False, "articles": []}

    # Normalise the result structure
    harmful = bool(result.get("harmful", False))
    articles = result.get("articles", [])

    if not isinstance(articles, list):
        articles = []

    # ── Step 5: Filter articles to only retrieved sections ──────────────
    filtered_articles = []
    for a in articles:
        # Check if the returned article matches or starts with a valid title
        # E.g., matching "Section 1798.135" from LLM output "Section 1798.135.a"
        for title in valid_titles:
            if title in a or a in title:
                if title not in filtered_articles:
                    filtered_articles.append(title)

    # If nothing survived filtering, default to safe
    if not filtered_articles:
        return {"harmful": False, "articles": []}

    return {"harmful": harmful, "articles": filtered_articles}


