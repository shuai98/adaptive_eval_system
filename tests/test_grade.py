from backend.models.tables import StudentKeywordMastery


def test_choice_grading_updates_mastery(client, session_factory, seeded_data, auth_headers):
    response = client.post(
        "/student/grade_answer",
        headers=auth_headers["student"],
        json={
            "question": "递归基础题",
            "standard_answer": "A",
            "student_answer": "A",
            "difficulty": "简单",
            "question_type": "choice",
            "question_id": seeded_data["question_id"],
            "direct_score": 100,
            "analysis": "递归需要明确终止条件。",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["data"]["score"] == 100
    assert payload["data"]["mastery_update"] is not None

    db = session_factory()
    try:
        mastery = (
            db.query(StudentKeywordMastery)
            .filter(
                StudentKeywordMastery.student_id == seeded_data["student_id"],
                StudentKeywordMastery.keyword == "递归",
            )
            .first()
        )
        assert mastery is not None
        assert mastery.attempt_count >= 2
    finally:
        db.close()
