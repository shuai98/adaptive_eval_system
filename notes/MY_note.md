Prompt（提示词） 就是你给 AI 下达的指令或说的话。
为什么选 async def:
    为什么要用？ 因为你后面要调用 LLM（通过网络请求）。这种操作很慢。
    如果不加 async？ 服务器在等 AI 回复的那几秒钟里，就像死机了一样，处理不了任何其他人的请求。
    加了之后？ 服务器会把等待 AI 的时间释放出来，去处理别人的请求，这就是异步非阻塞
    这样一来，服务器的吞吐量就大大提升了。

直接点了运行
![alt text](image.png)
解决方法：控制台使用：uvicorn main:app --reload

第一次fastapi后端启动：
![alt text](image-1.png)

将api key放入.env文件中，防止泄露，确保安全性

报错：
Error code: 402 - {'error': {'message': 'Insufficient Balance', 'type': 'unknown_error', 'param': None, 'code': 'invalid_request_error'}}
原因：deepseek没有token额度，充钱得以解决

Postman

第一次在自己的后端界面上连接上ai：
![alt text](image-2.png)
![alt text](image-3.png)

我现在有一个问题，为什么我提问的是循环语句，但是它直接好像默认问的就是python而没有想着有没有可能是其他语言：
1.Prompt（提示词）的惯性
2上下文关联
解决方法：修改prompt

运行 index.html 时：报错
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # 允许所有网站访问（开发阶段先全开）
    allow_credentials=True,
    allow_methods=["*"],      # 允许所有请求方式（GET, POST等）
    allow_headers=["*"],      # 允许所有请求头
)

回答太慢：（未改进）
1.流式传输
2增加“Loading”动画

ai说：如果数据库里已经有一道关于“循环语句”的题，直接给用户看，1秒都不到！
但是问题：用户搜“循环语句”，这样要是数据库中有包含“循环语句”但是意思完全不同的怎么办，或者说只能搜寻“循环语句”这四个字，那样又有什么意义呢
解决方法：语义向量搜索（向量数据库）

-----------------------------------------------------------------------------------------
以上是基础版，开发的第一阶段，实现调用大模型生成问题，将生成的问题存入数据库中（SQLite）
下面要实现RAG
-----------------------------------------------------------------------------------------

def get_ai_quiz(topic: str, difficulty: str = "中等"):
    """
    【核心函数】结合 RAG 技术生成题目
    1. 去向量数据库检索素材
    2. 把素材喂给 DeepSeek
    3. 返回题目 JSON
    """

chroma_db 并不是一个你需要手动创建的文件夹，它是通过代码自动生成的。

(FastAPI_env) D:\毕设_code\adaptive_eval_system>python -u "d:\毕设_code\adaptive_eval_system\init_rag.py"

报错：
Traceback (most recent call last):
  File "d:\毕设_code\adaptive_eval_system\init_rag.py", line 3, in <module>
    from langchain.text_splitter import CharacterTextSplitter
ModuleNotFoundError: No module named 'langchain'
解决：
from langchain_community.document_loaders import TextLoader
#注意这里：改用 langchain_text_splitters 导入，或者尝试直接从 langchain 导入

embedding模型的选择：bce-embedding-base_v1
![alt text](image-4.png)
简介：
输出的向量 维度为 512
属于 小规模模型：参数量约 24M

运行init_rag时错误：找不到 ./db.txt，请先创建该文件并写入教材内容。但是我的项目里面是有db,txt的
db.txt在docs文件夹中，不在根目录下

报错：
UnicodeEncodeError: 'ascii' codec can't encode characters in position 7-8: ordinal not in range(128)
原因：因为程序直接把 DEEPSEEK_API_KEY 这几个英文字母当成了真正的密钥发给服务器了，虽然我在.env文件中定义了DEEPSEEK_API_KEY并把我的apikey赋值，但是正确从 .env 读取 Key，需要使用 python-dotenv 库。
在代码中的修改：
加载 .env 文件中的变量
load_dotenv() 
从环境变量中提取真正的 Key
确保你的 .env 文件里写的是 DEEPSEEK_API_KEY=sk-xxxx
api_key = os.getenv("DEEPSEEK_API_KEY")
最核心的一点：.env 里的变量名和代码里的字符串必须通过 os.getenv 桥接。
ps：
1. 为什么以前可以？（以前的“宽容”）
在旧版本的 openai 库或 langchain-openai 中，当你把 'DEEPSEEK_API_KEY' 这个字符串传进去时，如果库的作者写了一段兼容代码（比如：“如果用户传进来的字符串不以 sk- 开头，就自动去环境变量里搜一下同名的值”），它就能跑通。
2. 为什么这次报错了？（现在的“严格”）
你现在用的 langchain-openai 0.1.x+ 版本，底层网络驱动换成了 httpx。
严格检查：新的驱动在发送请求前，会把所有参数强行转换并检查。
ASCII 限制：由于你现在的 FastAPI_env 环境可能在处理字符串编码时比较严格，当它发现你传入的 'DEEPSEEK_API_KEY' 这个字符串（或者它去寻找环境变量时遇到了系统层面的乱码）时，它试图用 ASCII 编码去发送。
报错触发：如果你的 Windows 系统用户名包含中文，或者 .env 文件的编码格式是 UTF-8 with BOM，甚至只是环境变量里有一个带中文的无关路径，httpx 在初始化时可能会被这些“非法字符”绊倒，导致报出那个 UnicodeEncodeError。

好的，我想问如果我在我的db.txt文件中添加了新的知识，我应该怎么操作使得它进入chroma
1.最稳妥的“清空重来”法：直接在 VS Code 或文件夹里把 chroma_db 这个文件夹彻底删掉，然后执行我之前写的初始化脚本
2.# 如果你想每次运行 init_rag.py 都用新的 db.txt 覆盖旧的数据库
if os.path.exists(db_path):
    shutil.rmtree(db_path) # 自动删除旧文件夹
我使用了方法二改进了我的init_rag文件

直接在 db.txt 加字，数据库并不知道这些新字对应的坐标是什么。必须通过 Embedding 模型（BGE） 计算一遍，才能转换成数据库能理解的格式。那为什么不通过操作让新加入的东西直接添加进去，而是清理完数据库重新加载一遍呢，那样不是更加费时费力吗
数据重复（Duplication）： 如果你在 db.txt 尾部加了一段话，然后运行“增量添加”脚本，代码怎么知道哪些是旧的，哪些是新的？如果没有复杂的 ID 校验逻辑，你每运行一次，数据库里就会多出一堆重复的片段，AI 检索时就会看到一堆一模一样的参考资料。
上下文断裂： RAG 的核心是“切片（Chunking）”。如果你修改了文档中间的一句话，这会导致这一块以及它前后衔接的片段全部失效。只加新字，不改旧块，会导致检索出来的知识支离破碎。
清理过期数据： 如果你删除了 db.txt 里的某段过时知识，数据库里的向量依然存在。如果不清空，AI 依然会检索出已经过时的错误答案（这在面试中叫“数据一致性问题”）。

我的一次输出：
RAG 生成的题目:
题目：**
在Python网络编程中，我们经常需要处理多个客户端连接。假设你有一个包含客户端连接对象（如`socket.socket`实例）的列表`client_sockets`， 每个连接对象都有一个`.getsockname()`方法，该方法返回一个元组`(ip地址, 端口)`。
请使用**列表推导式**，从`client_sockets`中提取所有客户端的**端口号**，并生成一个新的整数列表`client_ports`。
要求：**
1. 仅使用一行列表推导式完成。
2. 假设`client_sockets`中每个对象都是有效的socket连接，且`getsockname()`方法返回的元组格式始终为`(ip, port)`。
示例：**
若
``python

client_sockets = [socket1, socket2, socket3]
 其中：
 socket1.getsockname() 返回 ('192.168.1.10', 54321)
 socket2.getsockname() 返回 ('192.168.1.11', 54322)
 socket3.getsockname() 返回 ('192.168.1.12', 54323)
```
则结果应为：
```python
client_ports = [54321, 54322, 54323]
```
请补全代码：**
```
**请补全代码：**
**请补全代码：**
**请补全代码：**
```python
```python
client_ports = ________________________________________
client_ports = ________________________________________
```
```
我觉得这个输出有问题，解决方案：修改prompt：
请严格遵守以下输出格式，不要包含多余的废话或重复的内容：
1. 题目描述
2. 代码示例（如果有）
3. 正确答案
4. 答案解析

报错：
INFO:     Will watch for changes in these directories: ['D:\\毕设_code\\adaptive_eval_system']
ERROR:    [WinError 10013] 以一种访问权限不允许的方式做了一个访问套接字的尝试。
原先代码里面的8000端口被占用，修改为8080得以解决，
使用uvicorn main:app --reload --port 8080运行后解决

![alt text](image-5.png)

我想知道在我添加了RAG这个模块后，他是只能回答我给他的知识库里面的东西还是知识库没有的它会自己回答，或者说我给他的知识库和它自己的知识库使用的先后顺序，还有是怎样实现这个先后顺序的
：外部知识（你的 db.txt） > 内部知识（DeepSeek 自带记忆）
：这是靠 Prompt（提示词）的压力实现的

我在知识库加入了这个：python的apflag是wanjiashuai，但是当我把keyword设置为python的apflag是什么时，它提出的问题和我的keyword毫不相干
因为语义密度太低
后期准备使用rerank技术

将代码上传至github：（缺少README）
![alt text](image-6.png)
数据相关和可能泄露隐私，导致安全问题的文件并没有上传，详见.gitignore文件

-------------------------------------------------------------------------------------
阶段任务完成，结果如图：

-------------------------------------------------------------------------------------

在github上找到Datawhale，观看了他们的大量资料

后期准备使用RAGAS工具来评估我的系统，加上rerank技术，让系统可以操作pdf类型的数据，流式输出，docker部署，让ai生成更多种类型的题目，不仅限于单选题，ai智能评分，本地部署大模型
-------------------------------------------------------------------------------------


RAG还有：知识更新滞后性： LLM 基于静态的数据集训练，这可能导致模型的知识更新滞后，无法及时反映最新的信息动态。RAG 通过实时检索最新数据，保持内容的时效性，确保信息的持续更新和准确性。这个功能吗，怎么实现的：
RAG 解决滞后性不是靠重新训练模型，而是靠更换它能看到的“参考资料”。

待考虑：一键更新知识库”的功能吗？这样你在演示时，往 db.txt 随便加一句新话，系统就能立刻根据它出题，这种实时性非常有说服力

含金量体现：你是否尝试了混合搜索（Hybrid Search）？是否加入了重排序（Rerank）机制？是否针对 PDF 的复杂格式做了精准的数据清洗和切片（Chunking）？
含金量体现：使用 RAGAS 等框架进行自动化评估，或者建立自己的**“黄金数据集（Golden Dataset）”**（即准备 50 组标准问题和答案，测试系统的准确率）。

待考虑：语义切分 (Semantic Chunking)
——这是进阶方案。
工作原理：不看字数，而是用模型去“读”这段话。当发现下一句和上一句聊的不是一个话题时，才切开。
含金量：非常高，但计算量大，速度慢。
我现在的是按照字符长度切分（最拉）

我将 LLM 的 temperature 设置为 0.3
理由是：我们的目标是生成具有教育严肃性的‘题库’，而非文学创作。较低的温度值可以有效抑制模型的随机性，确保生成的内容严格基于检索到的背景知识。 实验发现，当温度高于 0.7 时，模型容易忽略检索到的约束，产生幻觉；而设置为 0.3 则能在生成稳定性（符合格式要求）和表达多样性之间取得平衡。”

在目前的 RAG 基础架构中，默认情况下是不存储用户问题的

问题：他的回答不完整呢![alt text](image-7.png)
原因：文本切块（Chunking）导致的“断头信息”。
问题：但是ai它自己就不会看看自己的回答不完整吗，还是说它纯看我的知识库而没有自己的想法
解决方法：修改prompt

问题：![alt text](image-8.png)
原因：在前端代码里依然写的是默认的 http://127.0.0.1:8000
修改前端代码得以解决

待考虑：你觉得让ai自己根据用户提供的问题生成prompt怎么样

Mermaid做图：
![alt text](image-9.png)

报错：ERROR:    [WinError 10013] 以一种访问权限不允许的方式做了一个访问套接字的尝试。


警告：Created a chunk of size 1563, which is longer than the specified 500
现在用的是 CharacterTextSplitter，它比较笨，只按简单的字符（比如换行符）切分。如果 PDF 里有一大段代码或者长难句中间没有换行，它切不开，只能被迫保留一大坨（1563字），这会导致检索不准，且容易撑爆 LLM 的上下文。
解决方法：换成 RecursiveCharacterTextSplitter（递归字符切分器）。它是业界的标准做法。它会尝试先按 \n\n 切，切不开就按 \n 切，还不行就按 空格 切，保证每个块都在 500 字左右。

设置了 chunk_size=500，但 CharacterTextSplitter 却“违抗命令”，切出了 1563 个字符的巨无霸
错误解释（ai回答）：CharacterTextSplitter 的工作逻辑
它的逻辑是这样的：
“我要把文本攒起来。攒一点，量一下长度。只要长度还没到 500，我就继续往下读。一旦超过了 500，我就开始寻找最近的一个换行符 \n，在那里切一刀。”
所以，500 的作用是： 告诉程序“什么时候开始准备切”。
但是，它的致命死穴是：
它只认你指定的那个分隔符（默认是 \n）。
如果它攒到了 500 字，触发了闹钟，开始找 \n，结果往后找了 1000 个字，竟然一个换行符都没找到（PDF 解析时常有的事，全是空格，没有回车），它就会崩溃。
这时候它的逻辑是：
“老板让我按 \n 切，可是这里 1500 个字中间连个 \n 都没有啊！我不能把单词切断啊（它以为中间没换行就是一句话）！算了，为了保证完整性，我只能违抗命令，把这 1500 字一整坨都扔出去。”
解决：RecursiveCharacterTextSplitter（递归字符切分器）
它的逻辑是这样的（chunk_size=500）：
第一轮尝试（用大刀 \n\n）：
“我先按段落切。哎呀，切出来的一块有 1500 字，超过 500 了！不行，启动第二套方案。”
第二轮尝试（用小刀 \n）：
“那我按句子切。哎呀，还是找不到换行符，这 1500 字还是连在一起的！不行，启动第三套方案。”
第三轮尝试（用剪刀  空格）：
“那我按空格切！把单词分开。嗯，切开了，现在每块大概 500 字了。”
第四轮尝试（暴力撕纸）：
“如果连空格都没有（比如一长串乱码），我就在第 500 个字那里硬切！不管有没有切断单词，必须保证不超过 500！”


修改前：![alt text](image-10.png)
修改后：![alt text](image-11.png)
文档被切分为更多块，说明大块少了，虽然报错，但是重新加载后还是成功切分并入库


报错：
正在发送请求，测试关键词：【装饰器】...
 失败: {"detail":"Error executing plan: Error sending backfill request to compactor: Error constructing hnsw segment reader: Error creating hnsw segment reader: Error loading hnsw index"}
  ![alt text](image-12.png)
 WARNING:  WatchFiles detected changes in 'test_rerank.py'. Reloading...
收到出题请求，关键词: 装饰器
INFO:     127.0.0.1:62639 - "POST /generate_question HTTP/1.1" 500 Internal Server Error
![alt text](image-13.png)

解决：删除chroma.db，重新运行init_rag.py
ChromaDB 是一个基于文件的数据库。当你之前的代码切分方式是 A，现在的代码切分方式是 B，或者上次写入没写完就关机了，它的索引文件（HNSW Index）就会对不上号，然后就崩了。以后遇到这种 hnsw 开头的报错，直接删掉 chroma_db 重建即可。

rerank测试结果：
![alt text](image-14.png)

前端报错：
![alt text](image-15.png)


接下来的目标：在前端做研发对比模式，左侧显示原始检索版本，右侧显示加入rerank后的结果
ragas
前端：三个界面
1.学生界面，负责给学生出题等
2.教师界面，更新学生答题状况等
3.测试界面，研发对比模式，左侧显示原始检索版本，右侧显示加入rerak后的结果

mysql连接，让已经出过的题目入库，这样下次出题更快

输入毫无意义时：![alt text](image-17.png)

对比结果：![alt text](image-19.png)
----------------------------------------------------------------
v3版本完成，现在实现：
学生界面（选择题基本完善，但是由于后端代码的固定，只能生成“简单”的题目，简答题功能还不完善）
老师界面（只有上传知识库，还没有其他功能）
上传了知识后，重新加载rag知识库，但是前端没有反馈，用户只能干等着，也不知道是否加载完成
对比模式（可以看到加入重排前后系统检索到的知识库里的内容（top3），但是感觉不够直观）
问题：不知道如何体现出这个系统的并发性和处理多项事务的能力
     有的时候系统会出一点bug，前端莫名其妙的把界面清空（明明输入了内容却不见了）
     后端响应很快，但是在后端有了反应后过几秒前端才能响应
----------------------------------------------------------------