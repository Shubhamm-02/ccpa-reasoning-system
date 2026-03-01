# CCPA Compliance Reasoning System

A hackathon project that parses the California Consumer Privacy Act (CCPA) from a PDF, indexes its sections for semantic retrieval, and actively reasons over business practices using a local LLM (Mistral-7B).

## What's included
- **`parse_statute.py`**: Extracts the 45 legal sections from the raw `ccpa_statute.pdf`.
- **`ccpa_sections.json`**: The extracted sections (you don't strictly need to re-run the parser unless this file is deleted).
- **`retrieval.py`**: Uses `sentence-transformers` and `faiss-cpu` to index sections and perform natural language semantic search.
- **`reasoning.py`**: Uses `llama-cpp-python` and a local Mistral 7B model to evaluate business scenarios against the retrieved CCPA sections, outputting strict JSON compliance judgements.

## Setup Instructions

### 1. Python Environment
Requires Python 3.9+ (3.11 recommended).
```bash
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Download the LLM Model
The reasoning engine uses a quantized Mistral 7B model. You need to download the `.gguf` file to a `models/` directory in the project root.

```bash
# First, ensure you have the models directory
mkdir -p models

# Download using huggingface-cli (included in requirements.txt)
huggingface-cli download TheBloke/Mistral-7B-Instruct-v0.2-GGUF \
  mistral-7b-instruct-v0.2.Q4_K_M.gguf \
  --local-dir models
```
*(Note: This is a ~4.4GB download and may take a few minutes).*

### 3. Verify the Installation
Run the two test scripts to confirm everything is working:

**Test the Semantic Retriever:**
```bash
python retrieval.py
```
*(You should see it retrieve sections relating to selling user data.)*

**Test the Reasoning Engine:**
```bash
python reasoning.py
```
*(This will run 6 diverse test scenarios through the local Mistral model. It might take 10-20 seconds to load the model into RAM for the first time.)*
