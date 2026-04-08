from pydantic import BaseModel


class TestRequest(BaseModel):
    keyword: str


class StressConfig(BaseModel):
    user_count: int
    spawn_rate: int
