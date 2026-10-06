"""Original accessible schematics, never reproductions of exam artwork.

Figure IDs are versioned because a changed figure is a changed question.
"""

FIGURE_IDS = frozenset({"hysteresis-loops-v1", "brace-loops-v1"})


def question_figure(figure: str | None) -> str:
    if figure is None:
        return ""
    if figure not in FIGURE_IDS:
        raise ValueError(f"Unknown question figure: {figure}")
    if figure == 'brace-loops-v1':
        return '''<figure class="question-figure">
  <svg viewBox="0 0 560 230" role="img" aria-label="同じ尺度の荷重Qと変形δの自作模式図。図1は原点付近でも抵抗を持つ幅広のループで、繰返し後の破線はピークが低下する。図2は中央がくびれて原点付近の抵抗とループ面積が小さい。">
    <g fill="none" stroke="currentColor" stroke-width="1.5">
      <path d="M25 125H265 M145 215V25 M300 125H540 M420 215V25"/>
      <path d="M259 121L265 125L259 129 M141 31L145 25L149 31 M534 121L540 125L534 129 M416 31L420 25L424 31"/>
    </g>
    <g fill="none" stroke="#294c40" stroke-width="3" stroke-linejoin="round">
      <path d="M65 195L113 83L181 82L199 55L225 71L177 167L109 168L91 195Z"/>
      <path stroke-dasharray="6 5" d="M59 184L112 94L184 93L208 72L231 87L178 157L106 157L82 178Z"/>
      <path d="M340 195 Q395 132 420 128 Q458 132 500 55 Q450 95 420 122 Q382 118 340 195Z"/>
    </g>
    <g fill="currentColor" font-size="15" font-family="sans-serif">
      <text x="131" y="18">図1</text><text x="406" y="18">図2</text>
      <text x="151" y="40">Q</text><text x="247" y="147">δ</text>
      <text x="426" y="40">Q</text><text x="522" y="147">δ</text>
      <text x="150" y="142">0</text><text x="425" y="142">0</text>
    </g>
  </svg>
  <figcaption>自作模式図。破線は繰返し後の例。特定部材の実験値・設計用曲線ではありません。</figcaption>
</figure>'''
    return '''<figure class="question-figure">
  <svg viewBox="0 0 560 230" role="img" aria-label="荷重Qと変形δの模式図。図1は幅のある平行四辺形状の閉ループ。図2は原点付近の抵抗が小さく中央がくびれた閉ループ。両図は同じ尺度。">
    <g fill="none" stroke="currentColor" stroke-width="1.5">
      <path d="M25 125H265 M145 215V25 M300 125H540 M420 215V25"/>
      <path d="M259 121L265 125L259 129 M141 31L145 25L149 31 M534 121L540 125L534 129 M416 31L420 25L424 31"/>
    </g>
    <g fill="none" stroke="#294c40" stroke-width="3" stroke-linejoin="round">
      <path d="M65 195L125 65L225 55L165 185Z"/>
      <path d="M340 195 Q395 132 420 128 Q458 132 500 55 Q450 95 420 122 Q382 118 340 195Z"/>
    </g>
    <g fill="currentColor" font-size="15" font-family="sans-serif">
      <text x="131" y="18">図1</text><text x="406" y="18">図2</text>
      <text x="151" y="40">Q</text><text x="247" y="147">δ</text>
      <text x="426" y="40">Q</text><text x="522" y="147">δ</text>
      <text x="150" y="142">0</text><text x="425" y="142">0</text>
    </g>
  </svg>
  <figcaption>学習用の自作模式図。特定部材の実験値・設計用曲線ではありません。</figcaption>
</figure>'''
