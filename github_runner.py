# github_runner.py
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
    return [
        {
            "name": "机器学习与深度学习",
            "query": 'TITLE-ABS-KEY("machine learning" OR "deep learning" OR "neural network")',
            "max_results": 10,
        },
        {
            "name": "计算机视觉",
            "query": 'TITLE-ABS-KEY("computer vision" OR "image recognition" OR "object detection")',
            "max_results": 10,
        },
        {
            "name": "自然语言处理",
            "query": 'TITLE-ABS-KEY("natural language processing" OR "large language model" OR "LLM")',
            "max_results": 10,
        },
    ]


def dict_to_paper(p: Dict[str, Any]) -> Paper:
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
    provider_failed: bool,
) -> None:
    filename = f"daily_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report = {
        "timestamp": datetime.now().isoformat(),
        "query_since": query_since.isoformat(),
        "total_found": total_found,
        "new_papers_prepared": len(papers),
        "email_sent": email_sent,
        "last_run_updated": last_run_updated,
        "provider_failed": provider_failed,
        "category_stats": stats,
        "new_papers": papers,
    }
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"📄 报告已保存: {filename}")


async def query_and_send() -> int:
    print("\n" + "=" * 60)
    print("📚 每日论文增量查询任务")
    print(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    api_key = os.getenv("QWEN_API_KEY", "").strip()
    scopus_api_key = os.getenv("SCOPUS_API_KEY", "").strip()
    sender_email = os.getenv("EMAIL_SENDER", "").strip()
    sender_password = os.getenv("EMAIL_PASSWORD", "").strip()
    receiver_email = os.getenv("EMAIL_RECEIVER", "").strip()

    if not api_key:
        print("❌ 错误：未设置 QWEN_API_KEY 环境变量")
        return 1

    if not scopus_api_key:
        print("❌ 错误：未设置 SCOPUS_API_KEY 环境变量")
        return 1

    if not sender_email or not sender_password or not receiver_email:
        print("❌ 邮件配置未设置完整，无法发送邮件")
        return 1

    tracker = PaperTracker("sent_papers.json")
    last_run_tracker = LastRunTracker("last_run.json")

    last_run = last_run_tracker.get_last_run()
    if last_run:
        print(f"📅 上次运行时间: {last_run.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print("📅 首次运行，将查询最近30天内的论文")
        last_run = datetime.now() - timedelta(days=30)

    stats = tracker.get_stats()
    print(f"📊 已发送论文总数: {stats['total_sent']} 篇")

    email_sender = EmailSender(
        smtp_server=EmailConfig.SMTP_SERVER,
        smtp_port=EmailConfig.SMTP_PORT,
        sender_email=sender_email,
        sender_password=sender_password,
    )

    model_client = QwenClient(api_key)
    query_agent = PaperQueryAgent("query_agent", model_client)
    analysis_agent = PaperAnalysisAgent("analysis_agent", model_client)

    queries = build_queries()
    all_new_papers: List[Dict[str, Any]] = []
    papers_to_mark_sent: List[Dict[str, Any]] = []
    category_stats: Dict[str, Any] = {}
    total_found = 0
    current_batch_ids = set()
    provider_failures = 0

    for q in queries:
        print("\n" + "=" * 50)
        print(f"🔍 查询领域: {q['name']}")
        print("=" * 50)

        papers = query_agent.query_papers_since(q["query"], last_run, q["max_results"])
        if papers == []:
            provider_failures += 1

        print(f"找到新论文: {len(papers)} 篇")
        total_found += len(papers)

        if not papers:
            category_stats[q["name"]] = {"found": 0, "new": 0, "to_send": 0}
            continue

        paper_dicts = [paper_to_dict(p) for p in papers]
        new_papers = tracker.get_new_papers(paper_dicts)

        unique_new_papers: List[Dict[str, Any]] = []
        for p in new_papers:
            paper_id = tracker.get_paper_id(p)
            if paper_id not in current_batch_ids:
                unique_new_papers.append(p)
                current_batch_ids.add(paper_id)

        category_stats[q["name"]] = {
            "found": len(papers),
            "new": len(unique_new_papers),
            "to_send": 0,
        }

        print(f"其中真正未发送过且本次未重复的: {len(unique_new_papers)} 篇")

        if not unique_new_papers:
            continue

        to_send = unique_new_papers[:5]
        category_stats[q["name"]]["to_send"] = len(to_send)

        print(f"📤 本次将发送: {len(to_send)} 篇")

        paper_objects = [dict_to_paper(p) for p in to_send]
        results = await analysis_agent.batch_analyze(paper_objects)

        for result in results:
            all_new_papers.append(
                {
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
            )

        papers_to_mark_sent.extend(to_send)

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

    if provider_failures == len(queries):
        print("❌ 上游论文库查询全部失败，本次不更新 last_run")
        save_report(
            papers=all_new_papers,
            stats=category_stats,
            total_found=total_found,
            email_sent=False,
            last_run_updated=False,
            query_since=last_run,
            provider_failed=True,
        )
        return 1

    email_sent = False
    last_run_updated = False

    if all_new_papers:
        query_info = f"新论文报告 - {len(all_new_papers)}篇新论文 ({last_run.strftime('%Y-%m-%d %H:%M')} 至今)"
        success = email_sender.send_paper_report(
            receiver_email=receiver_email,
            papers=all_new_papers,
            query_info=query_info,
            include_attachment=True,
        )

        if success:
            email_sent = True
            tracker.mark_batch_as_sent(papers_to_mark_sent)
            now_time = datetime.now()
            last_run_tracker.set_last_run(now_time)
            last_run_updated = True
            print("✅ 邮件发送成功！")
        else:
            print("❌ 邮件发送失败，不更新 last_run，不标记 sent_papers")

        save_report(
            papers=all_new_papers,
            stats=category_stats,
            total_found=total_found,
            email_sent=email_sent,
            last_run_updated=last_run_updated,
            query_since=last_run,
            provider_failed=False,
        )
        return 0 if success else 1

    print("📭 没有发现新论文，跳过邮件发送")
    now_time = datetime.now()
    last_run_tracker.set_last_run(now_time)
    last_run_updated = True

    save_report(
        papers=all_new_papers,
        stats=category_stats,
        total_found=total_found,
        email_sent=False,
        last_run_updated=last_run_updated,
        query_since=last_run,
        provider_failed=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(query_and_send()))
