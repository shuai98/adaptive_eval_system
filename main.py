import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings
#from langchain_chroma import Chroma
from langchain_community.vectorstores import FAISS
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from fastapi.middleware.cors import CORSMiddleware
from sentence_transformers import CrossEncoder
import shutil
from fastapi import UploadFile, File, BackgroundTasks
# 引入初始化逻辑 (确保 init_rag.py 在同一目录下)
from init_rag import init_local_rag

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
embeddings = HuggingFaceEmbeddings(
    model_name="BAAI/bge-small-zh-v1.5",
    model_kwargs={'device': 'cpu'},
    encode_kwargs={'normalize_embeddings': True} # 必须加上这个！
)
vector_db = FAISS.load_local(
    folder_path="./faiss_index", 
    embeddings=embeddings,
    allow_dangerous_deserialization=True 
)
# --- 新增：加载 BGE Rerank 模型 ---
# CrossEncoder 是用来做精细比对的
print(" 正在加载 BGE-Reranker 模型 (首次运行需下载，约1GB)...")
reranker = CrossEncoder('BAAI/bge-reranker-base')
print(" Rerank 模型加载完毕！")

llm = ChatOpenAI(
    model='deepseek-chat', 
    openai_api_key=os.getenv("DEEPSEEK_API_KEY"),
    openai_api_base='https://api.deepseek.com/v1',
    model_kwargs={"response_format": {"type": "json_object"}}#强制返回json格式
)

# 定义请求格式
class QuestionRequest(BaseModel):
    keyword: str

@app.post("/generate_question")
async def generate_question(request: QuestionRequest):
    try:
        # --- 核心 RAG 逻辑 ---
        # 1. 检索
        print(f" 收到出题请求，关键词: {request.keyword}")

        # ================= Rerank 核心逻辑 =================
        
        # 1. 【海选】(Recall): 先用向量检索找 10 个大概相关的
        # 为什么是 10？为了扩大搜索范围，先把沾边的都捞上来
        initial_docs = vector_db.similarity_search(request.keyword, k=10)
        
        # 2. 【配对】: 准备给 Rerank 模型打分的数据
        # 格式必须是: [[问题, 文档内容], [问题, 文档内容], ...]
        pairs = [[request.keyword, doc.page_content] for doc in initial_docs]

        # 3. 【打分】(Scoring): 让 BGE-Reranker 逐一阅读并打分
        # 分数越高，代表相关性越强
        scores = reranker.predict(pairs)

        # 4. 【排序】: 根据分数从高到低重新排队
        # zip 把文档和分数捆绑，sorted 进行排序
        scored_docs = sorted(zip(initial_docs, scores), key=lambda x: x[1], reverse=True)

        # 5. 【精选】(Precision): 只取前 3 名给 AI
        # Top 3 是给大模型看的精华
        top_k = 3
        final_docs = [doc for doc, score in scored_docs[:top_k]]
        
        # --- (可选) 打印日志，方便你面试时展示 Rerank 的效果 ---
        print(f" Rerank 优化报告:")
        for i, (doc, score) in enumerate(scored_docs[:top_k]):
            print(f"   Top{i+1} (得分 {score:.4f}): {doc.page_content[:30].replace(chr(10), ' ')}...")

        # ================= 逻辑结束 =================
        context = "\n\n".join([d.page_content for d in final_docs])
        
        # 2. 构造 Prompt（这里我针对你刚才遇到的“复读机”问题做了优化）
        template = """
        你是一个严谨的编程老师。请根据提供的教材背景知识，出一道关于"{keyword}"的单选题。
        
        【教材背景知识】：
        {context}
        
        【输出要求】：
        1. 必须返回标准的 JSON 格式。
        2. JSON 必须包含以下字段：
           - "question": 题目描述
           - "options": 一个字典，包含 "A", "B", "C", "D"
           - "answer": 正确选项的 Key (如 "A")
           - "analysis": 解析
        
        【示例格式】：
        {{
            "question": "Python中用于定义函数的关键字是？",
            "options": {{
                "A": "func",
                "B": "def",
                "C": "function",
                "D": "define"
            }},
            "answer": "B",
            "analysis": "Python使用def关键字定义函数。"
        }}
        """
        
        prompt = ChatPromptTemplate.from_template(template)
        chain = prompt | llm
        
        # 3. 调用生成
        response = chain.invoke({"context": context, "keyword": request.keyword})
        
        # --- 新增：清洗 AI 返回的数据 ---
        content = response.content
        # 1. 去掉可能存在的 markdown 代码块符号
        if "```json" in content:
            content = content.replace("```json", "").replace("```", "")
        # 2. 去掉首尾空格
        content = content.strip()
        
        # 3. 打印出来看看（方便调试）
        print(f"AI 返回清洗后的内容: {content[:50]}...")


        #以下两个变量是为了方便前端展示两种检索结果而返回的
        #1. 提取“原始检索”内容 (从 initial_docs 里拿)
        raw_docs_list = [doc.page_content for doc in initial_docs[:3]]
        #2. 提取“Rerank 后”内容 (从 final_docs 里拿)
        rerank_docs_list = [doc.page_content for doc in final_docs]

        return {
            "status": "success", 
            "data": content,  # <--- 注意：这里返回清洗后的 content
            "context": context,
            "debug_info": {         
                "raw_docs": raw_docs_list,
                "rerank_docs": rerank_docs_list
            }
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
    


@app.post("/upload_doc")
async def upload_document(file: UploadFile = File(...)):
    """
    教师端接口：上传教材文档(PDF/TXT)到服务器
    """
    try:
        # 确保 docs 目录存在
        save_dir = "docs"
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        
        file_path = os.path.join(save_dir, file.filename)
        
        # 保存文件
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        return {"status": "success", "message": f"文件 {file.filename} 上传成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")



@app.post("/reindex_kb")
async def reindex_knowledge_base(background_tasks: BackgroundTasks):
    """
    教师端接口：触发知识库重建 (异步执行，防止前端超时)
    """
    try:
        # 使用后台任务运行耗时的索引构建
        background_tasks.add_task(init_local_rag)
        return {"status": "success", "message": "索引重建任务已在后台启动，请稍后测试检索功能"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重建索引失败: {str(e)}")