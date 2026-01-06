import os
import json
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# 1. 加载配置
load_dotenv()

# 2. 初始化模型
llm = ChatOpenAI(
    model_name="deepseek-chat", 
    openai_api_key=os.getenv("DEEPSEEK_API_KEY"), 
    openai_api_base="https://api.deepseek.com"
)

def test_ai():
    print("--- 开始测试 DeepSeek 连接 ---")
    
    # 模拟一个出题请求
    topic = "Python基础"
    difficulty = "简单"
    
    prompt = f"请为我出一道关于 {topic} 的 {difficulty} 难度选择题。要求直接返回 JSON 格式。"
    
    try:
        print(f"正在向 AI 提问: {topic}...")
        response = llm.invoke(prompt)
        
        print("\n[控制台输出 - AI回复原文]:")
        print(response.content)
        print("\n--- 测试完成 ---")
        
    except Exception as e:
        print(f"\n[错误提示]: 运行出错了，具体原因如下：\n{e}")

if __name__ == "__main__":
    test_ai()