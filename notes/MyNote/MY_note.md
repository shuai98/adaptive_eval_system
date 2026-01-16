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
学生登录，记录学生信息，每个学生的做题情况等还没有实现
老师界面（只有上传知识库，还没有其他功能）
上传了知识后，重新加载rag知识库，但是前端没有反馈，用户只能干等着，也不知道是否加载完成
对比模式（可以看到加入重排前后系统检索到的知识库里的内容（top3），但是感觉不够直观）
问题：不知道如何体现出这个系统的并发性和处理多项事务的能力
     有的时候系统会出一点bug，前端莫名其妙的把界面清空（明明输入了内容却不见了）
     后端响应很快，但是在后端有了反应后过几秒前端才能响应
     main.py代码稍微有点大，还可以继续分块，保证代码的可读性
----------------------------------------------------------------
![alt text](image-20.png)


我觉得我的前端需要大改，首先，我觉得简答题和选择题应该放在同一个界面，由学生自己进行选择哪种题型，教师端应该可以看到每一个学生的答题情况，
那我先简单规划一下整个系统应该有的功能：
学生登录，学生选择题型，答案及解析，评语，
学生选择答题模式：
1：学生自由选择题目难易程度（简单等）
2：自适应
教师登录，教师查看学生答题情况，教师上传新资料，
研发对比界面倒是不需要改动了


换一种加密算法。我们将从 bcrypt 切换到 pbkdf2_sha256
![alt text](image-21.png)

问题：前端界面上的滑块划不动
在之前的代码中，那行提示文字“按住滑块拖动到最右边”的层级（z-index: 10）比滑块按钮的层级（z-index: 2）要高。
这就导致：当你鼠标点下去的时候，其实点到了文字上，而不是滑块按钮上，所以根本触发不了拖动事件

问题：输入题目，界面显示出题目后就返回了登录界面
ai回答：原因分析：
目前的 index.html 代码中，用户登录状态（user 变量）是保存在内存（RAM）里的。
当你点击“生成题目”或者按回车时，如果浏览器认为这是一个表单提交（Form Submission），或者代码里有某个地方触发了页面刷新（Page Reload），内存就会被清空。
页面一刷新，Vue 重新加载，user 变量重置为 null，系统就会认为你没登录，于是把你踢回了登录界面。
解决方法：
需要把登录状态存到浏览器的 LocalStorage（本地存储） 里。这样即使页面刷新，系统也能记得你是谁。

之前的 bug 是因为网页一刷新，内存里的 user 变量就清空了。
现在我们用了 localStorage（浏览器的本地存储）：
登录时：不仅更新内存，还把用户信息写进浏览器的一个小文件里。
刷新时：代码一运行，先去读那个小文件，如果读到了，就自动帮你“恢复登录”。
退出时：把那个小文件删掉。

现在不会退出登录了，但是出的题目只是一闪而过，然后界面将变成开始的界面了
破案：不是代码的问题，是VS Code 的 "Live Server" 插件的问题，
生成题目后数据库发生改动
Live Server 以为我修改了代码，于是自动帮我刷新了浏览器
在文件夹直接双击打开html文件就可以解决：
![alt text](image-22.png)

手动选择困难模式：![alt text](image-23.png)
胡乱回答：![alt text](image-24.png)
教师端：![alt text](image-25.png)

现在基本功能完成，还差场景题
场景题，gemini给出简单的回答：![alt text](image-26.png)
![alt text](image-27.png)
觉得这道题有点难，但是我设置新学生上来自适应的难度默认为中等
这道题得了75，下一道题还是中等，
![alt text](image-28.png)
中等题我瞎答得了0分，按照我代码的逻辑，下一道题是简单
按逻辑来说是简单，ai帮我回答了问题：
![alt text](image-29.png)
得了85分，按照逻辑来说下一道题是困难，（这里发现一个bug，我的本意应该是简单题80分以上变为正常，正常80分以上变为困难，而不是现在这样跳级）
![alt text](image-30.png)
下面这个截图应该是困难的：
![alt text](image-31.png)


现在着手解决自适应逻辑问题：先在数据库中加入一个字段让系统可以识别该学生做过的题目的难易程度，同时要是以后有更好的解决办法（如分析这个学生做过的所有题目的分数，难易程度等），可以更加方便
现在的解决思路：根据上一题的难易程度和分数共同决定下一道题的难度：

问题解决

现在发现一个问题，我输入循环语句后，简单题和正常题题目和选项基本差不多，困难题倒是明显不一样。
我认为解决方法有两个：
1.修改prompt，强制让ai有所区别
2.增加知识库内容
3.temperature设置为0.5，让ai生成的题目有点多样性

我还调整了一下困难题的难度，原来的太高太偏
修改后：![alt text](image-32.png)
![alt text](image-33.png)

---------------------------------------------------------------------
现在完成了我的v4版本，这个版本较上个版本更进了：
1.上个版本的main函数有些长，可读性不高，现在将main函数大多功能细分在其他文件里面，分工合作，逻辑性高
2.修改前端界面，添加了登录，注册，拖动验证等小功能
3.教师端新添可以查看学生答题情况的界面
4.使用数据库，存储用户信息，学生答题情况，每一个题及其难易程度等
5.修改了自适应逻辑使其更符合正常需求
6.更改了出题难易程度的prompt，规范了ai出题的难易程度（不会特别特别难）
7.更改了temperature，稍稍加大，使得ai的灵活性更高，出同一个题目或者雷同题目的概率减小
8.增加学生自己选择答题模式的功能（自适应或者固定难度）

我希望接下来可以：
1.增加教师端的功能，现在的教师端功能有点少，（但是加什么还在规划）
2.容器化
3.系统现在出题有点慢，希望可以得到优化
4.上传新的资料时希望添加进度条，不要让人傻等着，还不知道什么时候可以加载完
5.RAGAS 自动化评测
6.压力测试：使用 Locust 或 JMeter 模拟 50 个学生同时点击“生成题目”
---------------------------------------------------------------------
评估：
![alt text](image-34.png)

在看到DataWhale这张图片后：![alt text](image-35.png)
我觉得应该说明一下，我的RAG系统使用的是混合加载器策略，针对不同的文件类型使用了不同的加载器
.txt使用TextLoader
pdf使用PyPDFLoader
后续可以仿照DataWhale使用Unstructured
因为它功能更强一点：![alt text](image-36.png)

我的系统就使用了这个分块方法：![alt text](image-37.png)

我的系统现在是这个策略：![alt text](image-39.png)
能不能用上输出解释器来格式化输出呢：
![alt text](image-38.png)，如OutputParsers
Function Calling看起来也很棒呢
![alt text](image-40.png)

通过对比，查资料，最终选择使用RAGAS评估我的系统（需要对比）
![alt text](image-41.png)

了解到知识图谱增强RAG：
![alt text](image-42.png)

我的系统架构图：notes/MyNote/Untitled diagram-2026-01-06-052357.png

考虑：加入Hybrid Search

我对：[Timing] embedding recall: 120ms [Timing] rerank: 430ms [Timing] llm generation: 2.1s [Timing] total: 2.7s这个日志功能很感兴趣，也想要弄流式输出，RAGAS也要（最好对比无RAG，普通RAG和加上rerank），还有并发测试也想做，但是我希望我做的这些测试什么的都可以在前端被看到，还有我的前端现在只有一个，教师和学生还有研发对比都在一个界面上，我希望我有三个界面，一个教师界面，只做教师的业务，一个学生界面，只做学生的业务，还有一个管理端，可以看到测试数据，管理学生教师等功能


问题：登录界面打开以后输入账号密码后跳到一个界面，上面写Cannot GET /static/student/index.html
![alt text](image-43.png)
这个因为我是在 VS Code 里右键点击 HTML 文件然后选 "Open with Live Server" 打开的

问题：出题请求 - 模式: adaptive, 判定难度: 中等, 题型: choice
生成失败: Error code: 400 - {'error': {'message': 'This response_format type is unavailable now', 'type': 'invalid_request_error', 'param': None, 'code': 'invalid_request_error'}}
![alt text](image-44.png)
原因：json解析错误，
LangChain 默认以为你在用 OpenAI 的最新模型（如 GPT-4o），所以它默认采用了 OpenAI Structured Outputs 模式（即在后台自动加上 response_format: { "type": "json_schema" }）。
冲突：DeepSeek 目前还不支持 json_schema 这种最新的 OpenAI 格式，它只支持标准的 Tool Calling (工具调用)。
结果：DeepSeek 服务器收到请求，发现不支持的 response_format，直接报 400 错误。
解决：修改llm_service.py，在调用 with_structured_output 时，加上 method="function_calling" 参数



问题：生成的题目都好相似，学生端没有历史记录，性能监控没开始（我希望能做出炫酷的图）


反思，温度设置过低，导致LLM输出的问题严格按照筛选出来的片段出题，同时导致了出题雷同

解决：
1.将温度调高
2.在RAg检索取前6名，然后从中随机选3名给 LLM， 这样既保证了相关性，又保证了每次的 Context 不完全一样。如果候选够多，就随机选；不够就全选

python -m uvicorn backend.main:app --reload --port 8088

问题：不挂梯子加载不了

ragas报错：![alt text](image-45.png)
xception raised in Job[32]: BadRequestError(Error code: 400 - {'error': {'message': 'Invalid n value (currently only n = 1 is supported)', 'type': 'invalid_request_error', 'param': None, 'code': 'invalid_request_error'}})
RAGAS 为了提高评测的准确性，有时候会尝试让大模型“一次生成多个候选项”（比如生成 3 个理由，然后选最好的），这对应 API 参数 n > 1。
DeepSeek 的限制：DeepSeek 的 API 目前不支持 n > 1（即一次请求生成多个结果），它强制要求 n = 1。
冲突：RAGAS 默认发出了 n=2 或 n=3 的请求，DeepSeek 拒绝处理，所以报错 Invalid n value。

有Rerank的分数反而比无Rerank低了:![alt text](image-46.png)
