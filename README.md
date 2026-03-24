# 📚 论文自动查询智能体

自动查询arXiv最新学术论文，通过通义千问进行智能分析，并发送邮件报告。

## ✨ 功能特点

- 🔍 自动查询最新学术论文（arXiv）
- 🤖 AI智能分析论文内容（通义千问）
- 📧 邮件发送HTML格式报告
- ⏰ 定时自动执行（每天2次）
- 📊 支持导出JSON和HTML格式

## 🚀 使用方法

### 1. 配置GitHub Secrets

在仓库 Settings → Secrets and variables → Actions 中添加：

- `QWEN_API_KEY`: 通义千问API密钥
- `EMAIL_SENDER`: 发送邮箱（QQ邮箱）
- `EMAIL_PASSWORD`: SMTP授权码
- `EMAIL_RECEIVER`: 接收邮箱

### 2. 手动触发测试

进入 Actions 标签，选择工作流，点击 "Run workflow"

### 3. 自动执行

每天北京时间 9:00 和 15:00 自动执行

## 📝 查询领域

- 机器学习与深度学习
- 计算机视觉
- 自然语言处理

## 📧 邮件报告示例

邮件包含：
- 论文标题、作者、摘要
- AI分析结果
- 原文链接和PDF下载链接
- JSON附件

## 🔧 自定义配置

修改 `github_runner.py` 中的 `queries` 列表来调整查询内容。

## 📄 许可证

MIT License
