from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
import os

# 1. 加载相同的 Embedding 模型（必须和 init_rag.py 一致！）
model_name = "BAAI/bge-small-zh-v1.5"
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
embeddings = HuggingFaceEmbeddings(model_name=model_name)

# 2. 连接已经生成的向量数据库
persist_directory = "./chroma_db"
vector_db = Chroma(persist_directory=persist_directory, embedding_function=embeddings)

def generate_question_with_rag(user_keyword):
    # --- 第一步：检索 (Retrieval) ---
    # 找回最相关的 3 个知识片段
    docs = vector_db.similarity_search(user_keyword, k=3)
    context = "\n".join([doc.page_content for doc in docs])
    
    print(f"找到相关背景知识：\n{context[:100]}...") # 打印前100字看看

    # --- 第二步：构造 Prompt (Augmentation) ---
    template = """
    你是一个专业的编程老师。请根据以下提供的教材内容，出一道单选题。
    
    【教材背景知识】：
    {context}
    
    【用户要求的知识点】：{keyword}
    
    请严格遵守以下要求：
    1. 题目必须基于背景知识。
    2. 输出格式必须为 JSON，包含：question, options, answer, analysis。
    3. 选项为 A, B, C, D。
    """
    
    prompt = ChatPromptTemplate.from_template(template)
    
    # --- 第三步：调用 DeepSeek (Generation) ---
    llm = ChatOpenAI(
        model='deepseek-chat', 
        openai_api_key='DEEPSEEK_API_KEY', 
        openai_api_base='https://api.deepseek.com/v1'
    )
    
    chain = prompt | llm
    response = chain.invoke({"context": context, "keyword": user_keyword})
    
    return response.content