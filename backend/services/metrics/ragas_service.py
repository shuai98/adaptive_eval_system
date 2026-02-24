import asyncio
import os
import json
import pandas as pd
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
from langchain_openai import ChatOpenAI
from langchain_huggingface import HuggingFaceEmbeddings

from backend.services.rag_service import rag_service
from backend.services.llm_service import llm_service
from backend.core.config import settings

class RagasService:
    def __init__(self):
        # 裁判模型 (DeepSeek)
        self.judge_llm = ChatOpenAI(
            model='deepseek-chat',
            openai_api_key=os.getenv("DEEPSEEK_API_KEY"),
            openai_api_base='https://api.deepseek.com/v1',
            temperature=0,
            n=1
        )
        
        # Embedding (BGE)
        self.eval_embeddings = HuggingFaceEmbeddings(
            model_name="BAAI/bge-small-zh-v1.5",
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )

    async def run_evaluation(self):
        # 1. 加载数据集
        dataset_path = os.path.join(settings.DATA_DIR, "golden_dataset.json")
        if not os.path.exists(dataset_path):
            return {"error": "找不到 golden_dataset.json"}

        with open(dataset_path, "r", encoding="utf-8") as f:
            golden_data = json.load(f)

        # 准备两套数据容器
        data_no_rerank = {"question": [], "answer": [], "contexts": [], "ground_truth": []}
        data_with_rerank = {"question": [], "answer": [], "contexts": [], "ground_truth": []}

        # 2. 并发生成数据
        print(f"[RAGAS] 开始并发生成对比数据 (数据集大小: {len(golden_data)})...")
        
        # 限制并发数为 3，防止触发 API Rate Limit
        sem = asyncio.Semaphore(3)

        async def process_item(item):
            async with sem:
                q = item['question']
                gt = item['ground_truth']
                
                # 1. 异步检索
                search_result = await rag_service.search_async(q)
                
                # --- 组 A: 无 Rerank ---
                docs_a = search_result["raw_docs"] 
                context_a = "\n".join(docs_a)
                prompt_a = f"基于以下资料回答：\n{context_a}\n\n问题：{q}"
                
                # 异步生成
                resp_a = await llm_service.llm.ainvoke(prompt_a)
                ans_a = resp_a.content
                
                # --- 组 B: 有 Rerank ---
                docs_b = search_result["rerank_docs"]
                context_b = "\n".join(docs_b)
                prompt_b = f"基于以下资料回答：\n{context_b}\n\n问题：{q}"
                
                # 异步生成
                resp_b = await llm_service.llm.ainvoke(prompt_b)
                ans_b = resp_b.content
                
                return {
                    "q": q, "gt": gt,
                    "ans_a": ans_a, "ctx_a": docs_a,
                    "ans_b": ans_b, "ctx_b": docs_b
                }

        # 执行并发任务
        tasks = [process_item(item) for item in golden_data]
        results = await asyncio.gather(*tasks)

        # 整理结果
        for res in results:
            data_no_rerank["question"].append(res["q"])
            data_no_rerank["answer"].append(res["ans_a"])
            data_no_rerank["contexts"].append(res["ctx_a"])
            data_no_rerank["ground_truth"].append(res["gt"])
            
            data_with_rerank["question"].append(res["q"])
            data_with_rerank["answer"].append(res["ans_b"])
            data_with_rerank["contexts"].append(res["ctx_b"])
            data_with_rerank["ground_truth"].append(res["gt"])

        # 2. 执行评测 (跑两次)
        # 注意：ragas.evaluate 是同步阻塞的，且可能内部有 async 逻辑
        # 为了不阻塞 FastAPI 主线程，我们将其放入线程池
        loop = asyncio.get_running_loop()

        def _run_eval(data):
            return evaluate(
                dataset=Dataset.from_dict(data),
                metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
                llm=self.judge_llm,
                embeddings=self.eval_embeddings
            )

        print("[RAGAS] 正在评测：无 Rerank 组 & 有 Rerank 组 (并行执行)...")
        
        # 并行执行两个评测任务，时间减半
        future_a = loop.run_in_executor(None, _run_eval, data_no_rerank)
        future_b = loop.run_in_executor(None, _run_eval, data_with_rerank)
        
        results_a, results_b = await asyncio.gather(future_a, future_b)

        # 3. 辅助函数：计算平均分
        def safe_mean(res, metric_key):
            try:
                val = res[metric_key]
            except KeyError:
                return 0.0

            if isinstance(val, list):
                # 过滤 NaN
                valid = [v for v in val if pd.notna(v)]
                return sum(valid) / len(valid) if valid else 0.0
            
            try:
                return float(val)
            except:
                return 0.0

        # 4. 组装最终对比数据
        final_report = {
            "no_rerank": {
                "faithfulness": round(safe_mean(results_a, "faithfulness"), 4),
                "answer_relevancy": round(safe_mean(results_a, "answer_relevancy"), 4),
                "context_precision": round(safe_mean(results_a, "context_precision"), 4),
                "context_recall": round(safe_mean(results_a, "context_recall"), 4)
            },
            "with_rerank": {
                "faithfulness": round(safe_mean(results_b, "faithfulness"), 4),
                "answer_relevancy": round(safe_mean(results_b, "answer_relevancy"), 4),
                "context_precision": round(safe_mean(results_b, "context_precision"), 4),
                "context_recall": round(safe_mean(results_b, "context_recall"), 4)
            }
        }
        
        print(f"[RAGAS] 对比评测完成: {final_report}")
        return final_report

ragas_service = RagasService()