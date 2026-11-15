"""
BhumiLens AI — Land Knowledge RAG Service (Offline-First Vector & Lexical Hybrid Search).
Provides source-grounded passage retrieval and knowledge explanation for Bangladeshi land records.
Compatible with Apple Silicon M2 (MPS/CPU) and offline-cached multilingual embeddings.
"""
import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
import numpy as np
import torch
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from backend.schemas.rag_schema import (
    RAGCitation,
    RAGQueryRequest,
    RAGQueryResponse,
    RAGCorpusStats,
    DeedFieldExplanation,
    DeedExplanationResponse,
    SCHEMA_VERSION
)

logger = logging.getLogger("bhumilens.rag")

DEFAULT_CORPUS_PATH = Path("research/rag_corpus/land_knowledge_base.json")
DEFAULT_EMBEDDING_DIR = Path("models/embeddings/multilingual-e5-small")
DEFAULT_INDEX_DIR = Path("outputs/rag_index")

BANGLA_STOPWORDS = {
    "কী", "কি", "কীভাবে", "কবে", "কোথায়", "কে", "কেন", "এবং", "ও", "বা", "এর", 
    "তে", "এ", "হলো", "হয়", "হয়ে", "করা", "করে", "থাকে", "থাকলে", "যথা", "ইত্যাদি",
    "বলেন", "আছে", "ছিল", "হবে", "হলে", "একটি", "কোন", "কোনো", "কীসের"
}

LEGAL_DISCLAIMER_TEXT = (
    "আইনি সতর্কবার্তা: BhumiLens AI এর এই ব্যাখ্যা শুধুমাত্র তথ্যগত সহায়তা ও গবেষণার উদ্দেশ্যে প্রণীত। "
    "এটি কোনো আইনি পরামর্শ বা আদালতের রায় নয়। জমির চূড়ান্ত মালিকানা নির্ধারণের এখতিয়ার সহকারী কমিশনার (ভূমি), "
    "সাব-রেজিস্ট্রার ও উপযুক্ত আদালতের।"
)

class LandKnowledgeRAGService:
    def __init__(
        self,
        corpus_path: Optional[Path] = None,
        model_dir: Optional[Path] = None,
        index_dir: Optional[Path] = None,
        prefer_mps: bool = False
    ):
        self.corpus_path = corpus_path or DEFAULT_CORPUS_PATH
        self.model_dir = model_dir or DEFAULT_EMBEDDING_DIR
        self.index_dir = index_dir or DEFAULT_INDEX_DIR
        self.prefer_mps = prefer_mps

        self.documents: List[Dict[str, Any]] = []
        self.doc_texts: List[str] = []
        self.doc_keys: List[str] = []

        self._embedding_model = None
        self._dense_embeddings: Optional[np.ndarray] = None
        self._tfidf_vectorizer: Optional[TfidfVectorizer] = None
        self._tfidf_matrix = None

        self._load_corpus()
        self._initialize_retrievers()

    def _load_corpus(self):
        """Loads curated land knowledge corpus from disk."""
        if not self.corpus_path.exists():
            raise FileNotFoundError(f"Knowledge corpus file not found at: {self.corpus_path}")

        with open(self.corpus_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.corpus_version = data.get("version", SCHEMA_VERSION)
        self.documents = data.get("documents", [])
        
        self.doc_texts = []
        self.doc_keys = []
        for doc in self.documents:
            key_terms_str = " ".join(doc.get("key_terms", []))
            full_text = f"{doc.get('title', '')} | {key_terms_str} | {doc.get('content', '')}"
            self.doc_texts.append(full_text)
            self.doc_keys.append(doc["doc_id"])

        logger.info("[RAG] Loaded %d verified knowledge chunks from %s", len(self.documents), self.corpus_path)

    def _initialize_retrievers(self):
        """Initializes dense sentence transformer and lexical TF-IDF retrievers."""
        # 1. Lexical Retriever (TF-IDF with stopword suppression)
        self._tfidf_vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            token_pattern=r'(?u)\b\w+\b',
            stop_words=list(BANGLA_STOPWORDS)
        )
        self._tfidf_matrix = self._tfidf_vectorizer.fit_transform(self.doc_texts)

        # 2. Dense Embeddings
        self.index_dir.mkdir(parents=True, exist_ok=True)
        cached_emb_path = self.index_dir / "rag_embeddings.npz"

        # Check if precomputed embeddings exist
        if cached_emb_path.exists():
            try:
                npz = np.load(cached_emb_path)
                cached_embs = npz["embeddings"]
                if cached_embs.shape[0] == len(self.documents):
                    self._dense_embeddings = cached_embs
                    logger.info("[RAG] Loaded cached dense embeddings from %s (shape: %s)", cached_emb_path, self._dense_embeddings.shape)
                    self._ensure_embedding_model_loaded()
                    return
            except Exception as e:
                logger.warning("[RAG] Failed to load cached embeddings: %s. Recomputing...", e)

        # Compute embeddings using local offline model
        self._ensure_embedding_model_loaded()
        if self._embedding_model is not None:
            # E5 passages need "passage: " prefix for asymmetric search
            passage_inputs = [f"passage: {t}" for t in self.doc_texts]
            logger.info("[RAG] Encoding %d passages with %s...", len(passage_inputs), self.model_dir)
            embs = self._embedding_model.encode(
                passage_inputs,
                batch_size=8,
                show_progress_bar=False,
                normalize_embeddings=True
            )
            self._dense_embeddings = np.array(embs, dtype=np.float32)
            try:
                np.savez_compressed(cached_emb_path, embeddings=self._dense_embeddings)
                logger.info("[RAG] Cached dense embeddings saved to %s", cached_emb_path)
            except Exception as e:
                logger.warning("[RAG] Could not write cache: %s", e)
        else:
            logger.warning("[RAG] Dense model not loaded. Operating in pure lexical fallback mode.")

    def _ensure_embedding_model_loaded(self):
        """Loads SentenceTransformer from local cache dir."""
        if self._embedding_model is not None:
            return

        if not self.model_dir.exists():
            logger.warning("[RAG] Local model dir %s does not exist.", self.model_dir)
            return

        try:
            from sentence_transformers import SentenceTransformer
            device = "cpu"
            if self.prefer_mps and torch.backends.mps.is_available():
                device = "mps"
            logger.info("[RAG] Loading SentenceTransformer from %s (device: %s)", self.model_dir, device)
            self._embedding_model = SentenceTransformer(str(self.model_dir), device=device)
        except Exception as e:
            logger.error("[RAG] Failed to load SentenceTransformer: %s", e)
            self._embedding_model = None

    def retrieve(
        self,
        query: str,
        top_k: int = 3,
        threshold: float = 0.35,
        dense_weight: float = 0.50
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Hybrid retrieval combining dense multilingual embedding cosine similarity with TF-IDF lexical score.
        Returns list of tuples: (document_chunk, combined_score) sorted descending by score.
        """
        clean_query = query.strip()
        if not clean_query:
            return []

        self._ensure_embedding_model_loaded()

        # 1. Compute Lexical Scores
        q_vec = self._tfidf_vectorizer.transform([clean_query])
        lexical_sim = cosine_similarity(q_vec, self._tfidf_matrix)[0]

        # 2. Compute Dense Scores
        dense_sim = np.zeros(len(self.documents), dtype=np.float32)
        if self._embedding_model is not None and self._dense_embeddings is not None:
            try:
                query_input = f"query: {clean_query}"
                q_emb = self._embedding_model.encode([query_input], normalize_embeddings=True)
                dense_sim = cosine_similarity(q_emb, self._dense_embeddings)[0]
            except Exception as e:
                logger.warning("[RAG] Dense embedding query encoding failed: %s. Using lexical.", e)
                dense_weight = 0.0
        else:
            dense_weight = 0.0

        # 3. Combine scores with dense baseline calibration
        if dense_weight > 0.0:
            dense_calib = np.maximum(0.0, (dense_sim - 0.72) / 0.28)
            hybrid_scores = (dense_weight * dense_calib) + ((1.0 - dense_weight) * lexical_sim)
        else:
            hybrid_scores = lexical_sim

        # 4. Rank and filter
        ranked_indices = np.argsort(hybrid_scores)[::-1]
        results: List[Tuple[Dict[str, Any], float]] = []

        for idx in ranked_indices:
            score = float(hybrid_scores[idx])
            if score < threshold:
                break
            results.append((self.documents[idx], round(score, 4)))
            if len(results) >= top_k:
                break

        return results

    def answer_query(
        self,
        query: str,
        top_k: int = 3,
        similarity_threshold: float = 0.35
    ) -> RAGQueryResponse:
        """
        Executes source-grounded RAG query answering.
        If similarity is below threshold, returns INSUFFICIENT_SOURCE_EVIDENCE without hallucinating.
        """
        retrieved = self.retrieve(query, top_k=top_k, threshold=similarity_threshold)

        if not retrieved:
            return RAGQueryResponse(
                query=query,
                status="INSUFFICIENT_SOURCE_EVIDENCE",
                answer="উৎস জ্ঞানভাণ্ডারে (Corpus) এই প্রশ্নের উত্তরের স্বপক্ষে পর্যাপ্ত রেফারেন্স মেলেনি। মনগড়া বা অনুমাননির্ভর তথ্য প্রদান নিষিদ্ধ।",
                citations=[],
                top_score=0.0,
                model_used="intfloat/multilingual-e5-small + TF-IDF Hybrid (Grounding Guardrail Active)",
                legal_disclaimer=LEGAL_DISCLAIMER_TEXT
            )

        citations: List[RAGCitation] = []
        excerpts_for_answer: List[str] = []

        for doc, score in retrieved:
            citation = RAGCitation(
                doc_id=doc["doc_id"],
                section_id=doc["section_id"],
                source_title=doc["title"],
                source_authority=doc["source_authority"],
                verified_status=doc["verified_status"],
                category=doc["category"],
                similarity_score=score,
                excerpt=doc["content"][:280] + ("..." if len(doc["content"]) > 280 else "")
            )
            citations.append(citation)
            excerpts_for_answer.append(f"[{doc['title']} ({doc['source_authority']})]: {doc['content']}")

        # Build grounded synthesis
        top_doc, top_score = retrieved[0]
        answer_text = (
            f"উৎস রেফারেন্স ({top_doc['title']}) অনুসারে:\n\n"
            f"{top_doc['content']}\n\n"
            f"সংযুক্ত কর্তৃপক্ষ ও প্রমিতি: {top_doc['source_authority']} ({top_doc['verified_status']})।"
        )

        return RAGQueryResponse(
            query=query,
            status="ANSWERED",
            answer=answer_text,
            citations=citations,
            top_score=top_score,
            model_used="intfloat/multilingual-e5-small + TF-IDF Hybrid",
            legal_disclaimer=LEGAL_DISCLAIMER_TEXT
        )

    def explain_deed_fields(
        self,
        extracted_data: Dict[str, Any]
    ) -> List[DeedFieldExplanation]:
        """
        Cross-references extracted deed fields against the verified land knowledge base.
        Compiles authoritative explanations for deed type, land units, 16-Ana share, and warnings.
        """
        explanations: List[DeedFieldExplanation] = []

        # 1. Deed Type Explanation
        deed_type = extracted_data.get("deed_type")
        if deed_type and deed_type != "UNKNOWN":
            query_map = {
                "SAF_KABALA": "সাফ-কবলা বিক্রয় দলিল",
                "BAYNAPATRA": "বায়নাপত্র চুক্তিপত্র",
                "BONTONAMA": "বণ্টননামা ফারায়েজ",
                "HEBA_BIL_EWAZ": "হেবা-বিল-এওয়াজ দানপত্র",
                "HEBA_DECLARATION": "হেবা ঘোষণা দলিল",
                "MORTGAGE": "বন্ধকনামা দলিল"
            }
            search_q = query_map.get(deed_type, deed_type)
            hits = self.retrieve(search_q, top_k=1, threshold=0.2)
            if hits:
                doc, _ = hits[0]
                explanations.append(DeedFieldExplanation(
                    field_name="deed_type",
                    extracted_value=deed_type,
                    knowledge_title=doc["title"],
                    explanation=doc["content"][:320] + "...",
                    authority_reference=doc["source_authority"]
                ))

        # 2. Land Unit Explanation
        land_details = extracted_data.get("land_details") or {}
        land_unit = land_details.get("land_unit")
        if land_unit and land_unit != "UNKNOWN":
            hits = self.retrieve(f"ভূমি পরিমাপের একক {land_unit} শতক কাঠা বিঘা", top_k=1, threshold=0.2)
            if hits:
                doc, _ = hits[0]
                explanations.append(DeedFieldExplanation(
                    field_name="land_unit",
                    extracted_value=land_unit,
                    knowledge_title=doc["title"],
                    explanation=doc["content"][:320] + "...",
                    authority_reference=doc["source_authority"]
                ))

        # 3. 16-Ana Share Explanation
        sixteen_ana = land_details.get("sixteen_ana_share")
        if sixteen_ana:
            hits = self.retrieve("১৬ আনা হিস্যা আনা গন্ডা কড়া ক্রান্তি তিল", top_k=1, threshold=0.2)
            if hits:
                doc, _ = hits[0]
                explanations.append(DeedFieldExplanation(
                    field_name="sixteen_ana_share",
                    extracted_value=sixteen_ana,
                    knowledge_title=doc["title"],
                    explanation=doc["content"][:320] + "...",
                    authority_reference=doc["source_authority"]
                ))

        # 4. Khatian & Dag Classification
        khatian_numbers = land_details.get("khatian_numbers", [])
        if khatian_numbers:
            hits = self.retrieve("খতিয়ান বা পর্চার শ্রেণিবিভাগ CS SA RS BS", top_k=1, threshold=0.2)
            if hits:
                doc, _ = hits[0]
                explanations.append(DeedFieldExplanation(
                    field_name="khatian_numbers",
                    extracted_value=khatian_numbers,
                    knowledge_title=doc["title"],
                    explanation=doc["content"][:320] + "...",
                    authority_reference=doc["source_authority"]
                ))

        # 5. Missing Tafsil Warning Guidance
        provenance = extracted_data.get("provenance") or {}
        warnings = provenance.get("warnings") or []
        for w in warnings:
            if "TAFSIL" in str(w).upper() or "SCHEDULE" in str(w).upper():
                hits = self.retrieve("দলিলের তফসিল ও বায়ে-রেজিস্ট্রি বিবরণ দাগ অনুপস্থিত", top_k=1, threshold=0.2)
                if hits:
                    doc, _ = hits[0]
                    explanations.append(DeedFieldExplanation(
                        field_name="warning_tafsil",
                        extracted_value=w,
                        knowledge_title=doc["title"],
                        explanation=doc["content"][:320] + "...",
                        authority_reference=doc["source_authority"]
                    ))
                break

        return explanations

    def get_corpus_stats(self) -> RAGCorpusStats:
        """Returns statistics of indexed land documents and embedding configuration."""
        categories: Dict[str, int] = {}
        authorities: Dict[str, int] = {}

        for doc in self.documents:
            cat = doc.get("category", "OTHER")
            auth = doc.get("source_authority", "UNKNOWN")
            categories[cat] = categories.get(cat, 0) + 1
            authorities[auth] = authorities.get(auth, 0) + 1

        emb_dim = self._dense_embeddings.shape[1] if self._dense_embeddings is not None else 384

        return RAGCorpusStats(
            corpus_version=self.corpus_version,
            total_documents=len(self.documents),
            categories=categories,
            authorities=authorities,
            embedding_model="intfloat/multilingual-e5-small (Offline Cached)",
            embedding_dimension=emb_dim,
            is_offline_ready=True,
            index_storage_path=str(self.index_dir)
        )
