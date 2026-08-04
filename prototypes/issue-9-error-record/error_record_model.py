"""PROTOTYPE: pure state transitions for Issue 9's error-record model."""

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Cause:
    key: str
    label: str
    diagnostic: str
    immediate_action: str
    next_action: str
    counts_as_learner_failure: bool = True


CAUSES = (
    Cause(
        "knowledge_gap",
        "知識欠落",
        "学習範囲に含まれる必要な原理・式・用語を、手掛かり後も説明できない",
        "主教材の原理1つと代表例1つへ戻り、閉じて三点説明する",
        "翌日、同じ段階の別問題で再テストする",
    ),
    Cause(
        "causal_misunderstanding",
        "因果誤解",
        "用語は知っているが、原因から結論までの向きまたはつながりが誤っている",
        "主教材で因果の一段ずつを確認し、逆条件も含めて訂正版を生成する",
        "因果の一箇所だけを変えた単一条件変更問題を解く",
    ),
    Cause(
        "condition_misread",
        "条件誤認",
        "原理は説明できるが、成立条件・例外・適用する条件を見落とすか取り違えた",
        "適用する条件と適用しない条件を対にして訂正する",
        "混同した条件を使う概念識別問題を解く",
    ),
    Cause(
        "retrieval_failure",
        "想起失敗",
        "資料なしでは出なかったが、最小の手掛かり後は概念的な訂正なしに説明できた",
        "追加の読み込みをせず、概念名だけから三点説明を再生成する",
        "翌日、概念名だけを手掛かりに3分で三点説明する",
    ),
    Cause(
        "transfer_failure",
        "転移失敗",
        "既知の例は説明できるが、条件や表現が変わると原理を選択・適用できなかった",
        "元問題と変形問題で、変わった条件と固定条件だけを比較する",
        "同じ転移段階の、答えが異なる別問題を解く",
    ),
    Cause(
        "execution_slip",
        "処理ミス",
        "原理選択と説明は正しいが、計算・読解・転記・マークの操作だけを誤った",
        "誤った操作を一箇所だけ訂正し、再発防止の確認点を一つ決める",
        "同型の別問題を一問だけ解く。繰り返す場合は確認手順を学び直す",
    ),
    Cause(
        "needs_diagnosis",
        "要再診断",
        "未合格の事実はあるが、現在の観測だけでは主原因を一つに決められない",
        "原因を推測せず、確認できた未合格状態だけを残す",
        "次の枠で、候補を分ける3分の診断質問を一問だけ行う",
    ),
    Cause(
        "invalid_problem",
        "問題無効",
        "複数解、条件不足、主教材との不一致、未学習知識の要求が問題側にある",
        "学習者の誤答記録を作らず、作問条件を修正する",
        "修正した別問題で同じ段階をやり直す",
        counts_as_learner_failure=False,
    ),
)

CAUSE_BY_KEY = {cause.key: cause for cause in CAUSES}


@dataclass(frozen=True)
class Scenario:
    key: str
    label: str
    observation: str
    expected_cause: str
    reason: str


SCENARIOS = (
    Scenario(
        "unknown_formula",
        "必要な式を知らない",
        "診断問題で細長比を求められたが、λ = Lk / i という学習範囲の式を、式名を示されても説明できなかった。",
        "knowledge_gap",
        "学習済み範囲にある必要知識そのものが欠けている。",
    ),
    Scenario(
        "reversed_relation",
        "因果の向きを逆にした",
        "λ = Lk / i は書けたが、『iが大きいほどλも大きくなり、座屈しにくい』と説明した。",
        "causal_misunderstanding",
        "式の要素は知っているが、iからλ、λから座屈までの因果方向が崩れている。",
    ),
    Scenario(
        "missed_boundary",
        "適用条件を見落とした",
        "鋼材強度を上げれば許容圧縮応力度は必ず上がると答え、弾性座屈領域という条件を見落とした。原理は確認後に説明できた。",
        "condition_misread",
        "一般化できない領域条件の識別で崩れている。",
    ),
    Scenario(
        "blank_then_recall",
        "白紙では出なかった",
        "概念名だけでは無回答だったが、『細長比』という手掛かり後、資料を見ずに式・因果・条件を正しく説明できた。",
        "retrieval_failure",
        "知識の訂正は不要で、手掛かりなしの生成だけが失敗している。",
    ),
    Scenario(
        "remembered_original",
        "元問題だけ正答した",
        "見覚えのある過去問には正答し理由も言えたが、断面二次半径だけを変えた問題で使う原理を選べなかった。",
        "transfer_failure",
        "既知例の再生ではなく、変わった条件への適用で崩れている。",
    ),
    Scenario(
        "arithmetic_only",
        "計算だけ誤った",
        "λ = Lk / i の選択と大小関係の説明は正しかったが、1200 / 20 を80と計算した。",
        "execution_slip",
        "原理と条件は保たれ、算術操作だけが誤っている。",
    ),
    Scenario(
        "blank_without_followup",
        "白紙のまま時間切れになった",
        "資料なしでは無回答だったが、時間切れで手掛かり後の説明も主教材確認も行っておらず、知識がないのか想起できないだけか分からない。",
        "needs_diagnosis",
        "現在の証拠だけで知識欠落または想起失敗へ決めると推測になる。",
    ),
    Scenario(
        "missing_fixed_condition",
        "問題文の条件が不足した",
        "二つの圧縮材を比較する問題で、座屈長さと鋼種が同じか示されておらず、主教材から結論を一つに決められない。",
        "invalid_problem",
        "学習者側ではなく作問側の条件不足である。",
    ),
)


@dataclass(frozen=True)
class ReviewRecord:
    scenario_key: str
    cause_key: str
    evidence: str
    matched_expected: bool


@dataclass(frozen=True)
class PrototypeState:
    scenario_index: int = 0
    phase: str = "classify"
    selected_cause: str = ""
    evidence: str = ""
    records: tuple[ReviewRecord, ...] = ()

    @property
    def current_scenario(self) -> Scenario | None:
        if self.scenario_index < len(SCENARIOS):
            return SCENARIOS[self.scenario_index]
        return None

    @property
    def cause(self) -> Cause | None:
        return CAUSE_BY_KEY.get(self.selected_cause)


def transition(state: PrototypeState, action: str, value: str = "") -> PrototypeState:
    """Return the next state without terminal I/O."""
    if action == "reset":
        return PrototypeState()

    scenario = state.current_scenario
    if scenario is None:
        return state

    if action.startswith("select:"):
        cause_key = action.split(":", 1)[1]
        if cause_key in CAUSE_BY_KEY:
            return replace(state, phase="review", selected_cause=cause_key)

    if action == "evidence" and state.phase == "review" and value.strip():
        return replace(state, evidence=value.strip())

    if action == "next" and state.phase == "review" and state.cause and state.evidence:
        record = ReviewRecord(
            scenario_key=scenario.key,
            cause_key=state.selected_cause,
            evidence=state.evidence,
            matched_expected=state.selected_cause == scenario.expected_cause,
        )
        next_index = state.scenario_index + 1
        return replace(
            state,
            scenario_index=next_index,
            phase="complete" if next_index == len(SCENARIOS) else "classify",
            selected_cause="",
            evidence="",
            records=state.records + (record,),
        )

    return state
