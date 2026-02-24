import redis

try:
    # 连接本地 Redis
    r = redis.Redis(host='localhost', port=6379, decode_responses=True)
    
    # 1. 写入数据
    r.set('my_test_key', 'Hello Redis!')
    print("✅ 写入成功")
    
    # 2. 读取数据
    value = r.get('my_test_key')
    print(f"✅ 读取成功: {value}")
    
    print("🎉 Redis 连接完美！可以启动后端了。")
    
except Exception as e:
    print(f"❌ 连接失败: {e}")
    print("请检查那个黑窗口(redis-server.exe)是不是关掉了？")