# config.py
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    MODEL_NAME = os.getenv("MODEL_NAME", "gpt-3.5-turbo")

    # 论文查询配置
    DEFAULT_MAX_RESULTS = 10
    MAX_ABSTRACT_LENGTH = 2000

    # 定时任务配置
    QUERY_SCHEDULES = [
        {"query": "machine learning OR deep learning", "time": "09:00", "max_results": 10},
        {"query": "computer vision OR image recognition", "time": "15:00", "max_results": 10},
        {"query": "natural language processing OR NLP", "time": "21:00", "max_results": 5}
    ]