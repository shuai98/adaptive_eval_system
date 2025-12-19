import os
import json
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from database import SessionLocal  # 导入我们那个“银行柜台”
from models import Question       # 导入我们的“账本格式”

load_dotenv()

# 1. 准备好 AI 厨师
llm = ChatOpenAI(
    model_name="deepseek-chat", 
    openai_api_key=os.getenv("DEEPSEEK_API_KEY"), 
    openai_api_base="https://api.deepseek.com",
    model_kwargs={"response_format": {"type": "json_object"}}
)

def run_task():
    # 2. 让 AI 出一道题
    print("正在找 AI 出题，请稍等...")
    prompt = "请出一道 Python 基础选择题，要求返回 JSON，包含字段: question, options, answer, explanation"
    response = llm.invoke(prompt)
    
    # 3. 把 AI 返回的字符串变成 Python 能看懂的字典
    data = json.loads(response.content)
    print("AI 出好题了，准备存入数据库...")

    # 4. 开启一个数据库会话（打开柜台）
    db = SessionLocal()
    
    try:
        # 5. 创建一个 Question 对象（填好入库单）
        # 这里把 AI 给的内容一一对应填进去
        new_q = Question(
            content=data.get("question"),
            # 选项通常是字典，我们把它转成字符串存进去，省得麻烦
            options=str(data.get("options")),
            answer=data.get("answer"),
            analysis=data.get("explanation"),
            difficulty="简单", # 暂时写死，以后可以根据逻辑变
            tag="Python"
        )
        
        # 6. 执行存入动作
        db.add(new_q)
        db.commit() # 这一步才是真正写进硬盘！
        print(f"成功！题目已存入数据库，ID 为: {new_q.id}")
        
    except Exception as e:
        print(f"哎呀，出错了: {e}")
        db.rollback() # 出错了就撤销，别把数据库搞乱了
    finally:
        db.close() # 办完业务，关闭柜台

if __name__ == "__main__":
    run_task()