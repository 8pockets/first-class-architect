#!/usr/bin/env python3
"""PROTOTYPE TUI for trying Issue 9's minimal error record."""

from error_record_model import CAUSE_BY_KEY, CAUSES, SCENARIOS, PrototypeState, transition


BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
CLEAR = "\033[2J\033[H"


def render(state: PrototypeState) -> None:
    print(CLEAR, end="")
    print(f"{BOLD}PROTOTYPE — 誤答を次の学習へ変える最小記録{RESET}")
    print(f"{DIM}問い: 主原因1つ＋差分1文から、次の一件を迷わず決められるか{RESET}\n")
    print(f"{BOLD}進行{RESET}: {len(state.records)} / {len(SCENARIOS)} ケース記録済み")

    scenario = state.current_scenario
    if scenario:
        print(f"\n{BOLD}ケース{RESET}: {scenario.label}")
        print(f"{BOLD}観測{RESET}: {scenario.observation}")
        if state.cause:
            cause = state.cause
            matched = "一致" if cause.key == scenario.expected_cause else "不一致"
            learner_result = "数える" if cause.counts_as_learner_failure else "数えない"
            evidence_label = "無効理由" if cause.key == "invalid_problem" else "観測差分"
            print(f"\n{BOLD}選択した主原因{RESET}: {cause.label}（想定分類と{matched}）")
            print(f"{BOLD}診断境界{RESET}: {cause.diagnostic}")
            print(f"{BOLD}このケースの確認点{RESET}: {scenario.reason}")
            print(f"{BOLD}当日の訂正{RESET}: {cause.immediate_action}")
            print(f"{BOLD}次の一件{RESET}: {cause.next_action}")
            print(f"{BOLD}学習者の失敗回数{RESET}: {learner_result}")
            print(f"{BOLD}{evidence_label}1文{RESET}: {state.evidence or '未入力'}")
    else:
        print(f"\n{BOLD}全ケースの試行完了{RESET}")

    print(f"\n{BOLD}試行結果{RESET}")
    if state.records:
        scenario_by_key = {item.key: item for item in SCENARIOS}
        for record in state.records:
            cause = CAUSE_BY_KEY[record.cause_key]
            match = "✓" if record.matched_expected else "要見直し"
            print(f"- {scenario_by_key[record.scenario_key].label} | {cause.label} | {record.evidence} | {match}")
    else:
        print(f"{DIM}- まだなし{RESET}")

    if scenario:
        print(f"\n{BOLD}原因選択{RESET}")
        for index, cause in enumerate(CAUSES, start=1):
            print(f"[{index}] {cause.label}", end="  ")
        if state.phase == "review":
            print(f"\n{BOLD}[e]{RESET} 差分1文を入力  {BOLD}[n]{RESET} 記録して次へ", end="")
    print(f"  {BOLD}[r]{RESET} 最初から  {BOLD}[q]{RESET} 終了")


def main() -> None:
    state = PrototypeState()
    while True:
        render(state)
        command = input("\n操作> ").strip().lower()
        if command == "q":
            break
        if command == "e" and state.phase == "review":
            label = "無効理由" if state.selected_cause == "invalid_problem" else "観測差分"
            evidence = input(f"{label}（1文）> ")
            state = transition(state, "evidence", evidence)
            continue
        if command.isdigit() and 1 <= int(command) <= len(CAUSES):
            state = transition(state, f"select:{CAUSES[int(command) - 1].key}")
            continue
        actions = {"n": "next", "r": "reset"}
        state = transition(state, actions.get(command, "unknown"))


if __name__ == "__main__":
    main()
