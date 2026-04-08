from backend.services.learning_analytics_service import learning_analytics_service


def test_student_dashboard_contains_mastery_and_recommendations(session_factory, seeded_data):
    db = session_factory()
    try:
        dashboard = learning_analytics_service.build_student_dashboard(db, seeded_data["student_id"])
        assert dashboard["student_overview"]["total_attempts"] == 3
        assert dashboard["mastery_by_keyword"]
        assert dashboard["wrong_questions"]
        assert dashboard["recommended_practice"]
        assert dashboard["adaptive_state"]["next_difficulty"] in {"简单", "中等", "困难"}
    finally:
        db.close()


def test_teacher_profile_and_class_insights(session_factory, seeded_data):
    db = session_factory()
    try:
        profile = learning_analytics_service.build_teacher_student_profile(db, seeded_data["student_id"])
        insights = learning_analytics_service.build_class_insights(db)

        assert profile["student_overview"]["username"] == "student_demo"
        assert profile["student_keyword_mastery"]
        assert profile["intervention_suggestions"]
        assert insights["class_overview"]["student_count"] == 1
        assert isinstance(insights["weak_keywords"], list)
    finally:
        db.close()
