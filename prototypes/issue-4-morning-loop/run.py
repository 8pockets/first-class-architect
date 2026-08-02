#!/usr/bin/env python3
"""PROTOTYPE TUI for trying Issue #4's proposed morning loop by hand."""

import os

from loop_model import STEPS, SessionState, transition


BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def clear() -> None:
    os.system("clear")


def render(state: SessionState) -> None:
    clear()
    print(f"{BOLD}PROTOTYPE — 朝30分の基本学習ループ{RESET}")
    print(f"{DIM}問い: 固定順序で本質理解に必要なアウトプットを30分内に残せるか{RESET}\n")
    print(f"{BOLD}状態{RESET}: {state.status}")
    print(f"{BOLD}学習セット{RESET}: {'準備済み' if state.prepared else '未準備'}")
    print(f"{BOLD}経過時間{RESET}: {state.elapsed_minutes} / 30分")

    step = state.current_step
    if step:
        print(f"{BOLD}現在工程{RESET}: {step.label}（{step.minutes}分）")
        print(f"{BOLD}診断モード{RESET}: {state.diagnostic_mode}")
    elif state.status == "ready":
        print(f"{BOLD}現在工程{RESET}: 準備済みセットを開いて開始する")
    elif state.status == "blocked":
        print(f"{BOLD}現在工程{RESET}: 教材選びから必要なため開始できない")
    else:
        print(f"{BOLD}現在工程{RESET}: 完了")

    print(f"\n{BOLD}得られたアウトプット{RESET}")
    if state.outputs:
        for output in state.outputs:
            print(f"- {output}")
    else:
        print(f"{DIM}- まだなし{RESET}")

    print(f"\n{BOLD}未解決・持ち越し{RESET}")
    if state.gaps:
        for gap in state.gaps:
            print(f"- {gap}")
    else:
        print(f"{DIM}- なし{RESET}")

    print(f"\n{BOLD}30分の仮配分{RESET}")
    print("  ".join(f"{item.label} {item.minutes}分" for item in STEPS))

    print(f"\n{BOLD}[n]{RESET} 成功して次へ  {BOLD}[g]{RESET} 生成できず次へ", end="")
    if step and step.key == "diagnostic_application":
        print(f"  {BOLD}[m]{RESET} 過去問の答えを記憶していた", end="")
    if state.status in {"ready", "blocked"}:
        print(f"  {BOLD}[u]{RESET} 学習セット未準備  {BOLD}[p]{RESET} 準備済みにする", end="")
    print(f"  {BOLD}[r]{RESET} 最初から  {BOLD}[q]{RESET} 終了")


def main() -> None:
    state = SessionState()
    commands = {
        "n": "next",
        "g": "gap",
        "m": "memorized",
        "u": "unprepared",
        "p": "prepare",
        "r": "reset",
    }
    while True:
        render(state)
        command = input("\n操作> ").strip().lower()
        if command == "q":
            break
        state = transition(state, commands.get(command, "unknown"))


if __name__ == "__main__":
    main()
