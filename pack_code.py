import os

# 这里设置你想要包含的文件后缀
ALLOWED_EXTENSIONS = {'.py', '.js', '.ts', '.java', '.c', '.cpp', '.h', '.html', '.css', '.md', '.json', '.go', '.rs'}
# 这里设置想要忽略的文件夹
IGNORE_DIRS = {'.git', '__pycache__', 'node_modules', 'dist', 'build', 'venv', '.idea', '.vscode'}

output_file = 'project_context.txt'

with open(output_file, 'w', encoding='utf-8') as outfile:
    for root, dirs, files in os.walk('.'):
        # 过滤忽略的文件夹
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        for file in files:
            ext = os.path.splitext(file)[1]
            if ext in ALLOWED_EXTENSIONS:
                file_path = os.path.join(root, file)
                outfile.write(f"\n\n{'='*20}\nFile: {file_path}\n{'='*20}\n\n")
                try:
                    with open(file_path, 'r', encoding='utf-8') as infile:
                        outfile.write(infile.read())
                except Exception as e:
                    outfile.write(f"Error reading file: {e}")

print(f"完成！所有代码已保存到 {output_file}")