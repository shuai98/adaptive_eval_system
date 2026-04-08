import backend.services.async_task_service as task_module
from backend.models.tables import AsyncTaskLog


def test_learning_dashboard_endpoint(client, auth_headers):
    response = client.get("/student/learning_dashboard", headers=auth_headers["student"])
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert "mastery_by_keyword" in payload["data"]
    assert "wrong_questions" in payload["data"]
    assert "recommended_practice" in payload["data"]


def test_teacher_profile_endpoint(client, seeded_data, auth_headers):
    response = client.get(
        f"/teacher/student_profile/{seeded_data['student_id']}",
        headers=auth_headers["teacher"],
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["data"]["student_overview"]["username"] == "student_demo"
    assert payload["data"]["student_keyword_mastery"]


def test_class_insights_endpoint(client, auth_headers):
    response = client.get("/teacher/class_insights", headers=auth_headers["teacher"])
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert "class_overview" in payload["data"]
    assert "weak_keywords" in payload["data"]


def test_teacher_task_list_endpoint(client, session_factory, auth_headers, monkeypatch):
    monkeypatch.setattr(task_module, "SessionLocal", session_factory)

    db = session_factory()
    try:
        db.add_all(
            [
                AsyncTaskLog(
                    task_type="generate_question",
                    task_scope="student",
                    owner_id=2,
                    status="retrying",
                    detail="waiting to retry",
                    payload_json='{"keyword":"Python 递归","question_type":"choice"}',
                ),
                AsyncTaskLog(
                    task_type="reindex_kb",
                    task_scope="teacher",
                    owner_id=1,
                    status="success",
                    detail="done",
                    payload_json='{"triggered_by":1}',
                ),
            ]
        )
        db.commit()
    finally:
        db.close()

    response = client.get(
        "/teacher/tasks?task_type=generate_question&limit=10",
        headers=auth_headers["teacher"],
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["meta"]["count"] == 1
    assert payload["meta"]["filters"]["task_type"] == "generate_question"
    assert payload["data"][0]["task_type"] == "generate_question"
    assert payload["data"][0]["payload_summary"]["keyword"] == "Python 递归"
    assert payload["data"][0]["payload"] is None


def test_student_cannot_use_teacher_route(client, seeded_data, auth_headers):
    response = client.get(
        f"/teacher/student_profile/{seeded_data['student_id']}",
        headers=auth_headers["student"],
    )
    assert response.status_code == 403

    task_list_response = client.get("/teacher/tasks", headers=auth_headers["student"])
    assert task_list_response.status_code == 403
