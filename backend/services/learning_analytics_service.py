from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from backend.models.tables import ExamRecord, QuestionHistory, StudentKeywordMastery, User


DIFFICULTY_ORDER = ["简单", "中等", "困难"]
DIFFICULTY_INDEX = {value: index for index, value in enumerate(DIFFICULTY_ORDER)}
DIFFICULTY_BONUS = {"简单": -5.0, "中等": 0.0, "困难": 8.0}


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def normalize_difficulty(value: Optional[str]) -> str:
    if value in DIFFICULTY_INDEX:
        return value
    return "中等"


def difficulty_step(current: str, target: str) -> str:
    current_idx = DIFFICULTY_INDEX.get(normalize_difficulty(current), 1)
    target_idx = DIFFICULTY_INDEX.get(normalize_difficulty(target), 1)
    if target_idx > current_idx:
        return DIFFICULTY_ORDER[min(current_idx + 1, len(DIFFICULTY_ORDER) - 1)]
    if target_idx < current_idx:
        return DIFFICULTY_ORDER[max(current_idx - 1, 0)]
    return DIFFICULTY_ORDER[current_idx]


def score_to_level(score: float) -> str:
    if score >= 85:
        return "熟练掌握"
    if score >= 70:
        return "基本掌握"
    if score >= 60:
        return "需要练习"
    return "薄弱"


def score_to_band(score: float) -> str:
    if score >= 85:
        return "excellent"
    if score >= 70:
        return "good"
    if score >= 60:
        return "warning"
    return "risk"


def safe_excerpt(text: Optional[str], limit: int = 60) -> str:
    if not text:
        return "暂无题目内容"
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 3] + "..."


@dataclass
class AdaptiveSnapshot:
    current_difficulty: str
    next_difficulty: str
    avg_score_last_3: float
    recent_failures: int
    is_stable: bool
    mastery_score: float
    confidence: float
    focus_keyword: Optional[str]
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_difficulty": self.current_difficulty,
            "next_difficulty": self.next_difficulty,
            "avg_score_last_3": round(self.avg_score_last_3, 1),
            "recent_failures": self.recent_failures,
            "is_stable": self.is_stable,
            "mastery_score": round(self.mastery_score, 1),
            "confidence": round(self.confidence, 2),
            "focus_keyword": self.focus_keyword,
            "reason": self.reason,
        }


class LearningAnalyticsService:
    def get_question_keyword(self, db: Session, question_id: Optional[int]) -> Optional[str]:
        if not question_id:
            return None
        question = db.query(QuestionHistory).filter(QuestionHistory.id == question_id).first()
        return question.keyword if question else None

    def get_mastery_row(
        self, db: Session, student_id: int, keyword: Optional[str]
    ) -> Optional[StudentKeywordMastery]:
        if not keyword:
            return None
        return (
            db.query(StudentKeywordMastery)
            .filter(
                StudentKeywordMastery.student_id == student_id,
                StudentKeywordMastery.keyword == keyword,
            )
            .first()
        )

    def list_mastery_rows(self, db: Session, student_id: int) -> List[StudentKeywordMastery]:
        return (
            db.query(StudentKeywordMastery)
            .filter(StudentKeywordMastery.student_id == student_id)
            .order_by(
                StudentKeywordMastery.mastery_score.asc(),
                StudentKeywordMastery.updated_at.desc(),
            )
            .all()
        )

    def update_mastery_from_record(self, db: Session, record: ExamRecord) -> Optional[StudentKeywordMastery]:
        keyword = self.get_question_keyword(db, record.question_id)
        if not keyword:
            return None

        mastery = self.get_mastery_row(db, record.student_id, keyword)
        if mastery is None:
            mastery = StudentKeywordMastery(
                student_id=record.student_id,
                keyword=keyword,
                mastery_score=60.0,
                confidence=0.2,
                avg_score=0.0,
                attempt_count=0,
                success_count=0,
                wrong_count=0,
                last_score=0.0,
                streak=0,
                last_difficulty=normalize_difficulty(record.difficulty),
            )
            db.add(mastery)
            db.flush()

        attempts_before = mastery.attempt_count or 0
        prev_mastery = float(mastery.mastery_score or 60.0)
        score = float(record.ai_score or 0.0)
        adjusted_score = clamp(score + DIFFICULTY_BONUS.get(normalize_difficulty(record.difficulty), 0.0), 0.0, 100.0)
        learning_rate = 0.38 if attempts_before < 3 else 0.26 if attempts_before < 8 else 0.18
        new_mastery = clamp(prev_mastery * (1 - learning_rate) + adjusted_score * learning_rate, 0.0, 100.0)
        new_avg = ((float(mastery.avg_score or 0.0) * attempts_before) + score) / (attempts_before + 1)
        is_success = score >= 60

        mastery.attempt_count = attempts_before + 1
        mastery.avg_score = round(new_avg, 2)
        mastery.mastery_score = round(new_mastery, 2)
        mastery.confidence = round(min(1.0, 0.2 + mastery.attempt_count * 0.12), 2)
        mastery.last_score = round(score, 2)
        mastery.last_difficulty = normalize_difficulty(record.difficulty)
        mastery.success_count = int(mastery.success_count or 0) + (1 if is_success else 0)
        mastery.wrong_count = int(mastery.wrong_count or 0) + (0 if is_success else 1)
        mastery.streak = (int(mastery.streak or 0) + 1) if score >= 85 else 0 if not is_success else int(mastery.streak or 0)
        db.commit()
        db.refresh(mastery)
        return mastery

    def _recent_records(self, db: Session, student_id: int, limit: int = 10) -> List[ExamRecord]:
        return (
            db.query(ExamRecord)
            .filter(ExamRecord.student_id == student_id)
            .order_by(ExamRecord.created_at.desc())
            .limit(limit)
            .all()
        )

    def build_adaptive_snapshot(
        self, db: Session, student_id: int, keyword: Optional[str] = None
    ) -> AdaptiveSnapshot:
        recent_records = self._recent_records(db, student_id, limit=5)
        mastery_rows = self.list_mastery_rows(db, student_id)
        focus_keyword = keyword
        keyword_row = self.get_mastery_row(db, student_id, keyword) if keyword else None

        if keyword_row is None and mastery_rows:
            keyword_row = mastery_rows[0]
            if not focus_keyword:
                focus_keyword = keyword_row.keyword

        recent_scores = [float(record.ai_score or 0.0) for record in recent_records[:3]]
        avg_score_last_3 = mean(recent_scores) if recent_scores else 0.0
        current_difficulty = normalize_difficulty(recent_records[0].difficulty) if recent_records else "中等"
        last_3_difficulties = [normalize_difficulty(record.difficulty) for record in recent_records[:3]]
        is_stable = len(last_3_difficulties) >= 3 and len(set(last_3_difficulties)) == 1
        recent_failures = sum(1 for value in recent_scores if value < 60)
        mastery_score = float(keyword_row.mastery_score) if keyword_row else (
            mean([float(row.mastery_score or 0.0) for row in mastery_rows]) if mastery_rows else 60.0
        )
        confidence = float(keyword_row.confidence or 0.0) if keyword_row else (
            mean([float(row.confidence or 0.0) for row in mastery_rows]) if mastery_rows else 0.0
        )

        composite = 0.55 * mastery_score + 0.35 * avg_score_last_3 + 0.10 * (confidence * 100.0)
        if not recent_records and mastery_score >= 82:
            target_difficulty = "困难"
        elif recent_failures >= 2:
            target_difficulty = "简单"
        elif composite >= 84 and (is_stable or confidence >= 0.45):
            target_difficulty = "困难"
        elif composite >= 62:
            target_difficulty = "中等"
        else:
            target_difficulty = "简单"

        next_difficulty = difficulty_step(current_difficulty, target_difficulty)
        if len(recent_records) < 3 and keyword_row is None:
            next_difficulty = "中等"

        reason_parts = [
            f"近3题均分 {avg_score_last_3:.1f}",
            f"掌握度 {mastery_score:.1f}",
            f"置信度 {confidence:.2f}",
        ]
        if focus_keyword:
            reason_parts.append(f"聚焦知识点 {focus_keyword}")
        if recent_failures:
            reason_parts.append(f"近3题失分 {recent_failures} 次")
        reason_parts.append("难度稳定" if is_stable else "难度仍在调整")

        return AdaptiveSnapshot(
            current_difficulty=current_difficulty,
            next_difficulty=next_difficulty,
            avg_score_last_3=avg_score_last_3,
            recent_failures=recent_failures,
            is_stable=is_stable,
            mastery_score=mastery_score,
            confidence=confidence,
            focus_keyword=focus_keyword,
            reason=" | ".join(reason_parts),
        )

    def calculate_next_difficulty(self, db: Session, student_id: int, keyword: Optional[str] = None) -> str:
        return self.build_adaptive_snapshot(db, student_id, keyword).next_difficulty

    def mastery_payload(self, row: StudentKeywordMastery) -> Dict[str, Any]:
        attempts = int(row.attempt_count or 0)
        pass_rate = round((float(row.success_count or 0) / attempts) * 100, 1) if attempts else 0.0
        return {
            "keyword": row.keyword,
            "mastery_score": round(float(row.mastery_score or 0.0), 1),
            "confidence": round(float(row.confidence or 0.0), 2),
            "avg_score": round(float(row.avg_score or 0.0), 1),
            "attempt_count": attempts,
            "success_count": int(row.success_count or 0),
            "wrong_count": int(row.wrong_count or 0),
            "pass_rate": pass_rate,
            "level": score_to_level(float(row.mastery_score or 0.0)),
            "band": score_to_band(float(row.mastery_score or 0.0)),
            "last_difficulty": normalize_difficulty(row.last_difficulty),
            "updated_at": row.updated_at.strftime("%Y-%m-%d %H:%M") if row.updated_at else "",
        }

    def _records_with_keyword(self, db: Session, student_id: int) -> List[Tuple[ExamRecord, Optional[QuestionHistory]]]:
        return (
            db.query(ExamRecord, QuestionHistory)
            .outerjoin(QuestionHistory, ExamRecord.question_id == QuestionHistory.id)
            .filter(ExamRecord.student_id == student_id)
            .order_by(ExamRecord.created_at.desc())
            .all()
        )

    def _build_recent_trend(
        self, records_with_keyword: List[Tuple[ExamRecord, Optional[QuestionHistory]]], limit: int = 10
    ) -> List[Dict[str, Any]]:
        trend = []
        for record, question in reversed(records_with_keyword[:limit]):
            trend.append(
                {
                    "time": record.created_at.strftime("%m-%d %H:%M"),
                    "score": round(float(record.ai_score or 0.0), 1),
                    "difficulty": normalize_difficulty(record.difficulty),
                    "keyword": question.keyword if question else "未标注",
                }
            )
        return trend

    def _build_wrong_questions(
        self, records_with_keyword: List[Tuple[ExamRecord, Optional[QuestionHistory]]], limit: int = 6
    ) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for record, question in records_with_keyword:
            if float(record.ai_score or 0.0) >= 60:
                continue
            keyword = question.keyword if question else "未标注"
            items.append(
                {
                    "record_id": record.id,
                    "question_id": record.question_id,
                    "time": record.created_at.strftime("%Y-%m-%d %H:%M"),
                    "keyword": keyword,
                    "difficulty": normalize_difficulty(record.difficulty),
                    "score": round(float(record.ai_score or 0.0), 1),
                    "question_excerpt": safe_excerpt(record.question_content, 72),
                    "comment": safe_excerpt(record.ai_comment, 96),
                    "retry_reason": f"{keyword} 近次表现偏弱，建议先做 {normalize_difficulty(record.difficulty)} 或相邻难度复练。",
                }
            )
            if len(items) >= limit:
                break
        return items

    def _build_recommended_practice(
        self,
        db: Session,
        student_id: int,
        mastery_rows: List[StudentKeywordMastery],
        wrong_questions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        recommendations: List[Dict[str, Any]] = []
        weak_rows = sorted(
            mastery_rows,
            key=lambda row: (float(row.mastery_score or 0.0), -int(row.wrong_count or 0), -int(row.attempt_count or 0)),
        )
        used_keywords = set()
        for row in weak_rows[:3]:
            snapshot = self.build_adaptive_snapshot(db, student_id, row.keyword)
            recommendations.append(
                {
                    "keyword": row.keyword,
                    "mastery_score": round(float(row.mastery_score or 0.0), 1),
                    "target_difficulty": snapshot.next_difficulty,
                    "reason": f"{row.keyword} 掌握度 {float(row.mastery_score or 0.0):.1f}，错题 {int(row.wrong_count or 0)} 次。",
                    "action": "错题复练" if int(row.wrong_count or 0) else "巩固训练",
                }
            )
            used_keywords.add(row.keyword)

        for item in wrong_questions:
            if item["keyword"] in used_keywords:
                continue
            recommendations.append(
                {
                    "keyword": item["keyword"],
                    "mastery_score": item["score"],
                    "target_difficulty": difficulty_step(item["difficulty"], "简单"),
                    "reason": f"最近一次该知识点得分 {item['score']:.1f}，建议先回到基础题稳定正确率。",
                    "action": "纠错强化",
                }
            )
            used_keywords.add(item["keyword"])
            if len(recommendations) >= 4:
                break

        return recommendations[:4]

    def _build_learning_path(
        self, adaptive_state: AdaptiveSnapshot, recommended_practice: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        focus_items = recommended_practice[:3]
        return {
            "today_focus": focus_items,
            "headline": "今日练习建议",
            "summary": (
                f"建议优先练习 {focus_items[0]['keyword']}" if focus_items else "继续保持当前节奏，系统会根据新成绩动态调整。"
            ),
            "expected_difficulty": adaptive_state.next_difficulty,
            "reason": adaptive_state.reason,
        }

    def _build_student_overview(
        self,
        username: str,
        records_with_keyword: List[Tuple[ExamRecord, Optional[QuestionHistory]]],
        mastery_rows: List[StudentKeywordMastery],
    ) -> Dict[str, Any]:
        scores = [float(record.ai_score or 0.0) for record, _ in records_with_keyword]
        avg_score = round(mean(scores), 1) if scores else 0.0
        pass_rate = round((sum(1 for score in scores if score >= 60) / len(scores)) * 100, 1) if scores else 0.0
        strongest = max(mastery_rows, key=lambda row: float(row.mastery_score or 0.0), default=None)
        weakest = min(mastery_rows, key=lambda row: float(row.mastery_score or 0.0), default=None)
        last_active = records_with_keyword[0][0].created_at.strftime("%Y-%m-%d %H:%M") if records_with_keyword else "暂无记录"

        return {
            "username": username,
            "total_attempts": len(scores),
            "avg_score": avg_score,
            "pass_rate": pass_rate,
            "last_active": last_active,
            "strongest_keyword": strongest.keyword if strongest else None,
            "weakest_keyword": weakest.keyword if weakest else None,
        }

    def build_student_dashboard(
        self, db: Session, student_id: int, keyword: Optional[str] = None
    ) -> Dict[str, Any]:
        user = db.query(User).filter(User.id == student_id).first()
        records_with_keyword = self._records_with_keyword(db, student_id)
        mastery_rows = self.list_mastery_rows(db, student_id)
        adaptive_state = self.build_adaptive_snapshot(db, student_id, keyword)
        wrong_questions = self._build_wrong_questions(records_with_keyword)
        recommended_practice = self._build_recommended_practice(db, student_id, mastery_rows, wrong_questions)
        learning_path = self._build_learning_path(adaptive_state, recommended_practice)

        keyword_stats = {
            row.keyword: {
                "count": int(row.attempt_count or 0),
                "avg_score": round(float(row.avg_score or 0.0), 1),
                "mastery_score": round(float(row.mastery_score or 0.0), 1),
                "level": score_to_level(float(row.mastery_score or 0.0)),
                "confidence": round(float(row.confidence or 0.0), 2),
                "wrong_count": int(row.wrong_count or 0),
            }
            for row in mastery_rows
        }

        return {
            "student_overview": self._build_student_overview(
                user.username if user else f"student-{student_id}",
                records_with_keyword,
                mastery_rows,
            ),
            "recent_trend": self._build_recent_trend(records_with_keyword),
            "keyword_stats": keyword_stats,
            "mastery_by_keyword": [self.mastery_payload(row) for row in mastery_rows],
            "wrong_questions": wrong_questions,
            "recommended_practice": recommended_practice,
            "learning_path": learning_path,
            "adaptive_state": adaptive_state.to_dict(),
        }

    def build_teacher_student_profile(self, db: Session, student_id: int) -> Dict[str, Any]:
        dashboard = self.build_student_dashboard(db, student_id)
        overview = dashboard["student_overview"]
        adaptive_state = dashboard["adaptive_state"]
        recommendations = dashboard["recommended_practice"]
        wrong_questions = dashboard["wrong_questions"]

        intervention_suggestions: List[str] = []
        if overview["weakest_keyword"]:
            intervention_suggestions.append(
                f"优先关注 {overview['weakest_keyword']}，建议先用 {adaptive_state['next_difficulty']} 难度做 2-3 题纠错。"
            )
        if wrong_questions:
            intervention_suggestions.append(
                f"最近有 {len(wrong_questions)} 道低分题，先讲评最近一次错误，再安排针对性复练。"
            )
        if overview["pass_rate"] < 60:
            intervention_suggestions.append("整体通过率偏低，建议教师先补基础概念，再恢复自适应练习。")
        elif overview["pass_rate"] >= 80:
            intervention_suggestions.append("整体基础稳定，可以逐步增加困难题占比，拉升上限。")
        if not intervention_suggestions:
            intervention_suggestions.append("当前状态平稳，可继续按系统推荐路径练习。")

        return {
            "student_overview": overview,
            "student_trend": dashboard["recent_trend"],
            "student_keyword_mastery": dashboard["mastery_by_keyword"],
            "wrong_questions": wrong_questions,
            "recommended_practice": recommendations,
            "adaptive_state": adaptive_state,
            "intervention_suggestions": intervention_suggestions,
        }

    def build_class_insights(self, db: Session) -> Dict[str, Any]:
        students = db.query(User).filter(User.role == "student").order_by(User.username.asc()).all()
        recent_records = db.query(ExamRecord).order_by(ExamRecord.created_at.desc()).limit(200).all()
        mastery_rows = db.query(StudentKeywordMastery).all()

        recent_scores = [float(record.ai_score or 0.0) for record in recent_records]
        low_score_ratio = round((sum(1 for score in recent_scores if score < 60) / len(recent_scores)) * 100, 1) if recent_scores else 0.0
        score_distribution = {
            "excellent": sum(1 for score in recent_scores if score >= 85),
            "good": sum(1 for score in recent_scores if 70 <= score < 85),
            "warning": sum(1 for score in recent_scores if 60 <= score < 70),
            "risk": sum(1 for score in recent_scores if score < 60),
        }
        difficulty_distribution = Counter(normalize_difficulty(record.difficulty) for record in recent_records)

        keyword_scores: Dict[str, List[float]] = defaultdict(list)
        keyword_wrong_counts: Dict[str, List[int]] = defaultdict(list)
        for row in mastery_rows:
            keyword_scores[row.keyword].append(float(row.mastery_score or 0.0))
            keyword_wrong_counts[row.keyword].append(int(row.wrong_count or 0))

        weak_keywords: List[Dict[str, Any]] = []
        for keyword, scores in keyword_scores.items():
            avg_mastery = mean(scores)
            wrong_counts = keyword_wrong_counts[keyword]
            weak_keywords.append(
                {
                    "keyword": keyword,
                    "student_count": len(scores),
                    "avg_mastery": round(avg_mastery, 1),
                    "weak_students": sum(1 for value in scores if value < 70),
                    "avg_wrong_count": round(mean(wrong_counts), 1) if wrong_counts else 0.0,
                    "heat": round(clamp((100 - avg_mastery) / 100, 0.0, 1.0), 2),
                }
            )
        weak_keywords.sort(key=lambda item: (-item["weak_students"], item["avg_mastery"], -item["student_count"]))

        student_snapshots: List[Dict[str, Any]] = []
        for student in students:
            profile = self.build_teacher_student_profile(db, student.id)
            overview = profile["student_overview"]
            student_snapshots.append(
                {
                    "student_id": student.id,
                    "username": student.username,
                    "avg_score": overview["avg_score"],
                    "pass_rate": overview["pass_rate"],
                    "weakest_keyword": overview["weakest_keyword"],
                    "last_active": overview["last_active"],
                }
            )

        return {
            "class_overview": {
                "student_count": len(students),
                "recent_record_count": len(recent_records),
                "avg_score": round(mean(recent_scores), 1) if recent_scores else 0.0,
                "low_score_ratio": low_score_ratio,
            },
            "weak_keywords": weak_keywords[:8],
            "difficulty_distribution": {
                "简单": difficulty_distribution.get("简单", 0),
                "中等": difficulty_distribution.get("中等", 0),
                "困难": difficulty_distribution.get("困难", 0),
            },
            "score_distribution": score_distribution,
            "student_snapshots": student_snapshots,
        }


learning_analytics_service = LearningAnalyticsService()
