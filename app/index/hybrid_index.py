from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
import re

import faiss
import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

from app.core.schemas import RetrievalChunk, RetrievedItem


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


class HybridRetriever:
    """
    Hybrid retrieval (multimodal-aware):
    - Dense search via SentenceTransformers embeddings in FAISS (built per-modality)
    - Lexical search via BM25Okapi (built per-modality)
    - Rank fusion via Reciprocal Rank Fusion (RRF) across modalities with modality weights

    Notes: When saving/loading, multiple FAISS files and chunk JSON files are created using naming conventions derived
    from the provided paths (e.g., storage/faiss.index -> storage/faiss_audio.index)
    """

    def __init__(self, embedding_model_name: str, rrf_k: int = 60, modality_weights: dict | None = None) -> None:
        self._embedder = SentenceTransformer(embedding_model_name)
        self._rrf_k = rrf_k
        # modality -> list[RetrievalChunk]
        self._chunks_by_modality: dict[str, list[RetrievalChunk]] = {"text": [], "audio": [], "video": []}
        # modality -> faiss.Index
        self._indices: dict[str, faiss.Index] = {}
        # modality -> BM25
        self._bm25s: dict[str, BM25Okapi] = {}
        self._modality_weights = modality_weights or {"text": 1.0, "audio": 1.2, "video": 1.0}

    def build(self, chunks: list[RetrievalChunk]) -> None:
        if not chunks:
            raise ValueError("Cannot build retriever with empty chunks.")

        # Partition chunks by modality: audio chunks are entity_type starting with 'audio'
        text_chunks: list[RetrievalChunk] = []
        audio_chunks: list[RetrievalChunk] = []
        video_chunks: list[RetrievalChunk] = []
        for c in chunks:
            et = c.metadata.get("entity_type", "").lower()
            if et.startswith("audio"):
                audio_chunks.append(c)
            elif et.startswith("video"):
                video_chunks.append(c)
            else:
                text_chunks.append(c)

        self._chunks_by_modality["text"] = text_chunks
        self._chunks_by_modality["audio"] = audio_chunks
        self._chunks_by_modality["video"] = video_chunks

        # Build indices per modality
        for modality, m_chunks in self._chunks_by_modality.items():
            if not m_chunks:
                self._indices.pop(modality, None)
                self._bm25s.pop(modality, None)
                continue
            texts = [chunk.text for chunk in m_chunks]
            tokenized = [_tokenize(t) for t in texts]
            self._bm25s[modality] = BM25Okapi(tokenized)

            embeddings = self._embedder.encode(
                texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
            ).astype(np.float32)
            index = faiss.IndexFlatIP(embeddings.shape[1])
            index.add(embeddings)
            self._indices[modality] = index

    def save(self, faiss_index_path: Path, chunks_json_path: Path) -> None:
        # Write per-modality index files derived from provided paths
        base_dir = faiss_index_path.parent
        base_dir.mkdir(parents=True, exist_ok=True)
        # text
        if "text" in self._indices:
            faiss.write_index(self._indices["text"], str(faiss_index_path))
            serialized = [chunk.model_dump() for chunk in self._chunks_by_modality["text"]]
            chunks_json_path.write_text(json.dumps(serialized, indent=2), encoding="utf-8")
        # audio
        audio_index_path = faiss_index_path.with_name(faiss_index_path.stem + "_audio" + faiss_index_path.suffix)
        audio_chunks_path = chunks_json_path.with_name(chunks_json_path.stem + "_audio" + chunks_json_path.suffix)
        if "audio" in self._indices:
            faiss.write_index(self._indices["audio"], str(audio_index_path))
            serialized = [chunk.model_dump() for chunk in self._chunks_by_modality["audio"]]
            audio_chunks_path.write_text(json.dumps(serialized, indent=2), encoding="utf-8")
        # video
        video_index_path = faiss_index_path.with_name(faiss_index_path.stem + "_video" + faiss_index_path.suffix)
        video_chunks_path = chunks_json_path.with_name(chunks_json_path.stem + "_video" + chunks_json_path.suffix)
        if "video" in self._indices:
            faiss.write_index(self._indices["video"], str(video_index_path))
            serialized = [chunk.model_dump() for chunk in self._chunks_by_modality["video"]]
            video_chunks_path.write_text(json.dumps(serialized, indent=2), encoding="utf-8")

    def load(self, faiss_index_path: Path, chunks_json_path: Path) -> None:
        # Load text
        if faiss_index_path.exists() and chunks_json_path.exists():
            self._indices["text"] = faiss.read_index(str(faiss_index_path))
            payload = json.loads(chunks_json_path.read_text(encoding="utf-8"))
            self._chunks_by_modality["text"] = [RetrievalChunk.model_validate(item) for item in payload]
            self._bm25s["text"] = BM25Okapi([_tokenize(c.text) for c in self._chunks_by_modality["text"]])
        # audio
        audio_index_path = faiss_index_path.with_name(faiss_index_path.stem + "_audio" + faiss_index_path.suffix)
        audio_chunks_path = chunks_json_path.with_name(chunks_json_path.stem + "_audio" + chunks_json_path.suffix)
        if audio_index_path.exists() and audio_chunks_path.exists():
            self._indices["audio"] = faiss.read_index(str(audio_index_path))
            payload = json.loads(audio_chunks_path.read_text(encoding="utf-8"))
            self._chunks_by_modality["audio"] = [RetrievalChunk.model_validate(item) for item in payload]
            self._bm25s["audio"] = BM25Okapi([_tokenize(c.text) for c in self._chunks_by_modality["audio"]])
        # video
        video_index_path = faiss_index_path.with_name(faiss_index_path.stem + "_video" + faiss_index_path.suffix)
        video_chunks_path = chunks_json_path.with_name(chunks_json_path.stem + "_video" + chunks_json_path.suffix)
        if video_index_path.exists() and video_chunks_path.exists():
            self._indices["video"] = faiss.read_index(str(video_index_path))
            payload = json.loads(video_chunks_path.read_text(encoding="utf-8"))
            self._chunks_by_modality["video"] = [RetrievalChunk.model_validate(item) for item in payload]
            self._bm25s["video"] = BM25Okapi([_tokenize(c.text) for c in self._chunks_by_modality["video"]])

    def _dense_candidates_for_modality(self, modality: str, query: str, top_k: int) -> list[tuple[int, float]]:
        idx = self._indices.get(modality)
        if idx is None:
            return []
        query_embedding = self._embedder.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True,
        ).astype(np.float32)
        scores, indices = idx.search(query_embedding, top_k)
        return [(int(i), float(s)) for i, s in zip(indices[0], scores[0]) if i >= 0]

    def _bm25_candidates_for_modality(self, modality: str, query: str, top_k: int) -> list[tuple[int, float]]:
        bm = self._bm25s.get(modality)
        if bm is None:
            return []
        qtokens = _tokenize(query)
        scores = bm.get_scores(qtokens)
        ranked = np.argsort(scores)[::-1][:top_k]
        return [(int(idx), float(scores[idx])) for idx in ranked]

    def search(self, query: str, faiss_top_k: int = 8, bm25_top_k: int = 8) -> list[RetrievedItem]:
        modality_rrf_scores: dict[str, dict[int, float]] = {}
        # collect per-modality RRF scores
        for modality in ("text", "audio", "video"):
            dense = self._dense_candidates_for_modality(modality, query, faiss_top_k)
            lexical = self._bm25_candidates_for_modality(modality, query, bm25_top_k)
            dense_ranks = {doc_idx: rank for rank, (doc_idx, _) in enumerate(dense, start=1)}
            lexical_ranks = {doc_idx: rank for rank, (doc_idx, _) in enumerate(lexical, start=1)}
            rrf_scores: dict[int, float] = defaultdict(float)
            for doc_idx, rank in dense_ranks.items():
                rrf_scores[doc_idx] += 1.0 / (self._rrf_k + rank)
            for doc_idx, rank in lexical_ranks.items():
                rrf_scores[doc_idx] += 1.0 / (self._rrf_k + rank)
            modality_rrf_scores[modality] = rrf_scores

        # Combine modalities with weights
        combined_scores: dict[tuple[str, int], float] = defaultdict(float)
        for modality, scores in modality_rrf_scores.items():
            weight = float(self._modality_weights.get(modality, 1.0))
            for doc_idx, sc in scores.items():
                combined_scores[(modality, doc_idx)] += sc * weight

        # Flatten and sort
        sorted_items = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)
        results: list[RetrievedItem] = []
        for (modality, doc_idx), score in sorted_items:
            chunks = self._chunks_by_modality.get(modality, [])
            if doc_idx < 0 or doc_idx >= len(chunks):
                continue
            chunk = chunks[doc_idx]
            results.append(
                RetrievedItem(chunk_id=chunk.chunk_id, text=chunk.text, metadata=chunk.metadata, score=score)
            )
        return results
