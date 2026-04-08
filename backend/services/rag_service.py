import json
import os
import time
from collections import Counter
from functools import partial
from pathlib import Path

import redis
from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain_huggingface.embeddings import HuggingFaceEmbeddings
from sentence_transformers import CrossEncoder
from sklearn.feature_extraction.text import TfidfVectorizer

from backend.core.config import settings
from backend.core.observability import get_logger

# Keep HF mirror for mainland network conditions.
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

logger = get_logger("adaptive.rag")


def _resolve_local_hf_model(model_id: str) -> str:
    hub_root = Path.home() / ".cache" / "huggingface" / "hub"
    model_dir = hub_root / f"models--{model_id.replace('/', '--')}" / "snapshots"
    if not model_dir.exists():
        return model_id
    candidates = [p for p in model_dir.iterdir() if p.is_dir()]
    if not candidates:
        return model_id
    latest = sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)[0]
    return str(latest)


class RAGService:
    def __init__(self):
        self.embeddings = None
        self.vector_db = None
        self.reranker = None
        self.is_initialized = False
        self.index_path = None
        self.index_build_meta = {}
        self.rerank_load_error = ""
        self.reranker_backend = "none"
        self.fast_mode = os.getenv("RAG_FAST_MODE", "true").lower() == "true"

        try:
            self.redis_client = self._build_redis_client()
            if self.redis_client is not None:
                self.redis_client.ping()
            logger.info("redis_connected")
            self.use_redis = self.redis_client is not None
        except Exception as exc:
            logger.warning("redis_unavailable reason=%s", exc)
            self.redis_client = None
            self.use_redis = False

    def _build_redis_client(self):
        return redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True,
        )

    def _resolve_index_path(self):
        explicit_path = os.getenv("RAG_RUNTIME_INDEX_PATH", "").strip()
        if explicit_path:
            return os.path.abspath(explicit_path)
        return settings.FAISS_INDEX_DIR

    @staticmethod
    def _collect_docling_signal(build_meta):
        source_stats = build_meta.get("source_build_stats", {}) or {}
        requested_docling_sources = 0
        actual_docling_sources = 0
        fallback_sources = 0
        pages_total = 0
        pages_success = 0
        docling_chars = 0
        baseline_chars = 0
        strategy_breakdown = {}

        for stat in source_stats.values():
            if not isinstance(stat, dict):
                continue
            if stat.get("requested_parser") != "docling":
                continue
            requested_docling_sources += 1
            strategy = stat.get("docling_strategy") or "unknown"
            strategy_breakdown[strategy] = strategy_breakdown.get(strategy, 0) + 1
            pages_total += int(stat.get("docling_pages_total", 0) or 0)
            pages_success += int(stat.get("docling_pages_success", 0) or 0)
            docling_chars += int(stat.get("docling_chars", 0) or 0)
            baseline_chars += int(stat.get("baseline_chars", 0) or 0)
            if stat.get("actual_parser") == "docling":
                actual_docling_sources += 1
            if stat.get("actual_parser") == "pypdf":
                fallback_sources += 1

        page_ratio = round(pages_success / pages_total, 4) if pages_total else 0.0
        char_ratio = round(docling_chars / baseline_chars, 4) if baseline_chars else 0.0
        return {
            "requested_sources": requested_docling_sources,
            "actual_sources": actual_docling_sources,
            "fallback_sources": fallback_sources,
            "strategy_breakdown": strategy_breakdown,
            "page_ratio": page_ratio,
            "char_ratio": char_ratio,
        }

    @staticmethod
    def _read_build_meta(index_path):
        meta_path = os.path.join(index_path, "build_meta.json")
        if not os.path.exists(meta_path):
            return {}
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    @staticmethod
    def _infer_parser_usage(vector_db):
        try:
            docs = list(vector_db.docstore._dict.values())
        except Exception:
            return {}
        counter = Counter((doc.metadata or {}).get("parser", "<missing>") for doc in docs)
        return dict(counter)

    @staticmethod
    def _serialize_doc(doc, recall_rank=None, rerank_rank=None, rerank_score=None):
        meta = doc.metadata or {}
        source = meta.get("source") or "-"
        return {
            "text": doc.page_content,
            "source": os.path.basename(source),
            "source_path": source,
            "page": meta.get("page") or meta.get("page_label"),
            "parser": meta.get("parser") or "<legacy>",
            "docling_strategy": meta.get("docling_strategy"),
            "recall_rank": recall_rank,
            "rerank_rank": rerank_rank,
            "rerank_score": round(float(rerank_score), 4) if rerank_score is not None else None,
        }

    def _build_index_info(self):
        build_meta = self.index_build_meta or {}
        parser_usage = build_meta.get("parser_usage") or {}
        if not parser_usage and self.vector_db is not None:
            parser_usage = self._infer_parser_usage(self.vector_db)
        effective_parser = self._effective_parser(parser_usage)
        index_name = os.path.basename(self.index_path or "")
        docling_signal = self._collect_docling_signal(build_meta)
        return {
            "path": self.index_path,
            "name": index_name,
            "index_scope": "evaluation" if index_name.startswith("faiss_index_eval_") else "production",
            "is_evaluation_index": index_name.startswith("faiss_index_eval_"),
            "requested_parser": build_meta.get("requested_parser") or "<legacy>",
            "effective_parser": effective_parser if self.index_path else "<legacy>",
            "parser_usage": parser_usage,
            "source_usage": build_meta.get("source_usage") or {},
            "source_count": len((build_meta.get("source_usage") or {})),
            "docling_requested_sources": int(docling_signal.get("requested_sources", 0)),
            "docling_actual_sources": int(docling_signal.get("actual_sources", 0)),
            "docling_fallback_sources": int(docling_signal.get("fallback_sources", 0)),
            "docling_strategy_breakdown": docling_signal.get("strategy_breakdown", {}),
            "docling_page_ratio": float(docling_signal.get("page_ratio", 0.0)),
            "docling_char_ratio": float(docling_signal.get("char_ratio", 0.0)),
            "has_build_meta": bool(build_meta),
            "fast_mode": self.fast_mode,
            "reranker_loaded": self.reranker is not None,
            "reranker_backend": self.reranker_backend,
            "rerank_load_error": self.rerank_load_error,
        }

    def _effective_parser(self, parser_usage=None):
        parser_usage = parser_usage or {}
        if not parser_usage:
            return "<legacy>"
        return max(parser_usage.items(), key=lambda item: item[1])[0]

    def _build_runtime_config(self, requested_use_rerank=True, rerank_applied=False, fallback_reason=""):
        info = self._build_index_info()
        requested_parser = info.get("requested_parser") or "<legacy>"
        effective_parser = info.get("effective_parser") or self._effective_parser()
        rerank_available = (not self.fast_mode) and self.reranker_backend != "none"
        effective_rerank = bool(requested_use_rerank and rerank_applied)
        return {
            "requested": {
                "parser": requested_parser,
                "index_path": self.index_path,
                "use_rerank": bool(requested_use_rerank),
                "fast_mode": self.fast_mode,
            },
            "effective": {
                "parser": effective_parser,
                "index_path": self.index_path,
                "use_rerank": effective_rerank,
                "rerank_available": rerank_available,
                "reranker_loaded": self.reranker is not None,
                "reranker_backend": self.reranker_backend,
            },
            "fallback_reason": fallback_reason or "",
            "rerank_applied": bool(rerank_applied),
        }

    def _can_rerank(self, use_rerank: bool) -> bool:
        return bool(use_rerank and (not self.fast_mode) and self.reranker_backend != "none")

    def _score_documents(self, keyword: str, docs) -> list[float]:
        texts = [doc.page_content or "" for doc in docs]
        if not texts:
            return []
        if self.reranker_backend == "cross_encoder" and self.reranker is not None:
            pairs = [[keyword, text] for text in texts]
            return list(self.reranker.predict(pairs))
        if self.reranker_backend == "tfidf_fallback":
            try:
                matrix = TfidfVectorizer(max_features=5000).fit_transform([keyword, *texts])
                query_vec = matrix[0:1]
                doc_vecs = matrix[1:]
                scores = (doc_vecs @ query_vec.T).toarray().ravel()
                return [float(score) for score in scores]
            except Exception as exc:
                logger.warning("rag_tfidf_rerank_failed reason=%s", exc)
        return [0.0 for _ in texts]

    def initialize(self):
        if self.is_initialized:
            return

        load_dotenv(override=True)
        self.fast_mode = os.getenv("RAG_FAST_MODE", "true").lower() == "true"
        self.rerank_load_error = ""
        self.reranker_backend = "none"

        logger.info("rag_initialize_started")
        embedding_model = _resolve_local_hf_model("BAAI/bge-small-zh-v1.5")
        self.embeddings = HuggingFaceEmbeddings(
            model_name=embedding_model,
            model_kwargs={"device": "cpu", "local_files_only": True},
            encode_kwargs={"normalize_embeddings": True},
        )

        index_path = self._resolve_index_path()
        self.index_path = index_path
        self.index_build_meta = self._read_build_meta(index_path)

        logger.info("rag_loading_index path=%s", index_path)
        try:
            self.vector_db = FAISS.load_local(
                folder_path=index_path,
                embeddings=self.embeddings,
                allow_dangerous_deserialization=True,
            )
            logger.info("rag_index_loaded")
        except Exception as exc:
            logger.warning("rag_index_load_failed reason=%s", exc)
            self.vector_db = None

        if self.fast_mode:
            logger.info("rag_fast_mode_enabled rerank_loaded=0 reranker_backend=none")
            self.reranker = None
        else:
            logger.info("rag_loading_reranker")
            reranker_model = _resolve_local_hf_model("BAAI/bge-reranker-base")
            try:
                self.reranker = CrossEncoder(
                    reranker_model,
                    local_files_only=True,
                    model_kwargs={"low_cpu_mem_usage": True},
                )
                self.reranker_backend = "cross_encoder"
                logger.info("rag_reranker_ready backend=%s", self.reranker_backend)
            except Exception as exc:
                self.reranker = None
                self.rerank_load_error = f"{type(exc).__name__}: {exc}"
                logger.warning("rag_reranker_unavailable reason=%s", self.rerank_load_error)
                self.reranker_backend = "tfidf_fallback"
                logger.info("rag_reranker_fallback_enabled backend=%s", self.reranker_backend)
        self.is_initialized = True
        logger.info("rag_initialize_completed reranker_backend=%s", self.reranker_backend)

    def reload_db(self):
        logger.info("rag_reload_requested")
        self.is_initialized = False
        self.index_build_meta = {}
        self.index_path = None
        self.rerank_load_error = ""
        self.reranker_backend = "none"
        self.initialize()
        return True

    def _to_result(
        self,
        final_docs_objs,
        raw_docs_objs,
        recall_ms,
        rerank_ms,
        raw_doc_details=None,
        rerank_doc_details=None,
        requested_use_rerank=True,
        rerank_applied=False,
        rerank_reason="",
    ):
        return {
            "final_docs": [d.page_content for d in final_docs_objs],
            "raw_docs": [d.page_content for d in raw_docs_objs],
            "rerank_docs": [d.page_content for d in final_docs_objs],
            "raw_doc_details": raw_doc_details or [],
            "rerank_doc_details": rerank_doc_details or [],
            "rerank_applied": rerank_applied,
            "rerank_reason": rerank_reason,
            "index_info": self._build_index_info(),
            "runtime_config": self._build_runtime_config(
                requested_use_rerank=requested_use_rerank,
                rerank_applied=rerank_applied,
                fallback_reason=rerank_reason,
            ),
            "timings": {
                "recall": f"{recall_ms:.0f}ms",
                "rerank": rerank_ms,
            },
        }

    def _cache_key(self, keyword, top_k, recall_k, use_rerank):
        index_name = os.path.basename(self.index_path or settings.FAISS_INDEX_DIR)
        return (
            f"rag:{index_name}:{keyword}:{top_k}:{recall_k}:"
            f"rerank:{int(use_rerank)}:fast:{int(self.fast_mode)}:backend:{self.reranker_backend}"
        )

    def search(self, keyword, top_k=3, recall_k=None, use_rerank=True):
        if not self.vector_db:
            return {
                "final_docs": [],
                "raw_docs": [],
                "rerank_docs": [],
                "raw_doc_details": [],
                "rerank_doc_details": [],
                "rerank_applied": False,
                "rerank_reason": "vector_db_unavailable",
                "index_info": self._build_index_info(),
                "runtime_config": self._build_runtime_config(
                    requested_use_rerank=use_rerank,
                    rerank_applied=False,
                    fallback_reason="vector_db_unavailable",
                ),
                "timings": {},
            }

        can_rerank = self._can_rerank(use_rerank)
        if recall_k is None:
            recall_k = 15 if can_rerank else top_k

        # Branch A: similarity-only retrieval.
        if not can_rerank:
            t0 = time.time()
            recall_docs_objs = self.vector_db.similarity_search(keyword, k=recall_k)
            t1 = time.time()
            recall_ms = (t1 - t0) * 1000
            final_docs_objs = recall_docs_objs[:top_k]
            skip_reason = "fast_mode" if self.fast_mode else "reranker_unavailable"
            raw_doc_details = [
                self._serialize_doc(doc, recall_rank=index + 1)
                for index, doc in enumerate(recall_docs_objs)
            ]
            rerank_doc_details = [
                self._serialize_doc(doc, recall_rank=index + 1, rerank_rank=index + 1)
                for index, doc in enumerate(final_docs_objs)
            ]
            return self._to_result(
                final_docs_objs=final_docs_objs,
                raw_docs_objs=recall_docs_objs,
                recall_ms=recall_ms,
                rerank_ms="0ms (Skipped)",
                raw_doc_details=raw_doc_details,
                rerank_doc_details=rerank_doc_details,
                requested_use_rerank=use_rerank,
                rerank_applied=False,
                rerank_reason=skip_reason,
            )

        cache_key = self._cache_key(keyword, top_k, recall_k, use_rerank)
        if self.use_redis:
            try:
                t0 = time.perf_counter()
                cached_data = self.redis_client.get(cache_key)
                t1 = time.perf_counter()
                cache_ms = (t1 - t0) * 1000
                if cached_data:
                    logger.info("rag_cache_hit keyword=%s latency_ms=%.2f", keyword, cache_ms)
                    data = json.loads(cached_data)
                    data["timings"]["recall"] = f"{cache_ms:.2f}ms (Redis)"
                    data.setdefault("raw_doc_details", [])
                    data.setdefault("rerank_doc_details", [])
                    data["index_info"] = self._build_index_info()
                    data["runtime_config"] = self._build_runtime_config(
                        requested_use_rerank=use_rerank,
                        rerank_applied=bool(data.get("rerank_applied")),
                        fallback_reason=data.get("rerank_reason", ""),
                    )
                    if self.fast_mode:
                        data["timings"]["rerank"] = "0ms (Skipped)"
                        data["rerank_applied"] = False
                        data["rerank_reason"] = "fast_mode"
                        data["runtime_config"] = self._build_runtime_config(
                            requested_use_rerank=use_rerank,
                            rerank_applied=False,
                            fallback_reason="fast_mode",
                        )
                    return data
            except Exception as exc:
                logger.warning("rag_cache_read_failed reason=%s", exc)

        logger.info("rag_cache_miss keyword=%s", keyword)

        t0 = time.time()
        initial_docs = self.vector_db.similarity_search(keyword, k=recall_k)
        t1 = time.time()
        recall_ms = (t1 - t0) * 1000

        scores = self._score_documents(keyword, initial_docs)
        t2 = time.time()
        rerank_ms = (t2 - t1) * 1000

        scored_docs = sorted(zip(initial_docs, scores), key=lambda x: x[1], reverse=True)
        final_docs_objs = [doc for doc, _ in scored_docs[:top_k]]
        recall_rank_map = {id(doc): index + 1 for index, doc in enumerate(initial_docs)}
        raw_doc_details = [
            self._serialize_doc(
                doc,
                recall_rank=index + 1,
                rerank_score=scores[index],
            )
            for index, doc in enumerate(initial_docs)
        ]
        rerank_doc_details = [
            self._serialize_doc(
                doc,
                recall_rank=recall_rank_map.get(id(doc)),
                rerank_rank=index + 1,
                rerank_score=score,
            )
            for index, (doc, score) in enumerate(scored_docs[:top_k])
        ]

        result = self._to_result(
            final_docs_objs=final_docs_objs,
            raw_docs_objs=initial_docs,
            recall_ms=recall_ms,
            rerank_ms=f"{rerank_ms:.0f}ms",
            raw_doc_details=raw_doc_details,
            rerank_doc_details=rerank_doc_details,
            requested_use_rerank=use_rerank,
            rerank_applied=True,
            rerank_reason=f"applied:{self.reranker_backend}",
        )

        if self.use_redis:
            try:
                self.redis_client.setex(cache_key, 3600, json.dumps(result))
            except Exception as exc:
                logger.warning("rag_cache_write_failed reason=%s", exc)

        return result

    async def search_async(self, keyword, top_k=3, recall_k=None, use_rerank=True):
        import asyncio

        loop = asyncio.get_running_loop()
        fn = partial(self.search, keyword, top_k, recall_k, use_rerank)
        return await loop.run_in_executor(None, fn)


rag_service = RAGService()

