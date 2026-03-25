# paper_agent.py
import asyncio
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any, Optional

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


class LastRunTracker:
    """记录上次运行时间"""

    def __init__(self, state_file: str = "last_run.json"):
        self.state_file = state_file
        self.state = self.load_state()

    def load_state(self) -> Dict[str, Any]:
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def save_state(self) -> None:
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    def get_last_run(self) -> Optional[datetime]:
        last_run_str = self.state.get("last_run")
        if last_run_str:
            return datetime.fromisoformat(last_run_str)
        return None

    def set_last_run(self, run_time: datetime) -> None:
        self.state["last_run"] = run_time.isoformat()
        self.save_state()


class QwenClient:
    """通义千问客户端"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
        print("✅ QwenClient初始化成功")

    async def async_call(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
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
            },
        }

        try:
            response = requests.post(self.base_url, headers=headers, json=data, timeout=30)
            result = response.json()
            if response.status_code == 200:
                return result["output"]["choices"][0]["message"]["content"]
            return f"API错误: {result}"
        except Exception as e:
            print(f"API调用失败: {e}")
            return f"分析失败: {str(e)}"


class ElsevierAPIError(Exception):
    pass


class PaperQueryAgent:
    """
    基于 ScienceDirect Search API 的论文查询智能体

    设计原则：
    1. 只用 Search API 发现论文
    2. 不强行请求 FULL view，避免 entitlement 问题
    3. 先按关键词检索，再在本地按日期过滤
    """

    def __init__(self, name: str, model_client):
        self.name = name
        self.model = model_client

        self.api_key = os.getenv("ELSEVIER_API_KEY", "").strip()
        self.insttoken = os.getenv("ELSEVIER_INSTTOKEN", "").strip()

        if not self.api_key:
            raise ValueError("未设置 ELSEVIER_API_KEY 环境变量")

        self.base_url = "https://api.elsevier.com/content/search/scidir"
        self.session = requests.Session()
        print("✅ ScienceDirect 查询客户端初始化成功")

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/json",
            "X-ELS-APIKey": self.api_key,
        }
        if self.insttoken:
            headers["X-ELS-Insttoken"] = self.insttoken
        return headers

    def _request_json(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用 Elsevier Search API
        """
        last_error = None

        for attempt in range(3):
            try:
                response = self.session.get(
                    self.base_url,
                    headers=self._headers(),
                    params=params,
                    timeout=45,
                )

                if response.status_code == 429:
                    wait_s = 2 * (attempt + 1)
                    print(f"⚠️ ScienceDirect 限流，{wait_s} 秒后重试...")
                    time.sleep(wait_s)
                    continue

                if response.status_code in (401, 403):
                    raise ElsevierAPIError(
                        f"Elsevier 鉴权/授权失败，HTTP {response.status_code}。"
                        "请检查 API Key、机构 IP / Insttoken 或订阅权限。"
                    )

                response.raise_for_status()
                return response.json()

            except Exception as e:
                last_error = e
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))

        raise ElsevierAPIError(f"ScienceDirect API 请求失败: {last_error}")

    def _extract_entries(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        尽量兼容 Search API 的不同 JSON 外层结构
        """
        if isinstance(payload, dict):
            if "search-results" in payload:
                sr = payload.get("search-results", {})
                entries = sr.get("entry", [])
                if isinstance(entries, list):
                    return entries
                return []
            if "results" in payload and isinstance(payload["results"], list):
                return payload["results"]
        return []

    def _parse_date(self, entry: Dict[str, Any]) -> Optional[datetime]:
        """
        尽量从多个常见字段中取日期
        """
        candidates = [
            entry.get("prism:coverDate"),
            entry.get("coverDate"),
            entry.get("date"),
            entry.get("publicationDate"),
        ]

        for value in candidates:
            if not value:
                continue
            text = str(value).strip()
            try:
                # 常见格式：YYYY-MM-DD
                if len(text) >= 10:
                    return datetime.strptime(text[:10], "%Y-%m-%d")
            except Exception:
                continue
        return None

    def _parse_authors(self, entry: Dict[str, Any]) -> List[str]:
        """
        Search 结果里的作者字段并不总是统一，做宽松兼容
        """
        authors: List[str] = []

        creator = entry.get("dc:creator")
        if creator and isinstance(creator, str):
            authors.append(creator.strip())

        author_block = entry.get("authors")
        if isinstance(author_block, dict):
            author_items = author_block.get("author")
            if isinstance(author_items, list):
                for item in author_items:
                    if isinstance(item, dict):
                        name = item.get("$") or item.get("ce:indexed-name") or item.get("name")
                        if name:
                            authors.append(str(name).strip())
            elif isinstance(author_items, dict):
                name = author_items.get("$") or author_items.get("ce:indexed-name") or author_items.get("name")
                if name:
                    authors.append(str(name).strip())

        # 去重并保持顺序
        unique_authors = []
        seen = set()
        for a in authors:
            if a and a not in seen:
                seen.add(a)
                unique_authors.append(a)

        return unique_authors

    def _entry_to_paper(self, entry: Dict[str, Any]) -> Optional[Paper]:
        title = (
            entry.get("dc:title")
            or entry.get("title")
            or entry.get("articleTitle")
            or ""
        ).strip()

        if not title:
            return None

        published_dt = self._parse_date(entry)
        published = published_dt.strftime("%Y-%m-%d") if published_dt else ""

        abstract = (
            entry.get("dc:description")
            or entry.get("description")
            or entry.get("abstract")
            or ""
        ).strip()

        doi = entry.get("prism:doi") or entry.get("doi") or ""
        pii = entry.get("pii") or ""

        url = (
            entry.get("prism:url")
            or entry.get("link")
            or ""
        )

        if isinstance(url, list):
            # 有些返回的 link 是列表
            url = ""
            for item in entry.get("link", []):
                if isinstance(item, dict):
                    ref = item.get("@ref", "")
                    href = item.get("@href", "")
                    if href and ref in ("scidir", "self", "via", "alternate"):
                        url = href
                        break

        url = str(url).strip()

        # Search API 不一定给 PDF 链接，这里先置空
        pdf_url = ""

        categories: List[str] = []
        for field in ("prism:publicationName", "subtypeDescription", "openaccess"):
            value = entry.get(field)
            if value is not None and str(value).strip():
                categories.append(str(value).strip())

        # 若 url 为空，尽量用 DOI 构造稳定落地页
        if not url and doi:
            url = f"https://doi.org/{doi}"

        # DOI/PII 附加到 categories 里便于后续调试，不影响原逻辑
        if doi:
            categories.append(f"doi:{doi}")
        if pii:
            categories.append(f"pii:{pii}")

        return Paper(
            title=title,
            authors=self._parse_authors(entry),
            abstract=abstract,
            published=published,
            url=url,
            pdf_url=pdf_url,
            categories=categories,
        )

    def query_papers_since(self, query: str, since_date: datetime, max_results: int = 10) -> List[Paper]:
        """
        查询指定日期之后的论文

        说明：
        - Search API 这里采用“关键词检索 + 本地日期过滤”
        - 为了尽量拿到最近论文，会分页抓取少量页并本地排序
        """
        try:
            print(f"  📅 查询条件: {since_date.strftime('%Y-%m-%d %H:%M')} 之后发布的论文")
            print(f"  🔎 ScienceDirect 查询: {query}")

            collected: List[Paper] = []
            seen_keys = set()

            page_size = 25
            max_pages = 4

            for page_idx in range(max_pages):
                start = page_idx * page_size
                params = {
                    "query": query,
                    "start": start,
                    "count": page_size,
                    "httpAccept": "application/json",
                }

                payload = self._request_json(params)
                entries = self._extract_entries(payload)

                if not entries:
                    break

                page_has_recent = False

                for entry in entries:
                    paper = self._entry_to_paper(entry)
                    if not paper:
                        continue

                    paper_dt = None
                    if paper.published:
                        try:
                            paper_dt = datetime.strptime(paper.published, "%Y-%m-%d")
                        except Exception:
                            paper_dt = None

                    if paper_dt and paper_dt >= since_date:
                        page_has_recent = True
                        key = (paper.title, paper.url, paper.published)
                        if key not in seen_keys:
                            seen_keys.add(key)
                            collected.append(paper)

                # 如果这一页一个最近结果都没有，通常再往后也不会更近，提前停
                if not page_has_recent:
                    break

                if len(collected) >= max_results:
                    break

                time.sleep(0.4)

            # 本地按日期降序排序
            def sort_key(p: Paper):
                try:
                    return datetime.strptime(p.published, "%Y-%m-%d")
                except Exception:
                    return datetime.min

            collected.sort(key=sort_key, reverse=True)
            return collected[:max_results]

        except Exception as e:
            print(f"论文查询失败: {e}")
            return []

    def query_papers_today(self, query: str, max_results: int = 10) -> List[Paper]:
        try:
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            return self.query_papers_since(query, today, max_results)
        except Exception as e:
            print(f"论文查询失败: {e}")
            return []

    def query_papers(self, query: str, max_results: int = 10) -> List[Paper]:
        """
        向后兼容：默认查询最近 30 天
        """
        try:
            since_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            return self.query_papers_since(query, since_date, max_results)
        except Exception as e:
            print(f"论文查询失败: {e}")
            return []


class PaperAnalysisAgent:
    """论文分析智能体"""

    def __init__(self, name: str, model_client):
        self.name = name
        self.model = model_client

    async def analyze_paper(self, paper: Paper) -> Dict[str, Any]:
        prompt = f"""
请分析以下学术论文，并提供详细的分析报告：

标题：{paper.title}
作者：{", ".join(paper.authors[:5]) if paper.authors else "未知"}
发表时间：{paper.published}
摘要：{paper.abstract[:1000] if paper.abstract else "无摘要"}
链接：{paper.url}

请提供：
1. 研究目标
2. 研究方法
3. 主要发现
4. 创新点
5. 应用价值

请用中文回答，保持简洁。
"""

        try:
            analysis = await self.model.async_call(prompt)
            return {
                "paper": paper,
                "analysis": analysis,
                "analyzed_at": datetime.now().isoformat(),
            }
        except Exception as e:
            print(f"分析失败: {e}")
            return {
                "paper": paper,
                "analysis": f"分析失败: {str(e)}",
                "analyzed_at": datetime.now().isoformat(),
            }

    async def batch_analyze(self, papers: List[Paper]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for i, paper in enumerate(papers):
            print(f"  正在分析第 {i + 1}/{len(papers)} 篇论文...")
            result = await self.analyze_paper(paper)
            results.append(result)
            await asyncio.sleep(1)
        return results
