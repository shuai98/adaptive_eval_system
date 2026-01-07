import os
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from sentence_transformers import CrossEncoder

class RAGService:
    def __init__(self):
        self.embeddings = None
        self.vector_db = None
        self.reranker = None
        self.is_initialized = False

    def initialize(self):
        if self.is_initialized:
            return

        print("[System] Loading Embedding Model...")
        self.embeddings = HuggingFaceEmbeddings(
            model_name="BAAI/bge-small-zh-v1.5",
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )

        # 动态获取路径：从当前文件往上找3层，进入 data/faiss_index
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(current_dir, "../.."))
        index_path = os.path.join(project_root, "data", "faiss_index")

        print(f"[System] Loading FAISS Index from: {index_path}")
        try:
            self.vector_db = FAISS.load_local(
                folder_path=index_path, 
                embeddings=self.embeddings,
                allow_dangerous_deserialization=True
            )
        except Exception as e:
            print(f"[Warning] FAISS load failed: {e}")
            self.vector_db = None

        print("[System] Loading Rerank Model...")
        self.reranker = CrossEncoder('BAAI/bge-reranker-base')
        self.is_initialized = True
        print("[System] RAG Service Initialized.")

    def reload_db(self):
        # 用于教师上传文件后重新加载向量库
        print("[System] Reloading FAISS Index...")
        try:
            self.vector_db = FAISS.load_local(
                folder_path="./faiss_index", 
                embeddings=self.embeddings,
                allow_dangerous_deserialization=True
            )
            return True
        except Exception as e:
            print(f"[Error] Reload failed: {e}")
            return False

    def search(self, keyword, top_k=3):
        if not self.vector_db:
            return {"final_docs": [], "raw_docs": [], "rerank_docs": []}

        # 1. 初步检索 (Recall)
        initial_docs = self.vector_db.similarity_search(keyword, k=10)
        
        # 2. 重排序 (Rerank)
        pairs = [[keyword, doc.page_content] for doc in initial_docs]
        scores = self.reranker.predict(pairs)
        scored_docs = sorted(zip(initial_docs, scores), key=lambda x: x[1], reverse=True)
        
        final_docs = [doc for doc, score in scored_docs[:top_k]]
        
        return {
            "final_docs": final_docs,
            "raw_docs": [doc.page_content for doc in initial_docs[:3]],
            "rerank_docs": [doc.page_content for doc in final_docs]
        }

# 单例模式：全局只初始化一次
rag_service = RAGService()