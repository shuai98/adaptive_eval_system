"""
项目清理脚本 - 删除临时文件和无用文件
"""
import os
import shutil

def clean_project():
    """清理项目中的临时文件和无用文件"""
    
    project_root = os.path.dirname(os.path.abspath(__file__))
    
    # 要删除的文件列表
    files_to_delete = [
        "data/app.db",              # 已废弃的 SQLite 数据库
        "update_db.py",             # 功能已整合
        "pack_code.py",             # 打包工具（非必需）
        "project_context.txt",      # 临时文件
        "My_note.md",               # 个人笔记（建议移到 notes/）
        "README.pdf",               # 可从 README.md 重新生成
        "backend/services/metrics/locust_debug.log",  # 测试日志
    ]
    
    # 要删除的目录列表（递归删除）
    dirs_to_delete = [
        "__pycache__",
        "backend/__pycache__",
        "backend/api/__pycache__",
        "backend/core/__pycache__",
        "backend/db/__pycache__",
        "backend/models/__pycache__",
        "backend/scripts/__pycache__",
        "backend/services/__pycache__",
        "backend/services/metrics/__pycache__",
    ]
    
    print("=" * 60)
    print("项目清理工具")
    print("=" * 60)
    print("\n⚠️  警告：以下文件/目录将被删除：\n")
    
    # 显示将要删除的文件
    print("📄 文件：")
    for file in files_to_delete:
        file_path = os.path.join(project_root, file)
        if os.path.exists(file_path):
            size = os.path.getsize(file_path) / 1024  # KB
            print(f"  - {file} ({size:.1f} KB)")
    
    # 显示将要删除的目录
    print("\n📁 目录：")
    for dir_name in dirs_to_delete:
        dir_path = os.path.join(project_root, dir_name)
        if os.path.exists(dir_path):
            # 计算目录大小
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(dir_path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    total_size += os.path.getsize(fp)
            print(f"  - {dir_name} ({total_size / 1024:.1f} KB)")
    
    # 确认删除
    print("\n" + "=" * 60)
    confirm = input("确认删除以上文件？(y/n): ").strip().lower()
    
    if confirm != 'y':
        print("❌ 已取消清理")
        return
    
    # 执行删除
    deleted_count = 0
    
    # 删除文件
    for file in files_to_delete:
        file_path = os.path.join(project_root, file)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"✅ 已删除文件: {file}")
                deleted_count += 1
            except Exception as e:
                print(f"❌ 删除失败: {file} - {e}")
    
    # 删除目录
    for dir_name in dirs_to_delete:
        dir_path = os.path.join(project_root, dir_name)
        if os.path.exists(dir_path):
            try:
                shutil.rmtree(dir_path)
                print(f"✅ 已删除目录: {dir_name}")
                deleted_count += 1
            except Exception as e:
                print(f"❌ 删除失败: {dir_name} - {e}")
    
    print("\n" + "=" * 60)
    print(f"✅ 清理完成！共删除 {deleted_count} 项")
    print("=" * 60)
    
    # 建议
    print("\n💡 建议：")
    print("  1. 如果 My_note.md 有用，请移动到 notes/ 目录")
    print("  2. 如果需要 README.pdf，可以从 README.md 重新生成")
    print("  3. __pycache__ 目录会在运行 Python 时自动重新生成")
    print("  4. 可以将此脚本添加到 .gitignore 中")

if __name__ == "__main__":
    clean_project()

