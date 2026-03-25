# email_sender.py
import json
import os
import smtplib
import ssl
from datetime import datetime
from html import escape
from typing import List, Dict, Any
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


class EmailSender:
    """邮件发送器"""

    def __init__(self, smtp_server: str, smtp_port: int, sender_email: str, sender_password: str):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.sender_password = sender_password

    def send_paper_report(
        self,
        receiver_email: str,
        papers: List[Dict[str, Any]],
        query_info: str = "",
        include_attachment: bool = True,
    ) -> bool:
        """发送论文报告邮件"""
        message = MIMEMultipart("alternative")
        message["Subject"] = f"论文查询报告 - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        message["From"] = self.sender_email
        message["To"] = receiver_email

        html_content = self.generate_html_report(papers, query_info)
        html_part = MIMEText(html_content, "html", "utf-8")
        message.attach(html_part)

        if include_attachment and papers:
            json_data = {
                "query_info": query_info,
                "timestamp": datetime.now().isoformat(),
                "papers": papers,
            }
            json_str = json.dumps(json_data, ensure_ascii=False, indent=2)
            json_attachment = MIMEText(json_str, "json", "utf-8")
            json_attachment.add_header(
                "Content-Disposition",
                f"attachment; filename=papers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            )
            message.attach(json_attachment)

        try:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, context=context) as server:
                server.login(self.sender_email, self.sender_password)
                server.send_message(message)
            print(f"邮件已发送到 {receiver_email}")
            return True
        except Exception as e:
            print(f"邮件发送失败: {e}")
            return False

    def generate_html_report(self, papers: List[Dict[str, Any]], query_info: str = "") -> str:
        """生成HTML格式的报告"""
        html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>论文查询报告</title>
<style>
  body {{
    font-family: Arial, "Microsoft YaHei", sans-serif;
    line-height: 1.7;
    color: #222;
    background: #f7f7f9;
    margin: 0;
    padding: 0;
  }}
  .container {{
    max-width: 920px;
    margin: 24px auto;
    background: #ffffff;
    padding: 28px 32px;
    border-radius: 12px;
    box-shadow: 0 4px 18px rgba(0,0,0,0.06);
  }}
  h1 {{
    margin-top: 0;
    color: #1f2937;
  }}
  .meta {{
    color: #666;
    font-size: 14px;
    margin-bottom: 20px;
  }}
  .summary {{
    background: #f3f6fb;
    border-left: 4px solid #4f46e5;
    padding: 12px 16px;
    margin: 18px 0 24px 0;
    border-radius: 8px;
  }}
  .paper {{
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 18px 18px 14px 18px;
    margin-bottom: 18px;
    background: #fff;
  }}
  .paper h2 {{
    margin: 0 0 10px 0;
    font-size: 20px;
    color: #111827;
  }}
  .label {{
    font-weight: 700;
    color: #374151;
  }}
  .links {{
    margin: 10px 0;
  }}
  .links a {{
    color: #2563eb;
    text-decoration: none;
    margin-right: 12px;
  }}
  .abstract, .analysis {{
    background: #fafafa;
    padding: 12px 14px;
    border-radius: 8px;
    white-space: pre-wrap;
  }}
  .footer {{
    margin-top: 28px;
    font-size: 12px;
    color: #777;
    text-align: center;
  }}
  .muted {{
    color: #888;
  }}
</style>
</head>
<body>
  <div class="container">
    <h1>📚 学术论文智能报告</h1>
    <div class="meta">生成时间：{escape(datetime.now().strftime('%Y年%m月%d日 %H:%M:%S'))}</div>
    <div class="summary">
      <div><span class="label">查询条件：</span>{escape(query_info or "未提供")}</div>
      <div style="margin-top:6px;"><span class="label">论文数量：</span>{len(papers)}</div>
    </div>
"""

        if papers:
            for i, paper in enumerate(papers, 1):
                title = escape(paper.get("title", "N/A"))
                authors_list = paper.get("authors", []) or []
                authors_text = ", ".join(authors_list[:5])
                if len(authors_list) > 5:
                    authors_text += f" 等{len(authors_list)}人"
                authors_text = escape(authors_text or "未知")

                published = escape(paper.get("published", "N/A"))
                categories = escape(", ".join((paper.get("categories", []) or [])[:3]) or "N/A")
                abstract = escape(self.truncate_text(paper.get("abstract", "无摘要"), 500))
                analysis = paper.get("analysis", "")
                analysis_html = self.format_analysis(analysis) if analysis else ""

                url = (paper.get("url") or "").strip()
                pdf_url = (paper.get("pdf_url") or "").strip()

                links_html = ""
                if url:
                    safe_url = escape(url, quote=True)
                    links_html += f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer">查看原文</a>'
                if pdf_url:
                    safe_pdf_url = escape(pdf_url, quote=True)
                    links_html += f'<a href="{safe_pdf_url}" target="_blank" rel="noopener noreferrer">下载PDF</a>'
                if not links_html:
                    links_html = '<span class="muted">暂无可用链接</span>'

                html += f"""
    <div class="paper">
      <h2>{i}. {title}</h2>
      <div><span class="label">作者：</span>{authors_text}</div>
      <div><span class="label">发表时间：</span>{published}</div>
      <div><span class="label">分类：</span>{categories}</div>
      <div class="links"><span class="label">链接：</span>{links_html}</div>
      <div><span class="label">摘要：</span></div>
      <div class="abstract">{abstract}</div>
"""

                if analysis_html:
                    html += f"""
      <div style="margin-top:12px;"><span class="label">AI分析摘要：</span></div>
      <div class="analysis">{analysis_html}</div>
"""

                html += """
    </div>
"""

        else:
            html += """
    <div class="paper">
      <div>⚠️ 未找到相关论文</div>
    </div>
"""

        html += """
    <div class="footer">
      本邮件由论文自动查询系统生成 ｜ 智能分析由通义千问提供
    </div>
  </div>
</body>
</html>
"""
        return html

    def truncate_text(self, text: str, max_length: int) -> str:
        """截断文本"""
        text = text or ""
        if len(text) > max_length:
            return text[:max_length] + "..."
        return text

    def format_analysis(self, analysis: str) -> str:
        """格式化分析文本"""
        return escape(analysis or "").replace("\n", "<br>")


class EmailConfig:
    """邮件配置"""
    SMTP_SERVER = "smtp.qq.com"
    SMTP_PORT = 465
    SENDER_EMAIL = ""
    SENDER_PASSWORD = ""
    RECEIVER_EMAIL = ""
