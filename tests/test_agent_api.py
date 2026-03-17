"""
测试 Agent API 接口
用于验证 /api/query 端点是否正常工作
"""
import requests
import json

# 配置
BASE_URL = "http://127.0.0.1:8088"
API_ENDPOINT = f"{BASE_URL}/api/query"

def test_agent_query():
    """测试基本查询功能"""
    print("=" * 60)
    print("测试 Agent API 接口")
    print("=" * 60)
    
    # 测试数据
    test_cases = [
        {
            "question": "什么是机器学习？",
            "top_k": 3
        },
        {
            "question": "深度学习的基本原理是什么？",
            "top_k": 2
        }
    ]
    
    for i, test_data in enumerate(test_cases, 1):
        print(f"\n【测试用例 {i}】")
        print(f"问题: {test_data['question']}")
        print(f"Top-K: {test_data['top_k']}")
        print("-" * 60)
        
        try:
            # 发送 POST 请求
            response = requests.post(
                API_ENDPOINT,
                json=test_data,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            # 检查响应状态
            if response.status_code == 200:
                result = response.json()
                
                print("✓ 请求成功")
                print(f"\n【回答】\n{result['answer']}")
                print(f"\n【来源文档数量】{len(result['sources'])}")
                
                for j, source in enumerate(result['sources'], 1):
                    print(f"\n  来源 {j}: {source['title']}")
                    print(f"  内容预览: {source['content'][:100]}...")
                    
            else:
                print(f"✗ 请求失败")
                print(f"状态码: {response.status_code}")
                print(f"错误信息: {response.text}")
                
        except requests.exceptions.ConnectionError:
            print("✗ 连接失败：请确保后端服务已启动（端口 8088）")
        except requests.exceptions.Timeout:
            print("✗ 请求超时")
        except Exception as e:
            print(f"✗ 发生错误: {str(e)}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

def test_cors():
    """测试 CORS 配置"""
    print("\n【测试 CORS 配置】")
    print("-" * 60)
    
    try:
        response = requests.options(
            API_ENDPOINT,
            headers={
                "Origin": "http://localhost:8001",
                "Access-Control-Request-Method": "POST"
            }
        )
        
        if "access-control-allow-origin" in response.headers:
            print("✓ CORS 配置正确")
            print(f"  允许的来源: {response.headers.get('access-control-allow-origin')}")
        else:
            print("✗ CORS 配置可能有问题")
            
    except Exception as e:
        print(f"✗ CORS 测试失败: {str(e)}")

if __name__ == "__main__":
    test_agent_query()
    test_cors()

