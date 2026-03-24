# export_utils.py
import json
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any


class PaperResultExporter:
    """论文结果导出工具"""

    @staticmethod
    def export_to_excel(results: List[Dict[str, Any]], filename: str = None):
        """导出到Excel"""
        if not filename:
            filename = f"papers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

        data = []
        for result in results:
            data.append({
                "标题": result["paper"].title,
                "作者": ", ".join(result["paper"].authors),
                "发表时间": result["paper"].published,
                "URL": result["paper"].url,
                "分析结果": result["analysis"],
                "分析时间": result["analyzed_at"]
            })

        df = pd.DataFrame(data)
        df.to_excel(filename, index=False)
        print(f"已导出到Excel: {filename}")

    @staticmethod
    def export_to_markdown(results: List[Dict[str, Any]], filename: str = None):
        """导出到Markdown"""
        if not filename:
            filename = f"papers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"# 论文分析报告\n\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            for i, result in enumerate(results, 1):
                f.write(f"## {i}. {result['paper'].title}\n\n")
                f.write(f"**作者**: {', '.join(result['paper'].authors)}\n\n")
                f.write(f"**发表时间**: {result['paper'].published}\n\n")
                f.write(f"**链接**: [{result['paper'].url}]({result['paper'].url})\n\n")
                f.write(f"### 分析结果\n\n")
                f.write(f"{result['analysis']}\n\n")
                f.write("---\n\n")

        print(f"已导出到Markdown: {filename}")