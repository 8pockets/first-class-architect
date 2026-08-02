#!/usr/bin/env python3
"""PROTOTYPE TUI for trying Issue #6's transfer-test ladder."""

import os

from transfer_model import CASES, TransferState, transfer_status, transition


BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def clear() -> None:
    os.system("clear")


def mark(value: bool) -> str:
    return "✓" if value else "·"


def render(state: TransferState) -> None:
    clear()
    print(f"{BOLD}PROTOTYPE — 過去問暗記を見抜く転移テスト{RESET}")
    print(f"{DIM}問い: 段階問題と三点判定で、答えの記憶と転移を区別できるか{RESET}\n")
    print(f"{BOLD}元問題の答えを記憶{RESET}: {'はい' if state.remembered_original else 'いいえ／未指定'}")
    print(f"{BOLD}現在の判定{RESET}: {transfer_status(state)}")
    print(f"{BOLD}進行{RESET}: {len(state.attempts)} / {len(CASES)} 問完了")

    case = state.current_case
    if case:
        print(f"\n{BOLD}問題型{RESET}: {case.label}")
        print(f"{BOLD}問題{RESET}: {case.prompt}")
        if state.assisted:
            print(f"{BOLD}ヒント使用{RESET}: {case.hint}")
        else:
            print(f"{BOLD}ヒント使用{RESET}: なし")

        if state.phase == "answering":
            print(f"\n{DIM}資料を見ずに回答し、[a]で入力する。ヒント使用後の正答は合格扱いにしない。{RESET}")
        else:
            print(f"\n{BOLD}回答{RESET}: {state.response}")
            print(f"\n{BOLD}主教材で確認する3点{RESET}")
            labels = ("結論", "理由", "効いている条件")
            for index, (label, checkpoint) in enumerate(zip(labels, case.checkpoints), start=1):
                print(f"[{mark(state.criteria[index - 1])}] {index}. {label}: {checkpoint}")
    else:
        print(f"\n{BOLD}全問題型の試行完了{RESET}")

    print(f"\n{BOLD}結果{RESET}")
    if state.attempts:
        case_by_key = {item.key: item for item in CASES}
        for attempt in state.attempts:
            result = "合格" if attempt.passed else "未合格"
            assist = "・ヒントあり" if attempt.assisted else ""
            print(f"- {case_by_key[attempt.case_key].label}: {result}{assist}")
    else:
        print(f"{DIM}- まだなし{RESET}")

    print(f"\n{BOLD}[m]{RESET} 元問題を記憶していた", end="")
    if case and state.phase == "answering":
        print(f"  {BOLD}[a]{RESET} 回答する  {BOLD}[h]{RESET} ヒントを見る", end="")
    if case and state.phase == "scoring":
        print(f"  {BOLD}[1]{RESET} 結論  {BOLD}[2]{RESET} 理由  {BOLD}[3]{RESET} 条件  {BOLD}[n]{RESET} 判定して次へ", end="")
    print(f"  {BOLD}[r]{RESET} 最初から  {BOLD}[q]{RESET} 終了")


def main() -> None:
    state = TransferState()
    while True:
        render(state)
        command = input("\n操作> ").strip().lower()
        if command == "q":
            break
        if command == "a" and state.phase == "answering":
            response = input("回答> ")
            state = transition(state, "submit", response)
            continue
        actions = {
            "m": "remembered",
            "h": "hint",
            "1": "criterion_1",
            "2": "criterion_2",
            "3": "criterion_3",
            "n": "next",
            "r": "reset",
        }
        state = transition(state, actions.get(command, "unknown"))


if __name__ == "__main__":
    main()
