from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base

# 这里的 Base 是所有表的“老祖宗”，后面定义的表都要继承它
Base = declarative_base()

# 定义题目表，名字叫 questions
class Question(Base):
    __tablename__ = "questions"
    
    # 每一行数据都要有个唯一的 ID，就像学生的学号，方便系统找题
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 题干内容，因为字数不确定，所以用 Text 类型比较稳妥
    content = Column(Text, nullable=False)
    
    # 选项我打算先存成一个大字符串，后面取出来再处理
    options = Column(Text)
    
    # 答案存正确选项的字母或内容
    answer = Column(String(500))
    
    # AI 提供的解析，存起来方便给学生看
    analysis = Column(Text)
    
    # 难度等级（简单/中等/困难），这是自适应系统的核心参考指标
    difficulty = Column(String(50))
    
    # 知识点标签，以后可以用来分析学生哪块知识薄弱
    tag = Column(String(100))