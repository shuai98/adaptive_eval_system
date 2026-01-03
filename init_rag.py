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
    # 获取当前脚本所在目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    docs_dir = os.path.join(current_dir, "docs")
    
    # FAISS 索引保存路径
    faiss_index_path = os.path.join(current_dir, "faiss_index")

    # 如果存在旧的索引文件夹，先清理掉，保证纯净
    if os.path.exists(faiss_index_path):
        shutil.rmtree(faiss_index_path)
        print(f"已清理旧索引: {faiss_index_path}")

    print("开始初始化 RAG 知识库...")

    # 1. 加载文档
    documents = []
    if not os.path.exists(docs_dir):
        print("错误: docs 文件夹不存在")
        return

    # 加载 TXT 文件
    txt_files = glob.glob(os.path.join(docs_dir, "*.txt"))
    for file_path in txt_files:
        try:
            loader = TextLoader(file_path, encoding='utf-8')
            documents.extend(loader.load())
            print(f"已加载 TXT: {os.path.basename(file_path)}")
        except Exception as e:
            print(f"加载 TXT 失败 {os.path.basename(file_path)}: {e}")
    
    # 加载 PDF 文件
    pdf_files = glob.glob(os.path.join(docs_dir, "*.pdf"))
    for file_path in pdf_files:
        try:
            loader = PyPDFLoader(file_path)
            documents.extend(loader.load())
            print(f"已加载 PDF: {os.path.basename(file_path)}")
        except Exception as e:
            print(f"加载 PDF 失败 {os.path.basename(file_path)}: {e}")

    if not documents:
        print("未找到任何文档，请检查 docs 文件夹")
        return

    # 2. 文档切分
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500, 
        chunk_overlap=50
    )
    chunks = text_splitter.split_documents(documents)
    print(f"文档切分完成，共生成 {len(chunks)} 个片段")

    # 3. 初始化 Embedding 模型
    print("正在加载 BGE Embedding 模型...")
    embeddings = HuggingFaceEmbeddings(
        model_name="BAAI/bge-small-zh-v1.5",
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True}
    )

    # 4. 构建并保存 FAISS 索引
    print("正在构建向量索引...")
    vector_db = FAISS.from_documents(chunks, embeddings)
    
    # --- 修复点：保存前先手动创建文件夹 ---
    if not os.path.exists(faiss_index_path):
        os.makedirs(faiss_index_path)
    
    # 保存到本地
    vector_db.save_local(faiss_index_path)
    
    print(f"初始化完成，索引已保存至: {faiss_index_path}")

if __name__ == "__main__":
    init_local_rag()