# github_runner.py
import asyncio
import os
import json
from datetime import datetime
from typing import List, Dict, Any

# 导入你的模块
from paper_agent import PaperQueryAgent, PaperAnalysisAgent, QwenClient
from email_sender import EmailSender, EmailConfig


async def query_and_send():
    """查询论文并发送邮件"""

    print(f"开始执行论文查询任务: {datetime.now()}")

    # 从环境变量获取配置（GitHub Secrets）
    api_key = os.getenv("QWEN_API_KEY", "sk-59b02bd91f2b4c1e9ece97f0900aa750")
    sender_email = os.getenv("EMAIL_SENDER", "")
    sender_password = os.getenv("EMAIL_PASSWORD", "")
    receiver_email = os.getenv("EMAIL_RECEIVER", "")

    # 检查邮件配置
    if not sender_email or not sender_password:
        print("邮件配置未设置，将只保存结果文件")
        send_email = False
    else:
        send_email = True
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
            "max_results": 5
        },
        {
            "name": "计算机视觉",
            "query": "computer vision OR image recognition OR object detection",
            "max_results": 5
        },
        {
            "name": "自然语言处理",
            "query": "natural language processing OR large language model OR LLM",
            "max_results": 5
        }
    ]

    all_papers = []

    for q in queries:
        print(f"\n查询: {q['name']}")

        # 查询论文
        papers = query_agent.query_papers(q['query'], q['max_results'])
        print(f"找到 {len(papers)} 篇论文")

        if papers:
            # 分析论文
            print(f"正在分析 {len(papers)} 篇论文...")
            results = await analysis_agent.batch_analyze(papers)

            # 保存结果
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
                all_papers.append(paper_info)

            # 保存到JSON文件
            save_to_json(all_papers)

    print(f"\n共找到 {len(all_papers)} 篇论文")

    # 发送邮件
    if send_email and all_papers:
        query_info = "、".join([q["name"] for q in queries])
        success = email_sender.send_paper_report(
            receiver_email=receiver_email,
            papers=all_papers,
            query_info=query_info,
            include_attachment=True
        )

        if success:
            print("邮件发送成功！")
        else:
            print("邮件发送失败")

    # 生成HTML报告文件
    generate_html_report(all_papers)

    print("任务完成！")


def save_to_json(papers: List[Dict[str, Any]]):
    """保存到JSON文件"""
    filename = f"paper_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(papers, f, ensure_ascii=False, indent=2)

    print(f"结果已保存: {filename}")


def generate_html_report(papers: List[Dict[str, Any]]):
    """生成HTML报告"""
    from email_sender import EmailSender
    email_sender = EmailSender("", 0, "", "")

    html_content = email_sender.generate_html_report(
        papers,
        "自动查询任务"
    )

    filename = f"paper_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"HTML报告已保存: {filename}")


if __name__ == "__main__":
    asyncio.run(query_and_send())