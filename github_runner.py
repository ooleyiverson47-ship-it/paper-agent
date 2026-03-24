# github_runner.py - 每日增量查询版
import asyncio
import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any

from paper_agent import (
    PaperQueryAgent, PaperAnalysisAgent, QwenClient, LastRunTracker
)
from paper_tracker import PaperTracker 
from email_sender import EmailSender, EmailConfig


async def query_and_send():
    """
    每日增量查询：只查询上次运行之后发布的新论文
    有新论文就发送（最多5篇），没有就不发
    """

    print(f"\n{'=' * 60}")
    print(f"📚 每日论文增量查询任务")
    print(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 60}")

    # 从环境变量获取配置
    api_key = os.getenv("QWEN_API_KEY", "")
    sender_email = os.getenv("EMAIL_SENDER", "")
    sender_password = os.getenv("EMAIL_PASSWORD", "")
    receiver_email = os.getenv("EMAIL_RECEIVER", "")

    # 检查API密钥
    if not api_key:
        print("❌ 错误：未设置 QWEN_API_KEY 环境变量")
        print("请在 GitHub Secrets 中配置 QWEN_API_KEY")
        return

    # 初始化追踪器
    tracker = PaperTracker("sent_papers.json")
    last_run_tracker = LastRunTracker("last_run.json")

    # 获取上次运行时间
    last_run = last_run_tracker.get_last_run()

    if last_run:
        print(f"📅 上次运行时间: {last_run.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📅 将查询此时间之后发布的新论文")
    else:
        print(f"📅 首次运行，将查询最近30天内的论文")
        last_run = datetime.now() - timedelta(days=30)

    # 统计信息
    stats = tracker.get_stats()
    print(f"📊 已发送论文总数: {stats['total_sent']} 篇")

    # 检查邮件配置
    if not sender_email or not sender_password:
        print("❌ 邮件配置未设置，无法发送邮件")
        print("请在 GitHub Secrets 中配置 EMAIL_SENDER 和 EMAIL_PASSWORD")
        return

    email_sender = EmailSender(
        smtp_server=EmailConfig.SMTP_SERVER,
        smtp_port=EmailConfig.SMTP_PORT,
        sender_email=sender_email,
        sender_password=sender_password
    )

    # 创建智能体
    model_client = QwenClient(api_key)
    query_agent = PaperQueryAgent("query_agent", model_client)
    analysis_agent = PaperAnalysisAgent("analysis_agent", model_client)

    # 定义要查询的领域
    queries = [
        {
            "name": "机器学习与深度学习",
            "query": "machine learning OR deep learning OR neural networks",
            "max_results": 10
        },
        {
            "name": "计算机视觉",
            "query": "computer vision OR image recognition OR object detection",
            "max_results": 10
        },
        {
            "name": "自然语言处理",
            "query": "natural language processing OR large language model OR LLM",
            "max_results": 10
        }
    ]

    all_new_papers = []
    category_stats = {}
    total_found = 0

    for q in queries:
        print(f"\n{'=' * 50}")
        print(f"🔍 查询领域: {q['name']}")
        print(f"{'=' * 50}")

        # 增量查询：只查询上次运行之后的新论文
        papers = query_agent.query_papers_since(q['query'], last_run, q['max_results'])
        print(f"找到新论文: {len(papers)} 篇")
        total_found += len(papers)

        if papers:
            # 转换为字典格式（用于去重检查）
            paper_dicts = []
            for paper in papers:
                paper_dict = {
                    "title": paper.title,
                    "authors": paper.authors,
                    "abstract": paper.abstract,
                    "published": paper.published,
                    "url": paper.url,
                    "pdf_url": paper.pdf_url,
                    "categories": paper.categories
                }
                paper_dicts.append(paper_dict)

            # 再次去重（防止历史记录中有重复）
            new_papers = tracker.get_new_papers(paper_dicts)
            print(f"其中真正未发送过的: {len(new_papers)} 篇")

            category_stats[q['name']] = {
                "found": len(papers),
                "new": len(new_papers)
            }

            if new_papers:
                # 限制每次发送数量（最多5篇）
                to_send = new_papers[:5]

                print(f"📤 本次将发送: {len(to_send)} 篇")

                if len(new_papers) > 5:
                    print(f"💡 还有 {len(new_papers) - 5} 篇新论文将在下次运行中发送")

                # 分析要发送的论文
                print(f"\n📝 正在分析 {len(to_send)} 篇新论文...")

                # 重新创建Paper对象用于分析
                paper_objects = []
                for p in to_send:
                    from paper_agent import Paper
                    paper_obj = Paper(
                        title=p["title"],
                        authors=p["authors"],
                        abstract=p["abstract"],
                        published=p["published"],
                        url=p["url"],
                        pdf_url=p["pdf_url"],
                        categories=p["categories"]
                    )
                    paper_objects.append(paper_obj)

                # 分析论文
                results = await analysis_agent.batch_analyze(paper_objects)

                # 保存分析结果
                for result in results:
                    paper_info = {
                        "title": result["paper"].title,
                        "authors": result["paper"].authors,
                        "abstract": result["paper"].abstract,
                        "published": result["paper"].published,
                        "url": result["paper"].url,
                        "pdf_url": result["paper"].pdf_url,
                        "categories": result["paper"].categories,
                        "analysis": result["analysis"],
                        "query_category": q["name"]
                    }
                    all_new_papers.append(paper_info)

                # 标记为已发送（只标记实际发送的）
                tracker.mark_batch_as_sent(to_send)
                print(f"✅ 已标记 {len(to_send)} 篇新论文")
        else:
            category_stats[q['name']] = {
                "found": 0,
                "new": 0
            }

    # 打印统计信息
    print(f"\n{'=' * 60}")
    print("📊 今日查询统计")
    print(f"{'=' * 60}")
    print(f"查询时间范围: {last_run.strftime('%Y-%m-%d %H:%M')} 至今")
    print(f"总查询论文数: {total_found} 篇")

    for category, data in category_stats.items():
        print(f"\n  {category}:")
        print(f"    找到新论文: {data['found']} 篇")
        print(f"    未发送过: {data['new']} 篇")
        if data['new'] > 5:
            print(f"    本次发送: 5 篇 (剩余 {data['new'] - 5} 篇下次发送)")
        elif data['new'] > 0:
            print(f"    本次发送: {data['new']} 篇")

    # 发送邮件（只有新论文时才发送）
    if all_new_papers:
        print(f"\n📧 准备发送 {len(all_new_papers)} 篇新论文的邮件...")

        query_info = f"新论文报告 - {len(all_new_papers)}篇新论文 ({last_run.strftime('%Y-%m-%d')} 至今)"
        success = email_sender.send_paper_report(
            receiver_email=receiver_email,
            papers=all_new_papers,
            query_info=query_info,
            include_attachment=True
        )

        if success:
            print("✅ 邮件发送成功！")
        else:
            print("❌ 邮件发送失败")
    else:
        print(f"\n📭 没有发现新论文，跳过邮件发送")

    # 更新上次运行时间
    last_run_tracker.set_last_run(datetime.now())
    print(f"✅ 已更新上次运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 保存报告
    save_report(all_new_papers, category_stats, total_found)

    print(f"\n✅ 任务完成！")


def save_report(papers: List[Dict[str, Any]], stats: Dict[str, Any], total_found: int):
    """保存报告"""
    filename = f"daily_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    report = {
        "timestamp": datetime.now().isoformat(),
        "total_found": total_found,
        "new_papers_sent": len(papers),
        "category_stats": stats,
        "new_papers": papers
    }

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"📄 报告已保存: {filename}")


if __name__ == "__main__":
    asyncio.run(query_and_send())
