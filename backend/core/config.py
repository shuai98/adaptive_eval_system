import os
from dotenv import load_dotenv

# 加载 .env
load_dotenv()

class Settings:
    PROJECT_NAME: str = "自适应测评系统"
    VERSION: str = "5.0"
    
    # 路径配置
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    DATA_DIR = os.path.join(BASE_DIR, "data")
    DOCS_DIR = os.path.join(DATA_DIR, "docs")
    FAISS_INDEX_DIR = os.path.join(DATA_DIR, "faiss_index")
    DB_PATH = os.path.join(DATA_DIR, "app.db")
    
    # API Keys
    HF_ENDPOINT: str = os.getenv("HF_ENDPOINT", "https://hf-mirror.com")
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY")

settings = Settings()