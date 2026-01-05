import os
import json
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

class LLMService:
    def __init__(self):
        self.llm = ChatOpenAI(
            model='deepseek-chat', 
            openai_api_key=os.getenv("DEEPSEEK_API_KEY"),
            openai_api_base='https://api.deepseek.com/v1',
            model_kwargs={"response_format": {"type": "json_object"}},
            temperature=0.5
        )

    # 修改 services/llm_service.py 中的 generate_quiz 方法
    async def generate_quiz(self, keyword, context, difficulty="中等", question_type="choice"):
        
        # 1. 定义难度约束 (优化后的梯度)
        if difficulty == "简单":
            diff_instruction = """
            【难度要求：简单 (基础概念)】
            1. 侧重考察：定义、语法规则、关键字的作用。
            2. 形式要求：题目中【不要】出现代码片段，或者仅出现单行代码。
            3. 目标：考察学生是否记住了基础知识点（例如：“break语句的作用是什么？”）。
            """
        elif difficulty == "中等":
            diff_instruction = """
            【难度要求：中等 (代码理解)】
            1. 侧重考察：一段标准代码的执行结果预测。
            2. 形式要求：提供一段 3-5 行的常见代码逻辑。
            3. 目标：考察学生能否正确模拟代码运行过程（例如：简单的循环计数、条件判断）。
            """
        else:  # 困难 (修正版：侧重逻辑陷阱，而非底层原理)
            diff_instruction = """
            【难度要求：困难 (逻辑陷阱)】
            1. 侧重考察：易错点、逻辑陷阱、复合知识点应用。
            2. 形式要求：代码中包含稍微复杂的逻辑（如：双重循环、循环中包含 if-else、break/continue 的组合使用、列表推导式）。
            3. 目标：考察学生是否细心，能否识别代码中的“坑”（例如：循环提前结束了、变量被覆盖了等），但不要考过于冷门或底层的知识。
            """

        # 2. 定义题型约束
        if question_type == "choice":
            type_instruction = """
            题型：单项选择题
            JSON字段要求：
            - "question": 题目描述
            - "options": 字典 {"A": "...", "B": "...", "C": "...", "D": "..."}
            - "answer": 正确选项 Key (如 "A")
            - "analysis": 解析
            """
        elif question_type == "subjective":
            type_instruction = """
            题型：简答题/名词解释
            JSON字段要求：
            - "question": 题目描述
            - "options": null
            - "answer": 标准参考答案
            - "analysis": 详细解析
            """
        elif question_type == "scenario":
            type_instruction = """
            题型：场景应用题
            要求：构建一个具体的软件开发场景，询问技术选型或解决方案。
            JSON字段要求：
            - "question": 场景描述 + 问题
            - "options": null
            - "answer": 推荐方案及理由
            - "analysis": 结合场景的解析
            """
        else:
            type_instruction = "题型：通用问答"

        # 3. 构建完整 Prompt
        template = """
        你是一个严谨的编程老师。请根据提供的教材背景知识，出一道关于"{keyword}"的题目。
        
        {diff_instruction}
        
        【题型配置】：
        {type_instruction}
        
        【教材背景知识】：
        {context}
        
        【输出要求】：
        1. 必须返回标准的 JSON 格式。
        2. 题目内容必须严格遵守上述【难度要求】，确保区分度明显。
        """
        
        prompt = ChatPromptTemplate.from_template(template)
        chain = prompt | self.llm
        
        response = chain.invoke({
            "context": context, 
            "keyword": keyword,
            "diff_instruction": diff_instruction,
            "type_instruction": type_instruction
        })
        return self._clean_json(response.content)

    async def grade_answer(self, question, standard_answer, student_answer):
        # --- 升级：评分 Prompt 增加场景应用维度 ---
        system_prompt = """
        你是一位计算机专业阅卷老师。请对学生的回答进行专业评估。
        
        【评分维度】(总分100)：
        1. 知识准确性 (30%)：核心概念是否理解正确。
        2. 场景匹配度 (40%)：(针对场景题) 学生是否真正解决了场景中的问题？方案是否合理？
           - 如果题目是场景题，学生只背诵定义而未结合场景，最高不超过 60 分。
        3. 逻辑与完整性 (30%)：论述是否清晰，因果关系是否成立。
        
        【输入信息】：
        - 题目：{question}
        - 参考答案：{standard_answer}
        - 学生回答：{student_answer}
        
        【输出要求】：
        请返回 JSON 格式：
        - "score": (0-100的整数)
        - "reason": (详细指出得分点和失分点，特别是场景应用方面)
        - "suggestion": (针对薄弱环节的学习建议)
        """
        
        # 注意：这里不需要 user_prompt 再次重复 template 里的变量，
        # LangChain 的 ChatPromptTemplate 会自动处理。
        # 但为了稳妥，我们用标准的 Messages 结构。
        
        from langchain_core.messages import SystemMessage, HumanMessage
        
        messages = [
            SystemMessage(content=system_prompt.format(
                question=question, 
                standard_answer=standard_answer, 
                student_answer=student_answer
            ))
        ]
        
        response = self.llm.invoke(messages)
        return self._clean_json(response.content)

    def _clean_json(self, content):
        if "```json" in content:
            content = content.replace("```json", "").replace("```", "")
        return content.strip()

llm_service = LLMService()