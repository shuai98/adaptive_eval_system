import os
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_openai import ChatOpenAI

# 1. 加载配置
load_dotenv()
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

# 2. 初始化组件 (放在函数外面，确保全局可用)
embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-small-zh-v1.5")
# 确保 persist_directory 路径正确
vector_db = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)

llm = ChatOpenAI(
    model='deepseek-chat', 
    openai_api_key=os.getenv("DEEPSEEK_API_KEY"), 
    openai_api_base='https://api.deepseek.com/v1'
)

def test_comparison(keyword):
    print(f"\n" + "="*50)
    print(f"🔍 测试关键词: 【{keyword}】")
    print("="*50)

    # --- 状态 A: 纯 DeepSeek ---
    print("\n[状态 A: 纯 DeepSeek 出题]")
    res_raw = llm.invoke(f"请为知识点 '{keyword}' 出一道单选题。")
    print(res_raw.content)

    # --- 状态 B: RAG 模式 ---
    print("\n" + "-"*30)
    print("[状态 B: RAG 模式 (基于教材出题)]")
    
    # 这里现在能找到 vector_db 了
    docs = vector_db.similarity_search(keyword, k=2)
    context = "\n".join([d.page_content for d in docs])
    
    print(f"📑 检索到的教材原文片段:\n{context[:200]}...") 

    prompt = f"你是一个老师，请严格根据以下背景知识，为'{keyword}'出一道题。\n背景知识：{context}"
    res_rag = llm.invoke(prompt)
    print("\n🤖 RAG 生成的题目:")
    print(res_rag.content)

if __name__ == "__main__":
    # 确保你 db.txt 里确实有关于“列表推导式”的内容
    test_comparison("python的apflag是什么")