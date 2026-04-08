from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from backend.db.session import SessionLocal
from backend.models.tables import ExperimentVersion


def _env_flag(name: str, default: str) -> str:
    return os.getenv(name, default)


class ExperimentVersionService:
    def build_runtime_snapshot(self) -> Dict[str, Any]:
        return {
            "dataset_name": os.path.basename(_env_flag("RAG_EVAL_DATASET_PATH", "golden_dataset_formal_50.json")),
            "index_name": os.path.basename(_env_flag("RAG_RUNTIME_INDEX_PATH", "faiss_index")),
            "parser_mode": _env_flag("RAG_RUNTIME_PARSER_MODE", _env_flag("RAG_PDF_PARSER", "docling")),
            "rerank_mode": "disabled" if _env_flag("RAG_FAST_MODE", "true").lower() == "true" else "enabled",
            "prompt_version": _env_flag("PROMPT_VERSION", "v1"),
        }

    def record_snapshot(
        self,
        scene: str,
        version_key: str,
        summary: Dict[str, Any],
        db: Session | None = None,
    ) -> ExperimentVersion:
        own_session = db is None
        session = db or SessionLocal()
        try:
            runtime = self.build_runtime_snapshot()
            row = ExperimentVersion(
                scene=scene,
                version_key=version_key,
                dataset_name=summary.get("dataset_name") or runtime["dataset_name"],
                index_name=summary.get("index_name") or runtime["index_name"],
                parser_mode=summary.get("parser_mode") or runtime["parser_mode"],
                rerank_mode=summary.get("rerank_mode") or runtime["rerank_mode"],
                prompt_version=summary.get("prompt_version") or runtime["prompt_version"],
                summary_json=json.dumps(summary, ensure_ascii=False, default=str),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row
        finally:
            if own_session:
                session.close()

    def record_ragas_snapshot(self, report: Dict[str, Any]) -> Dict[str, Any]:
        config = report.get("config", {})
        version_key = f"ragas-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        summary = {
            "dataset_name": config.get("dataset_name"),
            "index_name": os.path.basename((config.get("index_paths", {}) or {}).get("docling", "")) or "faiss_index_eval_docling",
            "parser_mode": "docling" if config.get("docling_effective") else "pypdf",
            "rerank_mode": "enabled",
            "prompt_version": _env_flag("PROMPT_VERSION", "ragas-v1"),
            "dataset_size": config.get("dataset_size"),
            "formal_dataset_ready": config.get("formal_dataset_ready"),
            "docling_effective": config.get("docling_effective"),
            "v1": (report.get("versions", {}) or {}).get("V1", {}),
            "v2": (report.get("versions", {}) or {}).get("V2", {}),
            "v3": (report.get("versions", {}) or {}).get("V3", {}),
        }
        row = self.record_snapshot("ragas_eval", version_key, summary)
        return {
            "id": row.id,
            "scene": row.scene,
            "version_key": row.version_key,
            "created_at": row.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }

    def list_versions(self, scene: str | None = None, limit: int = 10) -> List[Dict[str, Any]]:
        db = SessionLocal()
        try:
            query = db.query(ExperimentVersion).order_by(ExperimentVersion.created_at.desc())
            if scene:
                query = query.filter(ExperimentVersion.scene == scene)
            rows = query.limit(limit).all()
            return [
                {
                    "id": row.id,
                    "scene": row.scene,
                    "version_key": row.version_key,
                    "dataset_name": row.dataset_name,
                    "index_name": row.index_name,
                    "parser_mode": row.parser_mode,
                    "rerank_mode": row.rerank_mode,
                    "prompt_version": row.prompt_version,
                    "created_at": row.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                }
                for row in rows
            ]
        finally:
            db.close()


experiment_version_service = ExperimentVersionService()
