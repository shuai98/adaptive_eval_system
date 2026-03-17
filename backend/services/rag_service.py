import os
import time
import json
import random
import redis # <--- 新增
#保持镜像源配置
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from sentence_transformers import CrossEncoder
from backend.core.config import settings # <--- 新增：读取 Redis 配置


class RAGService:
    def __init__(self):
        self.embeddings = None
        self.vector_db = None
        self.reranker = None
        self.is_initialized = False
        
        # --- 新增：连接 Redis ---
        try:
            self.redis_client = redis.Redis(
                host=settings.REDIS_HOST, 
                port=settings.REDIS_PORT, 
                db=settings.REDIS_DB,
                decode_responses=True # 自动将字节转为字符串
            )
            self.redis_client.ping() # 测试连接
            print("[System] Redis Connected Successfully.")
            self.use_redis = True
        except Exception as e:
            print(f"[Warning] Redis connection failed: {e}. Caching disabled.")
            self.use_redis = False

    def initialize(self):
        if self.is_initialized:
            return

        print("-" * 30)
        print("[System] Loading Embedding Model...")
        self.embeddings = HuggingFaceEmbeddings(
            model_name="BAAI/bge-small-zh-v1.5",
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )

        # 动态获取路径
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
            print(" FAISS 索引加载成功！")
        except Exception as e:
            print(f" [Warning] FAISS load failed: {e}")
            self.vector_db = None

        print("[System] Loading Rerank Model...")
        self.reranker = CrossEncoder('BAAI/bge-reranker-base')
        self.is_initialized = True
        print("[System] RAG Service Initialized.")
        print("-" * 30)

    def reload_db(self):
        # 重新加载逻辑
        print("[System] Reloading FAISS Index...")
        # 复用 initialize 里的路径逻辑，或者简单调用 initialize (如果支持重入)
        # 这里为了简单，我们重新走一遍加载流程
        self.is_initialized = False 
        self.initialize()
        return True

    #检索的全流程
    def search(self, keyword, top_k=3):
        #如果向量数据库还没准备好
        if not self.vector_db:
            return {"final_docs": [], "raw_docs": [], "rerank_docs": [], "timings": {}}

        # --- 1. 查缓存 (Cache Hit) ---
        cache_key = f"rag:{keyword}:{top_k}"
        
        if self.use_redis:
            try:
                # 1. 开始计时
                t0 = time.perf_counter()
                
                cached_data = self.redis_client.get(cache_key)
                
                # 2. 结束计时
                t1 = time.perf_counter()
                redis_cost_ms = (t1 - t0) * 1000  # 转换为毫秒

                if cached_data:
                    print(f" [Redis] 命中缓存: {keyword} (耗时: {redis_cost_ms:.2f}ms)")
                    data = json.loads(cached_data)
                    
                    # --- 填入真实的 Redis 读取时间 ---
                    # 把 Redis 读取时间算作 "recall" 时间，因为它们都是“取回数据”的过程
                    data["timings"]["recall"] = f"{redis_cost_ms:.2f}ms (Redis)"
                    
                    # Rerank 确实没做，所以是真正的 0，可以标记为 Skipped
                    data["timings"]["rerank"] = "0ms (Skipped)"
                    
                    return data
            except Exception as e:
                print(f"[Redis Error] Read failed: {e}")
                
        # --- 2. 没命中，走正常流程 (Cache Miss) ---
        print(f" [Redis] 未命中，执行检索: {keyword}")
        
        t0 = time.time()
        # 1. 初步检索 (扩大召回范围到 15 个)
        initial_docs = self.vector_db.similarity_search(keyword, k=15)
        t1 = time.time()
        recall_time_ms = (t1 - t0) * 1000
        
        # 2. 重排序
        pairs = [[keyword, doc.page_content] for doc in initial_docs]
        scores = self.reranker.predict(pairs)
        t2 = time.time()
        rerank_time_ms = (t2 - t1) * 1000

        scored_docs = sorted(zip(initial_docs, scores), key=lambda x: x[1], reverse=True)
        
        # 3. 随机/截断逻辑
        top_candidates = [doc for doc, score in scored_docs[:6]]
        
        if len(top_candidates) >= top_k:
            final_docs_objs = random.sample(top_candidates, top_k)
        else:
            final_docs_objs = top_candidates
            
        # --- 4. 格式化结果 (转成纯文本列表，方便缓存) ---
        # 注意：这里我们将 Document 对象转成了字符串列表
        result = {
            "final_docs": [d.page_content for d in final_docs_objs], 
            "raw_docs": [d.page_content for d in initial_docs[:3]],
            "rerank_docs": [d.page_content for d in final_docs_objs],
            "timings": {
                "recall": f"{recall_time_ms:.0f}ms",
                "rerank": f"{rerank_time_ms:.0f}ms"
            }
        }

        # --- 5. 写入缓存 (TTL 1小时) ---
        if self.use_redis:
            try:
                self.redis_client.setex(cache_key, 3600, json.dumps(result))
            except Exception as e:
                print(f"[Redis Error] Write failed: {e}")

        return result

    async def search_async(self, keyword, top_k=3):
        """
        异步检索入口：将 CPU 密集的 search 方法放入线程池运行
        避免阻塞 FastAPI 主线程
        """
        import asyncio
        loop = asyncio.get_running_loop()
        
        # run_in_executor(None, ...) 使用默认线程池
        return await loop.run_in_executor(None, self.search, keyword, top_k)

# 单例模式：全局只初始化一次
rag_service = RAGService()