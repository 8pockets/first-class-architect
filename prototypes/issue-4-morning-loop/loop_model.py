"""PROTOTYPE: pure state transitions for Issue #4's 30-minute loop."""

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Step:
    key: str
    label: str
    minutes: int
    output: str


STEPS = (
    Step("delayed_retrieval", "遅延想起", 5, "前回内容の原理・条件を資料なしで想起"),
    Step("narrow_input", "狭いインプット", 7, "新しい原理1つと代表例1つを特定"),
    Step("self_explanation", "資料なしの説明", 6, "理由・効く条件・類似概念との差を説明"),
    Step("diagnostic_application", "診断・変形問題", 8, "条件を変えた結論と理由を生成"),
    Step("feedback_regeneration", "根拠確認と再説明", 4, "差の原因を確認し、閉じて正しく再説明"),
)


@dataclass(frozen=True)
class SessionState:
    prepared: bool = True
    status: str = "ready"
    step_index: int = 0
    elapsed_minutes: int = 0
    outputs: tuple[str, ...] = ()
    gaps: tuple[str, ...] = ()
    diagnostic_mode: str = "通常の診断問題"

    @property
    def current_step(self) -> Step | None:
        if self.status == "running" and self.step_index < len(STEPS):
            return STEPS[self.step_index]
        return None


def transition(state: SessionState, action: str) -> SessionState:
    """Return the next state without doing terminal I/O."""
    if action == "reset":
        return SessionState()

    if action == "unprepared" and state.status == "ready":
        return replace(state, prepared=False, status="blocked")

    if action == "prepare" and state.status in {"ready", "blocked"}:
        return replace(state, prepared=True, status="ready")

    if action == "next" and state.status == "ready" and state.prepared:
        return replace(state, status="running")

    step = state.current_step
    if step is None:
        return state

    if action == "memorized" and step.key == "diagnostic_application":
        return replace(
            state,
            diagnostic_mode="条件反転・誤文訂正・類似概念との比較",
            gaps=state.gaps + ("元の過去問は答えを記憶していた",),
        )

    if action not in {"next", "gap"}:
        return state

    outputs = state.outputs
    gaps = state.gaps
    if action == "next":
        output = step.output
        if step.key == "diagnostic_application" and state.diagnostic_mode != "通常の診断問題":
            output = f"{state.diagnostic_mode}で新しい判断を生成"
        outputs = outputs + (output,)
    else:
        gaps = gaps + (f"{step.label}で必要なアウトプットを生成できなかった",)

    next_index = state.step_index + 1
    status = "complete" if next_index == len(STEPS) else "running"
    return replace(
        state,
        status=status,
        step_index=next_index,
        elapsed_minutes=state.elapsed_minutes + step.minutes,
        outputs=outputs,
        gaps=gaps,
    )
