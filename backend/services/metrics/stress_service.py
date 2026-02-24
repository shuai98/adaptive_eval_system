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
        
        # 获取 locustfile 的绝对路径 (同级目录)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        locust_file = os.path.join(base_dir, "locustfile.py")
        
        # 启动命令：直接调用 locust.exe
        # 路径推导：python.exe 同级目录下的 Scripts/locust.exe
        import sys
        env_root = os.path.dirname(sys.executable)
        locust_exe = os.path.join(env_root, "Scripts", "locust.exe")
        
        cmd = [locust_exe, "-f", locust_file, "--web-host", "127.0.0.1", "--web-port", "8089"]
        print(f"[Stress] Executing command: {' '.join(cmd)}")
        print(f"[Stress] CWD: {base_dir}")
        
        # shell=False (默认) 更安全，且能更好地捕获输出
        # 重定向输出到文件以便调试
        self.log_file = open(os.path.join(base_dir, "locust_debug.log"), "w")
        self.process = subprocess.Popen(cmd, cwd=base_dir, stdout=self.log_file, stderr=subprocess.STDOUT)
        print(f"[Stress] Locust process started on PID {self.process.pid}")
        
        # 等待 Locust Web 服务就绪
        self.wait_for_locust_ready()

    def wait_for_locust_ready(self, timeout=30):
        print("[Stress] Waiting for Locust web interface...")
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # 1. 先尝试访问根路径，检测端口通不通
                requests.get(f"{self.locust_url}/", timeout=1)
                print("[Stress] Locust Connectable! Checking API...")
                
                # 2. 再确认 API 可用
                requests.get(f"{self.locust_url}/stats/requests", timeout=1)
                print("[Stress] Locust API is ready!")
                return True
            except requests.exceptions.ConnectionError:
                time.sleep(1)
            except Exception as e:
                print(f"[Stress] Wait error: {e}")
                time.sleep(1)
        
        print("[Stress Error] Locust startup timed out!")
        return False

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
            }, timeout=5)
            return response.json()
        except Exception as e:
            print(f"[Stress Error] {e}")
            return {"success": False, "message": str(e)}

    def stop_test(self):
        """停止压测 (优先尝试优雅停止，失败则强杀)"""
        try:
            # 尝试通过 API 优雅停止
            requests.get(f"{self.locust_url}/stop", timeout=2)
            
            # 给它一点时间反应
            time.sleep(1)
            
            # 如果进程还在，再杀一次确保干净
            if self.process and self.process.poll() is None:
                self.kill_process()
                
            return {"status": "stopped"}
        except Exception as e:
            print(f"[Stress Stop Error] {e} - switching to force kill")
            self.kill_process()
            return {"status": "force_killed"}

    def get_stats(self):
        """获取实时数据"""
        try:
            response = requests.get(f"{self.locust_url}/stats/requests", timeout=5)
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
            try:
                self.process.kill() # Windows 上对应 TerminateProcess
                print(f"[Stress] Process {self.process.pid} force killed.")
            except Exception as e:
                print(f"[Stress Kill Error] {e}")
            self.process = None

stress_service = StressService()