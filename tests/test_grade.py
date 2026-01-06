import requests
import json

# 你的后端地址
API_URL = "http://127.0.0.1:8081/grade_answer"

def test_grading():
    payload = {
        "question": "请简述 Python 中列表（List）和元组（Tuple）的区别。",
        "standard_answer": "1. 列表是可变的(mutable)，元组是不可变的(immutable)。2. 列表用方括号[]，元组用圆括号()。3. 列表通常用于存储同构数据，元组用于存储异构数据。",
        "student_answer": "列表是用[]写的，可以修改。元组是用()写的，一旦定义就不能改了。"
    }

    print("正在提交答案给 AI 批改...")
    try:
        response = requests.post(API_URL, json=payload)
        
        if response.status_code == 200:
            result = response.json()
            print("\n✅ 批改成功！")
            print("-" * 30)
            data = result['data']
            print(f"分数: {data['score']}")
            print(f"理由: {data['reason']}")
            print(f"建议: {data['suggestion']}")
            print("-" * 30)
        else:
            print(f"❌ 失败: {response.text}")
            
    except Exception as e:
        print(f"连接错误: {e}")

if __name__ == "__main__":
    test_grading()