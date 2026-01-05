'''
上个版本使用了传统的字符串解析方法来获取模型输出，存在一定的解析失败风险。
这个版本使用Function Calling来实现结构化输出。
DeepSeek的Function Calling类似于OpenAI的Function Calling，可以让我们强制模型输出符合特定的JSON结构。
这样可以大大减少解析错误的概率。
'''


import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import Optional, Dict

load_dotenv()

# --- 1. 定义数据结构 (Schema) ---
# 这部分和刚才一样，Pydantic 是通用的
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
        # 初始化 LLM
        self.llm = ChatOpenAI(
            model='deepseek-chat', 
            openai_api_key=os.getenv("DEEPSEEK_API_KEY"),
            openai_api_base='https://api.deepseek.com/v1',
            temperature=0.5,
        )
        
        # --- 关键点：绑定结构化输出 ---
        # 这行代码底层会自动调用 DeepSeek 的 Function Calling 能力
        # 强制模型必须输出符合 QuizOutput 结构的 JSON
        self.quiz_llm = self.llm.with_structured_output(QuizOutput)
        self.grade_llm = self.llm.with_structured_output(GradeOutput)

    async def generate_quiz(self, keyword, context, difficulty="中等", question_type="choice"):
        # 2. 动态生成题型要求描述
        if question_type == "choice":
            type_desc = "单项选择题，必须包含 options 选项字典"
        elif question_type == "scenario":
            type_desc = "场景应用题，options 为 null，answer 为解决方案"
        else:
            type_desc = "简答题，options 为 null，answer 为参考答案"

        # 3. 构建 Prompt
        # 注意：现在不需要在 Prompt 里写 {format_instructions} 了！
        # Function Calling 会自动处理格式约束。
        template = """
        你是一个严谨的编程老师。请根据提供的教材背景知识，出一道关于"{keyword}"的题目。
        
        【难度等级】：{difficulty}
        【题型要求】：{type_desc}
        
        【教材背景知识】：
        {context}
        """
        
        prompt = ChatPromptTemplate.from_template(template)
        
        # 4. 执行链
        # prompt -> quiz_llm (带强类型约束的模型)
        chain = prompt | self.quiz_llm
        
        try:
            # result 直接就是 QuizOutput 类的实例对象，不是字符串！
            result = chain.invoke({
                "context": context, 
                "keyword": keyword,
                "difficulty": difficulty,
                "type_desc": type_desc
            })
            
            # 转成 JSON 字符串返回 (为了兼容你的前端接口)
            # exclude_none=True 可以去掉值为 null 的字段（可选）
            return result.json()
            
        except Exception as e:
            print(f"生成失败: {e}")
            # 兜底
            return '{"question": "生成出错，请重试", "options": {}, "answer": "", "analysis": ""}'

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
        
        # 使用绑定了 GradeOutput 的模型
        chain = prompt | self.grade_llm
        
        try:
            result = chain.invoke({
                "question": question, 
                "standard_answer": standard_answer, 
                "student_answer": student_answer
            })
            return result.json()
        except Exception as e:
            print(f"评分失败: {e}")
            return '{"score": 0, "reason": "评分异常", "suggestion": "请重试"}'

llm_service = LLMService()