# github_runner.py - 每日增量查询版（修正版，Python 3.9）
import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any

from paper_agent import (
    Paper,
    PaperQueryAgent,
    PaperAnalysisAgent,
    QwenClient,
    LastRunTracker,
)
from paper_tracker import PaperTracker
from email_sender import EmailSender, EmailConfig


def build_queries() -> List[Dict[str, Any]]:
    """定义要查询的领域"""
    return [
        {
            "name": "机器学习与深度学习",
            "query": 'all:"machine learning" OR all:"deep learning" OR all:"neural network"',
            "max_results": 10,
        },
        {
            "name": "计算机视觉",
            "query": 'all:"computer vision" OR all:"image recognition" OR all:"object detection"',
            "max_results": 10,
        },
        {
            "name": "自然语言处理",
            "query": 'all:"natural language processing" OR all:"large language model" OR all:"LLM"',
            "max_results": 10,
        },
    ]


def dict_to_paper(p: Dict[str, Any]) -> Paper:
    """将字典恢复为 Paper 对象"""
    return Paper(
        title=p["title"],
        authors=p["authors"],
        abstract=p["abstract"],
        published=p["published"],
        url=p["url"],
        pdf_url=p["pdf_url"],
        categories=p["categories"],
    )


def paper_to_dict(paper: Paper) -> Dict[str, Any]:
    """将 Paper 对象转为字典"""
    return {
        "title": paper.title,
        "authors": paper.authors,
        "abstract": paper.abstract,
        "published": paper.published,
        "url": paper.url,
        "pdf_url": paper.pdf_url,
        "categories": paper.categories,
    }


def save_report(
    papers: List[Dict[str, Any]],
    stats: Dict[str, Any],
    total_found: int,
    email_sent: bool,
    last_run_updated: bool,
    query_since: datetime,
) -> None:
    """保存报告"""
    filename = f"daily_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    report = {
        "timestamp": datetime.now().isoformat(),
        "query_since": query_since.isoformat(),
        "total_found": total_found,
        "new_papers_prepared": len(papers),
        "email_sent": email_sent,
        "last_run_updated": last_run_updated,
        "category_stats": stats,
        "new_papers": papers,
    }

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"📄 报告已保存: {filename}")


async def query_and_send() -> int:
    """
    每日增量查询：
    1. 只查询上次运行之后的新论文
    2. 有新论文才发送邮件
    3. 只有邮件发送成功后，才标记为已发送并推进 last_run
    """
    print("\n" + "=" * 60)
    print("📚 每日论文增量查询任务")
    print(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 从环境变量获取配置
    api_key = os.getenv("QWEN_API_KEY", "").strip()
    sender_email = os.getenv("EMAIL_SENDER", "").strip()
    sender_password = os.getenv("EMAIL_PASSWORD", "").strip()
    receiver_email = os.getenv("EMAIL_RECEIVER", "").strip()

    # 检查 API 配置
    if not api_key:
        print("❌ 错误：未设置 QWEN_API_KEY 环境变量")
        print("请在 GitHub Secrets 中配置 QWEN_API_KEY")
        return 1

    # 检查邮件配置
    if not sender_email or not sender_password or not receiver_email:
        print("❌ 邮件配置未设置完整，无法发送邮件")
        print("请在 GitHub Secrets 中配置 EMAIL_SENDER、EMAIL_PASSWORD 和 EMAIL_RECEIVER")
        return 1

    # 初始化追踪器
    tracker = PaperTracker("sent_papers.json")
    last_run_tracker = LastRunTracker("last_run.json")

    # 获取上次运行时间
    last_run = last_run_tracker.get_last_run()
    if last_run:
        print(f"📅 上次运行时间: {last_run.strftime('%Y-%m-%d %H:%M:%S')}")
        print("📅 将查询此时间之后发布的新论文")
    else:
        print("📅 首次运行，将查询最近30天内的论文")
        last_run = datetime.now() - timedelta(days=30)

    # 统计信息
    stats = tracker.get_stats()
    print(f"📊 已发送论文总数: {stats['total_sent']} 篇")

    # 初始化邮件发送器
    email_sender = EmailSender(
        smtp_server=EmailConfig.SMTP_SERVER,
        smtp_port=EmailConfig.SMTP_PORT,
        sender_email=sender_email,
        sender_password=sender_password,
    )

    # 创建智能体
    model_client = QwenClient(api_key)
    query_agent = PaperQueryAgent("query_agent", model_client)
    analysis_agent = PaperAnalysisAgent("analysis_agent", model_client)

    queries = build_queries()

    all_new_papers: List[Dict[str, Any]] = []
    papers_to_mark_sent: List[Dict[str, Any]] = []
    category_stats: Dict[str, Any] = {}
    total_found = 0

    # 用于避免同一篇论文在不同类别里重复进入本次邮件
    current_batch_ids = set()

    for q in queries:
        print("\n" + "=" * 50)
        print(f"🔍 查询领域: {q['name']}")
        print("=" * 50)

        papers = query_agent.query_papers_since(q["query"], last_run, q["max_results"])
        print(f"找到新论文: {len(papers)} 篇")
        total_found += len(papers)

        if not papers:
            category_stats[q["name"]] = {
                "found": 0,
                "new": 0,
                "to_send": 0,
            }
            continue

        # 转换为字典格式，便于去重检查
        paper_dicts = [paper_to_dict(p) for p in papers]

        # 与历史记录比对，过滤已发送论文
        new_papers = tracker.get_new_papers(paper_dicts)

        # 再和“本次任务已选中列表”去重，避免跨类别重复发送
        unique_new_papers: List[Dict[str, Any]] = []
        for p in new_papers:
            paper_id = tracker.get_paper_id(p)
            if paper_id not in current_batch_ids:
                unique_new_papers.append(p)
                current_batch_ids.add(paper_id)

        print(f"其中真正未发送过且本次未重复的: {len(unique_new_papers)} 篇")

        category_stats[q["name"]] = {
            "found": len(papers),
            "new": len(unique_new_papers),
            "to_send": 0,
        }

        if not unique_new_papers:
            continue

        # 每个类别最多发送 5 篇
        to_send = unique_new_papers[:5]
        category_stats[q["name"]]["to_send"] = len(to_send)

        print(f"📤 本次将发送: {len(to_send)} 篇")
        if len(unique_new_papers) > 5:
            print(f"💡 还有 {len(unique_new_papers) - 5} 篇新论文将在下次运行中发送")

        print(f"\n📝 正在分析 {len(to_send)} 篇新论文...")

        paper_objects = [dict_to_paper(p) for p in to_send]
        results = await analysis_agent.batch_analyze(paper_objects)

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
                "query_category": q["name"],
            }
            all_new_papers.append(paper_info)

        # 注意：这里只是暂存，邮件成功后才真正写入 sent_papers.json
        papers_to_mark_sent.extend(to_send)

    # 打印统计
    print("\n" + "=" * 60)
    print("📊 今日查询统计")
    print("=" * 60)
    print(f"查询时间范围: {last_run.strftime('%Y-%m-%d %H:%M')} 至今")
    print(f"总查询论文数: {total_found} 篇")

    for category, data in category_stats.items():
        print(f"\n  {category}:")
        print(f"    找到新论文: {data['found']} 篇")
        print(f"    未发送过且本次不重复: {data['new']} 篇")
        print(f"    本次发送: {data['to_send']} 篇")

    email_sent = False
    last_run_updated = False

    if all_new_papers:
        print(f"\n📧 准备发送 {len(all_new_papers)} 篇新论文的邮件...")

        query_info = (
            f"新论文报告 - {len(all_new_papers)}篇新论文 "
            f"({last_run.strftime('%Y-%m-%d %H:%M')} 至今)"
        )

        success = email_sender.send_paper_report(
            receiver_email=receiver_email,
            papers=all_new_papers,
            query_info=query_info,
            include_attachment=True,
        )

        if success:
            print("✅ 邮件发送成功！")
            email_sent = True

            tracker.mark_batch_as_sent(papers_to_mark_sent)
            print(f"✅ 已标记 {len(papers_to_mark_sent)} 篇新论文")

            now_time = datetime.now()
            last_run_tracker.set_last_run(now_time)
            last_run_updated = True
            print(f"✅ 已更新上次运行时间: {now_time.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print("❌ 邮件发送失败")
            print("⚠️ 未更新 last_run，也未标记 sent_papers，便于下次重试")

        save_report(
            papers=all_new_papers,
            stats=category_stats,
            total_found=total_found,
            email_sent=email_sent,
            last_run_updated=last_run_updated,
            query_since=last_run,
        )

        print("\n✅ 任务完成！" if success else "\n⚠️ 任务结束，但邮件发送失败")
        return 0 if success else 1

    print("\n📭 没有发现新论文，跳过邮件发送")

    now_time = datetime.now()
    last_run_tracker.set_last_run(now_time)
    last_run_updated = True
    print(f"✅ 已更新上次运行时间: {now_time.strftime('%Y-%m-%d %H:%M:%S')}")

    save_report(
        papers=all_new_papers,
        stats=category_stats,
        total_found=total_found,
        email_sent=False,
        last_run_updated=last_run_updated,
        query_since=last_run,
    )

    print("\n✅ 任务完成！")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(query_and_send()))
