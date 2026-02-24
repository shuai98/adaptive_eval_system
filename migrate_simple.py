"""
简化版数据库迁移脚本：直接使用 pymysql 添加 question_id 字段
"""
import pymysql
from dotenv import load_dotenv
import os

# 加载环境变量
load_dotenv()

def upgrade_database():
    """添加 question_id 字段"""
    print("开始数据库升级...")
    
    # 从环境变量读取数据库配置
    db_url = os.getenv("DATABASE_URL", "mysql+pymysql://root:123456@localhost:3306/adaptive_eval")
    
    # 解析数据库连接信息
    # 格式: mysql+pymysql://user:password@host:port/database
    parts = db_url.replace("mysql+pymysql://", "").split("@")
    user_pass = parts[0].split(":")
    host_db = parts[1].split("/")
    host_port = host_db[0].split(":")
    
    user = user_pass[0]
    password = user_pass[1]
    host = host_port[0]
    port = int(host_port[1]) if len(host_port) > 1 else 3306
    database = host_db[1]
    
    print(f"连接数据库: {user}@{host}:{port}/{database}")
    
    try:
        # 连接数据库
        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            charset='utf8mb4'
        )
        
        cursor = conn.cursor()
        
        # 1. 检查字段是否已存在
        cursor.execute("""
            SELECT COUNT(*) as count 
            FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = %s
            AND TABLE_NAME = 'exam_records' 
            AND COLUMN_NAME = 'question_id'
        """, (database,))
        
        exists = cursor.fetchone()[0] > 0
        
        if exists:
            print("✅ question_id 字段已存在，无需添加")
            cursor.close()
            conn.close()
            return
        
        # 2. 添加字段
        print("正在添加 question_id 字段...")
        cursor.execute("""
            ALTER TABLE exam_records 
            ADD COLUMN question_id INT NULL 
            AFTER student_id
        """)
        
        # 3. 添加外键约束
        print("正在添加外键约束...")
        cursor.execute("""
            ALTER TABLE exam_records 
            ADD CONSTRAINT fk_exam_records_question_id 
            FOREIGN KEY (question_id) 
            REFERENCES question_history(id) 
            ON DELETE SET NULL
        """)
        
        # 4. 添加索引
        print("正在添加索引...")
        cursor.execute("""
            CREATE INDEX ix_exam_records_question_id 
            ON exam_records(question_id)
        """)
        
        conn.commit()
        print("✅ 数据库升级成功！")
        print("\n字段说明：")
        print("  - question_id: 关联到 question_history 表的 ID")
        print("  - 允许为 NULL（兼容旧数据）")
        print("  - 已添加外键约束和索引")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ 数据库升级失败: {e}")
        raise

if __name__ == "__main__":
    upgrade_database()

