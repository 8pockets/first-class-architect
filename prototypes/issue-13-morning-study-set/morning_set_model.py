"""PROTOTYPE: pure allocation logic for Issue 13's morning study set."""

from dataclasses import dataclass


@dataclass(frozen=True)
class QueueItem:
    key: str
    label: str
    kind: str
    duration: int
    source: str


@dataclass(frozen=True)
class Scenario:
    key: str
    label: str
    weekday: bool
    state_exists: bool = True
    previous_set_exists: bool = True
    set_generated_today: bool = False
    previous_result_recorded: bool = True
    material_available: bool = True
    generation_available: bool = True
    queue: tuple[QueueItem, ...] = ()


@dataclass(frozen=True)
class Slot:
    label: str
    item: str
    finish: str


@dataclass(frozen=True)
class DayPlan:
    status: str
    reason: str
    main: Slot
    lunch: Slot
    commute: Slot
    minimum: Slot
    may_advance: bool
    answers_hidden: bool = True


NEW_ITEM = QueueItem(
    "S-K6-18-SLENDERNESS",
    "全体座屈と細長比",
    "new",
    30,
    "PDF 193ページ「K6. 鉄骨構造-18」",
)

NEXT_ITEM = QueueItem(
    "S-K6-18-ELASTIC-STRENGTH",
    "弾性座屈領域と鋼材強度",
    "new",
    30,
    "PDF 193ページ「K6. 鉄骨構造-18」",
)


def _slot(label: str, item: str, finish: str) -> Slot:
    return Slot(label, item, finish)


def _fallback(concept: str, source_available: bool = True, label: str = "最低5分") -> Slot:
    check = "主教材で1分確認する" if source_available else "1分で『主教材を確認できず』と記録する"
    return _slot(
        label,
        f"{concept}を概念名だけから3分で三点説明し、{check}",
        "残り1分で『自動準備フォールバック・次に行う一件』を一文残す。段階は進めない",
    )


def _empty(label: str, reason: str) -> Slot:
    return _slot(label, "割当てなし", reason)


def _describe(item: QueueItem) -> str:
    return f"{item.label}｜{item.kind}｜{item.duration}分｜{item.source}"


def build_plan(scenario: Scenario) -> DayPlan:
    """Build one answer-free day plan from an explicit snapshot."""
    concept = scenario.queue[0].label if scenario.queue else NEW_ITEM.label
    fallback = _fallback(concept)

    if scenario.set_generated_today:
        return DayPlan(
            "reuse",
            "同日分は既に生成済み。同じセットを再表示し、二重に進捗を作らない",
            _slot("朝30分", "本日生成済みのセットを再利用する", "既存セットの結果だけを一回記録する"),
            _empty("昼5分", "既存セットに書かれた割当てを使う"),
            _empty("通勤（任意）", "既存セットに書かれた任意項目だけを使う"),
            fallback,
            may_advance=False,
        )

    if not scenario.state_exists and scenario.previous_set_exists:
        return DayPlan(
            "fallback",
            "状態ファイルがないが前回セットは残っている。初日に戻さず、状態復旧まで前回セットを再利用する",
            _slot("朝5分フォールバック", "前回セットの概念名だけで3分想起する", "前回セットと状態不在を記録し、段階は進めない"),
            _empty("昼5分", "状態復旧まで正式な再テストを作らない"),
            _empty("通勤（任意）", "必須課題なし"),
            fallback,
            may_advance=False,
        )

    if not scenario.material_available or not scenario.generation_available:
        failure = "主教材を読めない" if not scenario.material_available else "有効な問題を生成・検証できない"
        safe_fallback = _fallback(concept, scenario.material_available, "朝5分フォールバック")
        return DayPlan(
            "fallback",
            f"{failure}。正解や進捗を推測せず、新規学習と正式テストを止める",
            safe_fallback,
            _empty("昼5分", "正式な再テストは作らず、復旧後へ送る"),
            _empty("通勤（任意）", "復旧作業も学習も割り当てない"),
            _fallback(concept, scenario.material_available),
            may_advance=False,
        )

    if not scenario.state_exists:
        return DayPlan(
            "bootstrap",
            "初回起動。履歴を推測せず、事前診断から0日目を作る",
            _slot(
                "朝30分",
                f"{_describe(NEW_ITEM)}。最初の5分は資料なしの事前診断、その後に狭い入力・三点説明・条件変更問題・根拠確認",
                "初回回答と訂正版を分け、次の一件だけを明示する",
            ),
            _empty("昼5分", "0日目は朝の結果確定後に復習日程を作る"),
            _empty("通勤（任意）", "必須課題を置かない"),
            fallback,
            may_advance=True,
        )

    if not scenario.previous_result_recorded:
        return DayPlan(
            "reuse",
            "前回結果が未記録。完了を推測せず、前回項目の再開だけを出す",
            _slot(
                "朝30分",
                f"{concept}の前回セットを開き、未完了工程から再開する。完了済みなら結果一行だけを先に記録する",
                "新規項目へ進まず、前回の状態と次の一件を確定する",
            ),
            _empty("昼5分", "前回結果の確定前は新しい再テストを作らない"),
            _empty("通勤（任意）", "結果確定を通勤へ依存させない"),
            fallback,
            may_advance=False,
        )

    priority = {"relearn": 0, "failed_retest": 1, "overdue": 2, "due": 3, "interrupted": 4, "new": 5}
    queue = tuple(sorted(scenario.queue, key=lambda item: priority.get(item.kind, 99)))
    blockers = tuple(item for item in queue if item.kind in {"relearn", "failed_retest", "overdue", "interrupted"})
    due = tuple(item for item in queue if item.kind == "due")

    if blockers:
        main_item = blockers[0]
        lunch_item = next((item for item in queue if item != main_item and item.duration <= 5), None)
        main = _slot(
            "朝30分",
            _describe(main_item),
            "この一件の根拠確認、結果一行、次の一件まで。新規学習は追加しない",
        )
        lunch = (
            _slot("昼5分", _describe(lunch_item), "制限時間で打ち切り、夜へ送らない")
            if scenario.weekday and lunch_item
            else _empty("昼5分", "休日または二件目の短い課題なし")
        )
        return DayPlan(
            "ready",
            "再学習・翌日再テスト・最古の期限超過を新規学習より優先",
            main,
            lunch,
            _slot("通勤（任意）", "昼の一件だけ。安全に座って文字入力できる場合に限る", "できなくても期限設計を壊さない")
            if scenario.weekday and lunch_item
            else _empty("通勤（任意）", "必須課題なし"),
            fallback,
            may_advance=True,
        )

    if due and not scenario.weekday:
        main_item = due[0]
        return DayPlan(
            "ready",
            "休日は昼・通勤へ置かず、当日期限の一件だけを朝へ移す",
            _slot("朝30分", _describe(main_item), "根拠確認と結果記録まで。新規学習は追加しない"),
            _empty("昼5分", "休日は割り当てない"),
            _empty("通勤（任意）", "休日は割り当てない"),
            fallback,
            may_advance=True,
        )

    main = _slot(
        "朝30分",
        _describe(NEXT_ITEM),
        "遅延想起5分、入力7分、三点説明6分、条件変更問題8分、根拠確認と再生成4分で終了",
    )
    lunch_item = due[0] if due and scenario.weekday else None
    lunch = (
        _slot("昼5分", _describe(lunch_item), "資料・ヒントなしで判定し、夜へ送らない")
        if lunch_item
        else _empty("昼5分", "当日期限の短い再テストなし、または休日")
    )
    return DayPlan(
        "ready",
        "阻害キューなし。当日期限の短い再テストは昼へ分け、朝は新規一件",
        main,
        lunch,
        _slot("通勤（任意）", "昼の一件だけ。安全に座って文字入力できる場合に限る", "できなくても期限設計を壊さない")
        if lunch_item
        else _empty("通勤（任意）", "必須課題なし"),
        fallback,
        may_advance=True,
    )


SCENARIOS = (
    Scenario("bootstrap", "初回・状態も前回セットもなし", weekday=True, state_exists=False, previous_set_exists=False),
    Scenario(
        "due_only",
        "当日期限の3分想起だけ",
        weekday=True,
        queue=(QueueItem("S-K6-18-SLENDERNESS-D1", "全体座屈と細長比", "due", 3, "1日後想起"),),
    ),
    Scenario(
        "backlog",
        "翌日再テストと期限超過が重複",
        weekday=True,
        queue=(
            QueueItem("S-K6-18-ELASTIC-D1R", "弾性座屈領域と鋼材強度", "failed_retest", 5, "翌日・別問題"),
            QueueItem("S-K6-19-LATERAL-D3", "横座屈", "overdue", 5, "3日後条件変更"),
            QueueItem("S-K6-20-LOCAL-D1", "局部座屈と幅厚比", "due", 3, "1日後想起"),
        ),
    ),
    Scenario(
        "unreported",
        "前回結果が未記録",
        weekday=True,
        previous_result_recorded=False,
        queue=(QueueItem("S-K6-19-LATERAL", "横座屈", "interrupted", 30, "PDF 194ページ"),),
    ),
    Scenario(
        "material_missing",
        "主教材が読めない",
        weekday=True,
        material_available=False,
        queue=(QueueItem("S-K6-18-SLENDERNESS", "全体座屈と細長比", "due", 3, "PDF 193ページ"),),
    ),
    Scenario(
        "generation_failed",
        "有効問題を生成できない",
        weekday=True,
        generation_available=False,
        queue=(QueueItem("S-K6-20-LOCAL-D3", "局部座屈と幅厚比", "due", 5, "3日後条件変更"),),
    ),
    Scenario(
        "weekend",
        "休日・期限項目あり",
        weekday=False,
        queue=(QueueItem("S-K6-19-LATERAL-D7", "横座屈", "due", 5, "7日後概念識別"),),
    ),
    Scenario(
        "state_missing",
        "状態ファイル消失・前回セットあり",
        weekday=True,
        state_exists=False,
        previous_set_exists=True,
        queue=(QueueItem("S-K6-19-LATERAL", "横座屈", "interrupted", 30, "前回セット"),),
    ),
    Scenario(
        "duplicate_run",
        "同日二回目の自動実行",
        weekday=True,
        set_generated_today=True,
        queue=(QueueItem("S-K6-18-ELASTIC-D1", "弾性座屈領域と鋼材強度", "due", 3, "1日後想起"),),
    ),
)
