import time

class RequestTimer:
    def __init__(self):
        self.start_time = time.time()
        self.checkpoints = {}
    
    def mark(self, name: str):
        """记录一个时间点"""
        self.checkpoints[name] = time.time()
    
    def get_duration(self, start_name: str, end_name: str) -> str:
        """计算两个时间点之间的耗时"""
        start = self.checkpoints.get(start_name, self.start_time)
        end = self.checkpoints.get(end_name, time.time())
        duration = end - start
        
        if duration < 1:
            return f"{duration * 1000:.0f}ms"
        else:
            return f"{duration:.2f}s"

    def generate_log(self):
        """生成最终的日志字符串"""
        # 计算各阶段耗时
        # 假设打点顺序：start -> after_recall -> after_rerank -> after_llm
        t_recall = self.get_duration("start", "after_recall")
        t_rerank = self.get_duration("after_recall", "after_rerank")
        t_llm = self.get_duration("after_rerank", "after_llm")
        t_total = self.get_duration("start", "after_llm")
        
        return (
            f"[Timing] embedding recall: {t_recall} "
            f"[Timing] rerank: {t_rerank} "
            f"[Timing] llm generation: {t_llm} "
            f"[Timing] total: {t_total}"
        )