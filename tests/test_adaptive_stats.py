"""
测试自适应统计接口
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.db.session import SessionLocal
from backend.api.student import AdaptiveEngine
from backend.models.tables import ExamRecord, QuestionHistory, User

def test_adaptive_stats():
    """测试自适应统计数据获取"""
    db = SessionLocal()
    
    try:
        # 1. 查找一个有答题记录的学生
        student = db.query(User).filter(User.role == 'student').first()
        
        if not student:
            print("❌ 没有找到学生用户")
            return
        
        print(f"✅ 找到学生: {student.username} (ID: {student.id})")
        
        # 2. 查看该学生的答题记录
        records = db.query(ExamRecord).filter(
            ExamRecord.student_id == student.id
        ).order_by(ExamRecord.created_at.desc()).limit(10).all()
        
        print(f"\n📊 最近 {len(records)} 条答题记录:")
        for i, r in enumerate(records, 1):
            print(f"  {i}. 分数: {r.ai_score}, 难度: {r.difficulty}, 时间: {r.created_at}")
        
        # 3. 测试自适应算法
        if len(records) >= 3:
            next_diff = AdaptiveEngine.calculate_next_difficulty(db, student.id)
            print(f"\n🎯 自适应算法建议下一题难度: {next_diff}")
            
            # 计算最近3题平均分
            last_3_scores = [r.ai_score for r in records[:3]]
            avg_score = sum(last_3_scores) / len(last_3_scores)
            print(f"   最近3题平均分: {avg_score:.1f}")
            
            # 稳定性检查
            last_3_diffs = [r.difficulty for r in records[:3]]
            is_stable = len(set(last_3_diffs)) == 1
            print(f"   难度稳定性: {'稳定' if is_stable else '不稳定'}")
        
        # 4. 查看知识点统计
        print("\n📚 知识点统计:")
        keyword_stats = {}
        
        all_records = db.query(ExamRecord, QuestionHistory).join(
            QuestionHistory, ExamRecord.question_id == QuestionHistory.id
        ).filter(
            ExamRecord.student_id == student.id
        ).all()
        
        for record, question in all_records:
            kw = question.keyword
            if kw not in keyword_stats:
                keyword_stats[kw] = {"count": 0, "total": 0}
            keyword_stats[kw]["count"] += 1
            keyword_stats[kw]["total"] += record.ai_score
        
        for kw, stat in keyword_stats.items():
            avg = stat["total"] / stat["count"]
            level = "熟练掌握" if avg >= 85 else "基本掌握" if avg >= 70 else "需要练习" if avg >= 60 else "未掌握"
            print(f"   {kw}: 平均分 {avg:.1f} ({stat['count']}题) - {level}")
        
        print("\n✅ 测试完成！")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_adaptive_stats()

