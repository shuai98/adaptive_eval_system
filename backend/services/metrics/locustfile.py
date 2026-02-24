from locust import HttpUser, task, between

class StudentUser(HttpUser):
    wait_time = between(1, 5) # 每个用户间隔 1-5秒 操作一次

    @task(3) # 权重3，更频繁
    def generate_question(self):
        # 模拟生成题目请求
        payload = {
            "keyword": "Python List",
            "student_id": 1,
            "mode": "adaptive",
            "question_type": "choice"
        }
        self.client.post("/student/generate_question", json=payload)

    @task(1) # 权重1，偶尔看历史
    def view_history(self):
        self.client.get("/student/history?student_id=1")
