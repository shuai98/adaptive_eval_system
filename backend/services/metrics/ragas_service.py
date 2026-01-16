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

        print("[RAGAS] 开始生成对比测试数据...")
        
        for item in golden_data:
            q = item['question']
            gt = item['ground_truth']
            
            # 1. 获取检索结果
            search_result = rag_service.search(q)
            
            # --- 组 A: 无 Rerank (原始 FAISS Top3) ---
            # 🔴 修复点：search_result["raw_docs"] 已经是字符串列表了，直接用
            docs_a = search_result["raw_docs"] 
            context_a = "\n".join(docs_a)
            
            # 简单生成 (不走 Function Calling)
            prompt_a = f"基于以下资料回答：\n{context_a}\n\n问题：{q}"
            ans_a = llm_service.llm.invoke(prompt_a).content
            
            data_no_rerank["question"].append(q)
            data_no_rerank["answer"].append(ans_a)
            data_no_rerank["contexts"].append(docs_a)
            data_no_rerank["ground_truth"].append(gt)

            # --- 组 B: 有 Rerank (重排序后 Top3) ---
            # 🔴 修复点：同上，直接用
            docs_b = search_result["rerank_docs"]
            context_b = "\n".join(docs_b)
            
            prompt_b = f"基于以下资料回答：\n{context_b}\n\n问题：{q}"
            ans_b = llm_service.llm.invoke(prompt_b).content
            
            data_with_rerank["question"].append(q)
            data_with_rerank["answer"].append(ans_b)
            data_with_rerank["contexts"].append(docs_b)
            data_with_rerank["ground_truth"].append(gt)

        # 2. 执行评测 (跑两次)
        print("[RAGAS] 正在评测：无 Rerank 组...")
        results_a = evaluate(
            dataset=Dataset.from_dict(data_no_rerank),
            metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
            llm=self.judge_llm,
            embeddings=self.eval_embeddings
        )

        print("[RAGAS] 正在评测：有 Rerank 组...")
        results_b = evaluate(
            dataset=Dataset.from_dict(data_with_rerank),
            metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
            llm=self.judge_llm,
            embeddings=self.eval_embeddings
        )

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