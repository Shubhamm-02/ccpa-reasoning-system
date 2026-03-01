# CCPA Compliance System — Project Summary

## Overview

A two-stage system that parses the California Consumer Privacy Act (CCPA) statute from PDF and enables semantic search over its legal sections.

---

## Stage 1: PDF Parsing → `ccpa_sections.json`

**Script:** [parse_statute.py](file:///Users/wizard/Desktop/ccpa%20hackathon/%20parse_statute.py)

### What It Does

Extracts all 45 legal sections (`Section 1798.xxx`) from `ccpa_statute.pdf` and saves them as a clean JSON file.

### How It Works

| Step | Description |
|------|-------------|
| **Extract** | Pulls raw text from all 65 pages using PyMuPDF (`fitz`) |
| **Clean** | Removes `Page X of Y` headers, normalizes whitespace |
| **TOC Parse** | Reads the Table of Contents to build an authoritative set of valid section numbers |
| **TOC Strip** | Removes the TOC so its entries don't create false header matches |
| **Boundaries** | Detects section headers via regex `^(1798.\d+(?:\.\d+)?)\.\s`, validated against the TOC set |
| **Filter** | Two filters eliminate false positives from inline cross-references: (1) skip if previous line ends with "Section", (2) skip duplicate section numbers that are just subdivision markers |
| **Post-process** | Final whitespace cleanup on section bodies |

### Key Design Decision

The biggest challenge was distinguishing **real section headers** from **inline cross-references** (e.g., `1798.185.` appearing on its own line after a page break inside Section 1798.135). Two filters handle this:

1. **Line-wrap filter** — If the previous line ends with "Section" or "Sections", the match is at a cross-reference split across lines, not a real header.
2. **Duplicate filter** — When a TOC-valid section number appears a second time, it's only accepted if it has a descriptive title (not just a subdivision marker like `(a)`).

### Accuracy Audit

- ✅ **45 sections** extracted, matching all 45 TOC entries
- ✅ All sections in correct numeric order
- ✅ No truncated endings (every section ends at a sentence boundary)
- ✅ No cross-contamination between sections

---

## Stage 2: Semantic Retrieval → `retrieval.py`

**Script:** [retrieval.py](file:///Users/wizard/Desktop/ccpa%20hackathon/retrieval.py)

### What It Does

Embeds all 45 CCPA sections using `all-MiniLM-L6-v2` and indexes them in FAISS for natural-language search.

### How It Works

| Component | Detail |
|-----------|--------|
| **Model** | `sentence-transformers/all-MiniLM-L6-v2` (384-dim) |
| **Index** | FAISS `IndexFlatIP` — exact cosine similarity via L2-normalized inner product |
| **Embeddings** | Precomputed once at init, L2-normalized before indexing |
| **API** | `retrieve_sections(query, top_k=5)` → list of `(section_name, full_text)` tuples |

### Usage

```python
# As CLI
python retrieval.py

# As library
from retrieval import CCPARetriever
retriever = CCPARetriever()
results = retriever.retrieve_sections("your query here", top_k=3)
```

### Stress Test Results (10 adversarial queries)

| # | Query | Top-1 | Result |
|---|-------|-------|--------|
| 1 | "privacy" (single word) | 1798.175 — Conflicting Provisions | ✅ |
| 2 | "definition of personal information" | 1798.115 | ❌ |
| 3 | "penalties for violating CCPA" | 1798.199.90 — Administrative Fines | ✅ |
| 4 | "sell a 14 year old child's data" | 1798.120 — Opt Out of Sale | ✅ |
| 5 | "employee records and HR data" | 1798.148 | ❌ |
| 6 | "data breach" | 1798.150 — Security Breaches | ✅ |
| 7 | "what data we collected about them" | 1798.110 — Right to Know | ✅ |
| 8 | "biometric data without consent" | 1798.140 — Definitions | ✅ |
| 9 | "service provider obligations" | 1798.145 — Exemptions | ✅ |
| 10 | "waive CCPA rights in a contract" | 1798.192 — Waiver | ✅ |

**Score: 8/10**

### Known Limitation

Tests 2 and 5 fail because `Section 1798.140` (Definitions, 32K chars) and `Section 1798.145` (Exemptions, 27K chars) are too long for a single 384-dim embedding to capture. The embedding gets diluted across dozens of distinct concepts. This can be addressed later with hardcoded fallbacks or chunk-based encoding on a machine with more RAM.

---

## File Structure

```
ccpa hackathon/
├── ccpa_statute.pdf          # Source PDF (65 pages)
├── parse_statute.py          # Stage 1: PDF → JSON
├── ccpa_sections.json        # Extracted sections (45 entries)
├── retrieval.py              # Stage 2: Semantic search
└── venv/                     # Python virtual environment
```

## Dependencies

```
PyMuPDF (fitz)
sentence-transformers
faiss-cpu
numpy
```
