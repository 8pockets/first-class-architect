"""PROTOTYPE: pure state transitions for Issue #6's transfer-test ladder."""

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class TestCase:
    key: str
    label: str
    prompt: str
    hint: str
    checkpoints: tuple[str, str, str]


CASES = (
    TestCase(
        "condition_change",
        "単一条件変更",
        "同じ鋼種・座屈長さの圧縮材AとBがある。Bだけ断面二次半径 i が大きい。どちらが座屈しにくいか。結論・理由・効いている条件を答える。",
        "細長比 λ = Lk / i の関係を使う。",
        (
            "Bの方が座屈しにくいという結論",
            "iが大きいと細長比λが小さくなり、座屈しにくくなるという因果",
            "変えた条件はiで、鋼種と座屈長さLkは同じだと特定",
        ),
    ),
    TestCase(
        "counterexample",
        "反例",
        "『鋼材をSN400からSN490へ変えれば、圧縮材の許容圧縮応力度は常に大きくなる』という主張が成り立たない条件を示し、理由を説明する。",
        "限界細長比より大きい領域で、何が耐力を決めるかを考える。",
        (
            "『常に大きくなる』とはいえないという結論",
            "弾性座屈領域では許容圧縮応力度がEとλで決まり、材の強度に依存しないという理由",
            "細長比λが限界細長比Λ以上という反例条件",
        ),
    ),
    TestCase(
        "discrimination",
        "概念識別",
        "部材長さと補剛条件は同じまま、板要素の幅 b だけを大きくし、厚さ t は変えなかった。直接高まるのは全体座屈・横座屈・局部座屈のどの危険か。理由と識別条件を答える。",
        "変化した比が、部材全体と板要素のどちらを表すかを考える。",
        (
            "局部座屈の危険が直接高まるという結論",
            "幅厚比b/tが大きくなり、板要素が局部座屈しやすくなるという理由",
            "部材長さ・補剛条件ではなく板要素の幅厚比が変わったと識別",
        ),
    ),
    TestCase(
        "unseen_integration",
        "初見統合",
        "等間隔に横補剛された同じ梁せいのH形鋼で、鋼材をSN400からSN490へ変えると同時にフランジ幅も大きくした。横補剛材の必要本数が必ず増えるか、減るか、与えられた情報だけでは決められないか。理由を答える。",
        "鋼材強度とフランジ幅は、必要本数へ同じ向きに効くかを考える。",
        (
            "与えられた情報だけでは増減を決められないという結論",
            "高強度化は必要本数を増やす方向、フランジ幅増加は減らす方向で、効果が競合するという理由",
            "鋼材強度とフランジ幅の2条件、および比較に必要な定量情報の不足を特定",
        ),
    ),
)


@dataclass(frozen=True)
class Attempt:
    case_key: str
    passed: bool
    assisted: bool
    criteria: tuple[bool, bool, bool]


@dataclass(frozen=True)
class TransferState:
    case_index: int = 0
    phase: str = "answering"
    remembered_original: bool = False
    response: str = ""
    assisted: bool = False
    criteria: tuple[bool, bool, bool] = (False, False, False)
    attempts: tuple[Attempt, ...] = ()

    @property
    def current_case(self) -> TestCase | None:
        if self.case_index < len(CASES):
            return CASES[self.case_index]
        return None


def transition(state: TransferState, action: str, value: str = "") -> TransferState:
    """Return the next state without terminal I/O."""
    if action == "reset":
        return TransferState()

    if action == "remembered" and state.case_index == 0:
        return replace(state, remembered_original=not state.remembered_original)

    case = state.current_case
    if case is None:
        return state

    if action == "hint" and state.phase == "answering":
        return replace(state, assisted=True)

    if action == "submit" and state.phase == "answering" and value.strip():
        return replace(state, response=value.strip(), phase="scoring")

    if action.startswith("criterion_") and state.phase == "scoring":
        index = int(action[-1]) - 1
        criteria = list(state.criteria)
        criteria[index] = not criteria[index]
        return replace(state, criteria=tuple(criteria))

    if action == "next" and state.phase == "scoring":
        passed = all(state.criteria) and not state.assisted
        attempt = Attempt(case.key, passed, state.assisted, state.criteria)
        next_index = state.case_index + 1
        return replace(
            state,
            case_index=next_index,
            phase="complete" if next_index == len(CASES) else "answering",
            response="",
            assisted=False,
            criteria=(False, False, False),
            attempts=state.attempts + (attempt,),
        )

    return state


def transfer_status(state: TransferState) -> str:
    """Summarise only the strongest consecutively demonstrated level."""
    passed = {attempt.case_key: attempt.passed for attempt in state.attempts}
    if not passed:
        return "未判定"
    if not passed.get("condition_change", False):
        return "元問題の記憶を超えた理解は未確認"
    if not passed.get("counterexample", False) or not passed.get("discrimination", False):
        return "単一条件の近い転移まで確認"
    if not passed.get("unseen_integration", False):
        return "反例と概念境界まで確認"
    return "初見統合まで確認（パイロットの仮判定）"
