import os

from locust import HttpUser, between, task
from locust.exception import StopUser


class StudentUser(HttpUser):
    wait_time = between(1, 4)

    def on_start(self):
        self.auth_headers = {}
        username = os.getenv("LOCUST_USERNAME", "student1")
        password = os.getenv("LOCUST_PASSWORD", "123456")
        role = os.getenv("LOCUST_ROLE", "student")
        with self.client.post(
            "/login",
            json={"username": username, "password": password, "role": role},
            name="/login",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"login failed: {response.status_code}")
                raise StopUser()

            payload = response.json()
            token = payload.get("access_token")
            if not token:
                response.failure("missing access_token")
                raise StopUser()

            self.auth_headers = {"Authorization": f"Bearer {token}"}

    def _wait_task(self, task_id: int, max_polls: int = 6) -> None:
        for _ in range(max_polls):
            with self.client.get(
                f"/student/tasks/{task_id}",
                headers=self.auth_headers,
                name="/student/tasks/[id]",
                catch_response=True,
            ) as response:
                if response.status_code != 200:
                    response.failure(f"task status failed: {response.status_code}")
                    return
                payload = response.json()
                task_data = payload.get("data", {})
                if task_data.get("status") in {"success", "failed", "cancelled", "timeout"}:
                    return

    @task(3)
    def generate_question(self):
        payload = {
            "keyword": "Python 递归",
            "mode": "adaptive",
            "question_type": "choice",
            "triggered_by": "load_test",
        }
        with self.client.post(
            "/student/generate_question_task",
            json=payload,
            headers=self.auth_headers,
            name="/student/generate_question_task",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"submit failed: {response.status_code}")
                return
            task_id = response.json().get("task_id")
            if not task_id:
                response.failure("missing task_id")
                return
            self._wait_task(task_id)

    @task(2)
    def load_dashboard(self):
        self.client.get("/student/learning_dashboard", headers=self.auth_headers, name="/student/learning_dashboard")

    @task(1)
    def view_history(self):
        self.client.get("/student/history", headers=self.auth_headers, name="/student/history")
