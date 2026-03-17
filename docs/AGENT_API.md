# Agent API 接口文档

## 接口概述

本接口为 EduReflex Agent 系统提供权威知识来源，基于 RAG 技术从知识库检索相关内容并生成答案。

## 基本信息

- **接口地址**: `http://127.0.0.1:8088/api/query`
- **请求方法**: POST
- **Content-Type**: application/json
- **支持 CORS**: 是（已配置允许 http://localhost:8001）

## 请求参数

### QueryRequest

```json
{
  "question": "string",  // 必填：用户的问题
  "top_k": 3            // 可选：返回的文档数量，默认为 3
}
```

**参数说明**：
- `question`: 用户提出的问题，系统会基于此问题检索知识库
- `top_k`: 返回的相关文档片段数量，范围建议 1-5

## 响应格式

### QueryResponse

```json
{
  "answer": "string",     // LLM 生成的答案
  "sources": [            // 来源文档列表
    {
      "title": "string",   // 文档标题
      "content": "string"  // 文档内容
    }
  ]
}
```

**字段说明**：
- `answer`: 基于知识库生成的简洁答案
- `sources`: 用于生成答案的原始文档片段，可用于溯源

## 使用示例

### Python 示例

```python
import requests

url = "http://127.0.0.1:8088/api/query"
data = {
    "question": "什么是机器学习？",
    "top_k": 3
}

response = requests.post(url, json=data)
result = response.json()

print(f"答案: {result['answer']}")
print(f"来源数量: {len(result['sources'])}")
```

### JavaScript 示例

```javascript
const url = "http://127.0.0.1:8088/api/query";
const data = {
  question: "什么是机器学习？",
  top_k: 3
};

fetch(url, {
  method: "POST",
  headers: {
    "Content-Type": "application/json"
  },
  body: JSON.stringify(data)
})
  .then(response => response.json())
  .then(result => {
    console.log("答案:", result.answer);
    console.log("来源数量:", result.sources.length);
  });
```

### cURL 示例

```bash
curl -X POST "http://127.0.0.1:8088/api/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "什么是机器学习？",
    "top_k": 3
  }'
```

## 技术实现

### 检索流程

1. **向量检索**: 使用 BGE-small-zh-v1.5 模型将问题向量化
2. **初步召回**: 从 FAISS 向量库检索 Top-15 相关文档
3. **重排序**: 使用 BGE-Reranker-Base 模型对结果重排序
4. **随机采样**: 从 Top-6 中随机选择指定数量的文档
5. **LLM 生成**: 将文档作为上下文，调用 DeepSeek 生成答案

### 性能优化

- **Redis 缓存**: 相同问题的查询结果会被缓存 1 小时
- **异步处理**: 使用 FastAPI 的异步特性，避免阻塞
- **响应时间**: 
  - 缓存命中: ~120ms
  - 缓存未命中: ~2.7s（包含检索和生成）

## 错误处理

### 常见错误码

- **200**: 请求成功
- **422**: 请求参数验证失败
- **500**: 服务器内部错误

### 错误响应示例

```json
{
  "detail": "查询失败: 具体错误信息"
}
```

## 测试方法

运行测试脚本：

```bash
conda activate FastAPI_env
python tests/test_agent_api.py
```

或访问 Swagger 文档进行在线测试：
- http://127.0.0.1:8088/docs

## 注意事项

1. **确保服务已启动**: 运行 `python backend/main.py` 启动后端服务
2. **端口配置**: 本项目固定使用 8088 端口，避免与 Agent 项目（8001）冲突
3. **知识库依赖**: 需要先运行 `python backend/scripts/init_rag.py` 初始化知识库
4. **Redis 可选**: 如果 Redis 未启动，系统会自动禁用缓存功能，不影响正常使用

## 集成到 Agent 项目

在 EduReflex Agent 项目中调用示例：

```python
# agent_project/services/knowledge_service.py
import httpx

class KnowledgeService:
    def __init__(self):
        self.rag_api_url = "http://127.0.0.1:8088/api/query"
    
    async def query_knowledge(self, question: str, top_k: int = 3):
        """查询 RAG 系统获取权威知识"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.rag_api_url,
                json={"question": question, "top_k": top_k},
                timeout=30.0
            )
            return response.json()
```

## 更新日志

- **2026-03-03**: 初始版本，支持基本的问答功能
- 支持 CORS 跨域访问
- 集成 Rerank 优化检索精度
- 添加 Redis 缓存加速

