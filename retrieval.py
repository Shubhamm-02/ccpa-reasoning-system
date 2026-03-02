"""
CCPA Semantic Retrieval System
===============================
Embeds all CCPA statute sections using sentence-transformers and indexes
them with FAISS for fast, semantic top-k retrieval.

Usage:
    python retrieval.py                  # runs the built-in demo query
    from retrieval import CCPARetriever  # use as a library
"""

import json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SECTIONS_PATH = "ccpa_sections.json"
MODEL_NAME = "all-MiniLM-L6-v2"


# ---------------------------------------------------------------------------
# Retriever class — encapsulates embedding, indexing, and querying
# ---------------------------------------------------------------------------
class CCPARetriever:
    """
    Precomputes normalised embeddings for every CCPA section, stores them
    in a FAISS inner-product index, and exposes a `retrieve_sections`
    method for semantic search.
    """

    def __init__(
        self,
        sections_path: str = SECTIONS_PATH,
        model_name: str = MODEL_NAME,
    ) -> None:
        # Step 1 — Load the JSON mapping of section titles → legal text
        print("Loading CCPA sections...")
        with open(sections_path, "r", encoding="utf-8") as f:
            self.sections: dict[str, str] = json.load(f)

        # Maintain an ordered mapping so FAISS index positions correspond
        # to section names deterministically.
        self.section_names: list[str] = list(self.sections.keys())
        self.section_texts: list[str] = list(self.sections.values())

        print(f"  Loaded {len(self.section_names)} sections")

        # Step 2 — Load the sentence-transformer model
        print(f"Loading embedding model ({model_name})...")
        self.model = SentenceTransformer(model_name)

        # Step 3 — Compute embeddings for all sections (done once)
        print("Computing section embeddings...")
        self.embeddings = self._embed_sections()

        # Step 4 — Build the FAISS index
        print("Building FAISS index...")
        self.index = self._build_index()

        print("Retriever ready.\n")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _embed_sections(self) -> np.ndarray:
        """
        Encode every section's text into a dense vector.

        Returns an (N, D) float32 array of L2-normalised embeddings,
        where N = number of sections and D = embedding dimensionality.
        """
        embeddings = self.model.encode(
            self.section_texts,
            show_progress_bar=True,
            convert_to_numpy=True,
            normalize_embeddings=True,  # L2-normalise so cosine ≈ inner product
        )
        return embeddings.astype(np.float32)

    def _build_index(self) -> faiss.IndexFlatIP:
        """
        Create a FAISS flat inner-product index from the precomputed
        embeddings.  Because vectors are already L2-normalised,
        inner product equals cosine similarity.
        """
        dim = self.embeddings.shape[1]
        index = faiss.IndexFlatIP(dim)  # inner-product index
        index.add(self.embeddings)      # add all section vectors
        return index

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def retrieve_sections(
        self, query: str, top_k: int = 5
    ) -> list[tuple[str, str]]:
        """
        Retrieve the *top_k* most semantically relevant CCPA sections
        for the given natural-language query.

        Parameters
        ----------
        query : str
            A plain-English question or statement describing a compliance
            scenario (e.g. "We sell customer data without notifying users.").
        top_k : int, optional
            Number of sections to return (default 5).

        Returns
        -------
        list[tuple[str, str]]
            Ordered list of (section_name, full_section_text) tuples,
            most relevant first.
        """
        # Encode the query with the same model and normalisation
        query_vec = self.model.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True,
        ).astype(np.float32)

        # Search the FAISS index for the closest vectors
        scores, indices = self.index.search(query_vec, top_k)

        # Map index positions back to section names and texts
        results: list[tuple[str, str]] = []
        for idx, score in zip(indices[0], scores[0]):
            if idx == -1:
                continue  # FAISS returns -1 when fewer than top_k results
            name = self.section_names[idx]
            text = self.section_texts[idx]
            results.append((name, text))

        return results


