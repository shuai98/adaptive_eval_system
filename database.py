from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base  # 把刚才定义的“账本格式”拿过来

# 数据库就建在当前文件夹下，名字叫 test.db
# sqlite 是最简单的数据库，不需要安装额外的软件，就是一个文件
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

# 创建数据库引擎，check_same_thread 是为了让 FastAPI 这种多线程运行时不报错
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# 以后每次要存取数据，就开一个 Session（会话），就像去银行办业务要开个窗口
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 这个函数是给系统初始化的，运行一下就会在硬盘上生成 test.db 文件
def init_db():
    print("系统提示：正在初始化数据库，检查表结构...")
    # 这行代码会扫描 models.py，把定义的表在数据库里建出来
    Base.metadata.create_all(bind=engine)
    print("系统提示：数据库已就绪！")

# 只有直接运行这个脚本时才会执行初始化
if __name__ == "__main__":
    init_db()