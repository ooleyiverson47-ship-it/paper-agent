# email_sender.py
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
from datetime import datetime
from typing import List, Dict, Any
import json


class EmailSender:
    """邮件发送器"""

    def __init__(self, smtp_server: str, smtp_port: int, sender_email: str, sender_password: str):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.sender_password = sender_password

    def send_paper_report(self, receiver_email: str, papers: List[Dict[str, Any]],
                          query_info: str = "", include_attachment: bool = True):
        """发送论文报告邮件"""

        # 创建邮件
        message = MIMEMultipart("alternative")
        message["Subject"] = f"📚 论文查询报告 - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        message["From"] = self.sender_email
        message["To"] = receiver_email

        # 生成HTML内容
        html_content = self.generate_html_report(papers, query_info)

        # 添加HTML内容
        html_part = MIMEText(html_content, "html")
        message.attach(html_part)

        # 添加附件（JSON文件）
        if include_attachment and papers:
            json_data = {
                "query_info": query_info,
                "timestamp": datetime.now().isoformat(),
                "papers": papers
            }
            json_str = json.dumps(json_data, ensure_ascii=False, indent=2)
            json_attachment = MIMEText(json_str, "json", "utf-8")
            json_attachment.add_header(
                "Content-Disposition",
                f"attachment; filename=papers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            message.attach(json_attachment)

        # 发送邮件
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
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 900px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 30px;
                    border-radius: 10px;
                    margin-bottom: 30px;
                }}
                .paper {{
                    background: #f8f9fa;
                    border-left: 4px solid #667eea;
                    padding: 20px;
                    margin-bottom: 25px;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .paper-title {{
                    font-size: 18px;
                    font-weight: bold;
                    color: #667eea;
                    margin-bottom: 10px;
                }}
                .paper-meta {{
                    color: #666;
                    font-size: 14px;
                    margin-bottom: 10px;
                }}
                .paper-abstract {{
                    margin: 15px 0;
                    padding: 10px;
                    background: white;
                    border-radius: 5px;
                }}
                .paper-analysis {{
                    background: #e8f4f8;
                    padding: 15px;
                    border-radius: 5px;
                    margin-top: 10px;
                }}
                .footer {{
                    text-align: center;
                    margin-top: 40px;
                    padding-top: 20px;
                    border-top: 1px solid #ddd;
                    color: #666;
                    font-size: 12px;
                }}
                .badge {{
                    display: inline-block;
                    padding: 3px 8px;
                    background: #667eea;
                    color: white;
                    border-radius: 3px;
                    font-size: 12px;
                    margin-right: 5px;
                }}
                h1 {{
                    margin: 0;
                    font-size: 24px;
                }}
                .stats {{
                    background: white;
                    border-radius: 8px;
                    padding: 15px;
                    margin-bottom: 20px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .stats span {{
                    font-weight: bold;
                    color: #667eea;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📚 学术论文智能报告</h1>
                <p>生成时间: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}</p>
                <p>查询条件: {query_info}</p>
            </div>
        """

        if papers:
            html += f"""
            <div class="stats">
                📊 本次共找到 <span>{len(papers)}</span> 篇相关论文
            </div>
            """

            for i, paper in enumerate(papers, 1):
                html += f"""
                <div class="paper">
                    <div class="paper-title">{i}. {paper.get('title', 'N/A')}</div>
                    <div class="paper-meta">
                        <span class="badge">作者</span> {', '.join(paper.get('authors', [])[:5])}
                        {f'等{len(paper.get("authors", []))}人' if len(paper.get('authors', [])) > 5 else ''}
                    </div>
                    <div class="paper-meta">
                        <span class="badge">发表时间</span> {paper.get('published', 'N/A')}
                    </div>
                    <div class="paper-meta">
                        <span class="badge">分类</span> {', '.join(paper.get('categories', [])[:3])}
                    </div>
                    <div class="paper-meta">
                        <span class="badge">链接</span> <a href="{paper.get('url', '#')}">查看原文</a> | 
                        <a href="{paper.get('pdf_url', '#')}">下载PDF</a>
                    </div>
                    <div class="paper-abstract">
                        <strong>📄 摘要:</strong><br>
                        {self.truncate_text(paper.get('abstract', '无摘要'), 500)}
                    </div>
                """

                if paper.get('analysis'):
                    html += f"""
                    <div class="paper-analysis">
                        <strong>🤖 AI分析摘要:</strong><br>
                        {self.format_analysis(paper.get('analysis', ''))}
                    </div>
                    """

                html += "</div>"
        else:
            html += """
            <div class="stats">
                ⚠️ 未找到相关论文
            </div>
            """

        html += """
            <div class="footer">
                <p>本邮件由论文自动查询系统生成 | 智能分析由通义千问提供</p>
                <p>如需取消订阅，请回复邮件</p>
            </div>
        </body>
        </html>
        """

        return html

    def truncate_text(self, text: str, max_length: int) -> str:
        """截断文本"""
        if len(text) > max_length:
            return text[:max_length] + "..."
        return text

    def format_analysis(self, analysis: str) -> str:
        """格式化分析文本"""
        # 将文本中的换行转换为HTML换行
        return analysis.replace('\n', '<br>')


# 配置文件
class EmailConfig:
    """邮件配置"""
    # 以QQ邮箱为例（需要开启SMTP服务）
    SMTP_SERVER = "smtp.qq.com"  # QQ邮箱
    # SMTP_SERVER = "smtp.163.com"  # 163邮箱
    # SMTP_SERVER = "smtp.gmail.com"  # Gmail

    SMTP_PORT = 465  # SSL端口

    # 请替换为你的邮箱信息
    SENDER_EMAIL = ""# 发送邮箱
    SENDER_PASSWORD = ""# SMTP授权码（不是登录密码）
    RECEIVER_EMAIL = "" # 接收邮箱