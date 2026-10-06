# 鉄骨構造カードの根拠完了・設問再点検（2026-10-06）

## 対象と結論

担当範囲は `data/principles/steel/01-*.yaml`〜`38-*.yaml` の既存169カード（36章ファイル）。開始時は確認済み83、source_gap84、draft2だった。根拠確認中86件を個別に教材本文・表・図および必要な一次資料と照合し、確認済みにした。保留ラベルの非表示や検索URLによる代替ではない。00章、39章の追加問題、履歴UI、公開マニフェストの集計は別担当であり、本書の169件に含めない。

既確認83件も再点検した。裏当て金の誤一般化に加え、最後の18件は条件・結論・設問を補正した。全カードのIDを維持し、Qの結論が変わる箇所は現版の独立監査スナップショットを更新することをroot担当へ連絡した。A/Bの正解位置はrootの全体調整後の位置を維持した。

`source_checked` はここに示した学習内容・適用条件についての確認であり、実構造物への設計適合の保証ではない。合格の保証や法令の全用途への一般化でもない。

## 照合の方法

- 所有する「2026_構造_文章問題.pdf」の鉄骨構造本文P176〜211を通読し、P159〜175の問題コード・要約と対応付けた。
- 図表に依存するP177・178・183・186・188・189・190・192・195・199・205・208・212・215はページ全体を画像で確認した。元の図や教材ページの公開複製は行わず、文章は論点を要約した。
- 数値・仕様は、教材の記述だけで適用範囲を断定できないとき、下記の行政・研究機関・専門団体の原文を確認した。外部資料の版・節をカードの `source.authoritative_sources` に残した。
- 原則（因果関係）、規定（条件・数値・例外）、識別（定義・見分け方）に必要な根拠を区別した。規定・定義カードに、原文にない因果説明を作って補わない。
- `H-SECTION-WEB-SHEAR` は簡略化した応力分担の識別、`STEEL-YOUNGS-MODULUS-STRENGTH-INDEPENDENT` は常温での設計物性値の扱いとして分類し直した。
- 二択は、単に本文を肯定・否定するだけでなく、数値適用、対象部位、施工条件、破壊形式など一つの判断を問う形に改めた。語の同じ単位で比較し、数値の誤答には別条件の係数・式などを用いた。

## 外部一次資料と適用上の注意

1. [建築基準法施行令（e-Gov）](https://laws.e-gov.go.jp/law/325CO0000000338)。
   2026-10-06にe-Gov法令APIの現行本文で第65・68・90・92・96・98条を照合。第68条の孔径例外は「構造耐力上支障がない場合」等の条件を残した。JIS材料のFの1.1倍は材料強度の扱いであり、許容応力度に一律乗算する規則ではない。
2. [国土交通省 公共建築工事標準仕様書（建築工事編）令和7年版](https://www.mlit.go.jp/gobuild/content/001888816.pdf)。
   7.4.8、7.6.5〜7.6.12、7.8.2、7.9を確認。国の公共工事標準仕様の適用条件であり、全ての建築にそのまま適用される法律と扱わない。
3. [大阪府 構造計算適合性判定の注意喚起事項](https://www.pref.osaka.lg.jp/documents/35034/09_btyuuikannkizikou_1.pdf)。
   2021年版・2023年一部改訂のB-1（1.1 材料強度）、B-2（2.2 有効断面積）、B-3（2.3 アンカー断面）。許容応力度用と破断耐力用の有効断面積算定を区別。
4. [大阪府 建築構造設計指針・各種構造の設計](https://www.pref.osaka.lg.jp/documents/35034/05_a41kakusyukouzounosekkei_1.pdf)。
   4.1.3-2〜3のX形・K形筋かいの耐力評価を確認。骨組・筋かいの抵抗を異なる変形時点の各最大値で足し合わせない。
5. [日本溶接協会 溶接管理技術者2級電子化教材](https://www-it.jwes.or.jp/we2/pageindices/index179.html)。
   冊子P177／電子179頁、3.7.1〔5〕・3.7.2〔1〕。ビードは1パスで形成された溶接金属であって長さの意味ではない。法令表の突合せ区分と建築鉄骨の完全溶込みの用語対応も確認。
6. [日本溶接協会 パルスアークの騒音Q&A](https://www-it.jwes.or.jp/qa/details.jsp?pg_no=0070010160)。
   波形と音の発生を確認。「溶接では騒音が発生しない」という全称命題を削除。
7. [日本溶接協会 裏当て金・裏溶接Q&A](https://www-it.jwes.or.jp/qa/details.jsp?pg_no=0010020140)。
   裏当てを用いる片面溶接と、裏はつり後の両面溶接を区別。裏当て金を単なる強度補強や全完全溶込み溶接の必須部材としない。
8. [建築研究所 えぴすとら第47号（2009年10月）](https://www.kenken.go.jp/japanese/contents/publications/epistura/pdf/47.pdf)。
   P3の鋼材の高温強度低下と耐火被覆機能を確認。非燃焼性と火災時の耐力保持は別。教材の250℃・300℃を全鋼材の耐火被覆要否の共通境界として掲載しない。
9. [日本鉄鋼連盟 鉄骨造建物の耐震・耐津波安全性と鋼材について](https://www.jisf.or.jp/business/tech/infrastructure/docs/infrastructure_pdf_02.pdf)。
   冊子P9〜10（PDF6頁）の降伏比・伸び・シャルピー吸収エネルギー・溶接部靭性。低降伏比の意味と、鋼材なら脆性破断しないという誤解を修正。
10. [建設省告示1456号の国交省公開統合本文](https://www.mlit.go.jp/notice/noticedata/pdf/201703/00006502.pdf) と [2025年4月1日国住指第502号](https://www.mlit.go.jp/jutakukentiku/build/content/001881640.pdf)。
    旧統合本文だけを「現行全文」とせず、2025年改正のコンテナ建築物の特例追加も確認。旧PDFの時点をlocatorに明記した。

## 重要な訂正と判断

| 論点 | 訂正・判断 |
| --- | --- |
| ビードの定義 | 「溶接の長さ」から「1パスで形成された溶接金属」へ訂正。 |
| 溶接の音 | 「施工騒音なし」を撤回し、アーク音が生じる事実に差し替え。 |
| 耐火被覆の温度 | 250℃／300℃の一律の合否境界を除去。温度上昇を遅らせ耐力低下を抑える機能を問う。 |
| エンドタブ残置 | 教材P162・問題28151を実確認し、3条件を全て満たすという誤読ではなく列挙条件のいずれかを確認。実施工の切断範囲は特記による。 |
| 裏当て金 | 「補強部材」「6mm以上なら普遍的に可」という一般化を撤回。完全溶込みの施工形式と品質を問う。 |
| 組立溶接長 | 板厚だけで30／40mmと断定せず、本溶接方法を条件に追加。サブマージアークは50／70mm。異厚は厚い方。 |
| ピンテール | 破断だけで所要張力・共回りなしを保証しない。マーキングによる追加確認を問う。 |
| 筋かい断面積 | 孔欠損と突出脚の無効部分を区別。許容応力度用の突出部1/2と破断耐力式を同一の簡略化として扱わない。対称二丁掛けでも孔欠損は別途控除。 |
| X形筋かい | 座屈前の圧縮最大値と座屈後安定耐力を区別。水平成分・同じ変形時点という条件を残す。 |
| 常温のE | 材料強度に比例するという誤りと、高温まで一定という過大一般化を排除。 |
| 靭性 | 「鋼材だから脆性破壊しない」でなく、必要な靭性が確保された材料・溶接部という条件に限定。 |
| 溶接熱管理 | 予熱の下限とパス間温度の上限を区別。50〜100℃は教材の例であって、全施工の指定温度ではない。 |
| H形鋼の横座屈 | 曲げ材の検討を「許容圧縮応力度を低減する」とだけ書かず、許容曲げ応力度と横補剛による拘束を明確化。 |
| 防錆 | 一律の全面塗装でなく、摩擦面・コンクリート密着面など塗装範囲の例外を明記。 |
| 内ダイアフラム | 教材の既成角形鋼管の製作例と、全ての箱形柱の製作方法を区別。 |
| 疲労 | 140／100N/mm²は教材の比較区分として残し、全ての継手詳細で固定の数値とはしない。 |
| 溶接の連続性 | 接合部全体の連続性と、溶接止端などの局部応力集中の検討を区別。 |

## 全169カードの処置台帳

「所有教材の記載・図を直接確認」は出典不足のまま昇格した意味ではなく、`source.pages` の記載自体で当該学習命題を確認できたもの。外部法令・規格を適用した場合は、直接参照した範囲を右欄に記した。root担当の図・数値問題3件についてはrootの最終内容を優先する。

| ID | 処置 | 所有教材の所在 | 追加一次資料・locator |
| --- | --- | --- | --- |
| `S-K6-COLUMN-BASE-TYPES-FIXITY-ORDER` | source_gap→確認済み／本文・条件・設問補正 | P176・180・204; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-H-SECTION-FLANGE-BENDING` | source_gap→確認済み／本文・条件・設問補正 | P176・178・187・192; コード20172・23173・26163 | 所有教材の記載・図を直接確認 |
| `S-K6-H-SECTION-WEB-SHEAR` | source_gap→確認済み／本文・条件・設問補正／principle→identification | P176・178・187・192; コード20172・23173・26163 | 所有教材の記載・図を直接確認 |
| `S-K6-HIGH-STRENGTH-BOLT-CONNECTION-TYPES` | source_gap→確認済み／本文・条件・設問補正 | P176・179・184; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-STEEL-CONNECTION-TYPE-IDENTIFICATION` | 既確認の再点検 | P176・179・183; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-STEEL-DUCTILITY-PREVENTS-BRITTLE-FRACTURE` | 既確認の再点検／本文・条件・設問補正 | P176・177・181; 解説・図 | [日本鉄鋼連盟 鉄骨造建物の耐震・耐津波安全性と鋼材について](https://www.jisf.or.jp/business/tech/infrastructure/docs/infrastructure_pdf_02.pdf)：冊子p.9–10（PDF6頁）「シャルピー吸収エネルギー」「溶接部のシャルピー吸収エネルギー」 |
| `S-K6-STEEL-ALLOWABLE-STRESS-DURATION` | 既確認の再点検 | P159・177・182; コード19165・23303 | [建築基準法施行令（e-Gov現行本文、2026-10-06照合）](https://laws.e-gov.go.jp/law/325CO0000000338)：第90条第1項表一・第2項 |
| `S-K6-STEEL-MATERIAL-STRENGTH-JIS-FACTOR` | source_gap→確認済み／本文・条件・設問補正 | P159・177・182; コード19165・23303 | [建築基準法施行令（e-Gov現行本文、2026-10-06照合）](https://laws.e-gov.go.jp/law/325CO0000000338)：第96条表一（材料強度用のFについては告示2464号も参照）<br>[大阪府 構造計算適合性判定 指摘事例集 2021年版（2023年一部改正版）](https://www.pref.osaka.lg.jp/documents/35034/09_btyuuikannkizikou_1.pdf)：B-1・1.1 材料強度の設定 |
| `S-K6-WELD-ALLOWABLE-STRESS-FULL-PENETRATION` | source_gap→確認済み／本文・条件・設問補正 | P159・177・182・212; コード03163・05162・07161・19153・20183・21171・26164・28154・30152 | [建築基準法施行令（e-Gov現行本文、2026-10-06照合）](https://laws.e-gov.go.jp/law/325CO0000000338)：第92条・第98条の突合せ欄<br>[日本溶接協会 溶接管理技術者2級電子化教材](https://www-it.jwes.or.jp/we2/pageindices/index179.html)：冊子P177（電子版179/332）、3.7.2〔1〕建築鉄骨の完全溶込みを突合せと呼ぶ用語対応 |
| `S-K6-WELD-ALLOWABLE-STRESS-NONFULL-PENETRATION` | source_gap→確認済み／本文・条件・設問補正 | P159・177・182; コード03163・05162・07161・19153・20183・26164・28154・30152 | [建築基準法施行令（e-Gov現行本文、2026-10-06照合）](https://laws.e-gov.go.jp/law/325CO0000000338)：第92条・第98条の突合せ以外欄 |
| `S-K6-STEEL-DIAMETER-THICKNESS-RATIO-SMALLER-PREFERRED` | source_gap→確認済み／本文・条件・設問補正 | P177; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-STEEL-F-VALUE-DEFINITION` | source_gap→確認済み／本文・条件・設問補正 | P177・182; コード19165・23303 | 所有教材の記載・図を直接確認 |
| `S-K6-STEEL-YIELD-RATIO-SMALLER-PREFERRED` | source_gap→確認済み／本文・条件・設問補正 | P177; 解説・図 | [日本鉄鋼連盟 建築構造用鋼材の材料特性](https://www.jisf.or.jp/business/tech/infrastructure/docs/infrastructure_pdf_02.pdf)：鋼材の機械的性質「降伏比」・「降伏比の上限値」 |
| `S-K6-STEEL-YOUNGS-MODULUS-STRENGTH-INDEPENDENT` | source_gap→確認済み／本文・条件・設問補正／principle→rule | P177・192; コード03173・20161・27173 | 所有教材の記載・図を直接確認 |
| `S-K6-STEEL-YOUNGS-MODULUS-VS-CONCRETE` | source_gap→確認済み／本文・条件・設問補正 | P177; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-NO-LATERAL-BUCKLING-SECTION-ALLOWABLE-BENDING` | 既確認の再点検 | P164・165・178・193; コード01152・03174・04164・05172・07182・18171・21151・22151・25163・26173・29302 | 所有教材の記載・図を直接確認 |
| `S-K6-BEAM-LATERAL-BUCKLING-COUNTERMEASURES` | 既確認の再点検 | P165・178・194; コード01153・03172・07183・18161・20163・21163・22154・23154・24154・26172・28171・30163 | 所有教材の記載・図を直接確認 |
| `S-K6-H-SECTION-AXIS-LATERAL-BUCKLING` | source_gap→確認済み／本文・条件・設問補正 | P178・193; コード04164・07182・21151・25163 | 所有教材の記載・図を直接確認 |
| `S-K6-H-SECTION-STRONG-AXIS-LATERAL-RESTRAINT` | 既確認の再点検／本文・条件・設問補正 | P178・193・194; コード04164・07182・21151・25163 | 所有教材の記載・図を直接確認 |
| `S-K6-H-SECTION-STRONG-WEAK-AXIS-RIGIDITY` | source_gap→確認済み | P178・193; コード04164・07182・21151・25163 | 所有教材の記載・図を直接確認 |
| `S-K6-STEEL-COMPRESSION-CAPACITY-BUCKLING` | 既確認の再点検 | P164・178・182・193; コード02153・04164・07182・21151・25163 | 所有教材の記載・図を直接確認 |
| `S-K6-FRICTION-JOINT-PRE-SLIP-FORCE-TRANSFER` | 既確認の再点検 | P160・179・184; コード02163・06163・07163・18172・27181・30171 | 所有教材の記載・図を直接確認 |
| `S-K6-FRICTION-SURFACE-PREPARATION` | 既確認の再点検 | P161・179・184; コード02163・06163・07163・18172・19252・27181・30171 | 所有教材の記載・図を直接確認 |
| `S-K6-PARTIAL-PENETRATION-WELD-APPLICABILITY` | source_gap→確認済み／本文・条件・設問補正 | P162・179・187・189; コード05161・22172・24171 | 所有教材の記載・図を直接確認 |
| `S-K6-SQUARE-TUBE-COLUMN-DIAPHRAGM-TYPES` | 既確認の再点検 | P168・179・198・209; コード01171・19151・24174・25181・28152・29182 | 所有教材の記載・図を直接確認 |
| `S-K6-GUSSET-PLATE-MEMBER-CONNECTION` | 既確認の再点検 | P179・199; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-WELD-NO-SECTION-LOSS-HIGH-RIGIDITY` | source_gap→確認済み／本文・条件・設問補正 | P179・187; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-WELD-TYPE-IDENTIFICATION` | source_gap→確認済み／本文・条件・設問補正 | P179・187; コード24171 | 所有教材の記載・図を直接確認 |
| `S-K6-EMBEDDED-BASE-MINIMUM-DEPTH` | source_gap→確認済み／本文・条件・設問補正 | P171・180・204; コード19161・23164 | [平成12年建設省告示第1456号（平成19年改正を含む公表本文）](https://www.mlit.go.jp/notice/noticedata/pdf/201703/00006502.pdf)：前文ただし書・第一号・第三号（通常の柱脚。後続のコンテナ等特例は令和7年技術的助言を参照）<br>[国土交通省 国住指第502号（令和7年4月1日）](https://www.mlit.go.jp/jutakukentiku/build/content/001881640.pdf)：3. コンテナ等建築物の柱の脚部の構造方法の合理化 |
| `S-K6-EXPOSED-BASE-ANCHOR-AREA-RATIO` | source_gap→確認済み／本文・条件・設問補正 | P171・180・204; コード施工06144・23162・28163 | [平成12年建設省告示第1456号（平成19年改正を含む公表本文）](https://www.mlit.go.jp/notice/noticedata/pdf/201703/00006502.pdf)：前文ただし書・第一号・第三号（通常の柱脚。後続のコンテナ等特例は令和7年技術的助言を参照）<br>[国土交通省 国住指第502号（令和7年4月1日）](https://www.mlit.go.jp/jutakukentiku/build/content/001881640.pdf)：3. コンテナ等建築物の柱の脚部の構造方法の合理化 |
| `S-K6-EXPOSED-BASE-ANCHOR-EMBEDMENT-LENGTH` | 既確認の再点検 | P171・180・204; コード23161・23162・28163 | 所有教材の記載・図を直接確認 |
| `S-K6-EXPOSED-BASE-ANCHOR-HOLE-CLEARANCE` | source_gap→確認済み／本文・条件・設問補正 | P171・180・204; コード24163・28163 | 所有教材の記載・図を直接確認 |
| `S-K6-EXPOSED-BASE-PLATE-MINIMUM-THICKNESS` | 既確認の再点検／本文・条件・設問補正 | P171・180・204; コード施工30141・28163 | 所有教材の記載・図を直接確認 |
| `S-K6-EXPOSED-BASE-SHEAR-CAPACITY-NOT-ADDITIVE` | source_gap→確認済み／本文・条件・設問補正 | P171・180・204; コード02263・07263・18184 | 所有教材の記載・図を直接確認 |
| `S-K6-WRAPPED-BASE-HEIGHT-AND-TOP-CONFINEMENT` | 既確認の再点検／本文・条件・設問補正 | P171・180・204; コード20173・23163・29163 | 所有教材の記載・図を直接確認 |
| `S-K6-EMBEDDED-BASE-EFFECTIVE-FIXED-POINT` | source_gap→確認済み／本文・条件・設問補正 | P172・180・204; コード19161・29164 | 所有教材の記載・図を直接確認 |
| `S-K6-EXPOSED-BASE-MODEL-BY-DESIGN-TARGET` | 既確認の再点検 | P173・180・210; コード03171・19162・27154 | 所有教材の記載・図を直接確認 |
| `S-K6-EXPOSED-BASE-ANCHOR-LOCKING` | source_gap→確認済み | P180・204; コード23161 | [平成12年建設省告示第1456号（平成19年改正を含む公表本文）](https://www.mlit.go.jp/notice/noticedata/pdf/201703/00006502.pdf)：前文ただし書・第一号・第三号（通常の柱脚。後続のコンテナ等特例は令和7年技術的助言を参照）<br>[国土交通省 国住指第502号（令和7年4月1日）](https://www.mlit.go.jp/jutakukentiku/build/content/001881640.pdf)：3. コンテナ等建築物の柱の脚部の構造方法の合理化 |
| `S-K6-STEEL-BUCKLING-MODE-IDENTIFICATION` | source_gap→確認済み／本文・条件・設問補正 | P181; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-STEEL-CORROSION-PROTECTION` | 既確認の再点検／本文・条件・設問補正 | P181; 解説・図 | [公共建築工事標準仕様書（建築工事編）令和7年版](https://www.mlit.go.jp/gobuild/content/001888816.pdf)：7.8.2(1)（塗装の範囲） |
| `S-K6-STEEL-FIRE-STRENGTH-FIREPROOFING` | draft→確認済み／本文・条件・設問補正 | P181; 解説・図 | [建築研究所 BRI NEWS Vol.47（2009年10月）](https://www.kenken.go.jp/japanese/contents/publications/epistura/pdf/47.pdf)：P3 鋼構造部材の耐火性・温度上昇による耐力低下 |
| `S-K6-STEEL-STRUCTURE-DEFINITION` | source_gap→確認済み／本文・条件・設問補正 | P181; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-STEEL-THIN-SECTION-BUCKLING` | 既確認の再点検／本文・条件・設問補正 | P181・196; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-STEEL-LONG-TERM-BEARING-ALLOWABLE-STRESS` | source_gap→確認済み | P182; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-ORDINARY-BOLT-HOLE-CLEARANCE` | source_gap→確認済み／本文・条件・設問補正 | P159・183; コード23302 | [建築基準法施行令（e-Gov現行本文、2026-10-06照合）](https://laws.e-gov.go.jp/law/325CO0000000338)：第68条第4項 |
| `S-K6-HIGH-STRENGTH-BOLT-SLIP-RIGIDITY` | 既確認の再点検 | P183・184; コード25171 | 所有教材の記載・図を直接確認 |
| `S-K6-ORDINARY-BOLT-CLEARANCE-LOOSENING` | 既確認の再点検 | P183; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-ORDINARY-BOLT-HOLE-DIAMETER-AIJ` | source_gap→確認済み／本文・条件・設問補正 | P183; コード23302 | 所有教材の記載・図を直接確認 |
| `S-K6-ORDINARY-BOLT-SHEAR-TRANSFER` | 既確認の再点検 | P183・184; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-ORDINARY-BOLT-THREAD-PROJECTION` | source_gap→確認済み | P183; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-ORDINARY-BOLT-WASHER-UNDER-NUT` | source_gap→確認済み | P183; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-FRICTION-JOINT-SHEAR-TENSION-INTERACTION` | 既確認の再点検 | P159・184; コード04183・27183・30172 | 所有教材の記載・図を直接確認 |
| `S-K6-FRICTION-JOINT-POST-SLIP-RUPTURE-MODEL` | 既確認の再点検 | P160・184; コード07163・30171 | 所有教材の記載・図を直接確認 |
| `S-K6-FRICTION-JOINT-REPEATED-LOAD-BELOW-SLIP` | 既確認の再点検 | P160・184; コード02162・02163・06163・07163・18172・25171・27181・27182・30171 | 所有教材の記載・図を直接確認 |
| `S-K6-HIGH-STRENGTH-BOLT-CONSTRUCTION-ADVANTAGE` | source_gap→確認済み／本文・条件・設問補正 | P184・206; コード27182 | 所有教材の記載・図を直接確認 |
| `S-K6-HIGH-STRENGTH-BOLT-STRESS-DISTRIBUTION` | 既確認の再点検 | P184; コード02163・06163・07163・18172・27181・30171 | 所有教材の記載・図を直接確認 |
| `S-K6-HIGH-STRENGTH-BOLT-TENSILE-STRENGTH-RATIO` | source_gap→確認済み／本文・条件・設問補正 | P184; コード02162 | 所有教材の記載・図を直接確認 |
| `S-K6-FATIGUE-CHECK-CYCLE-THRESHOLD` | source_gap→確認済み | P160・185; コード05152・06184・24161 | 所有教材の記載・図を直接確認 |
| `S-K6-REFERENCE-FATIGUE-STRENGTH-JOINT-TYPE` | 既確認の再点検／本文・条件・設問補正 | P160・185; コード05152・06184・24161 | 所有教材の記載・図を直接確認 |
| `S-K6-HIGH-STRENGTH-BOLT-PRODUCT-TYPES` | source_gap→確認済み／本文・条件・設問補正 | P185; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-TORSHEAR-BOLT-PINTAIL-SECONDARY-TIGHTENING` | 既確認の再点検／本文・条件・設問補正 | P185; コード17045 | [公共建築工事標準仕様書（建築工事編）令和7年版](https://www.mlit.go.jp/gobuild/content/001888816.pdf)：7.4.8(1)(ア)（締付け後の確認） |
| `S-K6-TORSHEAR-BOLT-ROTATION-MARKING-INSPECTION` | 既確認の再点検 | P185; コード17045・21134 | 所有教材の記載・図を直接確認 |
| `S-K6-FRICTION-JOINT-SLIP-COEFFICIENT` | source_gap→確認済み／本文・条件・設問補正 | P160・161・186; コード02164・19252 | 所有教材の記載・図を直接確認 |
| `S-K6-HIGH-STRENGTH-BOLT-ALLOWABLE-SHEAR-TABLE` | 既確認の再点検 | P160・161・162・186; コード02164・03162・07164・19252・21153・21154・25173・26161・28162・30174 | 所有教材の記載・図を直接確認 |
| `S-K6-BOLT-MINIMUM-EDGE-DISTANCE` | source_gap→確認済み／本文・条件・設問補正 | P161・186; コード01174・06164・25172 | 所有教材の記載・図を直接確認 |
| `S-K6-F10T-TENSILE-STRENGTH-MEANING` | 既確認の再点検 | P161・186; コード19253・27294 | 所有教材の記載・図を直接確認 |
| `S-K6-HIGH-STRENGTH-BOLT-HOLE-CLEARANCE` | source_gap→確認済み／本文・条件・設問補正 | P161・186; コード05164・19251・23171 | [建築基準法施行令（e-Gov現行本文、2026-10-06照合）](https://laws.e-gov.go.jp/law/325CO0000000338)：第68条第2項・第3項 |
| `S-K6-HIGH-STRENGTH-BOLT-MINIMUM-PITCH` | source_gap→確認済み／本文・条件・設問補正 | P161・186; コード23171 | [建築基準法施行令（e-Gov現行本文、2026-10-06照合）](https://laws.e-gov.go.jp/law/325CO0000000338)：第68条第1項 |
| `S-K6-BOLT-EDGE-DISTANCE-TERM-IDENTIFICATION` | source_gap→確認済み | P186; コード01174・06164・25172 | 所有教材の記載・図を直接確認 |
| `S-K6-BOLT-MAXIMUM-EDGE-DISTANCE` | source_gap→確認済み／本文・条件・設問補正 | P186; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-TACK-WELD-MINIMUM-BEAD` | 既確認の再点検／本文・条件・設問補正 | P162・187; コード施工06143・施工23142・07162・24173・30154 | [公共建築工事標準仕様書（建築工事編）令和7年版](https://www.mlit.go.jp/gobuild/content/001888816.pdf)：7.6.5(4)、表7.6.1（p.78） |
| `S-K6-BEAM-FLANGE-WEB-FORCE-SHARING` | 既確認の再点検 | P187・207; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-BOX-COLUMN-H-BEAM-WELD-TYPES` | 既確認の再点検 | P167・187; コード20172・23173・26163 | 所有教材の記載・図を直接確認 |
| `S-K6-BUILT-UP-H-SECTION-FLANGE-WEB-FILLET` | source_gap→確認済み／本文・条件・設問補正 | P187; コード20172・23173・26163 | 所有教材の記載・図を直接確認 |
| `S-K6-WELD-BEAD-DEFINITION` | source_gap→確認済み／本文・条件・設問補正 | P187; 解説・図 | [日本溶接協会 溶接管理技術者2級電子化教材](https://www-it.jwes.or.jp/we2/pageindices/index179.html)：冊子P177（電子版179/332）、3.7.1〔5〕ビードの定義 |
| `S-K6-WELD-CONSTRUCTION-DEFECT-RISK` | source_gap→確認済み／本文・条件・設問補正 | P187; 解説・図 | [公共建築工事標準仕様書（建築工事編）令和7年版](https://www.mlit.go.jp/gobuild/content/001888816.pdf)：7.6.6、7.6.7(1)(キ)、7.6.10（清掃・層間スラグ・内部欠陥） |
| `S-K6-WELD-CONTINUOUS-STRESS-FLOW` | 既確認の再点検／本文・条件・設問補正 | P187・192; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-WELD-FORM-FLEXIBILITY` | source_gap→確認済み／本文・条件・設問補正 | P187; 解説・図 | [日本溶接協会 溶接管理技術者2級電子化教材](https://www-it.jwes.or.jp/we2/pageindices/index179.html)：冊子P177（電子版179/332）、3.7.2 溶接継手の種類 |
| `S-K6-WELD-HEAT-DISTORTION` | 既確認の再点検 | P187; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-WELD-INSPECTION-DIFFICULTY` | source_gap→確認済み／本文・条件・設問補正 | P187; 解説・図 | [公共建築工事標準仕様書（建築工事編）令和7年版](https://www.mlit.go.jp/gobuild/content/001888816.pdf)：7.6.10～7.6.12（外観・内部欠陥・超音波探傷） |
| `S-K6-WELD-NO-CONSTRUCTION-NOISE` | source_gap→確認済み／本文・条件・設問補正 | P187; 解説・図 | [日本溶接協会 接合・溶接技術Q&A（2012年新規）](https://www-it.jwes.or.jp/qa/details.jsp?pg_no=0070010160)：Q-07-01-16、パルスアーク形態の変動による発音・波形による低減 |
| `S-K6-END-TABS-SECURE-SOUND-WELD-ENDS` | 既確認の再点検 | P162・188; コード20185 | 所有教材の記載・図を直接確認 |
| `S-K6-STEEL-END-TAB-RETENTION-CONDITIONS` | source_gap→確認済み／本文・条件・設問補正 | P162・188; コード28151 | [公共建築工事標準仕様書（建築工事編）令和7年版](https://www.mlit.go.jp/gobuild/content/001888816.pdf)：7.6.7(1)(カ)(b)（切断箇所・範囲の特記。教材の三条件の根拠は教材P162） |
| `S-K6-FULL-PENETRATION-WELD-ANATOMY` | source_gap→確認済み／本文・条件・設問補正 | P188; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-FULL-PENETRATION-WELD-DEFINITION-REPEATED-STRESS` | source_gap→確認済み／本文・条件・設問補正 | P188; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-FULL-PENETRATION-WELD-EFFECTIVE-LENGTH` | 既確認の再点検 | P188; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-FULL-PENETRATION-WELD-EFFECTIVE-THROAT` | source_gap→確認済み／本文・条件・設問補正 | P188; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-WELD-BACK-GOUGING-PURPOSE` | 既確認の再点検 | P188; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-WELD-BACKING-BAR-ROOT-GAP` | 既確認の再点検／本文・条件・設問補正 | P188; 解説・図 | [公共建築工事標準仕様書（建築工事編）令和7年版](https://www.mlit.go.jp/gobuild/content/001888816.pdf)：7.6.7(1)(コ)、(2)(ア)（裏当て・裏はつり・裏溶接）<br>[日本溶接協会 接合・溶接技術Q&A](https://www-it.jwes.or.jp/qa/details.jsp?pg_no=0010020140)：Q-01-02-14、裏当て金タイプと裏はつりタイプ・健全なルート部 |
| `S-K6-FILLET-WELD-EFFECTIVE-AREA` | source_gap→確認済み／本文・条件・設問補正 | P162・189; コード22174・25193 | 所有教材の記載・図を直接確認 |
| `S-K6-FILLET-WELD-EFFECTIVE-LENGTH` | 既確認の再点検 | P162・189; コード20182・24172 | 所有教材の記載・図を直接確認 |
| `S-K6-FILLET-WELD-ANATOMY` | source_gap→確認済み／本文・条件・設問補正 | P189; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-FILLET-WELD-DEFINITION-REPEATED-STRESS` | source_gap→確認済み／本文・条件・設問補正 | P189; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-FILLET-WELD-SIZE-EFFECTIVE-THROAT` | source_gap→確認済み／本文・条件・設問補正 | P189; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-WELD-DEFECT-BLOWHOLE` | 既確認の再点検 | P190; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-WELD-DEFECT-OVERLAP` | source_gap→確認済み／本文・条件・設問補正 | P190; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-WELD-DEFECT-PIT` | 既確認の再点検 | P190; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-WELD-DEFECT-SLAG-INCLUSION` | 既確認の再点検 | P190; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-WELD-DEFECT-UNDERCUT` | 既確認の再点検 | P190; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-WELD-SCALLOP-DEFINITION` | 既確認の再点検 | P190; コード04182・18183・25183・26162・30153 | 所有教材の記載・図を直接確認 |
| `S-K6-WELD-SYMBOL-ARROW-SIDE-POSITION` | source_gap→確認済み | P190・213; コード21171 | 所有教材の記載・図を直接確認 |
| `S-K6-COMBINED-BOLT-WELD-CONSTRUCTION-ORDER` | 既確認の再点検 | P163・191; コード05163・24164・27184・30173 | 所有教材の記載・図を直接確認 |
| `S-K6-MIXED-BUTT-FILLET-WELD-LOAD-SHARING` | source_gap→確認済み | P191; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-MIXED-WELD-ORDINARY-BOLT-LOAD-SHARING` | source_gap→確認済み／本文・条件・設問補正 | P191; コード05163 | 所有教材の記載・図を直接確認 |
| `S-K6-ELASTIC-DEFLECTION-NOT-REDUCED-BY-HIGHER-STEEL-GRADE` | 既確認の再点検 | P163・164・192; コード02173・03173・05174・20161・26304・27173 | 所有教材の記載・図を直接確認 |
| `S-K6-STEEL-BEAM-COMMON-SECTIONS` | source_gap→確認済み／本文・条件・設問補正 | P192; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-STEEL-BEAM-DEFLECTION-CHECK` | source_gap→確認済み | P192; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-STEEL-BEAM-DEFLECTION-CHECK-OMISSION` | source_gap→確認済み／本文・条件・設問補正 | P192; コード02173・26304 | 所有教材の記載・図を直接確認 |
| `S-K6-STEEL-BEAM-DEFLECTION-LIMITS` | source_gap→確認済み／本文・条件・設問補正 | P192; コード05174 | 所有教材の記載・図を直接確認 |
| `S-K6-STEEL-BEAM-DEPTH-SPAN-RANGE` | source_gap→確認済み／本文・条件・設問補正 | P192; コード28173 | 所有教材の記載・図を直接確認 |
| `S-K6-STEEL-BEAM-DESIGN-ACTIONS` | source_gap→確認済み／本文・条件・設問補正 | P192; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-18-ELASTIC-STRENGTH` | 既確認の再点検 | P164・193; コード01161・02153 | 所有教材の記載・図を直接確認 |
| `S-K6-18-SLENDERNESS` | 既確認の再点検 | P164・165・177・193; コード01152・04163・05172・07184・18162・22152・27164・28172・29254・29302 | 所有教材の記載・図を直接確認 |
| `S-K6-EFFECTIVE-SLENDERNESS-MAXIMUMS` | source_gap→確認済み／本文・条件・設問補正 | P164・193; コード01152・04163・05172・07184・18162・22152・23153・28172・29254・29302 | [建築基準法施行令（e-Gov現行本文、2026-10-06照合）](https://laws.e-gov.go.jp/law/325CO0000000338)：第65条（柱200・柱以外250） |
| `S-K6-LIMIT-SLENDERNESS-STRENGTH-RELATION` | 既確認の再点検 | P164・193; コード01161・02153・04161・24152・27163 | 所有教材の記載・図を直接確認 |
| `S-K6-19-LATERAL-BUCKLING` | source_gap→確認済み／本文・条件・設問補正 | P165・194; コード02172 | 所有教材の記載・図を直接確認 |
| `S-K6-LATERAL-BRACE-STRENGTH-AND-STIFFNESS` | 既確認の再点検 | P165・194; コード01154・20163・24154・27172・30163 | 所有教材の記載・図を直接確認 |
| `S-K6-FULL-PLASTIC-LATERAL-BRACING-PLACEMENT-METHODS` | 既確認の再点検 | P166・194; コード03154・06183・24183・29154・30164 | 所有教材の記載・図を直接確認 |
| `S-K6-HIGHER-STRENGTH-REQUIRES-MORE-UNIFORM-BRACING` | 既確認の再点検 | P166・194; コード01153・07183・18161・22154・24183・25191・28171 | 所有教材の記載・図を直接確認 |
| `S-K6-WIDER-FLANGE-REDUCES-BRACING-DEMAND` | 既確認の再点検 | P166・194; コード04171 | 所有教材の記載・図を直接確認 |
| `S-K6-BEAM-SECTION-SHAPE-LATERAL-BUCKLING` | source_gap→確認済み／本文・条件・設問補正 | P194; コード03174 | 所有教材の記載・図を直接確認 |
| `S-K6-20-LOCAL-BUCKLING` | 既確認の再点検 | P166・177・195; コード02174・23151・25164・28174 | 所有教材の記載・図を直接確認 |
| `S-K6-LATERAL-LOCAL-BUCKLING-INTERACTION` | 既確認の再点検 | P166・195; コード06151・23151・25164 | 所有教材の記載・図を直接確認 |
| `S-K6-COLUMN-WEB-WIDTH-THICKNESS-STRICTER-THAN-BEAM` | 既確認の再点検 | P167・195; コード06153 | 所有教材の記載・図を直接確認 |
| `S-K6-FA-H-BEAM-FLANGE-WEB-WIDTH-THICKNESS-LIMITS` | source_gap→確認済み／本文・条件・設問補正 | P167・195; コード01162・01163・05171・05173・06181・20165・24151・27162・30161 | 所有教材の記載・図を直接確認 |
| `S-K6-WIDTH-THICKNESS-LIMIT-DECREASES-WITH-STRENGTH` | 既確認の再点検 | P167・195; コード01162・03152・05171・06181・21161・24151・26171・27161・30162 | 所有教材の記載・図を直接確認 |
| `S-K6-WIDTH-THICKNESS-LIMIT-MEANING` | 既確認の再点検 | P195; コード01162・01163・05173・06181・30161 | 所有教材の記載・図を直接確認 |
| `S-K6-BEAM-SPLICE-METHODS-FIELD-SHOP` | 既確認の再点検 | P196・206; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-BEAM-TYPES-ROLLED-BUILT-UP` | source_gap→確認済み／本文・条件・設問補正 | P196; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-FILLER-PLATE-EQUALIZES-THICKNESS` | source_gap→確認済み | P197; コード03161・23172 | 所有教材の記載・図を直接確認 |
| `S-K6-SPLICE-PLATE-TRANSFERS-FORCE` | source_gap→確認済み | P197; コード01173 | 所有教材の記載・図を直接確認 |
| `S-K6-STIFFENER-ROLE-BY-POSITION-AND-STRESS` | 既確認の再点検 | P197; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-BRACE-CAPACITY-DESIGN-JOINT-OVERSTRENGTH` | 既確認の再点検／本文・条件・設問補正 | P169・199; コード01164・02171・06182・18181・19171・21183・22164・25192・26151・29151 | 所有教材の記載・図を直接確認 |
| `S-K6-BRACE-BALANCED-DIRECTIONAL-LAYOUT` | source_gap→確認済み／本文・条件・設問補正 | P199; コード06182 | 所有教材の記載・図を直接確認 |
| `S-K6-BRACE-HORIZONTAL-LOAD-AXIAL-FORCE` | 既確認の再点検 | P199; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-VERTICAL-HORIZONTAL-BRACE-ROLES` | 既確認の再点検 | P199; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-BRACE-SECTION-USE-IDENTIFICATION` | source_gap→確認済み／本文・条件・設問補正 | P199; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-ANGLE-CHANNEL-BRACE-EFFECTIVE-AREA` | 既確認の再点検／本文・条件・設問補正 | P169・170・200・202; コード04184・21181・22163・26152・26154・29152 | [大阪府 建築構造設計指針 第1編 B 注意喚起事項（2021年版・2023年一部改訂）](https://www.pref.osaka.lg.jp/documents/35034/09_btyuuikannkizikou_1.pdf)：B-2、2.2 鉄骨ブレースの有効断面積 |
| `S-K6-BRACE-ECCENTRIC-JOINT-EFFECTS` | 既確認の再点検 | P169・200; コード26154 | 所有教材の記載・図を直接確認 |
| `S-K6-DOUBLE-ANGLE-BRACE-REDUCES-ECCENTRICITY` | 既確認の再点検／本文・条件・設問補正 | P170・201; コード29252 | 所有教材の記載・図を直接確認 |
| `S-K6-BRACE-BOLT-COUNT-INCREASES-EFFECTIVE-AREA` | 既確認の再点検 | P170・202; コード02161・07153・18174・25174 | 所有教材の記載・図を直接確認 |
| `S-K6-BRACE-TENSION-YIELD-COMPRESSION-BUCKLING` | 既確認の再点検 | P170・203・214; コード05181・21184・26153 | 所有教材の記載・図を直接確認 |
| `S-K6-BRACED-FRAME-COLUMN-BRACE-CAPACITY-SUM` | source_gap→確認済み／本文・条件・設問補正 | P203; 解説・図 | [大阪府 構造計算適合性判定 指摘事例集 2021年版（2023年一部改正版）](https://www.pref.osaka.lg.jp/documents/35034/05_a41kakusyukouzounosekkei_1.pdf)：4.1.3-2～3・図4（同一変形時のX形筋かい付きラーメンの水平耐力） |
| `S-K6-X-BRACE-TENSION-COMPRESSION-CAPACITY` | 既確認の再点検／本文・条件・設問補正 | P170・203; コード14225・26153・29251 | 所有教材の記載・図を直接確認 |
| `S-K6-COLUMN-BASE-NOTIFICATION-1456` | source_gap→確認済み／本文・条件・設問補正 | P204; 解説・図 | [建築基準法施行令（e-Gov現行本文、2026-10-06照合）](https://laws.e-gov.go.jp/law/325CO0000000338)：第66条<br>[平成12年建設省告示第1456号（平成19年改正を含む公表本文）](https://www.mlit.go.jp/notice/noticedata/pdf/201703/00006502.pdf)：前文ただし書・第一号・第三号（通常の柱脚。後続のコンテナ等特例は令和7年技術的助言を参照）<br>[国土交通省 国住指第502号（令和7年4月1日）](https://www.mlit.go.jp/jutakukentiku/build/content/001881640.pdf)：3. コンテナ等建築物の柱の脚部の構造方法の合理化 |
| `S-K6-ENCASED-BASE-BOTTOM-PIN-MOMENT-TRANSFER` | 既確認の再点検 | P204; コード20173 | 所有教材の記載・図を直接確認 |
| `S-K6-FIREPROOFING-BOARD-ATTACHMENT` | source_gap→確認済み／本文・条件・設問補正 | P205; 解説・図 | [公共建築工事標準仕様書（建築工事編）令和7年版](https://www.mlit.go.jp/gobuild/content/001888816.pdf)：7.9.2、7.9.3、7.9.5（工法区分・性能・法定又は認定仕様） |
| `S-K6-FIREPROOFING-CAST-IN` | source_gap→確認済み／本文・条件・設問補正 | P205; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-FIREPROOFING-PLASTER-FINISH` | source_gap→確認済み／本文・条件・設問補正 | P205; 解説・図 | [公共建築工事標準仕様書（建築工事編）令和7年版](https://www.mlit.go.jp/gobuild/content/001888816.pdf)：7.9.2、7.9.3、7.9.7（ラス張りモルタル塗り） |
| `S-K6-FIREPROOFING-REQUIRED-ABOVE-250C` | draft→確認済み／本文・条件・設問補正 | P205; 解説・図 | [建築研究所 BRI NEWS Vol.47（2009年10月）](https://www.kenken.go.jp/japanese/contents/publications/epistura/pdf/47.pdf)：P3 鋼構造部材の耐火性・温度上昇による耐力低下 |
| `S-K6-FIREPROOFING-SPRAY-APPLIED` | source_gap→確認済み／本文・条件・設問補正 | P205; 解説・図 | [公共建築工事標準仕様書（建築工事編）令和7年版](https://www.mlit.go.jp/gobuild/content/001888816.pdf)：7.9.2～7.9.4（工法区分・認定工法・飛散防止） |
| `S-K6-COLUMN-SPLICE-NEAR-MIDSTORY` | 既確認の再点検 | P172・206; コード05153・19152・26261・29183 | 所有教材の記載・図を直接確認 |
| `S-K6-JOINT-SPLICE-LOCATION-FABRICATION` | 既確認の再点検 | P206; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-SPLICE-FRICTION-JOINT-SELECTION` | source_gap→確認済み／本文・条件・設問補正 | P207; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-FRAME-COLUMN-BUCKLING-LENGTH-RESTRAINT` | 既確認の再点検 | P172・208; コード02151・03151・20162・26174・29153 | 所有教材の記載・図を直接確認 |
| `S-K6-TRUSS-MEMBER-IN-OUT-PLANE-BUCKLING-LENGTH` | source_gap→確認済み／本文・条件・設問補正 | P172・208; コード27171 | 所有教材の記載・図を直接確認 |
| `S-K6-THROUGH-DIAPHRAGM-THICKNESS-MISMATCH-PREVENTION` | 既確認の再点検 | P173・209; コード01171・06162・25181 | 所有教材の記載・図を直接確認 |
| `S-K6-INTERNAL-DIAPHRAGM-CONSTRUCTION` | 既確認の再点検／本文・条件・設問補正 | P209; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-THROUGH-DIAPHRAGM-CONSTRUCTION-AND-WELD` | source_gap→確認済み | P209; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-MULTIPASS-HEAT-INPUT-INTERPASS-UPPER-CONTROL` | 既確認の再点検／本文・条件・設問補正 | P174・211; コード04181・20184・23174・30151 | 所有教材の記載・図を直接確認 |
| `S-K6-PREHEAT-PREVENTS-LOW-TEMPERATURE-CRACKING` | 既確認の再点検／本文・条件・設問補正 | P175・211; コード22173・28153 | [公共建築工事標準仕様書（建築工事編）令和7年版](https://www.mlit.go.jp/gobuild/content/001888816.pdf)：7.6.7(1)(オ)、7.6.8（予熱・施工条件） |
| `S-K6-WELD-PASS-AND-MULTIPASS-IDENTIFICATION` | 既確認の再点検／本文・条件・設問補正 | P211; 解説・図 | 所有教材の記載・図を直接確認 |
| `S-K6-HEAT-AFFECTED-ZONE-IDENTIFICATION` | 既確認の再点検 | P212; コード21171 | 所有教材の記載・図を直接確認 |
| `S-K6-WELD-BASIC-SYMBOL-SHAPES` | source_gap→確認済み／本文・条件・設問補正 | P212; コード21171 | 所有教材の記載・図を直接確認 |
| `S-K6-WELD-METAL-COMPOSITION` | 既確認の再点検 | P212; コード21171 | 所有教材の記載・図を直接確認 |
| `S-K6-BRACE-HYSTERESIS-BY-SLENDERNESS` | 既確認の再点検 | P214・215; コード05181 | 所有教材の記載・図を直接確認 |
| `S-K6-MOMENT-FRAME-HYSTERESIS` | 既確認の再点検 | P214・215; コード05181 | 所有教材の記載・図を直接確認 |
| `S-K6-HYSTERESIS-LOOP-AREA-ENERGY-ABSORPTION` | source_gap→確認済み／本文・条件・設問補正 | P214・215; コード05181 | 所有教材の記載・図を直接確認 |
| `S-K6-BRACE-SHARE-SEISMIC-STRESS-AMPLIFICATION` | 既確認の再点検 | P215; コード05181 | 所有教材の記載・図を直接確認 |

## 残課題・検証記録

- この担当範囲について、公開を止める未入手の必須資料は残っていない。AIJ有料規準の全文を読んだとは記録していない。外部資料が引用している有料規準については、実際に確認した行政の解説範囲だけを根拠とした。
- 法令や規格の適用対象を拡張する新問題を追加する際は、その対象・版・例外について再確認が必要。
- 最新章YAMLで `python -m principle_catalog validate` の章スキーマ・設問内容検証を通過。最後の18件の問題変更後は、マニフェストの独立監査スナップショットの再計算が必要となり、root担当へ連絡済み。
- `git diff --check` は通過。本担当はコミット・公開を実施していない。全サイトの統合テスト・公開可否はroot側の検証結果に従う。
