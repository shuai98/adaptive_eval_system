import os
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import CharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
import shutil


# 1. 解决下载慢的问题：强制使用国内 HuggingFace 镜像源
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

def init_local_rag():
    # 配置路径
    # 获取当前脚本所在的文件夹绝对路径 (D:\毕设_code\adaptive_eval_system)
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # 正确指向 docs 文件夹下的 db.txt
    raw_data_path = os.path.join(current_dir, "docs", "db.txt")

    # 向量数据库建议也放在根目录或指定位置
    persist_directory = os.path.join(current_dir, "chroma_db")


    # 路径设置
    db_path = "./chroma_db"

    # 如果你想每次运行 init_rag.py 都用新的 db.txt 覆盖旧的数据库
    if os.path.exists(db_path):
      shutil.rmtree(db_path) # 自动删除旧文件夹
      print("🧹 已清理旧的向量数据库")

    # 然后再执行加载文档、切片、生成向量的代码...

    print(f"✅ 脚本正在查找路径: {raw_data_path}")

    print("开始 RAG 初始化流程...")

    # --- 第一步：加载文档 ---
    if not os.path.exists(raw_data_path):
        print(f"错误：找不到 {raw_data_path}，请先创建该文件并写入教材内容。")
        return
    
    loader = TextLoader(raw_data_path, encoding='utf-8')
    documents = loader.load()
    print(f"成功加载文档，当前字符数：{len(documents[0].page_content)}")

    # --- 第二步：文档分块 (Chunking) ---
    # 找工作重点：面试官会问为什么选这个 size。
    # 答：300-500字符能保留足够的上下文，同时方便检索。
    text_splitter = CharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = text_splitter.split_documents(documents)
    print(f"分块完成，共切分为 {len(chunks)} 个片段。")

    # --- 第三步：加载 BGE Embedding 模型 ---
    print("正在加载 BGE-small-zh 模型（首次运行将自动下载，请保持网络畅通）...")
    model_name = "BAAI/bge-small-zh-v1.5"
    model_kwargs = {'device': 'cpu'} # 没显卡也能跑
    encode_kwargs = {'normalize_embeddings': True} # 归一化处理，提升检索精度
    
    embeddings = HuggingFaceEmbeddings(
    model_name="BAAI/bge-small-zh-v1.5",
    model_kwargs={'device': 'cpu'},
    encode_kwargs={'normalize_embeddings': True}
)

    # --- 第四步：存入向量数据库 (Vector DB) ---
    print("正在计算向量并存入 Chroma 数据库...")
    vector_db = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=persist_directory
    )
    
    # 强制保存（旧版 LangChain 需要，新版建议也写上）
    vector_db.persist()
    print(f" 成功！向量数据库已保存至: {persist_directory}")
    print("你现在可以去文件夹里看看，是不是多了个 chroma_db 文件夹？")

if __name__ == "__main__":
    init_local_rag()