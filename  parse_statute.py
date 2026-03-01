"""
CCPA Statute PDF Parser
========================
Extracts all legal sections (Section 1798.xxx) from the CCPA statute PDF
and outputs them as a structured JSON file.

Usage: python parse_statute.py
Output: ccpa_sections.json
"""

import fitz  # PyMuPDF
import re
import json

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
PDF_PATH = "ccpa_statute.pdf"
OUTPUT_PATH = "ccpa_sections.json"

# ---------------------------------------------------------------------------
# Step 1: Extract raw text from the PDF
# ---------------------------------------------------------------------------
def extract_text_from_pdf(path: str) -> str:
    """Open the PDF with PyMuPDF and concatenate text from every page."""
    doc = fitz.open(path)
    pages: list[str] = []
    for page in doc:
        pages.append(page.get_text())
    doc.close()
    return "\n".join(pages)


# ---------------------------------------------------------------------------
# Step 2: Clean extracted text
# ---------------------------------------------------------------------------
def clean_text(raw: str) -> str:
    """
    Remove artefacts that interfere with section detection:
      - Page headers like 'Page X of Y'
      - Excessive blank lines and trailing whitespace
    """
    # Remove page-number headers (e.g. "Page 1 of 65")
    text = re.sub(r"Page\s+\d+\s+of\s+\d+\s*", "", raw)

    # Collapse runs of 3+ newlines into two (paragraph break)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Strip trailing spaces on every line
    text = "\n".join(line.rstrip() for line in text.split("\n"))

    return text


# ---------------------------------------------------------------------------
# Step 3: Extract valid section numbers from the Table of Contents
# ---------------------------------------------------------------------------

# Regex to match TOC entries: "1798.xxx.  Title .............. page"
TOC_ENTRY_RE = re.compile(r"(1798\.\d+(?:\.\d+)?)\.?\s+.*?\.{4,}")

# Regex for section-number-only TOC entries (sections without visible title)
TOC_ENTRY_BARE_RE = re.compile(r"^(1798\.\d+(?:\.\d+)?)\.\s*\.{4,}", re.MULTILINE)


def extract_toc_section_numbers(text: str) -> set[str]:
    """
    Parse the Table of Contents to build a set of valid section numbers.
    The TOC is the authoritative source for which sections exist.
    TOC entries have dot-leaders (.....) which distinguish them from body text.
    """
    valid: set[str] = set()
    lines = text.split("\n")

    # First, find the TOC region: it spans from the first line with
    # dot-leaders to the last line with dot-leaders.
    toc_start = toc_end = -1
    for i, line in enumerate(lines):
        if re.search(r"\.{4,}", line):
            if toc_start == -1:
                toc_start = i
            toc_end = i

    if toc_start == -1:
        return valid  # No TOC found

    # Scan the TOC region for all section numbers.  Some TOC entries
    # wrap over two lines (title is too long), so the section number
    # may be on a line that does NOT contain dot-leaders.
    for i in range(max(0, toc_start - 2), toc_end + 1):
        m = re.match(r"\s*(1798\.\d+(?:\.\d+)?)\.", lines[i])
        if m:
            valid.add(m.group(1))

    return valid


# ---------------------------------------------------------------------------
# Step 4: Remove the Table of Contents from text
# ---------------------------------------------------------------------------
def remove_toc(text: str) -> str:
    """
    Strip the TOC section so its entries aren't mistaken for section headers.
    TOC entries contain dot-leaders (.....) — we find the last one and
    return everything after it.
    """
    lines = text.split("\n")
    last_toc_line = -1
    for i, line in enumerate(lines):
        if re.search(r"\.{4,}", line):
            last_toc_line = i

    if last_toc_line == -1:
        return text

    return "\n".join(lines[last_toc_line + 1 :])


# ---------------------------------------------------------------------------
# Step 5: Locate section boundaries using TOC-validated section numbers
# ---------------------------------------------------------------------------

# Matches lines starting with a section number followed by a period and space.
# Examples:   1798.100.  General Duties...
#             1798.199.65.  The agency may ...
#             1798.146.  (starts with subsection on same line)
SECTION_HEADER_RE = re.compile(
    r"^(1798\.\d+(?:\.\d+)?)\.\s",
    re.MULTILINE,
)


def find_section_boundaries(
    text: str, valid_sections: set[str]
) -> list[tuple[str, int]]:
    """
    Scan the body text for section headers and return only those whose
    section number appears in the Table of Contents.  This filters out
    inline cross-references that happen to land at the start of a line
    (e.g. '1798.185.' appearing inside Section 1798.135's body).
    """
    boundaries: list[tuple[str, int]] = []
    seen_at: dict[str, int] = {}  # track first occurrence of each section

    for match in SECTION_HEADER_RE.finditer(text):
        sec_num = match.group(1)

        # Only keep matches whose section number is listed in the TOC
        if sec_num not in valid_sections:
            continue

        # ── Filter 1: Inline cross-references split across lines ────────
        # PDF text extraction can wrap "Section 1798.185." so that
        # "Section" ends one line and "1798.185." starts the next.
        # Detect this by checking if the previous line ends with
        # "Section" or "Sections".
        prev_nl = text.rfind("\n", 0, match.start())
        if prev_nl > 0:
            prev_line_start = text.rfind("\n", 0, prev_nl) + 1
            prev_line = text[prev_line_start:prev_nl].strip()
            if prev_line.endswith("Section") or prev_line.endswith("Sections"):
                continue

        # ── Filter 2: Duplicate section numbers ─────────────────────────
        # For sections that appear more than once, keep only the FIRST
        # occurrence that looks like a real header (has a title or is
        # the first time we see it).  Inline refs that survived
        # Filter 1 but duplicate a section number are caught here.
        rest_of_line = text[match.end() : text.find("\n", match.end())].strip()

        if sec_num in seen_at:
            # Second occurrence — only keep if it has a descriptive title
            # (not just a subdivision marker like "(a)" or "(3)")
            if re.match(r"^\([a-zA-Z0-9]+\)$", rest_of_line):
                continue
            # Also skip if the rest is very short and looks like a
            # cross-reference continuation
            if len(rest_of_line) < 5 and not re.match(r"^[A-Z]", rest_of_line):
                continue

        boundaries.append((sec_num, match.start()))
        if sec_num not in seen_at:
            seen_at[sec_num] = match.start()

    return boundaries


# ---------------------------------------------------------------------------
# Step 6: Extract section bodies
# ---------------------------------------------------------------------------
def extract_sections(
    text: str, boundaries: list[tuple[str, int]]
) -> dict[str, str]:
    """
    Slice the text between consecutive section boundaries.
    Each section runs from its header to just before the next header.
    The last section runs to the end of the document.
    """
    sections: dict[str, str] = {}

    for i, (sec_num, start) in enumerate(boundaries):
        # Determine where this section ends
        if i + 1 < len(boundaries):
            end = boundaries[i + 1][1]
        else:
            end = len(text)

        body = text[start:end].strip()

        # Collapse multiple consecutive spaces
        body = re.sub(r" {2,}", " ", body)

        key = f"Section {sec_num}"

        # If the same section number already appeared, append (safety net)
        if key in sections:
            sections[key] += "\n" + body
        else:
            sections[key] = body

    return sections


# ---------------------------------------------------------------------------
# Step 7: Post-process section text
# ---------------------------------------------------------------------------
def postprocess(sections: dict[str, str]) -> dict[str, str]:
    """
    Final cleanup pass on each section body:
      - Remove any stray page headers that survived earlier cleaning
      - Normalize internal whitespace
    """
    cleaned: dict[str, str] = {}
    for key, body in sections.items():
        # Remove any remaining page headers
        body = re.sub(r"Page\s+\d+\s+of\s+\d+\s*", "", body)
        # Collapse excessive blank lines within a section
        body = re.sub(r"\n{3,}", "\n\n", body)
        body = body.strip()
        cleaned[key] = body
    return cleaned


# ---------------------------------------------------------------------------
# Main execution
# ---------------------------------------------------------------------------
def main() -> None:
    # 1 — Extract raw text
    print("Extracting text from PDF...")
    raw_text = extract_text_from_pdf(PDF_PATH)
    print(f"  Raw text length: {len(raw_text):,} characters")

    # 2 — Clean text (remove page headers, normalize whitespace)
    text = clean_text(raw_text)

    # 3 — Extract valid section numbers from TOC before removing it
    valid_sections = extract_toc_section_numbers(text)
    print(f"  TOC contains {len(valid_sections)} section numbers")

    # 4 — Remove TOC so its entries don't interfere
    body = remove_toc(text)

    # 5 — Find section headers (validated against TOC)
    boundaries = find_section_boundaries(body, valid_sections)
    print(f"  Detected {len(boundaries)} section boundaries")

    # 6 — Extract section bodies
    sections = extract_sections(body, boundaries)

    # 7 — Post-process
    sections = postprocess(sections)

    print(f"\nTotal sections extracted: {len(sections)}")

    # 8 — Save to JSON
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(sections, f, indent=2, ensure_ascii=False)
    print(f"Saved to {OUTPUT_PATH}")

    # 9 — Verification: print first 3 section titles and previews
    print("\n" + "=" * 60)
    print("VERIFICATION — First 3 sections:")
    print("=" * 60)
    for i, (title, body) in enumerate(sections.items()):
        if i >= 3:
            break
        print(f"\n[{title}]")
        print(body[:300])
        print("..." if len(body) > 300 else "")
        print("-" * 50)


if __name__ == "__main__":
    main()