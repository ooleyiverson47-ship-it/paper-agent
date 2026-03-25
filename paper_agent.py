class PaperQueryAgent:
    """论文查询智能体"""

    def __init__(self, name: str, model_client):
        self.name = name
        self.model = model_client
        self.arxiv_client = arxiv.Client()

    def query_papers_since(self, query: str, since_date: datetime, max_results: int = 10) -> List[Paper]:
        """查询指定日期之后发布的论文"""
        try:
            print(f"  📅 查询条件: {since_date.strftime('%Y-%m-%d %H:%M')} 之后发布的论文")

            # 不把 submittedDate 直接拼进 arXiv query
            # 先按关键词查，再在本地按时间过滤
            search = arxiv.Search(
                query=query,
                max_results=max_results * 5,
                sort_by=arxiv.SortCriterion.SubmittedDate
            )

            papers = []
            for result in self.arxiv_client.results(search):
                published_dt = result.published.replace(tzinfo=None)

                # 已按时间降序，遇到更早的结果可直接停止
                if published_dt < since_date:
                    break

                paper = Paper(
                    title=result.title,
                    authors=[author.name for author in result.authors],
                    abstract=result.summary,
                    published=result.published.strftime("%Y-%m-%d"),
                    url=result.entry_id,
                    pdf_url=result.pdf_url,
                    categories=result.categories
                )
                papers.append(paper)

                if len(papers) >= max_results:
                    break

            return papers

        except Exception as e:
            print(f"论文查询失败: {e}")
            return []

    def query_papers_today(self, query: str, max_results: int = 10) -> List[Paper]:
        """查询今天发布的论文"""
        try:
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            return self.query_papers_since(query, today, max_results)
        except Exception as e:
            print(f"论文查询失败: {e}")
            return []

    def query_papers(self, query: str, max_results: int = 10) -> List[Paper]:
        """普通查询（向后兼容）"""
        try:
            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.SubmittedDate
            )

            papers = []
            for result in self.arxiv_client.results(search):
                paper = Paper(
                    title=result.title,
                    authors=[author.name for author in result.authors],
                    abstract=result.summary,
                    published=result.published.strftime("%Y-%m-%d"),
                    url=result.entry_id,
                    pdf_url=result.pdf_url,
                    categories=result.categories
                )
                papers.append(paper)

            return papers

        except Exception as e:
            print(f"论文查询失败: {e}")
            return []
