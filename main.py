import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 允许所有来源，开发环境可以这样写
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#访问根目录时报404错
@app.get("/")
def read_root():
    return {"message": "欢迎使用自适应学习出题系统 API！请通过前端界面或 /docs 进行访问。"}

# 定义评分请求的数据格式
class GradeRequest(BaseModel):
    question: str       # 题目
    standard_answer: str # 标准答案（或者参考资料）
    student_answer: str  # 学生写的答案

# 定义评分结果的结构（可选，用于文档展示，这里主要给 AI 看）
# 期望 AI 返回这样的 JSON:
# {
#   "score": 85,
#   "reason": "回答了核心概念，但缺少具体例子...",
#   "suggestion": "建议复习一下..."
# }

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
    

@app.post("/grade_answer")
async def grade_answer(request: GradeRequest):
    try:
        # 1. 构造“阅卷老师”的 Prompt
        # 技巧：CoT (思维链) - 让 AI 先思考再打分，不仅准，而且理由充分。
        system_prompt = """
        你是一位经验丰富、公正的计算机专业阅卷老师。
        请根据【题目】和【标准答案】，对【学生回答】进行评估。
        
        评分标准：
        1. 准确性（60%）：核心概念是否正确？
        2. 完整性（20%）：是否遗漏了关键细节？
        3. 表达逻辑（20%）：表述是否清晰？
        
        【输出要求】：
        请严格返回 JSON 格式，包含以下字段：
        - "score": (0-100的整数)
        - "reason": (简短的评分理由，指出哪里对哪里错)
        - "suggestion": (给学生的改进建议，语气要鼓励)
        """
        
        user_prompt = f"""
        【题目】：{request.question}
        【标准答案】：{request.standard_answer}
        【学生回答】：{request.student_answer}
        """

        # 2. 组装 Chain
        # 注意：这里我们复用你之前定义的 llm 对象
        # 确保你的 llm 初始化时开启了 json_object 模式（在 save_quiz_to_db.py 里你用过，这里最好也加上）
        
        # 临时创建一个强制 JSON 输出的 Prompt Template
        grade_prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", user_prompt)
        ])
        
        chain = grade_prompt | llm
        
        # 3. 调用 AI
        print(f"正在批改：学生回答了 - {request.student_answer[:20]}...")
        response = chain.invoke({})
        
        # 4. 解析结果
        # 这一步是为了防止 AI 偶尔抽风返回了 markdown 格式 (```json ... ```)
        # 简单的清洗逻辑
        content = response.content
        if "```json" in content:
            content = content.replace("```json", "").replace("```", "")
        
        import json
        result_json = json.loads(content)
        
        return {
            "status": "success",
            "data": result_json
        }

    except Exception as e:
        print(f"评分出错: {str(e)}")
        raise HTTPException(status_code=500, detail=f"评分失败: {str(e)}")