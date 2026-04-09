import asyncio
import json
import os
import random
import gc
import shutil
import csv
import copy
import logging
from pathlib import Path
from typing import Any, Dict, List

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from dotenv import load_dotenv
from datasets import Dataset
import httpx
from langchain_community.vectorstores import FAISS
from langchain_huggingface.embeddings import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from ragas import evaluate
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness
from ragas.run_config import RunConfig
from sentence_transformers import CrossEncoder

from backend.core.config import settings
from backend.scripts.init_rag import init_local_rag
from backend.services.experiment_version_service import experiment_version_service

load_dotenv()
logger = logging.getLogger(__name__)


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


class RagasService:
    def __init__(self):
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")
        if not base_url.endswith("/v1"):
            base_url = f"{base_url}/v1"

        self.request_timeout = float(
            os.getenv("RAGAS_LLM_TIMEOUT_SEC", str(settings.LLM_REQUEST_TIMEOUT_SEC))
        )
        self.llm_max_retries = int(os.getenv("RAGAS_LLM_MAX_RETRIES", "6"))
        max_connections = int(os.getenv("RAGAS_HTTP_MAX_CONNECTIONS", "8"))
        max_keepalive_connections = int(os.getenv("RAGAS_HTTP_KEEPALIVE_CONNECTIONS", "4"))
        self.sample_concurrency = max(1, int(os.getenv("RAGAS_SAMPLE_CONCURRENCY", "1")))

        http_limits = httpx.Limits(
            max_connections=max_connections,
            max_keepalive_connections=max_keepalive_connections,
        )
        self._sync_http_client = httpx.Client(timeout=self.request_timeout, limits=http_limits)
        self._async_http_client = httpx.AsyncClient(timeout=self.request_timeout, limits=http_limits)
        llm_common_kwargs = {
            "model": "deepseek-chat",
            "openai_api_key": os.getenv("DEEPSEEK_API_KEY"),
            "openai_api_base": base_url,
            "temperature": 0,
            "n": 1,
            "timeout": self.request_timeout,
            "max_retries": self.llm_max_retries,
            "http_client": self._sync_http_client,
            "http_async_client": self._async_http_client,
        }

        # Judge LLM for RAGAS itself
        judge_base_llm = ChatOpenAI(**llm_common_kwargs)
        self.judge_llm = LangchainLLMWrapper(judge_base_llm)

        if hasattr(self.judge_llm, "generate"):
            origin_generate = self.judge_llm.generate

            def patched_generate(prompts, **kwargs):
                kwargs["n"] = 1
                return origin_generate(prompts, **kwargs)

            self.judge_llm.generate = patched_generate

        if hasattr(self.judge_llm, "agenerate"):
            origin_agenerate = self.judge_llm.agenerate

            async def patched_agenerate(prompts, **kwargs):
                kwargs["n"] = 1
                return await origin_agenerate(prompts, **kwargs)

            self.judge_llm.agenerate = patched_agenerate

        # Generation LLM used during evaluation data creation.
        self.answer_llm = ChatOpenAI(**llm_common_kwargs)

        embedding_model = _resolve_local_hf_model("BAAI/bge-small-zh-v1.5")
        self.eval_embeddings = HuggingFaceEmbeddings(
            model_name=embedding_model,
            model_kwargs={"device": "cpu", "local_files_only": True},
            encode_kwargs={"normalize_embeddings": True},
        )
        reranker_model = _resolve_local_hf_model("BAAI/bge-reranker-base")
        self.eval_reranker = CrossEncoder(reranker_model, local_files_only=True)

        self.metric_keys = [
            "faithfulness",
            "answer_relevancy",
            "context_precision",
            "context_recall",
        ]
        self.answer_relevancy_metric = answer_relevancy
        strictness = int(os.getenv("RAGAS_ANSWER_RELEVANCY_STRICTNESS", "1"))
        if hasattr(self.answer_relevancy_metric, "strictness"):
            self.answer_relevancy_metric.strictness = strictness

        timeout_sec = int(os.getenv("RAGAS_TIMEOUT_SEC", "360"))
        max_workers = int(os.getenv("RAGAS_MAX_WORKERS", "2"))
        max_retries = int(os.getenv("RAGAS_MAX_RETRIES", "4"))
        self.run_config = RunConfig(
            timeout=timeout_sec,
            max_workers=max_workers,
            max_retries=max_retries,
            seed=42,
        )
        self.docling_fallback_reason = None

    @staticmethod
    def _extract_metric_values(result_obj: Any, metric_key: str) -> List[float]:
        try:
            values = result_obj[metric_key]
        except Exception:
            return []

        if hasattr(values, "tolist"):
            values = values.tolist()

        if isinstance(values, (int, float)):
            values = [float(values)]

        clean: List[float] = []
        for value in values:
            try:
                f = float(value)
                if f == f:  # not NaN
                    clean.append(f)
            except Exception:
                continue
        return clean

    @staticmethod
    def _mean(values: List[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    @staticmethod
    def _bootstrap_ci(values: List[float], n_boot: int = 1000) -> List[float]:
        if not values:
            return [0.0, 0.0]
        if len(values) == 1:
            v = round(values[0], 4)
            return [v, v]

        rng = random.Random(42)
        sample_size = len(values)
        means = []
        for _ in range(n_boot):
            sample = [values[rng.randrange(sample_size)] for _ in range(sample_size)]
            means.append(sum(sample) / sample_size)
        means.sort()
        low = means[int(0.025 * n_boot)]
        high = means[int(0.975 * n_boot) - 1]
        return [round(low, 4), round(high, 4)]

    @staticmethod
    def _delta_block(base: Dict[str, float], target: Dict[str, float]) -> Dict[str, Dict[str, float]]:
        out: Dict[str, Dict[str, float]] = {}
        for metric, base_val in base.items():
            if metric not in target:
                continue
            target_val = target[metric]
            abs_delta = round(target_val - base_val, 4)
            rel_delta = round(((target_val - base_val) / base_val) * 100, 2) if base_val else 0.0
            out[metric] = {
                "abs": abs_delta,
                "rel_pct": rel_delta,
            }
        return out

    @staticmethod
    def _collect_docling_signal(build_meta: Dict[str, Any]) -> Dict[str, Any]:
        source_stats = build_meta.get("source_build_stats", {}) or {}
        pages_total = 0
        pages_success = 0
        docling_chars = 0
        baseline_chars = 0
        strategy_breakdown: Dict[str, int] = {}
        actual_docling_sources = 0
        fallback_sources = 0

        for source_name, stat in source_stats.items():
            if not isinstance(stat, dict):
                continue
            if stat.get("requested_parser") != "docling":
                continue
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
            "pages_total": pages_total,
            "pages_success": pages_success,
            "page_ratio": page_ratio,
            "docling_chars": docling_chars,
            "baseline_chars": baseline_chars,
            "char_ratio": char_ratio,
            "strategy_breakdown": strategy_breakdown,
            "actual_docling_sources": actual_docling_sources,
            "fallback_sources": fallback_sources,
            "source_count": len(source_stats),
        }

    @staticmethod
    def _build_version_summary(
        version_id: str,
        label: str,
        group_key: str,
        group_scores: Dict[str, Dict[str, float]],
        group_scores_pct: Dict[str, Dict[str, float]],
        group_ci95: Dict[str, Dict[str, List[float]]],
    ) -> Dict[str, Any]:
        metrics: Dict[str, Dict[str, Any]] = {}
        for metric in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
            metrics[metric] = {
                "mean": group_scores.get(group_key, {}).get(metric, 0.0),
                "pct": group_scores_pct.get(group_key, {}).get(metric, 0.0),
                "ci95": group_ci95.get(group_key, {}).get(metric, [0.0, 0.0]),
            }
        return {
            "id": version_id,
            "label": label,
            "group_key": group_key,
            "metrics": metrics,
        }

    async def _generate_answer(self, question: str, contexts: List[str]) -> str:
        context = "\n".join(contexts)
        prompt = f"基于以下资料回答：\n{context}\n\n问题：{question}"
        max_retries = int(os.getenv("RAG_EVAL_LLM_RETRIES", "3"))
        retry_delay = float(os.getenv("RAG_EVAL_LLM_RETRY_DELAY", "1.5"))

        last_exc: Exception | None = None
        for attempt in range(1, max_retries + 1):
            try:
                resp = await self.answer_llm.ainvoke(prompt)
                return (resp.content or "").strip()
            except Exception as exc:
                last_exc = exc
                if attempt >= max_retries:
                    break
                await asyncio.sleep(retry_delay * attempt)

        print(
            f"[RAGAS] Answer generation failed after {max_retries} retries: {last_exc}. "
            "Returning empty answer for this sample."
        )
        return ""

    def _retrieve_contexts(
        self,
        vector_db: FAISS,
        question: str,
        top_k: int,
        recall_k: int,
        use_rerank: bool,
    ) -> List[str]:
        recalled_docs = vector_db.similarity_search(question, k=recall_k)
        if not use_rerank:
            return [doc.page_content for doc in recalled_docs[:top_k]]

        pairs = [[question, doc.page_content] for doc in recalled_docs]
        scores = self.eval_reranker.predict(pairs)
        scored = sorted(zip(recalled_docs, scores), key=lambda x: x[1], reverse=True)
        return [doc.page_content for doc, _ in scored[:top_k]]

    def _group_key(self, parser_mode: str, use_rerank: bool) -> str:
        suffix = "with_rerank" if use_rerank else "no_rerank"
        return f"{parser_mode}_{suffix}"

    def _prepare_group_buffers(self) -> Dict[str, Dict[str, List[Any]]]:
        keys = [
            "pypdf_no_rerank",
            "pypdf_with_rerank",
            "docling_no_rerank",
            "docling_with_rerank",
        ]
        return {
            k: {"question": [], "answer": [], "contexts": [], "ground_truth": []}
            for k in keys
        }

    @staticmethod
    def _copy_index(src_index_path: str, dst_index_path: str) -> None:
        os.makedirs(dst_index_path, exist_ok=True)
        for name in os.listdir(dst_index_path):
            target = os.path.join(dst_index_path, name)
            if os.path.isdir(target):
                shutil.rmtree(target, ignore_errors=True)
            else:
                try:
                    os.remove(target)
                except OSError:
                    pass
        for name in os.listdir(src_index_path):
            src = os.path.join(src_index_path, name)
            dst = os.path.join(dst_index_path, name)
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

    @staticmethod
    def _read_build_meta(index_path: str) -> Dict[str, Any]:
        meta_path = os.path.join(index_path, "build_meta.json")
        if not os.path.exists(meta_path):
            return {}
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _is_reusable_index(self, parser_mode: str, index_path: str) -> bool:
        index_faiss = os.path.join(index_path, "index.faiss")
        index_pkl = os.path.join(index_path, "index.pkl")
        if not (os.path.exists(index_faiss) and os.path.exists(index_pkl)):
            return False

        build_meta = self._read_build_meta(index_path)
        if not build_meta or int(build_meta.get("total_chunks", 0) or 0) <= 0:
            return False

        parser_usage = build_meta.get("parser_usage", {}) or {}
        if parser_mode == "pypdf":
            return bool(parser_usage.get("pypdf", 0))

        if parser_usage.get("docling", 0):
            return True

        docling_signal = self._collect_docling_signal(build_meta)
        return bool(docling_signal.get("actual_docling_sources", 0))

    def _build_index(self, parser_mode: str) -> str:
        index_path = os.path.join(settings.DATA_DIR, f"faiss_index_eval_{parser_mode}")
        os.makedirs(index_path, exist_ok=True)
        reuse_index = os.getenv("RAG_EVAL_REUSE_INDEX", "1") == "1"
        force_rebuild = os.getenv("RAG_EVAL_FORCE_REBUILD", "0") == "1"
        if reuse_index and not force_rebuild and self._is_reusable_index(parser_mode, index_path):
            print(f"[RAGAS] Reusing evaluation index for parser={parser_mode}: {index_path}")
            return index_path
        try:
            return init_local_rag(
                parser_mode=parser_mode,
                faiss_index_path=index_path,
                embeddings=self.eval_embeddings,
            )
        except Exception as exc:
            if parser_mode != "docling":
                raise
            baseline_path = os.path.join(settings.DATA_DIR, "faiss_index_eval_pypdf")
            baseline_faiss = os.path.join(baseline_path, "index.faiss")
            baseline_meta = os.path.join(baseline_path, "index.pkl")
            if not (os.path.exists(baseline_faiss) and os.path.exists(baseline_meta)):
                raise
            self.docling_fallback_reason = f"{type(exc).__name__}: {exc}"
            print(
                "[RAGAS] Docling index build failed. "
                f"Fallback to copied pypdf index. Reason: {self.docling_fallback_reason}"
            )
            self._copy_index(baseline_path, index_path)
            return index_path

    def _load_index(self, index_path: str) -> FAISS:
        return FAISS.load_local(
            folder_path=index_path,
            embeddings=self.eval_embeddings,
            allow_dangerous_deserialization=True,
        )

    def _write_summary_exports(self, report: Dict[str, Any]) -> Dict[str, str]:
        output_dir = Path(settings.DATA_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)

        csv_path = output_dir / "ragas_2x2_summary.csv"
        md_path = output_dir / "ragas_2x2_summary.md"

        group_order = [
            "pypdf_no_rerank",
            "pypdf_with_rerank",
            "docling_no_rerank",
            "docling_with_rerank",
        ]
        metric_order = [
            "faithfulness",
            "answer_relevancy",
            "context_precision",
            "context_recall",
        ]
        groups = report.get("groups", {})
        groups_pct = report.get("groups_pct", {})
        groups_ci95 = report.get("groups_ci95", {})
        comparisons = report.get("comparisons", {})
        versions = report.get("versions", {})
        config = report.get("config", {})

        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "section",
                    "label",
                    "group",
                    "metric",
                    "mean",
                    "pct",
                    "ci95_low",
                    "ci95_high",
                    "abs_delta",
                    "rel_pct",
                ]
            )
            for version_key, version_data in versions.items():
                for metric in metric_order:
                    metric_data = version_data.get("metrics", {}).get(metric, {})
                    ci95 = metric_data.get("ci95", [0.0, 0.0])
                    writer.writerow(
                        [
                            "version",
                            version_key,
                            version_data.get("group_key"),
                            metric,
                            metric_data.get("mean", 0.0),
                            metric_data.get("pct", 0.0),
                            ci95[0],
                            ci95[1],
                            "",
                            "",
                        ]
                    )
            for group in group_order:
                for metric in metric_order:
                    ci95 = groups_ci95.get(group, {}).get(metric, [0.0, 0.0])
                    writer.writerow(
                        [
                            "group",
                            group,
                            group,
                            metric,
                            groups.get(group, {}).get(metric, 0.0),
                            groups_pct.get(group, {}).get(metric, 0.0),
                            ci95[0],
                            ci95[1],
                            "",
                            "",
                        ]
                    )
            for comp_key, block in comparisons.items():
                for metric in metric_order:
                    item = block.get(metric, {})
                    writer.writerow(
                        [
                            "comparison",
                            comp_key,
                            "",
                            metric,
                            "",
                            "",
                            "",
                            "",
                            item.get("abs", 0.0),
                            item.get("rel_pct", 0.0),
                        ]
                    )

        md_lines = [
            "# RAGAS 2x2 Summary",
            "",
            f"- Dataset size: {config.get('dataset_size', 0)}",
            f"- Dataset target: {config.get('formal_dataset_target', 50)}",
            f"- Formal dataset ready: {config.get('formal_dataset_ready', False)}",
            f"- Docling effective: {config.get('docling_effective', False)}",
            f"- Docling chunk ratio: {config.get('docling_chunk_ratio', 0.0):.4f}",
            f"- Docling page ratio: {config.get('docling_page_ratio', 0.0):.4f}",
            f"- Docling char ratio: {config.get('docling_char_ratio', 0.0):.4f}",
            "",
            "## Executive Versions",
            "",
            "| Version | Group | Faithfulness | Precision | Recall |",
            "|---|---|---:|---:|---:|",
        ]

        for version_key in ["V1", "V2", "V3"]:
            version_data = versions.get(version_key, {})
            metrics = version_data.get("metrics", {})
            md_lines.append(
                "| "
                + version_key
                + " | "
                + str(version_data.get("group_key", "-"))
                + " | "
                + f"{metrics.get('faithfulness', {}).get('mean', 0.0):.4f}"
                + " | "
                + f"{metrics.get('context_precision', {}).get('mean', 0.0):.4f}"
                + " | "
                + f"{metrics.get('context_recall', {}).get('mean', 0.0):.4f}"
                + " |"
            )

        md_lines.extend(["", "## 2x2 Group Means", "", "| Group | Faithfulness | Relevancy | Precision | Recall |", "|---|---:|---:|---:|---:|"])
        for group in group_order:
            md_lines.append(
                "| "
                + group
                + " | "
                + " | ".join([f"{groups.get(group, {}).get(m, 0.0):.4f}" for m in metric_order])
                + " |"
            )

        md_lines.extend(["", "## Key Deltas (abs / rel%)"])
        for comp_key in [
            "rerank_gain_on_pypdf",
            "rerank_gain_on_docling",
            "docling_gain_without_rerank",
            "docling_gain_with_rerank",
            "overall_best_vs_baseline",
        ]:
            md_lines.extend(
                [
                    "",
                    f"### {comp_key}",
                    "| Metric | Abs | Rel% |",
                    "|---|---:|---:|",
                ]
            )
            block = comparisons.get(comp_key, {})
            for metric in metric_order:
                item = block.get(metric, {})
                md_lines.append(
                    f"| {metric} | {item.get('abs', 0.0):.4f} | {item.get('rel_pct', 0.0):.2f}% |"
                )

        md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
        return {"csv": str(csv_path), "markdown": str(md_path)}

    async def run_evaluation(self):
        default_dataset_path = os.path.join(settings.DATA_DIR, "golden_dataset_formal_50.json")
        if not os.path.exists(default_dataset_path):
            default_dataset_path = os.path.join(settings.DATA_DIR, "golden_dataset.json")
        dataset_path = os.getenv("RAG_EVAL_DATASET_PATH", default_dataset_path)
        if not os.path.exists(dataset_path):
            return {"error": f"找不到评测集文件: {dataset_path}"}

        with open(dataset_path, "r", encoding="utf-8") as f:
            golden_data = json.load(f)

        if not golden_data:
            return {"error": f"评测集为空: {dataset_path}"}

        top_k = int(os.getenv("RAG_EVAL_TOP_K", "3"))
        recall_k = int(os.getenv("RAG_EVAL_RECALL_K", "15"))
        formal_dataset_target = int(os.getenv("RAG_EVAL_FORMAL_SIZE", "30"))
        source_dataset_size = len(golden_data)
        if formal_dataset_target > 0 and len(golden_data) > formal_dataset_target:
            golden_data = golden_data[:formal_dataset_target]
        self.docling_fallback_reason = None

        print(f"[RAGAS] Building evaluation indexes in sequence. Dataset size: {len(golden_data)}")
        loop = asyncio.get_running_loop()
        try:
            built_pypdf_path = await loop.run_in_executor(None, self._build_index, "pypdf")
            gc.collect()
            # Build docling index after pypdf to avoid memory spikes on Windows.
            built_docling_path = await loop.run_in_executor(None, self._build_index, "docling")
            gc.collect()
        except Exception as exc:
            return {
                "error": (
                    "构建评估索引失败。请确认 docling 和本地模型缓存可用，"
                    f"详情: {exc}"
                )
            }

        pypdf_meta = self._read_build_meta(built_pypdf_path)
        docling_meta = self._read_build_meta(built_docling_path)
        docling_usage = docling_meta.get("parser_usage", {})
        docling_signal = self._collect_docling_signal(docling_meta)
        pypdf_chunks = int(pypdf_meta.get("total_chunks", 0) or 0)
        docling_chunks = int(docling_meta.get("total_chunks", 0) or 0)
        has_docling_parser = bool(docling_usage.get("docling", 0))
        raw_chunk_ratio = (docling_chunks / pypdf_chunks) if pypdf_chunks else 0.0
        docling_chunk_ratio = raw_chunk_ratio if has_docling_parser else 0.0
        min_chunk_ratio = float(os.getenv("DOCLING_MIN_CHUNK_RATIO", "0.15"))
        min_page_ratio = float(os.getenv("DOCLING_MIN_PAGE_RATIO", "0.50"))
        min_char_ratio = float(os.getenv("DOCLING_MIN_CHAR_RATIO", "0.30"))
        min_abs_chars = int(os.getenv("DOCLING_MIN_ABS_CHARS", "8000"))
        docling_page_ratio = (
            float(docling_signal.get("page_ratio", 0.0)) if has_docling_parser else 0.0
        )
        docling_char_ratio = (
            float(docling_signal.get("char_ratio", 0.0)) if has_docling_parser else 0.0
        )
        baseline_chars = int(docling_signal.get("baseline_chars", 0) or 0)
        docling_effective = (
            has_docling_parser
            and (pypdf_chunks == 0 or docling_chunk_ratio >= min_chunk_ratio)
            and (baseline_chars < min_abs_chars or docling_char_ratio >= min_char_ratio)
            and (
                int(docling_signal.get("pages_total", 0) or 0) == 0
                or docling_page_ratio >= min_page_ratio
            )
        )
        if not docling_effective and not self.docling_fallback_reason:
            self.docling_fallback_reason = (
                "Docling extraction quality below threshold: "
                f"has_docling_parser={has_docling_parser}, "
                f"chunk_ratio={docling_chunk_ratio:.4f}, "
                f"page_ratio={docling_page_ratio:.4f}, "
                f"char_ratio={docling_char_ratio:.4f}, "
                f"min_chunk_ratio={min_chunk_ratio:.4f}, "
                f"min_page_ratio={min_page_ratio:.4f}, "
                f"min_char_ratio={min_char_ratio:.4f}"
            )

        group_data = self._prepare_group_buffers()
        parser_modes = ["pypdf"]
        if docling_effective:
            parser_modes.append("docling")
        else:
            print(
                "[RAGAS] Docling ineffective in this run; "
                "docling groups will be aligned with pypdf groups."
            )

        print("[RAGAS] Generating 2x2 evaluation samples...")
        sem = asyncio.Semaphore(self.sample_concurrency)
        parser_index_map = {
            "pypdf": built_pypdf_path,
            "docling": built_docling_path,
        }

        for parser_mode in parser_modes:
            vector_db = await loop.run_in_executor(
                None, self._load_index, parser_index_map[parser_mode]
            )
            print(
                f"[RAGAS] Loaded index for parser={parser_mode}: "
                f"{parser_index_map[parser_mode]}"
            )

            async def process_item(item):
                async with sem:
                    q = item["question"]
                    gt = item["ground_truth"]
                    item_rows = []
                    for use_rerank in (False, True):
                        contexts = self._retrieve_contexts(
                            vector_db=vector_db,
                            question=q,
                            top_k=top_k,
                            recall_k=recall_k,
                            use_rerank=use_rerank,
                        )
                        answer = await self._generate_answer(q, contexts)
                        item_rows.append(
                            {
                                "key": self._group_key(parser_mode, use_rerank),
                                "question": q,
                                "ground_truth": gt,
                                "answer": answer,
                                "contexts": contexts,
                            }
                        )
                    return item_rows

            rows_nested = await asyncio.gather(*[process_item(item) for item in golden_data])
            for rows in rows_nested:
                for row in rows:
                    buffer = group_data[row["key"]]
                    buffer["question"].append(row["question"])
                    buffer["answer"].append(row["answer"])
                    buffer["contexts"].append(row["contexts"])
                    buffer["ground_truth"].append(row["ground_truth"])

            del vector_db
            gc.collect()

        print("[RAGAS] Running RAGAS scoring for 4 groups...")
        logger.info(
            "ragas_eval_runtime timeout=%ss llm_max_retries=%s max_workers=%s sample_concurrency=%s",
            self.request_timeout,
            self.llm_max_retries,
            self.run_config.max_workers,
            self.sample_concurrency,
        )

        def _run_eval(data: Dict[str, List[Any]]):
            return evaluate(
                dataset=Dataset.from_dict(data),
                metrics=[
                    faithfulness,
                    self.answer_relevancy_metric,
                    context_precision,
                    context_recall,
                ],
                llm=self.judge_llm,
                embeddings=self.eval_embeddings,
                run_config=self.run_config,
                raise_exceptions=False,
            )

        eval_results = {}
        for key, payload in group_data.items():
            if not payload.get("question"):
                continue
            eval_results[key] = await loop.run_in_executor(None, _run_eval, payload)

        group_scores: Dict[str, Dict[str, float]] = {}
        group_scores_pct: Dict[str, Dict[str, float]] = {}
        group_ci95: Dict[str, Dict[str, List[float]]] = {}

        for key, result_obj in eval_results.items():
            metric_means: Dict[str, float] = {}
            metric_pcts: Dict[str, float] = {}
            metric_cis: Dict[str, List[float]] = {}
            for metric in self.metric_keys:
                values = self._extract_metric_values(result_obj, metric)
                mean_val = round(self._mean(values), 4)
                metric_means[metric] = mean_val
                metric_pcts[metric] = round(mean_val * 100, 2)
                metric_cis[metric] = self._bootstrap_ci(values)
            group_scores[key] = metric_means
            group_scores_pct[key] = metric_pcts
            group_ci95[key] = metric_cis

        if not docling_effective:
            for suffix in ("no_rerank", "with_rerank"):
                p_key = f"pypdf_{suffix}"
                d_key = f"docling_{suffix}"
                group_scores[d_key] = copy.deepcopy(group_scores[p_key])
                group_scores_pct[d_key] = copy.deepcopy(group_scores_pct[p_key])
                group_ci95[d_key] = copy.deepcopy(group_ci95[p_key])

        comparisons = {
            "rerank_gain_on_pypdf": self._delta_block(
                group_scores["pypdf_no_rerank"],
                group_scores["pypdf_with_rerank"],
            ),
            "rerank_gain_on_docling": self._delta_block(
                group_scores["docling_no_rerank"],
                group_scores["docling_with_rerank"],
            ),
            "docling_gain_without_rerank": self._delta_block(
                group_scores["pypdf_no_rerank"],
                group_scores["docling_no_rerank"],
            ),
            "docling_gain_with_rerank": self._delta_block(
                group_scores["pypdf_with_rerank"],
                group_scores["docling_with_rerank"],
            ),
            "overall_best_vs_baseline": self._delta_block(
                group_scores["pypdf_no_rerank"],
                group_scores["docling_with_rerank"],
            ),
        }

        versions = {
            "V1": self._build_version_summary(
                "V1",
                "Baseline",
                "pypdf_no_rerank",
                group_scores,
                group_scores_pct,
                group_ci95,
            ),
            "V2": self._build_version_summary(
                "V2",
                "Rerank",
                "pypdf_with_rerank",
                group_scores,
                group_scores_pct,
                group_ci95,
            ),
            "V3": self._build_version_summary(
                "V3",
                "Docling + Rerank",
                "docling_with_rerank",
                group_scores,
                group_scores_pct,
                group_ci95,
            ),
        }

        final_report = {
            "config": {
                "dataset_size": len(golden_data),
                "dataset_source_size": source_dataset_size,
                "dataset_path": dataset_path,
                "dataset_name": os.path.basename(dataset_path),
                "formal_dataset_target": formal_dataset_target,
                "formal_dataset_ready": len(golden_data) >= formal_dataset_target,
                "top_k": top_k,
                "recall_k": recall_k,
                "temperature": 0,
                "index_paths": {
                    "pypdf": built_pypdf_path,
                    "docling": built_docling_path,
                },
                "index_build_meta": {
                    "pypdf": pypdf_meta,
                    "docling": docling_meta,
                },
                "docling_effective": docling_effective,
                "docling_chunk_ratio": round(docling_chunk_ratio, 4),
                "docling_page_ratio": round(docling_page_ratio, 4),
                "docling_char_ratio": round(docling_char_ratio, 4),
                "docling_signal": docling_signal,
                "docling_fallback": bool(self.docling_fallback_reason),
                "docling_fallback_reason": self.docling_fallback_reason,
                "v3_real_effective": docling_effective,
            },
            "groups": group_scores,
            "groups_pct": group_scores_pct,
            "groups_ci95": group_ci95,
            "comparisons": comparisons,
            "versions": versions,
            # Backward compatibility for old UI blocks
            "no_rerank": group_scores["pypdf_no_rerank"],
            "with_rerank": group_scores["pypdf_with_rerank"],
        }

        try:
            final_report["export_paths"] = self._write_summary_exports(final_report)
        except Exception as exc:
            final_report["export_error"] = f"{type(exc).__name__}: {exc}"

        try:
            final_report["version_record"] = experiment_version_service.record_ragas_snapshot(final_report)
        except Exception as exc:
            final_report["version_record_error"] = f"{type(exc).__name__}: {exc}"

        print(f"[RAGAS] 2x2 evaluation completed: {final_report}")
        return final_report


ragas_service = RagasService()


