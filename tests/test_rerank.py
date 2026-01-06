import requests
import json

# 确保端口号和你后端运行的一致 
API_URL = "http://127.0.0.1:8088/generate_question"

def test_rerank():
    # 挑一个你 PDF (流畅的Python) 里的知识点
    # 比如 "装饰器"、"元组拆包"、"鸭子类型"
    keyword = "装饰器" 
    
    payload = {
        "keyword": keyword
    }

    print(f" 正在发送请求，测试关键词：【{keyword}】...")
    try:
        response = requests.post(API_URL, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            print("\n 请求成功！")
            print("="*30)
            print(" AI 出题内容：")
            print(data['data'][:100] + "...") # 只打印前100个字看看
            print("="*30)
            print("\n 快去看后端(main.py)的控制台！")
            print("找找有没有 ' Rerank 优化报告'，看看分数是多少？")
        else:
            print(f" 失败: {response.text}")
            
    except Exception as e:
        print(f"连接错误: {e}")

if __name__ == "__main__":
    test_rerank()