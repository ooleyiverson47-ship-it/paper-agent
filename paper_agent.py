# paper_agent.py
import asyncio
import schedule
import time
import json
import os
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any
from dataclasses import dataclass
import arxiv
import requests


@dataclass
class Paper:
    """论文数据结构"""
    title: str
    authors: List[str]
    abstract: str
    published: str
    url: str
    pdf_url: str
    categories: List[str]


class PaperTracker:
    """论文追踪器 - 记录已发送的论文"""

    def __init__(self, history_file="sent_papers.json"):
        self.history_file = history_file
        self.sent_papers = self.load_history()

    def load_history(self) -> set:
        """加载已发送论文历史"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
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

    def get_paper_id(self, paper) -> str:
        """生成论文唯一ID"""
        title = paper.title if hasattr(paper, 'title') else paper.get('title', '')
        authors = ','.join(paper.authors[:3] if hasattr(paper, 'authors') else paper.get('authors', [])[:3])
        published = paper.published if hasattr(paper, 'published') else paper.get('published', '')
        unique_str = f"{title}|{authors}|{published}"
        return hashlib.md5(unique_str.encode()).hexdigest()

    def is_new_paper(self, paper) -> bool:
        """检查论文是否未发送过"""
        paper_id = self.get_paper_id(paper)
        return paper_id not in self.sent_papers

    def mark_as_sent(self, paper):
        """标记论文为已发送"""
        paper_id = self.get_paper_id(paper)
        self.sent_papers.add(paper_id)

    def mark_batch_as_sent(self, papers):
        """批量标记论文为已发送"""
        for paper in papers:
            self.mark_as_sent(paper)
        self.save_history()

    def get_new_papers(self, papers):
        """过滤出未发送过的新论文"""
        return [p for p in papers if self.is_new_paper(p)]

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_sent": len(self.sent_papers),
            "last_updated": datetime.now().isoformat()
        }


class LastRunTracker:
    """记录上次运行时间"""

    def __init__(self, state_file="last_run.json"):
        self.state_file = state_file
        self.state = self.load_state()

    def load_state(self) -> Dict[str, Any]:
        """加载状态"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_state(self):
        """保存状态"""
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    def get_last_run(self) -> datetime:
        """获取上次运行时间"""
        last_run_str = self.state.get("last_run")
        if last_run_str:
            return datetime.fromisoformat(last_run_str)
        return None

    def set_last_run(self, run_time: datetime):
        """设置本次运行时间"""
        self.state["last_run"] = run_time.isoformat()
        self.save_state()


class QwenClient:
    """通义千问客户端"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
        print(f"✅ QwenClient初始化成功")

    async def async_call(self, prompt: str) -> str:
        """调用通义千问API"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "qwen-turbo",
            "input": {
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            },
            "parameters": {
                "result_format": "message"
            }
        }

        try:
            response = requests.post(self.base_url, headers=headers, json=data, timeout=30)
            result = response.json()
            if response.status_code == 200:
                return result["output"]["choices"][0]["message"]["content"]
            else:
                return f"API错误: {result}"
        except Exception as e:
            print(f"API调用失败: {e}")
            return f"分析失败: {str(e)}"


class PaperQueryAgent:
    """论文查询智能体"""

    def __init__(self, name: str, model_client):
        self.name = name
        self.model = model_client
        self.arxiv_client = arxiv.Client()

    def query_papers_since(self, query: str, since_date: datetime, max_results: int = 10) -> List[Paper]:
    """查询指定日期之后发布的论文"""
    try:
        print(f"  📅 查询条件: {since_date.strftime('%Y-%m-%d %H:%M')} 之后发布的论文")

        # 不把 submittedDate 直接拼进 arXiv query
        # 先按关键词查，再在本地按时间过滤
        search = arxiv.Search(
            query=query,
            max_results=max_results * 5,
            sort_by=arxiv.SortCriterion.SubmittedDate
        )

        papers = []
        for result in self.arxiv_client.results(search):
            published_dt = result.published.replace(tzinfo=None)

            # 已经按时间降序了，遇到更早的可以直接停
            if published_dt < since_date:
                continue

            paper = Paper(
                title=result.title,
                authors=[author.name for author in result.authors],
                abstract=result.summary,
                published=result.published.strftime("%Y-%m-%d"),
                url=result.entry_id,
                pdf_url=result.pdf_url,
                categories=result.categories
            )
            papers.append(paper)

            if len(papers) >= max_results:
                break

        return papers

    except Exception as e:
        print(f"论文查询失败: {e}")
        return []

    def query_papers_today(self, query: str, max_results: int = 10) -> List[Paper]:
        """查询今天发布的论文"""
        try:
            today = datetime.now().strftime("%Y%m%d000000")
            full_query = f"{query} AND submittedDate:[{today} TO *]"

            search = arxiv.Search(
                query=full_query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.SubmittedDate
            )

            papers = []
            for result in self.arxiv_client.results(search):
                paper = Paper(
                    title=result.title,
                    authors=[author.name for author in result.authors],
                    abstract=result.summary,
                    published=result.published.strftime("%Y-%m-%d"),
                    url=result.entry_id,
                    pdf_url=result.pdf_url,
                    categories=result.categories
                )
                papers.append(paper)
            return papers
        except Exception as e:
            print(f"论文查询失败: {e}")
            return []

    def query_papers(self, query: str, max_results: int = 10) -> List[Paper]:
        """普通查询（向后兼容）"""
        try:
            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.SubmittedDate
            )

            papers = []
            for result in self.arxiv_client.results(search):
                paper = Paper(
                    title=result.title,
                    authors=[author.name for author in result.authors],
                    abstract=result.summary,
                    published=result.published.strftime("%Y-%m-%d"),
                    url=result.entry_id,
                    pdf_url=result.pdf_url,
                    categories=result.categories
                )
                papers.append(paper)
            return papers
        except Exception as e:
            print(f"论文查询失败: {e}")
            return []


class PaperAnalysisAgent:
    """论文分析智能体"""

    def __init__(self, name: str, model_client):
        self.name = name
        self.model = model_client

    async def analyze_paper(self, paper: Paper) -> Dict[str, Any]:
        """分析单篇论文"""
        prompt = f"""
        请分析以下学术论文，并提供详细的分析报告：

        标题：{paper.title}
        作者：{', '.join(paper.authors[:5])}
        发表时间：{paper.published}
        摘要：{paper.abstract[:1000]}

        请提供：
        1. 研究目标
        2. 研究方法
        3. 主要发现
        4. 创新点
        5. 应用价值

        请用中文回答，保持简洁。
        """

        try:
            analysis = await self.model.async_call(prompt)
            return {
                "paper": paper,
                "analysis": analysis,
                "analyzed_at": datetime.now().isoformat()
            }
        except Exception as e:
            print(f"分析失败: {e}")
            return {
                "paper": paper,
                "analysis": f"分析失败: {str(e)}",
                "analyzed_at": datetime.now().isoformat()
            }

    async def batch_analyze(self, papers: List[Paper]) -> List[Dict[str, Any]]:
        """批量分析"""
        results = []
        for i, paper in enumerate(papers):
            print(f"  正在分析第 {i + 1}/{len(papers)} 篇论文...")
            result = await self.analyze_paper(paper)
            results.append(result)
            await asyncio.sleep(1)
        return results
