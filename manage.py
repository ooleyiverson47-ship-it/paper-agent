# manage.py - 管理脚本
import json
import os
from datetime import datetime
from paper_agent import PaperTracker, LastRunTracker


def show_status():
    """显示当前状态"""
    print("\n" + "=" * 60)
    print("📊 系统状态")
    print("=" * 60)

    tracker = PaperTracker("sent_papers.json")
    stats = tracker.get_stats()
    print(f"\n📚 已发送论文统计:")
    print(f"  总数: {stats['total_sent']} 篇")
    print(f"  最后更新: {stats['last_updated']}")

    last_run_tracker = LastRunTracker("last_run.json")
    last_run = last_run_tracker.get_last_run()
    print(f"\n⏰ 定时任务:")
    if last_run:
        print(f"  上次运行: {last_run.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print(f"  尚未运行")
    print(f"  下次运行: 每天 9:00 和 15:00 (自动)")


def reset_history():
    """重置历史记录"""
    confirm = input("\n⚠️ 确认清空所有历史记录？(y/n): ")
    if confirm.lower() == 'y':
        if os.path.exists("sent_papers.json"):
            os.remove("sent_papers.json")
            print("✅ 已清空发送记录")
        if os.path.exists("last_run.json"):
            os.remove("last_run.json")
            print("✅ 已清空运行时间记录")
        print("✅ 重置完成")


def show_recent():
    """显示最近发送的论文"""
    if not os.path.exists("sent_papers.json"):
        print("没有历史记录")
        return

    with open("sent_papers.json", 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"\n📚 已发送论文统计:")
    print(f"  总数: {data.get('total_count', 0)} 篇")
    print(f"  最后更新: {data.get('last_updated', 'N/A')}")


def main():
    """主菜单"""
    while True:
        print("\n" + "=" * 60)
        print("📚 论文查询系统管理")
        print("=" * 60)
        print("1. 查看状态")
        print("2. 重置历史记录")
        print("3. 查看统计")
        print("4. 退出")

        choice = input("\n请选择 (1-4): ").strip()

        if choice == "1":
            show_status()
        elif choice == "2":
            reset_history()
        elif choice == "3":
            show_recent()
        elif choice == "4":
            break
        else:
            print("无效选择")


if __name__ == "__main__":
    main()