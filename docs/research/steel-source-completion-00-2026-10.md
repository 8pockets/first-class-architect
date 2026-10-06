# 本試験知識表の未確認14項目の確認記録

確認日：2026-10-06。対象は `00-prior-question-knowledge.yaml` の未確認14項目。

元資料：所有教材 `2026_構造_文章問題.pdf`、PDF P159–175。原本・本文転載・図版は公開しない。表の問いの成立条件を確認し、自作文の問題・規定・識別へ置き換えた。ページ番号はPDF上のページを指す。

## 判定方針

- 規定値と用語識別に、教材にない因果説明を作らない。規定は適用範囲・数値／例外、識別は識別条件・混同注意を確認する。
- `MINIMIZE-WELD-DISTORTION-AND-RESIDUAL-STRESS` は物理的因果を新規断定する原理ではなく、設計・施工計画の規定へ型を訂正した。旧暫定記録の型と本文は変更しない。
- 問題は元の正誤文の転載ではなく、条件を指定した判断、計算、比較にした。回答履歴用の内容版は問題・正解・解説・図が変わると変わる。

## 確認対象と修正

| 内部キー末尾 | 検証した判断／適用境界 |
|---|---|
| DISSIMILAR-STEEL-WELD-WEAKER-BASE-GOVERNS | 異強度材の溶接部の基準強度は小さい側。235と325の具体例。教材P159と[専門団体Q&A](https://sasst.jp/qa/q4/q4-23.html)の設計部分を照合。溶材選定・施工条件の保証とは分離。 |
| BEAM-END-MOMENT-STRENGTH-FLANGE-PLUS-WEB | フランジ・ウェブの曲げ負担の合計。せん断力との単位混同を除く。 |
| EXISTING-RIVET-JOINT-WELDED-EXTENSION-LOAD-SHARING | 既存死荷重がリベットへ作用した状態で増設した溶接は、その既存応力を自動的に肩代わりしない。 |
| H-BEAM-ALLOWABLE-BENDING-INPUTS | 曲げモーメント分布、圧縮フランジの横補剛間隔等を指定して許容曲げを判断。 |
| UNIFORM-BRACING-SLENDERNESS-FORMULAS | 指定された均等横補剛の式・鋼種・限界条件を維持。細長比200で必要数を算定。 |
| FRICTION-JOINT-GAP-FILLER-RULE | 摩擦面の肌すきの境界とフィラープレートの使用。施工条件・板材条件を維持。 |
| NONSEISMIC-TRUSS-JOINT-MINIMUM-STRENGTH | 耐震設計を行わないトラス節点という条件を明記。部材耐力と作用応力のどちらを用いるか判断。 |
| METAL-TOUCH-SPLICE-DIRECT-TRANSFER-FRACTIONS | 柱継手と柱脚の直接接触負担割合を区別。軸力800の具体例。 |
| MINIMIZE-WELD-DISTORTION-AND-RESIDUAL-STRESS | 耐力のみを満たせばよいとはせず、溶接変形・残留応力を抑える設計・施工計画を扱う。 |
| DIAPHRAGM-FLANGE-MISALIGNMENT-LIMIT | 薄い側の板厚を指定し、不一致の限度と補強要否を判断。 |
| EXPOSED-BASE-CAPACITY-DESIGN-DS-PENALTY | 伸び能力のあるアンカーボルトでも保有耐力接合に該当しない場合のDs加算を区別。 |
| BOX-COLUMN-FIELD-BUTT-WELD-WITH-BACKING | 引張応力を伝達する現場柱継手の接合形式。圧縮のみの直接接触とは区別。 |
| FIRE-LOAD-FIXED-PLUS-LIVE-COMBUSTIBLES | 固定・積載可燃物の合計という火災荷重の定義。耐火性能検証法全体や不燃材重量と混同しない。 |
| OVERHEAD-CRANE-SEISMIC-WEIGHT | 教材P175の天井走行クレーン・地震時・吊荷除外の条件と特例を確認。走行レール頂部位置の条件を維持。 |

14件とも出典確認済みに移行した。これは試験の全出題範囲を14件で保証する意味ではない。本試験横断の不足論点・図計算の監査は別の `exam-coverage.yaml` と公式試験照合記録で管理する。
