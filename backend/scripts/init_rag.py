import os
import glob
import shutil
from langchain_community.document_loaders import TextLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

# 设置 HuggingFace 镜像
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

def init_local_rag():
    # --- 关键路径修复 ---
    # 1. 获取当前脚本绝对路径: .../ADAPTIVE_EVAL_SYSTEM/backend/scripts
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 2. 往上走两层，定位到项目根目录: .../ADAPTIVE_EVAL_SYSTEM
    project_root = os.path.abspath(os.path.join(current_dir, "../../"))
    
    # 3. 定位数据目录
    docs_dir = os.path.join(project_root, "data", "docs")
    faiss_index_path = os.path.join(project_root, "data", "faiss_index")

    print(f" 定位项目根目录: {project_root}")
    print(f" 扫描文档目录: {docs_dir}")
    print(f" 索引保存路径: {faiss_index_path}")

    print("-" * 30)
    print(" 开始初始化 RAG 知识库...")

    # 1. 加载文档
    documents = []
    
    # 检查 docs 目录是否存在
    if not os.path.exists(docs_dir):
        print(f" 错误: 找不到 docs 文件夹！\n请确认路径: {docs_dir}")
        # 自动创建文件夹，防止下次报错
        os.makedirs(docs_dir)
        print("已自动创建空文件夹，请往里面放入 PDF 或 TXT 文件后重试。")
        return

    # 加载 TXT 文件
    txt_files = glob.glob(os.path.join(docs_dir, "*.txt"))
    for file_path in txt_files:
        try:
            loader = TextLoader(file_path, encoding='utf-8')
            documents.extend(loader.load())
            print(f"    已加载 TXT: {os.path.basename(file_path)}")
        except Exception as e:
            print(f"    加载 TXT 失败 {os.path.basename(file_path)}: {e}")
    
    # 加载 PDF 文件
    pdf_files = glob.glob(os.path.join(docs_dir, "*.pdf"))
    for file_path in pdf_files:
        try:
            loader = PyPDFLoader(file_path)
            documents.extend(loader.load())
            print(f"    已加载 PDF: {os.path.basename(file_path)}")
        except Exception as e:
            print(f"    加载 PDF 失败 {os.path.basename(file_path)}: {e}")

    if not documents:
        print(" 警告: data/docs 文件夹是空的！请放入教材文件。")
        return

    # 2. 文档切分
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500, 
        chunk_overlap=50
    )
    chunks = text_splitter.split_documents(documents)
    print(f" 文档切分完成，共生成 {len(chunks)} 个片段")

    # 3. 初始化 Embedding 模型
    print(" 正在加载 BGE Embedding 模型...")
    embeddings = HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-zh-v1.5",
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True}
    )

    # 4. 构建并保存 FAISS 索引
    print(" 正在构建向量索引...")
    vector_db = FAISS.from_documents(chunks, embeddings)
    
    # 确保保存目录存在
    if not os.path.exists(faiss_index_path):
        os.makedirs(faiss_index_path)
        
    # 保存到本地
    vector_db.save_local(faiss_index_path)
    
    print(f" 成功！索引已保存至: {faiss_index_path}")

if __name__ == "__main__":
    init_local_rag()