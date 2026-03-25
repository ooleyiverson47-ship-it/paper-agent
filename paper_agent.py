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
    title: str
    authors: List[str]
    abstract: str
    published: str
    url: str
    pdf_url: str
    categories: List[str]


class LastRunTracker:
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
            "input": {"messages": [{"role": "user", "content": prompt}]},
            "parameters": {"result_format": "message"},
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


class ScopusAPIError(Exception):
    pass


class PaperQueryAgent:
    """基于 Scopus Search API 的论文查询智能体"""

    def __init__(self, name: str, model_client):
        self.name = name
        self.model = model_client

        self.api_key = os.getenv("SCOPUS_API_KEY", "").strip()
        self.insttoken = os.getenv("ELSEVIER_INSTTOKEN", "").strip()

        if not self.api_key:
            raise ValueError("未设置 SCOPUS_API_KEY 环境变量")

        self.base_url = "https://api.elsevier.com/content/search/scopus"
        self.session = requests.Session()
        print("✅ Scopus 查询客户端初始化成功")

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/json",
            "X-ELS-APIKey": self.api_key,
        }
        if self.insttoken:
            headers["X-ELS-Insttoken"] = self.insttoken
        return headers

    def _request_json(self, params: Dict[str, Any]) -> Dict[str, Any]:
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
                    print(f"⚠️ Scopus 限流，{wait_s} 秒后重试...")
                    time.sleep(wait_s)
                    continue

                if response.status_code in (401, 403):
                    raise ScopusAPIError(
                        f"Scopus 鉴权/授权失败，HTTP {response.status_code}。"
                        "请检查 API Key、机构 IP / Insttoken 或订阅权限。"
                    )

                response.raise_for_status()
                return response.json()

            except Exception as e:
                last_error = e
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))

        raise ScopusAPIError(f"Scopus API 请求失败: {last_error}")

    def _extract_entries(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        if isinstance(payload, dict):
            sr = payload.get("search-results", {})
            entries = sr.get("entry", [])
            if isinstance(entries, list):
                return entries
        return []

    def _parse_date(self, entry: Dict[str, Any]) -> Optional[datetime]:
        candidates = [
            entry.get("prism:coverDate"),
            entry.get("coverDate"),
            entry.get("dc:date"),
        ]
        for value in candidates:
            if not value:
                continue
            try:
                return datetime.strptime(str(value)[:10], "%Y-%m-%d")
            except Exception:
                continue
        return None

    def _parse_authors(self, entry: Dict[str, Any]) -> List[str]:
        authors: List[str] = []
        creator = entry.get("dc:creator")
        if creator:
            authors.append(str(creator).strip())
        return authors

    def _extract_best_url(self, entry: Dict[str, Any], doi: str) -> str:
        """
        给邮件里的“查看原文”找一个尽量适合人点击的链接。

        优先级：
        1. DOI 落地页
        2. link 里 ref=scidir / doi / scopus / alternate / self
        3. prism:url
        4. 空字符串
        """
        if doi:
            return f"https://doi.org/{doi}"

        preferred = {
            "scidir": "",
            "doi": "",
            "scopus": "",
            "alternate": "",
            "self": "",
        }
        fallback = ""

        links = entry.get("link", [])
        if isinstance(links, list):
            for item in links:
                if not isinstance(item, dict):
                    continue
                ref = str(item.get("@ref", "")).strip().lower()
                href = str(item.get("@href", "")).strip()
                if not href:
                    continue
                if not fallback:
                    fallback = href
                if ref in preferred and not preferred[ref]:
                    preferred[ref] = href

        for key in ("scidir", "doi", "scopus", "alternate", "self"):
            if preferred[key]:
                return preferred[key]

        prism_url = str(entry.get("prism:url", "")).strip()
        if prism_url:
            return prism_url

        return fallback

    def _extract_pdf_url(self, entry: Dict[str, Any]) -> str:
        """
        Scopus Search 结果通常不稳定提供可直接下载的 PDF 链接。
        这里仅在明确出现 pdf 标记链接时才返回，否则留空。
        """
        links = entry.get("link", [])
        if isinstance(links, list):
            for item in links:
                if not isinstance(item, dict):
                    continue
                ref = str(item.get("@ref", "")).strip().lower()
                href = str(item.get("@href", "")).strip()
                if not href:
                    continue
                if "pdf" in ref or href.lower().endswith(".pdf"):
                    return href
        return ""

    def _entry_to_paper(self, entry: Dict[str, Any]) -> Optional[Paper]:
        title = (entry.get("dc:title") or "").strip()
        if not title:
            return None

        published_dt = self._parse_date(entry)
        published = published_dt.strftime("%Y-%m-%d") if published_dt else ""

        abstract = (entry.get("dc:description") or "").strip()
        doi = str(entry.get("prism:doi") or "").strip()
        eid = str(entry.get("eid") or "").strip()
        subtype = str(entry.get("subtypeDescription") or "").strip()
        source = str(entry.get("prism:publicationName") or "").strip()

        url = self._extract_best_url(entry, doi)
        pdf_url = self._extract_pdf_url(entry)

        categories: List[str] = []
        if source:
            categories.append(source)
        if subtype:
            categories.append(subtype)
        if doi:
            categories.append(f"doi:{doi}")
        if eid:
            categories.append(f"eid:{eid}")

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
        try:
            print(f"  📅 查询条件: {since_date.strftime('%Y-%m-%d %H:%M')} 之后发布的论文")
            print(f"  🔎 Scopus 查询: {query}")

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
                    "sort": "-coverDate",
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

                if not page_has_recent:
                    break

                if len(collected) >= max_results:
                    break

                time.sleep(0.4)

            collected.sort(
                key=lambda p: datetime.strptime(p.published, "%Y-%m-%d") if p.published else datetime.min,
                reverse=True,
            )
            return collected[:max_results]

        except Exception as e:
            print(f"论文查询失败: {e}")
            return []

    def query_papers_today(self, query: str, max_results: int = 10) -> List[Paper]:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return self.query_papers_since(query, today, max_results)

    def query_papers(self, query: str, max_results: int = 10) -> List[Paper]:
        since_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return self.query_papers_since(query, since_date, max_results)


class PaperAnalysisAgent:
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
        results = []
        for i, paper in enumerate(papers):
            print(f"  正在分析第 {i + 1}/{len(papers)} 篇论文...")
            result = await self.analyze_paper(paper)
            results.append(result)
            await asyncio.sleep(1)
        return results
