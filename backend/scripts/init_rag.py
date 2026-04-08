import gc
import glob
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_huggingface.embeddings import HuggingFaceEmbeddings
from langchain_text_splitters.character import RecursiveCharacterTextSplitter

# Keep HF mirror for mainland network conditions.
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

SUPPORTED_SOURCE_EXTENSIONS = {".pdf", ".txt"}


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


def _resolve_project_paths() -> tuple[str, str, str]:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, "../../"))
    docs_dir = os.path.join(project_root, "data", "docs")
    default_faiss_path = os.path.join(project_root, "data", "faiss_index")
    return project_root, docs_dir, default_faiss_path


def resolve_rag_build_config(
    parser_mode: Optional[str] = None,
    faiss_index_path: Optional[str] = None,
) -> Dict[str, Any]:
    load_dotenv(override=True)
    project_root, docs_dir, default_faiss_path = _resolve_project_paths()
    parser = (parser_mode or os.getenv("RAG_PDF_PARSER", "docling")).strip().lower()
    if parser not in {"pypdf", "docling"}:
        print(f" [Warning] Unsupported parser '{parser}', fallback to 'pypdf'.")
        parser = "pypdf"
    return {
        "project_root": project_root,
        "docs_dir": docs_dir,
        "index_path": os.path.abspath(faiss_index_path) if faiss_index_path else default_faiss_path,
        "parser": parser,
        "chunk_size": int(os.getenv("RAG_CHUNK_SIZE", "500")),
        "chunk_overlap": int(os.getenv("RAG_CHUNK_OVERLAP", "50")),
    }


def list_supported_source_files(docs_dir: str) -> List[str]:
    if not os.path.exists(docs_dir):
        return []
    files = [
        os.path.join(docs_dir, name)
        for name in os.listdir(docs_dir)
        if os.path.splitext(name)[1].lower() in SUPPORTED_SOURCE_EXTENSIONS
    ]
    return sorted(files)


def _safe_int(value: str, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_float(value: str, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _env_flag(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() == "true"


def _doc_chars(docs: List[Document]) -> int:
    return sum(len((doc.page_content or "").strip()) for doc in docs)


def _normalize_page_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _batched_documents(documents: List[Document], batch_size: int):
    for start in range(0, len(documents), batch_size):
        yield documents[start : start + batch_size]


def _build_docling_standard_options():
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import PdfFormatOption

    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = _env_flag("DOCLING_ENABLE_OCR", False)
    pipeline_options.do_table_structure = _env_flag("DOCLING_ENABLE_TABLES", False)
    pipeline_options.do_code_enrichment = _env_flag(
        "DOCLING_ENABLE_CODE_ENRICHMENT", False
    )
    pipeline_options.do_formula_enrichment = _env_flag(
        "DOCLING_ENABLE_FORMULA_ENRICHMENT", False
    )
    pipeline_options.force_backend_text = _env_flag("DOCLING_FORCE_BACKEND_TEXT", True)
    pipeline_options.images_scale = _safe_float(
        os.getenv("DOCLING_IMAGES_SCALE", "0.5"),
        0.5,
    )
    pipeline_options.generate_page_images = False
    pipeline_options.generate_picture_images = False
    pipeline_options.generate_parsed_pages = False

    os.environ.setdefault(
        "DOCLING_PERF_PAGE_BATCH_SIZE",
        str(_safe_int(os.getenv("DOCLING_PERF_PAGE_BATCH_SIZE", "1"), 1)),
    )
    os.environ.setdefault(
        "DOCLING_PERF_DOC_BATCH_SIZE",
        str(_safe_int(os.getenv("DOCLING_PERF_DOC_BATCH_SIZE", "1"), 1)),
    )

    return {
        InputFormat.PDF: PdfFormatOption(
            pipeline_options=pipeline_options,
        )
    }, pipeline_options


def _load_pdf_with_docling_standard(
    file_path: str,
) -> Tuple[List[Document], Dict[str, Any]]:
    from docling.document_converter import DocumentConverter

    format_options, pipeline_options = _build_docling_standard_options()
    converter = DocumentConverter(format_options=format_options)

    convert_kwargs: Dict[str, Any] = {"raises_on_error": False}
    page_end = _safe_int(os.getenv("DOCLING_STANDARD_PAGE_END", "0"), 0)
    if page_end > 0:
        convert_kwargs["page_range"] = (
            _safe_int(os.getenv("DOCLING_STANDARD_PAGE_START", "1"), 1),
            page_end,
        )

    result = converter.convert(file_path, **convert_kwargs)
    markdown = result.document.export_to_markdown()
    if not markdown or not markdown.strip():
        errors = "; ".join(str(err) for err in result.errors) if result.errors else ""
        raise ValueError(f"Docling standard strategy returned empty markdown. {errors}")

    stats = {
        "requested_parser": "docling",
        "actual_parser": "docling",
        "docling_strategy": "standard",
        "docling_status": str(result.status),
        "docling_errors": len(result.errors or []),
        "docling_force_backend_text": pipeline_options.force_backend_text,
        "docling_images_scale": pipeline_options.images_scale,
        "docling_used_ocr": pipeline_options.do_ocr,
        "docling_used_tables": pipeline_options.do_table_structure,
    }
    return (
        [
            Document(
                page_content=markdown,
                metadata={
                    "source": file_path,
                    "parser": "docling",
                    "docling_strategy": "standard",
                },
            )
        ],
        stats,
    )


def _load_pdf_with_docling_backend(
    file_path: str,
) -> Tuple[List[Document], Dict[str, Any]]:
    from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.document import InputDocument

    page_min_chars = _safe_int(os.getenv("DOCLING_MIN_PAGE_CHARS", "1"), 1)
    input_doc = InputDocument(Path(file_path), InputFormat.PDF, PyPdfiumDocumentBackend)
    if not input_doc.valid:
        raise ValueError(f"Docling backend could not open {os.path.basename(file_path)}")

    backend = input_doc._backend
    total_pages = int(input_doc.page_count or 0)
    documents: List[Document] = []
    success_pages = 0
    empty_pages = 0

    try:
        for page_index in range(total_pages):
            page_backend = backend.load_page(page_index)
            try:
                text_cells = page_backend.get_text_cells()
                page_text = _normalize_page_text(
                    " ".join(cell.text for cell in text_cells if (cell.text or "").strip())
                )
            finally:
                page_backend.unload()

            if len(page_text) < page_min_chars:
                empty_pages += 1
                continue

            success_pages += 1
            documents.append(
                Document(
                    page_content=page_text,
                    metadata={
                        "source": file_path,
                        "parser": "docling",
                        "docling_strategy": "backend_only",
                        "page": page_index + 1,
                    },
                )
            )
    finally:
        backend.unload()
        gc.collect()

    if not documents:
        raise ValueError(
            f"Docling backend extracted no usable text pages from {os.path.basename(file_path)}"
        )

    stats = {
        "requested_parser": "docling",
        "actual_parser": "docling",
        "docling_strategy": "backend_only",
        "docling_pages_total": total_pages,
        "docling_pages_success": success_pages,
        "docling_pages_empty": empty_pages,
        "docling_page_ratio": round(success_pages / total_pages, 4) if total_pages else 0.0,
        "docling_errors": 0,
    }
    return documents, stats


def _load_pdf_with_docling(file_path: str) -> Tuple[List[Document], Dict[str, Any]]:
    strategies = [
        item.strip().lower()
        for item in os.getenv("DOCLING_STRATEGY", "backend_only,standard").split(",")
        if item.strip()
    ]
    last_exc: Exception | None = None

    for strategy in strategies:
        try:
            if strategy == "backend_only":
                return _load_pdf_with_docling_backend(file_path)
            if strategy == "standard":
                return _load_pdf_with_docling_standard(file_path)
            print(f"    Unknown docling strategy '{strategy}', skipping.")
        except Exception as exc:
            last_exc = exc
            print(
                f"    Docling strategy '{strategy}' failed for "
                f"{os.path.basename(file_path)}: {exc}"
            )
            gc.collect()

    raise RuntimeError(
        f"All docling strategies failed for {os.path.basename(file_path)}: {last_exc}"
    )


def _load_pdf_with_pypdf(file_path: str) -> List[Document]:
    loader = PyPDFLoader(file_path)
    docs = loader.load()
    for doc in docs:
        doc.metadata = doc.metadata or {}
        doc.metadata["parser"] = "pypdf"
    return docs


def _load_pdf(file_path: str, parser_mode: str) -> Tuple[List[Document], Dict[str, Any]]:
    use_docling = parser_mode == "docling"
    if use_docling:
        baseline_docs: List[Document] | None = None
        try:
            docs, stats = _load_pdf_with_docling(file_path)
            quality_check = os.getenv("DOCLING_QUALITY_CHECK", "true").lower() == "true"
            if quality_check:
                baseline_docs = _load_pdf_with_pypdf(file_path)
                docling_chars = _doc_chars(docs)
                baseline_chars = _doc_chars(baseline_docs)
                min_ratio = float(os.getenv("DOCLING_MIN_CHAR_RATIO", "0.30"))
                min_chars = int(os.getenv("DOCLING_MIN_ABS_CHARS", "8000"))
                min_page_ratio = float(os.getenv("DOCLING_MIN_PAGE_RATIO", "0.50"))
                ratio = (docling_chars / baseline_chars) if baseline_chars > 0 else 1.0
                page_ratio = stats.get("docling_page_ratio")
                if (
                    (baseline_chars >= min_chars and docling_chars < min_chars)
                    or ratio < min_ratio
                    or (
                        isinstance(page_ratio, (float, int))
                        and baseline_chars >= min_chars
                        and page_ratio < min_page_ratio
                    )
                ):
                    raise ValueError(
                        f"docling quality too low (chars={docling_chars}, "
                        f"baseline_chars={baseline_chars}, ratio={ratio:.3f}, "
                        f"page_ratio={page_ratio})"
                    )
                stats["docling_chars"] = docling_chars
                stats["baseline_chars"] = baseline_chars
                stats["docling_char_ratio"] = round(ratio, 4)
            print(f"    Loaded PDF via Docling: {os.path.basename(file_path)}")
            return docs, stats
        except Exception as exc:
            print(
                f"    Docling failed for {os.path.basename(file_path)}: {exc}. "
                "Falling back to PyPDFLoader."
            )
            if baseline_docs is not None:
                print(f"    Loaded PDF via PyPDFLoader: {os.path.basename(file_path)}")
                return baseline_docs, {
                    "requested_parser": "docling",
                    "actual_parser": "pypdf",
                    "docling_strategy": "fallback_to_pypdf",
                    "fallback_reason": f"{type(exc).__name__}: {exc}",
                    "docling_page_ratio": 0.0,
                    "docling_char_ratio": 0.0,
                }

    docs = _load_pdf_with_pypdf(file_path)
    print(f"    Loaded PDF via PyPDFLoader: {os.path.basename(file_path)}")
    return docs, {
        "requested_parser": "pypdf",
        "actual_parser": "pypdf",
        "docling_strategy": None,
    }


def load_source_documents(file_path: str, parser_mode: str) -> Tuple[List[Document], Dict[str, Any]]:
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".txt":
        loader = TextLoader(file_path, encoding="utf-8")
        loaded = loader.load()
        for doc in loaded:
            doc.metadata = doc.metadata or {}
            doc.metadata["source"] = file_path
            doc.metadata["parser"] = "text"
        return loaded, {
            "requested_parser": "text",
            "actual_parser": "text",
            "docling_strategy": None,
        }
    if ext == ".pdf":
        return _load_pdf(file_path, parser_mode)
    raise ValueError(f"Unsupported source extension: {ext or 'unknown'}")


def split_documents_for_rag(
    documents: List[Document],
    chunk_size: int,
    chunk_overlap: int,
) -> List[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return splitter.split_documents(documents)


def summarize_documents(documents: List[Document]) -> Tuple[Dict[str, int], Dict[str, int]]:
    parser_usage: Dict[str, int] = {}
    source_usage: Dict[str, int] = {}
    for doc in documents:
        parser_key = (doc.metadata or {}).get("parser", "unknown")
        parser_usage[parser_key] = parser_usage.get(parser_key, 0) + 1
        source_key = os.path.basename((doc.metadata or {}).get("source", "unknown"))
        source_usage[source_key] = source_usage.get(source_key, 0) + 1
    return parser_usage, source_usage


def read_build_meta(index_path: str) -> Dict[str, Any]:
    meta_path = os.path.join(index_path, "build_meta.json")
    if not os.path.exists(meta_path):
        return {}
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def write_build_meta(index_path: str, build_meta: Dict[str, Any]) -> None:
    os.makedirs(index_path, exist_ok=True)
    with open(os.path.join(index_path, "build_meta.json"), "w", encoding="utf-8") as f:
        json.dump(build_meta, f, ensure_ascii=False, indent=2)


def faiss_index_exists(index_path: str) -> bool:
    return os.path.exists(os.path.join(index_path, "index.faiss")) and os.path.exists(
        os.path.join(index_path, "index.pkl")
    )


def get_embedding_model(embeddings: Optional[Any] = None):
    if embeddings is not None:
        print(" Reusing provided embedding model instance.")
        return embeddings

    print(" Loading BGE embedding model...")
    embedding_model = _resolve_local_hf_model("BAAI/bge-small-zh-v1.5")
    return HuggingFaceEmbeddings(
        model_name=embedding_model,
        model_kwargs={"device": "cpu", "local_files_only": True},
        encode_kwargs={"normalize_embeddings": True},
    )


def init_local_rag(
    parser_mode: Optional[str] = None,
    faiss_index_path: Optional[str] = None,
    embeddings: Optional[Any] = None,
) -> str:
    """
    Build FAISS index from files under data/docs.
    Returns the absolute FAISS index path that was written.
    """
    config = resolve_rag_build_config(parser_mode=parser_mode, faiss_index_path=faiss_index_path)
    project_root = config["project_root"]
    docs_dir = config["docs_dir"]
    index_path = config["index_path"]
    parser = config["parser"]
    chunk_size = config["chunk_size"]
    chunk_overlap = config["chunk_overlap"]

    print(f" Project root: {project_root}")
    print(f" Docs directory: {docs_dir}")
    print(f" FAISS save path: {index_path}")
    print(f" PDF parser mode: {parser}")
    print(f" Splitter config: chunk_size={chunk_size}, overlap={chunk_overlap}")
    print("-" * 30)
    print(" Start initializing RAG knowledge base...")

    documents: List[Document] = []
    source_build_stats: Dict[str, Dict[str, Any]] = {}

    if not os.path.exists(docs_dir):
        print(f" [Error] docs directory not found: {docs_dir}")
        os.makedirs(docs_dir, exist_ok=True)
        print(" Created empty docs directory. Put PDF/TXT files and retry.")
        return index_path

    txt_files = glob.glob(os.path.join(docs_dir, "*.txt"))
    for file_path in txt_files:
        try:
            loaded, file_stats = load_source_documents(file_path, parser)
            documents.extend(loaded)
            source_build_stats[os.path.basename(file_path)] = file_stats
            print(f"    Loaded TXT: {os.path.basename(file_path)}")
        except Exception as exc:
            print(f"    Failed to load TXT {os.path.basename(file_path)}: {exc}")

    pdf_files = glob.glob(os.path.join(docs_dir, "*.pdf"))
    for file_path in pdf_files:
        try:
            loaded_docs, file_stats = load_source_documents(file_path, parser)
            documents.extend(loaded_docs)
            source_build_stats[os.path.basename(file_path)] = file_stats
        except Exception as exc:
            print(f"    Failed to load PDF {os.path.basename(file_path)}: {exc}")

    if not documents:
        print(" [Warning] No valid documents found under data/docs.")
        return index_path

    parser_usage, source_usage = summarize_documents(documents)
    print(f" Parser usage stats: {parser_usage}")
    print(f" Source usage stats: {source_usage}")
    chunks = split_documents_for_rag(documents, chunk_size, chunk_overlap)
    print(f" Split done. Total chunks: {len(chunks)}")

    used_embeddings = get_embedding_model(embeddings)

    print(" Building FAISS index...")
    faiss_batch_size = _safe_int(os.getenv("RAG_FAISS_BATCH_SIZE", "64"), 64)
    first_batch = chunks[:faiss_batch_size]
    vector_db = FAISS.from_documents(first_batch, used_embeddings)
    del first_batch
    gc.collect()
    for batch in _batched_documents(chunks[faiss_batch_size:], faiss_batch_size):
        vector_db.add_documents(batch)
        del batch
        gc.collect()

    os.makedirs(index_path, exist_ok=True)
    vector_db.save_local(index_path)
    build_meta = {
        "requested_parser": parser,
        "parser_usage": parser_usage,
        "source_usage": source_usage,
        "source_build_stats": source_build_stats,
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "total_documents": len(documents),
        "total_chunks": len(chunks),
    }
    write_build_meta(index_path, build_meta)
    print(f" Success! FAISS index saved to: {index_path}")
    return index_path


if __name__ == "__main__":
    init_local_rag()
