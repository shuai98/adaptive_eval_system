import subprocess
import requests
import time
import os
import signal

class StressService:
    def __init__(self):
        self.process = None
        self.locust_url = "http://127.0.0.1:8089"

    def start_locust_process(self):
        """启动 Locust 后台进程"""
        if self.process:
            return # 已经在运行
        
        # 获取 locustfile 的绝对路径
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        locust_file = os.path.join(base_dir, "tests", "locustfile.py")
        
        # 启动命令：locust -f tests/locustfile.py --web-port 8089
        # 注意：这里不加 --headless，因为我们需要它的 API
        cmd = ["locust", "-f", locust_file, "--web-port", "8089"]
        
        self.process = subprocess.Popen(cmd, shell=True)
        print(f"[Stress] Locust process started on PID {self.process.pid}")
        time.sleep(2) # 等待启动

    def start_test(self, user_count: int, spawn_rate: int):
        """告诉 Locust 开始压测"""
        if not self.process:
            self.start_locust_process()
            
        try:
            # 调用 Locust 的 API 启动 Swarm
            response = requests.post(f"{self.locust_url}/swarm", data={
                "user_count": user_count,
                "spawn_rate": spawn_rate,
                "host": "http://127.0.0.1:8088" # 攻击目标：你的后端
            })
            return response.json()
        except Exception as e:
            print(f"[Stress Error] {e}")
            return {"success": False, "message": str(e)}

    def stop_test(self):
        """停止压测"""
        try:
            requests.get(f"{self.locust_url}/stop")
            return {"status": "stopped"}
        except:
            return {"status": "error"}

    def get_stats(self):
        """获取实时数据"""
        try:
            response = requests.get(f"{self.locust_url}/stats/requests")
            data = response.json()
            
            # 提取我们需要的数据
            return {
                "state": data["state"], # running / stopped
                "total_rps": data["total_rps"],
                "fail_ratio": data["fail_ratio"],
                "current_response_time_percentile_95": data["current_response_time_percentile_95"],
                "user_count": data["user_count"]
            }
        except:
            return None

    def kill_process(self):
        """彻底杀死进程 (关闭后端时调用)"""
        if self.process:
            os.kill(self.process.pid, signal.SIGTERM)
            self.process = None

stress_service = StressService()