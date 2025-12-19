import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 允许所有来源，开发环境可以这样写
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. 加载环境变量和配置
load_dotenv()
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

# 2. 初始化 RAG 组件（单例模式，启动时加载一次）
embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-small-zh-v1.5")
vector_db = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)

llm = ChatOpenAI(
    model='deepseek-chat', 
    openai_api_key=os.getenv("DEEPSEEK_API_KEY"), 
    openai_api_base='https://api.deepseek.com/v1'
)

# 定义请求格式
class QuestionRequest(BaseModel):
    keyword: str

@app.post("/generate_question")
async def generate_question(request: QuestionRequest):
    try:
        # --- 核心 RAG 逻辑 ---
        # 1. 检索
        docs = vector_db.similarity_search(request.keyword, k=2)
        context = "\n".join([d.page_content for d in docs])
        
        # 2. 构造 Prompt（这里我针对你刚才遇到的“复读机”问题做了优化）
        template = """
        你是一个严谨的编程老师。请根据提供的教材背景知识，出一道关于"{keyword}"的单选题。
        
        【教材背景知识】：
        {context}
        
        【输出要求】：
        1. 题目必须基于背景知识。
        2. 请直接输出题目、选项、答案和解析。
        3. 禁止重复输出，禁止出现多余的填充字符。
        4. 格式：
           题目：...
           A. ...
           B. ...
           C. ...
           D. ...
           答案：...
           解析：...
        """
        
        prompt = ChatPromptTemplate.from_template(template)
        chain = prompt | llm
        
        # 3. 调用生成
        response = chain.invoke({"context": context, "keyword": request.keyword})
        
        return {
            "status": "success", 
            "data": response.content, 
            "context": context  # <--- 必须加上这一行，前端才能拿到检索到的原文
}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))