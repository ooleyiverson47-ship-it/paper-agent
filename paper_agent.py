import asyncio
import schedule
import time
import json
from datetime import datetime
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


class QwenClient:
    """通义千问客户端"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"

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
            response = requests.post(self.base_url, headers=headers, json=data)
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

    def query_papers(self, query: str, max_results: int = 10) -> List[Paper]:
        """查询论文"""
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
        作者：{', '.join(paper.authors)}
        发表时间：{paper.published}
        摘要：{paper.abstract}

        请提供：
        1. 研究目标
        2. 研究方法
        3. 主要发现
        4. 创新点
        5. 应用价值
        6. 综合评价

        请用中文回答，保持简洁但全面。
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
            print(f"正在分析第 {i + 1}/{len(papers)} 篇论文...")
            result = await self.analyze_paper(paper)
            results.append(result)
            await asyncio.sleep(2)  # 避免API请求过快
        return results


class PaperScheduler:
    """论文定时调度器"""

    def __init__(self, query_agent: PaperQueryAgent, analysis_agent: PaperAnalysisAgent):
        self.query_agent = query_agent
        self.analysis_agent = analysis_agent
        self.tasks = []

    def schedule_paper_query(self, query: str, schedule_time: str, max_results: int = 5):
        """定时查询论文"""

        def job():
            print(f"\n{'=' * 50}")
            print(f"执行定时查询任务: {datetime.now()}")
            print(f"查询内容: {query}")

            # 查询论文
            papers = self.query_agent.query_papers(query, max_results)
            print(f"找到 {len(papers)} 篇论文")

            if papers:
                # 分析论文
                print("开始分析论文...")
                analysis_results = asyncio.run(
                    self.analysis_agent.batch_analyze(papers)
                )
                # 保存结果
                self.save_results(query, analysis_results)

        schedule.every().day.at(schedule_time).do(job)
        self.tasks.append({"query": query, "time": schedule_time})
        print(f"已添加定时任务: 每天 {schedule_time} 查询 '{query}'")

    def schedule_recurring_query(self, query: str, interval_minutes: int, max_results: int = 5):
        """周期性查询论文"""

        def job():
            print(f"\n{'=' * 50}")
            print(f"执行周期性查询任务: {datetime.now()}")
            print(f"查询内容: {query}")

            papers = self.query_agent.query_papers(query, max_results)
            print(f"找到 {len(papers)} 篇论文")

            if papers:
                analysis_results = asyncio.run(
                    self.analysis_agent.batch_analyze(papers)
                )
                self.save_results(query, analysis_results)

        schedule.every(interval_minutes).minutes.do(job)
        self.tasks.append({"query": query, "interval": f"{interval_minutes}分钟"})
        print(f"已添加周期性任务: 每 {interval_minutes} 分钟查询 '{query}'")

    def save_results(self, query: str, results: List[Dict[str, Any]]):
        """保存分析结果"""
        filename = f"paper_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        output = {
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "results": []
        }

        for result in results:
            output["results"].append({
                "title": result["paper"].title,
                "authors": result["paper"].authors,
                "published": result["paper"].published,
                "url": result["paper"].url,
                "analysis": result["analysis"],
                "analyzed_at": result["analyzed_at"]
            })

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print(f"结果已保存到: {filename}")

        # 打印摘要
        print("\n论文分析摘要:")
        for result in results[:3]:
            print(f"\n标题: {result['paper'].title}")
            print(f"分析: {result['analysis'][:200]}...")

    def run(self):
        """运行调度器"""
        print("论文定时查询系统已启动...")
        print("当前任务列表:")
        for task in self.tasks:
            print(f"  {task}")
        print("\n等待定时任务执行...")
        print("提示: 按 Ctrl+C 停止程序\n")

        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n程序已停止")


async def run_once():
    """单次运行（不循环）"""
    print("单次论文查询模式")
    print("=" * 50)

    # 使用通义千问
    api_key = "sk-59b02bd91f2b4c1e9ece97f0900aa750"
    model_client = QwenClient(api_key)

    # 创建智能体
    query_agent = PaperQueryAgent("query_agent", model_client)
    analysis_agent = PaperAnalysisAgent("analysis_agent", model_client)

    # 查询论文
    print("正在查询论文...")
    papers = query_agent.query_papers("machine learning", max_results=3)
    print(f"找到 {len(papers)} 篇论文\n")

    if papers:
        # 分析论文
        print("正在分析论文...")
        results = await analysis_agent.batch_analyze(papers)

        # 保存结果
        scheduler = PaperScheduler(query_agent, analysis_agent)
        scheduler.save_results("machine learning", results)

        print("\n完成！")


def main():
    """主函数 - 定时运行模式"""
    # 使用通义千问
    api_key = "sk-59b02bd91f2b4c1e9ece97f0900aa750"
    model_client = QwenClient(api_key)

    # 创建智能体
    query_agent = PaperQueryAgent("query_agent", model_client)
    analysis_agent = PaperAnalysisAgent("analysis_agent", model_client)

    # 创建调度器
    scheduler = PaperScheduler(query_agent, analysis_agent)

    # 添加测试任务（每5分钟查询一次，用于测试）
    scheduler.schedule_recurring_query(
        "machine learning",
        interval_minutes=5,  # 每5分钟
        max_results=3
    )

    # 正式任务（可选）
    # scheduler.schedule_paper_query(
    #     "deep learning",
    #     "09:00",
    #     max_results=5
    # )

    # 运行调度器
    scheduler.run()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        # 单次运行模式
        asyncio.run(run_once())
    else:
        # 定时运行模式
        main()