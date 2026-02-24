import os
import json
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import Optional, Dict, AsyncIterator

load_dotenv()

# --- 1. 定义数据结构 (Schema) ---
class QuizOutput(BaseModel):
    """生成的题目信息"""
    question: str = Field(description="题目的具体描述或场景描述")
    options: Optional[Dict[str, str]] = Field(description="选项字典，如 {'A': '...', 'B': '...'}，简答题为 null")
    answer: str = Field(description="正确答案的选项Key（如'A'）或标准参考答案文本")
    analysis: str = Field(description="详细的解析和知识点扩展")

class GradeOutput(BaseModel):
    """评分结果信息"""
    score: int = Field(description="0-100之间的整数评分")
    reason: str = Field(description="具体的评分理由")
    suggestion: str = Field(description="给学生的改进建议")

class LLMService:
    def __init__(self):
        # 1. 初始化基础模型
        self.llm = ChatOpenAI(
            model='deepseek-chat', 
            openai_api_key=os.getenv("DEEPSEEK_API_KEY"),
            openai_api_base='https://api.deepseek.com/v1',
            temperature=0.7,#温度调高一点，防止每一次出题雷同
            # 确保这里没有任何 model_kwargs
        )
        
        # 1.5 流式输出专用（不带结构化）
        self.llm_streaming = ChatOpenAI(
            model='deepseek-chat',
            openai_api_key=os.getenv("DEEPSEEK_API_KEY"),
            openai_api_base='https://api.deepseek.com/v1',
            temperature=0.7,
            streaming=True  # 启用流式
        )
        
        # 2. 绑定结构化输出 (Function Calling)
        #  关键修复：显式指定 method="function_calling"
        # 这会强制 LangChain 使用 tools 参数，而不是 response_format
        self.quiz_llm = self.llm.with_structured_output(QuizOutput, method="function_calling")
        self.grade_llm = self.llm.with_structured_output(GradeOutput, method="function_calling")

    async def generate_quiz(self, keyword, context, difficulty="中等", question_type="choice"):
        if question_type == "choice":
            type_desc = "单项选择题，必须包含 options 选项字典"
        elif question_type == "scenario":
            type_desc = "场景应用题，options 为 null，answer 为解决方案"
        else:
            type_desc = "简答题，options 为 null，answer 为参考答案"

        template = """
        你是一个严谨的编程老师。请根据提供的教材背景知识，出一道关于"{keyword}"的题目。
        
        【难度等级】：{difficulty}
        【题型要求】：{type_desc}
        
        【教材背景知识】：
        {context}
        """
        
        prompt = ChatPromptTemplate.from_template(template)
        chain = prompt | self.quiz_llm
        
        try:
            result = chain.invoke({
                "context": context, 
                "keyword": keyword,
                "difficulty": difficulty,
                "type_desc": type_desc
            })
            return result.model_dump()
        except Exception as e:
            print(f"生成失败: {e}")
            return {
                "question": "生成出错，请重试", 
                "options": {}, 
                "answer": "", 
                "analysis": str(e)
            }

    async def stream_generate_quiz(
        self, 
        keyword: str, 
        context: str, 
        difficulty: str = "中等", 
        question_type: str = "choice"
    ) -> AsyncIterator[str]:
        """
        流式生成题目，逐字返回
        """
        if question_type == "choice":
            type_desc = "单项选择题，必须包含4个选项（A、B、C、D）"
            format_instruction = """
请严格按照以下格式输出（不要有其他内容）：
题目：[题目内容]
A. [选项A内容]
B. [选项B内容]
C. [选项C内容]
D. [选项D内容]
答案：[正确答案的字母]
解析：[详细解析]
"""
        elif question_type == "scenario":
            type_desc = "场景应用题，给出实际问题场景"
            format_instruction = """
请严格按照以下格式输出：
题目：[场景描述和问题]
答案：[解决方案]
解析：[思路分析]
"""
        else:
            type_desc = "简答题"
            format_instruction = """
请严格按照以下格式输出：
题目：[问题描述]
答案：[参考答案]
解析：[知识点说明]
"""

        template = """你是一个严谨的编程老师。请根据提供的教材背景知识，出一道关于"{keyword}"的题目。

【难度等级】：{difficulty}
【题型要求】：{type_desc}

{format_instruction}

【教材背景知识】：
{context}
"""
        
        prompt = ChatPromptTemplate.from_template(template)
        chain = prompt | self.llm_streaming
        
        try:
            # 流式调用
            async for chunk in chain.astream({
                "context": context,
                "keyword": keyword,
                "difficulty": difficulty,
                "type_desc": type_desc,
                "format_instruction": format_instruction
            }):
                # chunk.content 是每次返回的文本片段
                if hasattr(chunk, 'content'):
                    yield chunk.content
                    
        except Exception as e:
            yield f"\n\n[生成出错: {str(e)}]"

    async def grade_answer(self, question, standard_answer, student_answer):
        system_prompt = """
        你是一位计算机专业阅卷老师。请对学生的回答进行专业评估。
        
        【评分维度】：准确性(40%)、完整性(30%)、逻辑性(30%)。
        
        【输入信息】：
        - 题目：{question}
        - 参考答案：{standard_answer}
        - 学生回答：{student_answer}
        """
        
        prompt = ChatPromptTemplate.from_template(system_prompt)
        chain = prompt | self.grade_llm
        
        try:
            result = chain.invoke({
                "question": question, 
                "standard_answer": standard_answer, 
                "student_answer": student_answer
            })
            return result.model_dump()
        except Exception as e:
            print(f"评分失败: {e}")
            return {
                "score": 0, 
                "reason": "评分异常", 
                "suggestion": "请重试"
            }

llm_service = LLMService()