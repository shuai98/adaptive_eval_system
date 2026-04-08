import os
import subprocess
import sys
import time

import requests

from backend.core.security import verify_password
from backend.db.session import SessionLocal
from backend.models.tables import User


class StressService:
    def __init__(self):
        self.process = None
        self.log_file = None
        self.locust_url = "http://127.0.0.1:8089"
        self.target_host = os.getenv("LOCUST_TARGET_HOST", "http://127.0.0.1:8088").rstrip("/")
        self.stats_timeout = 1.5
        self.stats_cache_ttl = 2.0
        self.stats_cache = None
        self.stats_cache_at = 0.0
        self.active_credentials = None
        self.started_at = 0.0

    @staticmethod
    def _number(*values, default=0.0):
        for value in values:
            if value is None:
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
        return float(default)

    def _idle_stats(self):
        return {
            "state": "idle",
            "current_rps": 0.0,
            "avg_rps": 0.0,
            "total_rps": 0.0,
            "fail_ratio": 0.0,
            "current_p50_latency_ms": 0.0,
            "current_p95_latency_ms": 0.0,
            "current_response_time_percentile_95": 0.0,
            "median_response_time": 0.0,
            "avg_latency_ms": 0.0,
            "request_count": 0,
            "user_count": 0,
            "auth_user": self.active_credentials["username"] if self.active_credentials else "",
            "auth_role": self.active_credentials["role"] if self.active_credentials else "",
            "auth_source": self.active_credentials["source"] if self.active_credentials else "",
        }

    def _reset_stats_cache(self):
        self.stats_cache = None
        self.stats_cache_at = 0.0

    def _resolve_locust_executable(self):
        env_root = os.path.dirname(sys.executable)
        candidate = os.path.join(env_root, "Scripts", "locust.exe")
        return candidate if os.path.exists(candidate) else "locust"

    def _configured_credentials(self):
        return {
            "username": os.getenv("LOCUST_USERNAME", "student1").strip(),
            "password": os.getenv("LOCUST_PASSWORD", "123456").strip(),
            "role": os.getenv("LOCUST_ROLE", "student").strip() or "student",
            "source": "env",
        }

    def _candidate_passwords(self, username: str, configured_password: str):
        raw_candidates = [
            configured_password,
            "123456",
            "student12345",
            username,
            f"{username}123",
            f"{username}12345",
        ]
        candidates = []
        for item in raw_candidates:
            value = (item or "").strip()
            if value and value not in candidates:
                candidates.append(value)
        return candidates

    def _find_local_student_credentials(self, preferred_username: str = ""):
        db = SessionLocal()
        try:
            students = (
                db.query(User)
                .filter(User.role == "student")
                .order_by(User.username.asc())
                .all()
            )
        finally:
            db.close()

        if preferred_username:
            students.sort(key=lambda item: (item.username != preferred_username, item.username))

        for student in students:
            for password in self._candidate_passwords(
                student.username,
                os.getenv("LOCUST_PASSWORD", ""),
            ):
                if verify_password(password, student.password_hash):
                    return {
                        "username": student.username,
                        "password": password,
                        "role": student.role,
                        "source": "database_auto",
                    }
        return None

    def _login_target(self, credentials):
        response = requests.post(
            f"{self.target_host}/login",
            json={
                "username": credentials["username"],
                "password": credentials["password"],
                "role": credentials["role"],
            },
            timeout=5,
        )
        try:
            payload = response.json()
        except Exception:
            payload = {}

        if response.status_code != 200:
            detail = payload.get("detail") or response.text.strip() or f"HTTP {response.status_code}"
            return {
                "ok": False,
                "message": detail,
            }

        token = payload.get("access_token")
        if not token:
            return {
                "ok": False,
                "message": "登录成功，但响应中缺少 access_token。",
            }

        return {
            "ok": True,
            "token": token,
        }

    def validate_target_login(self):
        configured = self._configured_credentials()
        try:
            configured_result = self._login_target(configured)
            if configured_result["ok"]:
                self.active_credentials = configured
                return {
                    "ok": True,
                    "context": {
                        "username": configured["username"],
                        "role": configured["role"],
                        "source": configured["source"],
                    },
                }

            fallback = self._find_local_student_credentials(preferred_username=configured["username"])
            if fallback:
                fallback_result = self._login_target(fallback)
                if fallback_result["ok"]:
                    self.active_credentials = fallback
                    return {
                        "ok": True,
                        "context": {
                            "username": fallback["username"],
                            "role": fallback["role"],
                            "source": fallback["source"],
                        },
                    }

            return {
                "ok": False,
                "message": (
                    "压测账号登录失败。请检查 LOCUST_USERNAME / LOCUST_PASSWORD / LOCUST_ROLE，"
                    f"或确认数据库里存在可用的学生账号。当前返回：{configured_result['message']}"
                ),
            }
        except Exception as error:
            return {
                "ok": False,
                "message": f"压测前置登录校验失败：{error}",
            }

    def start_locust_process(self):
        if self.process and self.process.poll() is None:
            return

        base_dir = os.path.dirname(os.path.abspath(__file__))
        locust_file = os.path.join(base_dir, "locustfile.py")
        locust_exe = self._resolve_locust_executable()
        cmd = [locust_exe, "-f", locust_file, "--web-host", "127.0.0.1", "--web-port", "8089"]

        if self.log_file and not self.log_file.closed:
            self.log_file.close()

        env = os.environ.copy()
        if self.active_credentials:
            env["LOCUST_USERNAME"] = self.active_credentials["username"]
            env["LOCUST_PASSWORD"] = self.active_credentials["password"]
            env["LOCUST_ROLE"] = self.active_credentials["role"]

        self.log_file = open(os.path.join(base_dir, "locust_debug.log"), "w", encoding="utf-8")
        self.process = subprocess.Popen(
            cmd,
            cwd=base_dir,
            stdout=self.log_file,
            stderr=subprocess.STDOUT,
            env=env,
        )
        self.wait_for_locust_ready()

    def wait_for_locust_ready(self, timeout=30):
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                requests.get(f"{self.locust_url}/", timeout=1)
                requests.get(f"{self.locust_url}/stats/requests", timeout=1)
                return True
            except requests.exceptions.ConnectionError:
                time.sleep(1)
            except Exception:
                time.sleep(1)
        return False

    def start_test(self, user_count: int, spawn_rate: int):
        validation = self.validate_target_login()
        if not validation["ok"]:
            return {"success": False, "message": validation["message"]}

        if self.process and self.process.poll() is None and self.active_credentials:
            self.kill_process()

        if not self.process or self.process.poll() is not None:
            self.start_locust_process()

        try:
            response = requests.post(
                f"{self.locust_url}/swarm",
                data={
                    "user_count": user_count,
                    "spawn_rate": spawn_rate,
                    "host": self.target_host,
                },
                timeout=5,
            )
            data = response.json()
            if response.status_code >= 400:
                return {
                    "success": False,
                    "message": data.get("message") or f"Locust returned HTTP {response.status_code}",
                }
            self.started_at = time.time()
            self._reset_stats_cache()
            return {
                "success": True,
                "data": {
                    **data,
                    "auth_user": self.active_credentials["username"] if self.active_credentials else "",
                    "auth_role": self.active_credentials["role"] if self.active_credentials else "",
                    "auth_source": self.active_credentials["source"] if self.active_credentials else "",
                },
            }
        except Exception as error:
            return {"success": False, "message": str(error)}

    def stop_test(self):
        try:
            requests.get(f"{self.locust_url}/stop", timeout=2)
            time.sleep(1)
            if self.process and self.process.poll() is None:
                self.kill_process()
            self.started_at = 0.0
            self.stats_cache = self._idle_stats()
            self.stats_cache_at = time.time()
            return {"status": "stopped"}
        except Exception:
            self.kill_process()
            self.started_at = 0.0
            self.stats_cache = self._idle_stats()
            self.stats_cache_at = time.time()
            return {"status": "force_killed"}

    def get_stats(self):
        now = time.time()
        if self.stats_cache and (now - self.stats_cache_at) < self.stats_cache_ttl:
            return self.stats_cache

        if not self.process or self.process.poll() is not None:
            return self._idle_stats()

        try:
            response = requests.get(f"{self.locust_url}/stats/requests", timeout=self.stats_timeout)
            response.raise_for_status()
            data = response.json()

            aggregated = next(
                (item for item in data.get("stats", []) if item.get("name") == "Aggregated"),
                {},
            )
            current_percentiles = data.get("current_response_time_percentiles") or {}

            current_rps = self._number(
                aggregated.get("current_rps"),
                data.get("total_rps"),
            )
            request_count = int(self._number(aggregated.get("num_requests")))
            elapsed = max(0.0, now - self.started_at) if self.started_at else 0.0
            avg_rps = (request_count / elapsed) if elapsed > 0 else 0.0
            current_p50 = self._number(
                current_percentiles.get("response_time_percentile_0.5"),
                aggregated.get("median_response_time"),
            )
            current_p95 = self._number(
                current_percentiles.get("response_time_percentile_0.95"),
                aggregated.get("response_time_percentile_0.95"),
                data.get("current_response_time_percentile_95"),
            )
            avg_latency = self._number(aggregated.get("avg_response_time"))

            stats = {
                "state": data.get("state") or "idle",
                "current_rps": current_rps,
                "avg_rps": avg_rps,
                "total_rps": current_rps,
                "fail_ratio": self._number(data.get("fail_ratio")),
                "current_p50_latency_ms": current_p50,
                "current_p95_latency_ms": current_p95,
                "current_response_time_percentile_95": current_p95,
                "median_response_time": current_p50,
                "avg_latency_ms": avg_latency,
                "request_count": request_count,
                "user_count": int(self._number(data.get("user_count"))),
                "auth_user": self.active_credentials["username"] if self.active_credentials else "",
                "auth_role": self.active_credentials["role"] if self.active_credentials else "",
                "auth_source": self.active_credentials["source"] if self.active_credentials else "",
            }
            self.stats_cache = stats
            self.stats_cache_at = now
            return stats
        except Exception:
            return self._idle_stats()

    def kill_process(self):
        if self.process:
            try:
                self.process.kill()
            except Exception:
                pass
            self.process = None
        self.started_at = 0.0
        if self.log_file and not self.log_file.closed:
            self.log_file.close()


stress_service = StressService()
