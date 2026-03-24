# manage_history.py
import json
import os
from datetime import datetime


class PaperHistoryManager:
    """管理已发送论文历史"""

    def __init__(self, history_file="sent_papers.json"):
        self.history_file = history_file

    def show_stats(self):
        """显示统计信息"""
        if not os.path.exists(self.history_file):
            print("没有历史记录文件")
            return

        with open(self.history_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        print(f"\n{'=' * 50}")
        print("已发送论文统计")
        print(f"{'=' * 50}")
        print(f"最后更新: {data.get('last_updated', 'N/A')}")
        print(f"已发送总数: {data.get('total_count', 0)}")
        print(f"{'=' * 50}")

    def clear_history(self):
        """清空历史记录"""
        if os.path.exists(self.history_file):
            os.remove(self.history_file)
            print("✅ 历史记录已清空")
        else:
            print("没有历史记录文件")

    def export_history(self, output_file="history_export.json"):
        """导出历史记录"""
        if os.path.exists(self.history_file):
            import shutil
            shutil.copy(self.history_file, output_file)
            print(f"✅ 历史记录已导出到: {output_file}")
        else:
            print("没有历史记录文件")

    def show_recent(self, limit=10):
        """显示最近的论文"""
        if not os.path.exists(self.history_file):
            print("没有历史记录文件")
            return

        with open(self.history_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        papers = data.get('sent_papers', [])
        print(f"\n最近 {min(limit, len(papers))} 篇论文ID:")
        for i, pid in enumerate(papers[-limit:], 1):
            print(f"  {i}. {pid}")


def main():
    """管理界面"""
    manager = PaperHistoryManager()

    while True:
        print("\n" + "=" * 50)
        print("论文历史记录管理")
        print("=" * 50)
        print("1. 查看统计信息")
        print("2. 清空历史记录（重新发送所有论文）")
        print("3. 导出历史记录")
        print("4. 查看最近论文")
        print("5. 退出")

        choice = input("\n请选择 (1-5): ").strip()

        if choice == "1":
            manager.show_stats()
        elif choice == "2":
            confirm = input("确认清空所有历史记录？(y/n): ")
            if confirm.lower() == 'y':
                manager.clear_history()
        elif choice == "3":
            manager.export_history()
        elif choice == "4":
            manager.show_recent()
        elif choice == "5":
            break
        else:
            print("无效选择")


if __name__ == "__main__":
    main()