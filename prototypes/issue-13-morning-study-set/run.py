#!/usr/bin/env python3
"""PROTOTYPE TUI for trying Issue 13's daily set allocation."""

from morning_set_model import SCENARIOS, DayPlan, build_plan


BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
CLEAR = "\033[2J\033[H"


def render_slot(slot) -> None:
    print(f"\n{BOLD}{slot.label}{RESET}")
    print(f"課題: {slot.item}")
    print(f"終了: {slot.finish}")


def render(index: int, plan: DayPlan) -> None:
    scenario = SCENARIOS[index]
    print(CLEAR, end="")
    print(f"{BOLD}PROTOTYPE — 毎朝の準備済み学習セット{RESET}")
    print(f"{DIM}問い: 明示状態だけから一件ずつ割り当て、失敗時も安全に縮退できるか{RESET}\n")
    print(f"{BOLD}シナリオ{RESET}: {index + 1}/{len(SCENARIOS)} {scenario.label}")
    print(f"{BOLD}曜日{RESET}: {'平日' if scenario.weekday else '休日'}")
    print(f"{BOLD}状態ファイル{RESET}: {'あり' if scenario.state_exists else 'なし'}")
    print(f"{BOLD}前回セット{RESET}: {'あり' if scenario.previous_set_exists else 'なし'}")
    print(f"{BOLD}本日生成済み{RESET}: {'はい' if scenario.set_generated_today else 'いいえ'}")
    print(f"{BOLD}前回結果{RESET}: {'記録済み' if scenario.previous_result_recorded else '未記録'}")
    print(f"{BOLD}主教材{RESET}: {'利用可' if scenario.material_available else '利用不可'}")
    print(f"{BOLD}問題生成{RESET}: {'利用可' if scenario.generation_available else '失敗'}")
    queue = " / ".join(f"{item.kind}:{item.label}" for item in scenario.queue) or "なし"
    print(f"{BOLD}入力キュー{RESET}: {queue}")
    print(f"\n{BOLD}生成状態{RESET}: {plan.status}")
    print(f"{BOLD}割当て理由{RESET}: {plan.reason}")
    print(f"{BOLD}進捗更新{RESET}: {'明示結果後のみ可' if plan.may_advance else '禁止'}")
    print(f"{BOLD}答えの先取り{RESET}: {'なし' if plan.answers_hidden else '要修正'}")
    render_slot(plan.main)
    render_slot(plan.lunch)
    render_slot(plan.commute)
    render_slot(plan.minimum)
    print(f"\n{BOLD}[1-9]{RESET} シナリオ選択  {BOLD}[n]{RESET} 次へ  {BOLD}[p]{RESET} 前へ  {BOLD}[q]{RESET} 終了")


def main() -> None:
    index = 0
    while True:
        render(index, build_plan(SCENARIOS[index]))
        command = input("\n操作> ").strip().lower()
        if command == "q":
            break
        if command == "n":
            index = (index + 1) % len(SCENARIOS)
        elif command == "p":
            index = (index - 1) % len(SCENARIOS)
        elif command.isdigit() and 1 <= int(command) <= len(SCENARIOS):
            index = int(command) - 1


if __name__ == "__main__":
    main()
