"""
数据库迁移脚本：为 exam_records 表添加 question_id 字段
"""
import sys
import os

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../..'))
sys.path.insert(0, project_root)

from backend.db.session import engine
from sqlalchemy import text

def upgrade_database():
    """添加 question_id 字段"""
    print("开始数据库升级...")
    
    with engine.connect() as conn:
        try:
            # 1. 检查字段是否已存在
            result = conn.execute(text("""
                SELECT COUNT(*) as count 
                FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = 'exam_records' 
                AND COLUMN_NAME = 'question_id'
            """))
            
            exists = result.fetchone()[0] > 0
            
            if exists:
                print("✅ question_id 字段已存在，无需添加")
                return
            
            # 2. 添加字段
            print("正在添加 question_id 字段...")
            conn.execute(text("""
                ALTER TABLE exam_records 
                ADD COLUMN question_id INT NULL 
                AFTER student_id
            """))
            
            # 3. 添加外键约束
            print("正在添加外键约束...")
            conn.execute(text("""
                ALTER TABLE exam_records 
                ADD CONSTRAINT fk_exam_records_question_id 
                FOREIGN KEY (question_id) 
                REFERENCES question_history(id) 
                ON DELETE SET NULL
            """))
            
            # 4. 添加索引
            print("正在添加索引...")
            conn.execute(text("""
                CREATE INDEX ix_exam_records_question_id 
                ON exam_records(question_id)
            """))
            
            conn.commit()
            print("✅ 数据库升级成功！")
            print("\n字段说明：")
            print("  - question_id: 关联到 question_history 表的 ID")
            print("  - 允许为 NULL（兼容旧数据）")
            print("  - 已添加外键约束和索引")
            
        except Exception as e:
            conn.rollback()
            print(f"❌ 数据库升级失败: {e}")
            raise

def downgrade_database():
    """回滚：删除 question_id 字段"""
    print("开始数据库回滚...")
    
    with engine.connect() as conn:
        try:
            # 1. 删除外键约束
            print("正在删除外键约束...")
            conn.execute(text("""
                ALTER TABLE exam_records 
                DROP FOREIGN KEY fk_exam_records_question_id
            """))
            
            # 2. 删除索引
            print("正在删除索引...")
            conn.execute(text("""
                DROP INDEX ix_exam_records_question_id 
                ON exam_records
            """))
            
            # 3. 删除字段
            print("正在删除 question_id 字段...")
            conn.execute(text("""
                ALTER TABLE exam_records 
                DROP COLUMN question_id
            """))
            
            conn.commit()
            print("✅ 数据库回滚成功！")
            
        except Exception as e:
            conn.rollback()
            print(f"❌ 数据库回滚失败: {e}")
            raise

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "downgrade":
        downgrade_database()
    else:
        upgrade_database()

