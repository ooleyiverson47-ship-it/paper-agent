# paper_tracker.py
import json
import os
from datetime import datetime
from typing import List, Dict, Any, Set
import hashlib


class PaperTracker:
    """论文追踪器 - 记录已发送的论文"""

    def __init__(self, history_file="sent_papers.json"):
        self.history_file = history_file
        self.sent_papers = self.load_history()

    def load_history(self) -> Set[str]:
        """加载已发送论文历史"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 返回论文ID的集合
                    return set(data.get("sent_papers", []))
            except:
                return set()
        return set()

    def save_history(self):
        """保存论文历史"""
        data = {
            "last_updated": datetime.now().isoformat(),
            "total_count": len(self.sent_papers),
            "sent_papers": list(self.sent_papers)
        }
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_paper_id(self, paper: Dict[str, Any]) -> str:
        """生成论文唯一ID"""
        # 使用标题+作者+发表时间生成唯一ID
        title = paper.get('title', '')
        authors = ','.join(paper.get('authors', [])[:3])
        published = paper.get('published', '')
        # 使用MD5生成固定长度的ID
        unique_str = f"{title}|{authors}|{published}"
        return hashlib.md5(unique_str.encode()).hexdigest()

    def is_new_paper(self, paper: Dict[str, Any]) -> bool:
        """检查论文是否未发送过"""
        paper_id = self.get_paper_id(paper)
        return paper_id not in self.sent_papers

    def mark_as_sent(self, paper: Dict[str, Any]):
        """标记论文为已发送"""
        paper_id = self.get_paper_id(paper)
        self.sent_papers.add(paper_id)

    def mark_batch_as_sent(self, papers: List[Dict[str, Any]]):
        """批量标记论文为已发送"""
        for paper in papers:
            self.mark_as_sent(paper)
        self.save_history()

    def get_new_papers(self, papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """过滤出未发送过的新论文"""
        new_papers = []
        for paper in papers:
            if self.is_new_paper(paper):
                new_papers.append(paper)
        return new_papers

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_sent": len(self.sent_papers),
            "last_updated": datetime.now().isoformat()
        }


class PaperFilter:
    """论文过滤器 - 按条件过滤"""

    def __init__(self, min_date=None, max_results=10):
        self.min_date = min_date  # 最早日期
        self.max_results = max_results  # 最大数量

    def filter_by_date(self, papers: List[Dict[str, Any]], days_ago: int = 7) -> List[Dict[str, Any]]:
        """按日期过滤（最近N天）"""
        from datetime import datetime, timedelta

        cutoff_date = datetime.now() - timedelta(days=days_ago)
        filtered = []

        for paper in papers:
            try:
                pub_date = datetime.strptime(paper.get('published', '2000-01-01'), '%Y-%m-%d')
                if pub_date >= cutoff_date:
                    filtered.append(paper)
            except:
                pass

        return filtered

    def filter_by_keywords(self, papers: List[Dict[str, Any]], keywords: List[str]) -> List[Dict[str, Any]]:
        """按关键词过滤"""
        filtered = []
        for paper in papers:
            title = paper.get('title', '').lower()
            abstract = paper.get('abstract', '').lower()
            text = title + " " + abstract

            # 检查是否包含任何关键词
            if any(keyword.lower() in text for keyword in keywords):
                filtered.append(paper)

        return filtered