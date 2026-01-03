import os
import glob
import shutil
from langchain_community.document_loaders import TextLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

# 1. 解决下载慢的问题：强制使用国内 HuggingFace 镜像源
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

def init_local_rag():
    # --- 配置路径 ---
    # 获取当前脚本所在的文件夹绝对路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 指向 docs 文件夹
    docs_dir = os.path.join(current_dir, "docs")
    
    # 向量数据库存储位置
    persist_directory = os.path.join(current_dir, "chroma_db")

    # --- 清理旧数据 ---
    # 每次运行都清空旧库，保证数据是最新的
    if os.path.exists(persist_directory):
        shutil.rmtree(persist_directory)
        print(f"已清理旧的向量数据库: {persist_directory}")

    print("开始 RAG 初始化流程...")
    print(f"正在扫描文档目录: {docs_dir}")

    # --- 第一步：加载文档 (支持 TXT 和 PDF) ---
    documents = []
    
    # 1.1 检查目录是否存在
    if not os.path.exists(docs_dir):
        print(f"错误：找不到 docs 文件夹！请在 {current_dir} 下创建 docs 文件夹。")
        return

    # 1.2 加载所有 .txt 文件
    txt_files = glob.glob(os.path.join(docs_dir, "*.txt"))
    for file_path in txt_files:
        try:
            loader = TextLoader(file_path, encoding='utf-8')
            documents.extend(loader.load())
            print(f"   已加载 TXT: {os.path.basename(file_path)}")
        except Exception as e:
            print(f"   加载 TXT 失败 {os.path.basename(file_path)}: {e}")

    # 1.3 加载所有 .pdf 文件 (新增功能！)
    pdf_files = glob.glob(os.path.join(docs_dir, "*.pdf"))
    for file_path in pdf_files:
        try:
            # 面试加分点：PyPDFLoader 会自动处理分页，把每一页作为一个 Document
            loader = PyPDFLoader(file_path)
            documents.extend(loader.load())
            print(f"   已加载 PDF: {os.path.basename(file_path)}")
        except Exception as e:
            print(f"   加载 PDF 失败 {os.path.basename(file_path)}: {e}")

    # 1.4 检查是否加载到了数据
    if not documents:
        print("警告：docs 文件夹里是空的，或者没有 .txt/.pdf 文件！")
        return
    
    print(f"文档加载完毕，共加载了 {len(documents)} 个文档片段/页面。")

    # --- 第二步：文档分块 (Chunking) ---
    print("正在进行文档分块...")
    # 优化点：面试时可以说“我选择了500字符+50重叠，以平衡上下文完整性和检索粒度”
    #将CharacterTextSplitter改为RecursiveCharacterTextSplitter，这样不会切出来一千多字的块
    text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
    separators=["\n\n", "\n", "。", "！", "？", "，", " ", ""] # 优先按段落和句号切
    )
    chunks = text_splitter.split_documents(documents)
    print(f"   分块完成，共切分为 {len(chunks)} 个片段。")

    # --- 第三步：加载 Embedding 模型 ---
    print("正在加载 BGE-small-zh 模型...")
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
    
    # 新版 Chroma 自动保存，但这行留着也没事
    # vector_db.persist() 
    print(f"成功！RAG 知识库初始化完成！")
    print(f"数据库路径: {persist_directory}")

if __name__ == "__main__":
    init_local_rag()