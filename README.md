# paper-agent

一个基于 **Scopus Search API + 通义千问 + 邮件推送** 的论文自动查询智能体。

它会定时查询指定主题下的新论文，过滤历史已发送记录，自动生成中文分析摘要，并将结果通过邮件发送给你。

---

## 功能简介

- 基于 **Scopus Search API** 查询最新论文
- 支持 **增量查询**，只处理上次成功运行之后的新论文
- 使用 **通义千问** 自动生成中文分析
- 通过 **HTML 邮件** 发送结构化报告
- 支持 **GitHub Actions 定时自动执行**
- 自动生成 `daily_report_*.json` 运行报告
- 自动维护：
  - `sent_papers.json`，避免重复发送
  - `last_run.json`，记录上次成功运行时间
- 当上游论文库查询失败时，不推进时间窗口，避免漏抓论文

---

## 当前支持的查询主题

默认内置以下主题：

- 机器学习与深度学习
- 计算机视觉
- 自然语言处理

可以在 `github_runner.py` 中自由修改。

---

## 项目结构

```text
paper-agent/
├─ .github/
│  └─ workflows/
│     └─ paper_query_email.yml     # GitHub Actions 工作流
├─ github_runner.py                # 主入口，负责查询、分析、发邮件
├─ paper_agent.py                  # Scopus 查询与 Qwen 分析逻辑
├─ paper_tracker.py                # 已发送论文去重记录
├─ email_sender.py                 # 邮件内容生成与发送
├─ requirements.txt                # Python 依赖
├─ sent_papers.json                # 已发送论文状态文件
├─ last_run.json                   # 上次成功运行时间
├─ daily_report_*.json             # 每次运行的报告
└─ README.md
