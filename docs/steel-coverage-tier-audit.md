# 鉄骨構造の導入層 監査記録

## 結論

公開条件を満たす116問を、全体を薄く見てから段階的に厚くする累積三層へ固定した。骨格32問は公開問のある32小項目を各1問ずつ含み、標準42問と発展42問を追加すると、学習対象は32問、74問、116問と広がる。

この層は実測難易度や価値の上下ではない。内容上の導入段階を固定する投影であり、個人の苦手度は非公開の学習結果から別に扱う。

## 層の定義

| Tier | slug | 表示名 | 新規問数 | 累積問数 | 役割 |
|---:|---|---|---:|---:|---|
| 1 | foundation | 骨格 | 32 | 32 | 公開32小項目の代表と、その理解に必要な前提 |
| 2 | standard | 標準 | 42 | 74 | 各小項目の標準的な機構・適用・基本識別 |
| 3 | advanced | 発展 | 42 | 116 | 統合判断、例外、細部。重要度が低いという意味ではない |

現行スキームは steel-coverage-v1。K6-R2の問題番号、公開コード、内部キーは変更せず、層と導入順だけを独立して版管理する。

## 制約監査

| 制約 | 期待値 | 実測 |
|---|---|---|
| 対象 | source_checked の正式公開問のみ | 116/116問。調査中100問の候補層は別台帳であり、v1の集計対象外 |
| Tier件数 | 32 / 42 / 42 | 32 / 42 / 42 |
| 正解A/B | 16/16、21/21、21/21 | 16/16、21/21、21/21 |
| 型（原理/規定/識別） | 19/7/6、25/9/8、25/9/8 | 19/7/6、25/9/8、25/9/8 |
| 骨格の小項目網羅 | 公開問のある全小項目を各1問 | 32/32小項目、重複なし |
| 標準の広がり | 2問以上ある小項目に追加問 | 25/25小項目 |
| 前提関係 | 前提のTier以下、かつ導入順が先 | 公開59辺すべて適合 |
| 同一正解の連続 | 各Tierで3以下 | 最大3 |
| 導入順 | スキーム内で1〜116を一意に使用 | 欠番・重複なし |
| 分野巡回 | その時点で導入可能な大項目を巡回 | 6公開大項目をeligible group breadth-firstで配置 |

## 選定規則

1. Tier 1は、公開問のある32小項目から1問ずつ選ぶ。全前提がTier 1内で先に導入されることを最優先し、型構成とA/Bを均衡させる。
2. Tier 2は、2問以上ある25小項目すべてに追加問を置き、残りを標準的な機構・適用で構成する。前提閉包が件数配分より優先する。
3. Tier 3は残りを収容する。前提深度2以上、直接前提2件以上、又は大項目をまたぐ前提を持つ場合は integrated_judgment、それ以外は exception_detail とした。
4. prerequisite は公開後続問を持つ項目、basic_identification はTier 1又は2の識別項目に付す。理由語彙はYAMLに現れる6種類だけとする。
5. 問題コード参照数、文章量、条件数を単独の重要度・難易度にはしない。コードは複数カードへ重複し、構造的複雑性は個人の認知難度と一致しないためである。

## 導入順の決定規則

各Tierを1から3の順に処理する。未導入の前提がない項目だけをeligibleとし、直前まで同じ正解が3回続いた場合は反対の正解だけをeligibleとする。大項目1〜6の巡回カーソルから最初に見つかるeligibleな大項目を選び、同一大項目では小項目順、同じTier内で直後に解禁する項目数の多い順、K6-R2順で決定する。カーソルはTier境界でも維持する。

## 第7群と未公開小項目

第7群「耐火・特殊荷重」は8項目あるが、3小項目とも確認済み公開問が0件であるため steel-coverage-v1 には含めない。`/research/` にある全100件は暫定問題と候補層を持つが、正式な問題版、正解、学習状態、coverage tierには含めない。候補層は既存116件の割当を保持した全216件の導入順として別台帳で監査し、正式昇格時に次版の正式割当へ持ち越すかを再確認する。

第2群「梁の種類・断面・設計応力」と第6群「柱脚形式・共通規定」も現在は公開問が0件である。骨格32問が網羅するのは37小項目全体ではなく、公開問のある32小項目である。

## 調査100問の候補層 v1

`steel-research-coverage-v1` は正式な `steel-coverage-v1` を変更せず、未確認100問を全216件の累積学習順へ仮配置する。件数は骨格5、標準47、発展48であり、均等割当や難易度スコアではなく、小項目網羅、内容の役割、前提関係で決めた。既存32件の骨格代表と合わせると、37小項目を各1件で網羅する。

新たに骨格候補とした5件は次のとおりである。

| 小項目 | 候補項目 | 選定理由 |
|---|---|---|
| 梁の種類・断面・設計応力 | 梁によく使う形鋼 | 基本的な形鋼識別で、当該小項目の入口になる |
| 柱脚形式・共通規定 | 柱脚形式と固定度の大小 | 3形式の全体像を示し、後続2件の前提になる |
| 高温時挙動・火災荷重 | 耐火設計の火災荷重 | 当該小項目でdraftではない基本識別を代表にする |
| 耐火被覆工法 | 吹付け耐火被覆の施工法と特徴 | 4工法のうち代表的な基本識別として仮置きする |
| 特殊荷重・付帯設備 | 天井走行クレーンの地震力算定 | 当該小項目にある唯一の項目を代表にする |

標準候補は通常条件の規定、基本機構、基本識別を中心とし、発展候補は例外・数値細部又は複数前提の統合判断を中心とする。全候補について、前提項目の候補層又は正式層が後続項目より後にならないことをvalidatorで確認する。候補層は正しさの判定ではなく、正式昇格時には内容と前提を再監査する。

## ハッシュ

content_sha256: 2a10b30fe54b4f608db1e2dcdcfbc31f8a6dacc249e8d426ff05b76e9ae53a7d
coverage registry SHA-256: 6f63d9df0776cea7976431b8b0638b726f46444b74d4660a778b7941de515df9

content_sha256 の対象は当該スキームの constraints と、導入順の key/tier/introduction_order/reasons 配列である。status とハッシュ値自身は含めず、sort_keys=true、空白なしのUTF-8 JSONでSHA-256を計算する。registry SHA-256は版一覧、層定義、status、content_sha256を含む投影全体の監査値である。

## 全116問の割当

| 導入順 | Tier | K6-R2 | 公開コード | 問題名 | 大項目 | 小項目 | 型 | 正解 | 理由 |
|---:|---:|---:|---|---|---|---|---|:---:|---|
| 1 | 1 | Q001 | structure.steel.frame-h-section-axis-role | H形断面柱の強軸・弱軸と架構形式 | 架構・鋼材・許容応力度 | 架構形式・H形鋼断面 | principle | A | coverage_representative |
| 2 | 1 | Q007 | structure.steel.elastic-deflection-not-reduced-by-higher-steel-grade | 鋼種の高強度化と弾性たわみ | 梁・柱・座屈 | 高強度化・断面縮小・たわみ | principle | A | coverage_representative |
| 3 | 1 | Q031 | structure.steel.connection-type-identification | 鋼材の接合方法 | ボルト接合 | 接合形式・普通ボルト | identification | B | coverage_representative, prerequisite, basic_identification |
| 4 | 1 | Q049 | structure.steel.weld-metal-composition | 溶着金属と溶接金属の構成 | 溶接接合 | 溶接の種類・構成・特徴 | identification | B | coverage_representative, prerequisite, basic_identification |
| 5 | 1 | Q073 | structure.steel.brace-horizontal-load-axial-force | ブレースによる水平力から軸力への変換 | ブレース・耐震 | ブレースの役割・荷重経路・配置 | principle | A | coverage_representative, prerequisite |
| 6 | 1 | Q097 | structure.steel.box-column-h-beam-weld-types | 角形鋼管柱・H形鋼梁仕口の溶接形式 | 柱脚・仕口・継手 | 柱梁仕口・梁端 | principle | B | coverage_representative |
| 7 | 1 | Q002 | structure.steel.ductility-prevents-brittle-fracture | 鋼材の靭性と破断 | 架構・鋼材・許容応力度 | 鉄骨構造・鋼材特性 | principle | B | coverage_representative |
| 8 | 1 | Q009 | structure.steel.compression-member-slenderness | 全体座屈と細長比 | 梁・柱・座屈 | 圧縮材・全体座屈・細長比 | principle | A | coverage_representative, prerequisite |
| 9 | 1 | Q035 | structure.steel.friction-joint-pre-slip-force-transfer | 高力ボルト摩擦接合のすべり前の伝力機構 | ボルト接合 | 高力ボルト摩擦接合の機構 | principle | A | coverage_representative, prerequisite |
| 10 | 1 | Q052 | structure.steel.weld-throat-allowable-shear-independent-of-joint-form | 溶接継目の形式と許容せん断応力度 | 溶接接合 | 溶接部の許容応力度 | rule | B | coverage_representative |
| 11 | 1 | Q079 | structure.steel.brace-capacity-design-joint-overstrength | 筋かい端部・接合部の保有耐力接合 | ブレース・耐震 | ブレース・トラス接合 | rule | B | coverage_representative |
| 12 | 1 | Q099 | structure.steel.internal-diaphragm-construction | 内ダイアフラム形式の製作手順 | 柱脚・仕口・継手 | ダイアフラム | identification | B | coverage_representative, basic_identification |
| 13 | 1 | Q015 | structure.steel.no-lateral-buckling-section-allowable-bending | 横座屈しない断面の許容曲げ応力度 | 梁・柱・座屈 | 横座屈の機構・断面条件 | rule | A | coverage_representative |
| 14 | 1 | Q041 | structure.steel.high-strength-bolt-allowable-shear-table | 摩擦面数・荷重期間と高力ボルト許容せん断耐力 | ボルト接合 | 高力ボルトの耐力・配置・摩擦面 | rule | A | coverage_representative |
| 15 | 1 | Q053 | structure.steel.end-tabs-secure-sound-weld-ends | 完全溶込み溶接端部のエンドタブ | 溶接接合 | 完全溶込み溶接 | principle | A | coverage_representative, prerequisite |
| 16 | 1 | Q084 | structure.steel.brace-tension-yield-compression-buckling | ブレースの引張降伏と圧縮座屈 | ブレース・耐震 | 座屈・終局耐力 | principle | B | coverage_representative, prerequisite |
| 17 | 1 | Q102 | structure.steel.beam-splice-methods-field-shop | 現場継手と工場仕口の接合方法 | 柱脚・仕口・継手 | 柱・梁の継手、工場・現場接合 | identification | A | coverage_representative, basic_identification |
| 18 | 1 | Q003 | structure.steel.allowable-stress-duration | 構造用鋼材の長期・短期許容応力度 | 架構・鋼材・許容応力度 | 基準強度・材料強度・許容応力度 | rule | B | coverage_representative |
| 19 | 1 | Q017 | structure.steel.lateral-bracing-enables-full-plastic-moment | 横補剛と梁の全塑性モーメント | 梁・柱・座屈 | 横補剛・保有耐力設計 | principle | B | coverage_representative, prerequisite |
| 20 | 1 | Q042 | structure.steel.f10t-tensile-strength-meaning | F10Tの記号と引張強さ | ボルト接合 | ボルト製品・締付け・検査 | identification | B | coverage_representative, basic_identification |
| 21 | 1 | Q060 | structure.steel.weld-scallop-definition | スカラップとノンスカラップ | 溶接接合 | 溶接記号・欠陥・非破壊検査 | identification | A | coverage_representative, prerequisite, basic_identification |
| 22 | 1 | Q080 | structure.steel.angle-channel-brace-effective-area | 山形鋼・溝形鋼筋かいの有効断面積 | ブレース・耐震 | 偏心・有効断面 | principle | A | coverage_representative, prerequisite |
| 23 | 1 | Q108 | structure.steel.exposed-base-model-by-design-target | 露出柱脚の解析モデルと設計対象 | 柱脚・仕口・継手 | 露出柱脚 | principle | A | coverage_representative, prerequisite |
| 24 | 1 | Q004 | structure.steel.corrosion-protection | 鋼材の発錆と防錆処理 | 架構・鋼材・許容応力度 | 腐食・防錆 | principle | B | coverage_representative |
| 25 | 1 | Q024 | structure.steel.member-local-buckling-width-thickness | 局部座屈と幅厚比 | 梁・柱・座屈 | 局部座屈・幅厚比・スチフナ | principle | B | coverage_representative, prerequisite |
| 26 | 1 | Q048 | structure.steel.reference-fatigue-strength-joint-type | 接合形式別の基準疲労強さ | ボルト接合 | 繰返し荷重・疲労 | rule | A | coverage_representative |
| 27 | 1 | Q058 | structure.steel.fillet-weld-effective-length | すみ肉溶接の有効長さ | 溶接接合 | すみ肉・部分溶込み溶接 | rule | B | coverage_representative |
| 28 | 1 | Q087 | structure.steel.buckling-restrained-brace-force-roles | 座屈拘束ブレースの芯材と拘束材の役割 | ブレース・耐震 | 履歴特性・特殊ブレース・地震応力 | principle | B | coverage_representative |
| 29 | 1 | Q113 | structure.steel.wrapped-base-moment-distribution | 根巻き柱脚内の曲げモーメント分布 | 柱脚・仕口・継手 | 根巻き柱脚 | principle | A | coverage_representative, prerequisite |
| 30 | 1 | Q071 | structure.steel.weld-heat-distortion | 溶接熱とひずみ | 溶接接合 | 溶接熱・パス・施工管理 | principle | B | coverage_representative, prerequisite |
| 31 | 1 | Q116 | structure.steel.embedded-base-force-transfer | 埋込み柱脚の応力伝達 | 柱脚・仕口・継手 | 埋込み柱脚 | principle | A | coverage_representative |
| 32 | 1 | Q072 | structure.steel.combined-bolt-weld-construction-order | 高力ボルト・溶接併用継手の施工順序 | 溶接接合 | 併用接合 | principle | A | coverage_representative |
| 33 | 2 | Q075 | structure.steel.floor-horizontal-truss-secondary-beam-axial-force | 小梁・水平ブレース床トラスの小梁軸力 | ブレース・耐震 | ブレースの役割・荷重経路・配置 | principle | A | standard_application |
| 34 | 2 | Q093 | structure.steel.no-scallop-improves-beam-end-ductility | スカラップと梁端の塑性変形能力 | 柱脚・仕口・継手 | 柱梁仕口・梁端 | principle | B | standard_application |
| 35 | 2 | Q005 | structure.steel.higher-strength-steel-reduces-depth-only-strength-governs | 強度支配部材での高強度鋼による断面縮小 | 梁・柱・座屈 | 高強度化・断面縮小・たわみ | principle | A | standard_application |
| 36 | 2 | Q032 | structure.steel.ordinary-bolt-shear-transfer | 普通ボルト接合のせん断伝達 | ボルト接合 | 接合形式・普通ボルト | principle | B | standard_application, prerequisite |
| 37 | 2 | Q050 | structure.steel.heat-affected-zone-identification | 熱影響部の位置と性質 | 溶接接合 | 溶接の種類・構成・特徴 | identification | A | standard_application, basic_identification |
| 38 | 2 | Q076 | structure.steel.gusset-plate-member-connection | ガセットプレートの用途 | ブレース・耐震 | ブレース・トラス接合 | identification | B | standard_application, prerequisite, basic_identification |
| 39 | 2 | Q098 | structure.steel.square-tube-column-diaphragm-types | 柱梁仕口のダイアフラムの役割と形式 | 柱脚・仕口・継手 | ダイアフラム | identification | A | standard_application, prerequisite, basic_identification |
| 40 | 2 | Q013 | structure.steel.limit-slenderness-strength-relation | 限界細長比と基準強度 | 梁・柱・座屈 | 圧縮材・全体座屈・細長比 | principle | B | standard_application, prerequisite |
| 41 | 2 | Q036 | structure.steel.high-strength-bolt-stress-distribution | 高力ボルト摩擦接合の応力集中 | ボルト接合 | 高力ボルト摩擦接合の機構 | principle | B | standard_application |
| 42 | 2 | Q057 | structure.steel.end-tab-tack-weld-to-backing | 鋼製エンドタブの組立溶接位置 | 溶接接合 | 完全溶込み溶接 | principle | A | standard_application |
| 43 | 2 | Q077 | structure.steel.brace-to-hollow-column-diaphragm-reinforcement | 中空角形鋼管柱への筋かい接合補強 | ブレース・耐震 | ブレース・トラス接合 | principle | A | standard_application |
| 44 | 2 | Q100 | structure.steel.through-diaphragm-thickness-mismatch-prevention | 通しダイアフラムの食い違い防止板厚 | 柱脚・仕口・継手 | ダイアフラム | principle | A | standard_application |
| 45 | 2 | Q008 | structure.steel.compression-capacity-buckling | 圧縮耐力の座屈支配 | 梁・柱・座屈 | 圧縮材・全体座屈・細長比 | principle | B | standard_application |
| 46 | 2 | Q039 | structure.steel.friction-surface-preparation | 摩擦接合面の表面状態 | ボルト接合 | 高力ボルト摩擦接合の機構 | rule | B | standard_application |
| 47 | 2 | Q059 | structure.steel.partial-penetration-effective-throat-deduction | 部分溶込み溶接の有効のど厚 | 溶接接合 | すみ肉・部分溶込み溶接 | rule | B | standard_application |
| 48 | 2 | Q083 | structure.steel.brace-bolt-count-increases-effective-area | 筋かい接合のボルト本数と有効断面積 | ブレース・耐震 | 偏心・有効断面 | principle | A | standard_application |
| 49 | 2 | Q103 | structure.steel.column-splice-near-midstory | 柱・梁の継手位置と作用力 | 柱脚・仕口・継手 | 柱・梁の継手、工場・現場接合 | principle | A | standard_application |
| 50 | 2 | Q010 | structure.steel.frame-column-buckling-length-restraint | ラーメン柱の水平移動拘束と座屈長さ | 梁・柱・座屈 | 圧縮材・全体座屈・細長比 | principle | B | standard_application |
| 51 | 2 | Q040 | structure.steel.friction-joint-shear-tension-interaction | 高力ボルト摩擦接合のせん断・引張相互作用 | ボルト接合 | 高力ボルトの耐力・配置・摩擦面 | principle | A | standard_application |
| 52 | 2 | Q062 | structure.steel.weld-defect-slag-inclusion | スラグ巻込みの識別 | 溶接接合 | 溶接記号・欠陥・非破壊検査 | identification | A | standard_application, basic_identification |
| 53 | 2 | Q085 | structure.steel.brace-slenderness-and-deformation-capacity | 筋かいの有効細長比と変形性能 | ブレース・耐震 | 座屈・終局耐力 | principle | A | standard_application |
| 54 | 2 | Q109 | structure.steel.exposed-base-anchor-embedment-length | 露出柱脚アンカーボルトの定着長さ | 柱脚・仕口・継手 | 露出柱脚 | rule | B | standard_application |
| 55 | 2 | Q014 | structure.steel.compression-elastic-buckling-strength-independence | 弾性座屈領域と鋼材強度 | 梁・柱・座屈 | 圧縮材・全体座屈・細長比 | principle | B | standard_application |
| 56 | 2 | Q044 | structure.steel.torshear-bolt-pintail-secondary-tightening | トルシア形高力ボルトのピンテール破断 | ボルト接合 | ボルト製品・締付け・検査 | principle | B | standard_application, prerequisite |
| 57 | 2 | Q088 | structure.steel.moment-frame-hysteresis | ラーメン架構の履歴特性 | ブレース・耐震 | 履歴特性・特殊ブレース・地震応力 | principle | A | standard_application |
| 58 | 2 | Q107 | structure.steel.ductile-anchor-bolt-types-and-yield-sequence | 伸び能力のあるアンカーボルト | 柱脚・仕口・継手 | 露出柱脚 | identification | A | standard_application, basic_identification |
| 59 | 2 | Q016 | structure.steel.beam-lateral-buckling-countermeasures | 横座屈の抑制方法 | 梁・柱・座屈 | 横座屈の機構・断面条件 | rule | A | standard_application, prerequisite |
| 60 | 2 | Q047 | structure.steel.friction-joint-repeated-load-below-slip | すべり耐力以下の繰返し応力と摩擦接合 | ボルト接合 | 繰返し荷重・疲労 | principle | B | standard_application |
| 61 | 2 | Q063 | structure.steel.weld-ndt-internal-vs-surface-defects | 溶接欠陥の位置と非破壊試験 | 溶接接合 | 溶接記号・欠陥・非破壊検査 | identification | B | standard_application, basic_identification |
| 62 | 2 | Q086 | structure.steel.x-brace-tension-compression-capacity | X形筋かいの引張側・圧縮側耐力の合算 | ブレース・耐震 | 座屈・終局耐力 | rule | B | standard_application |
| 63 | 2 | Q115 | structure.steel.wrapped-base-height-and-top-confinement | 根巻き柱脚の高さと上端拘束 | 柱脚・仕口・継手 | 根巻き柱脚 | rule | A | standard_application |
| 64 | 2 | Q019 | structure.steel.full-plastic-lateral-bracing-placement-methods | 保有耐力横補剛の配置方法 | 梁・柱・座屈 | 横補剛・保有耐力設計 | identification | B | standard_application, prerequisite, basic_identification |
| 65 | 2 | Q066 | structure.steel.preheat-prevents-low-temperature-cracking | 予熱と低温割れ防止 | 溶接接合 | 溶接熱・パス・施工管理 | principle | B | standard_application, prerequisite |
| 66 | 2 | Q018 | structure.steel.h-section-strong-axis-lateral-restraint | 強軸曲げを受けるH形鋼の横座屈対応 | 梁・柱・座屈 | 横補剛・保有耐力設計 | rule | A | standard_application |
| 67 | 2 | Q068 | structure.steel.multipass-heat-input-interpass-upper-control | 入熱量・パス間温度と溶接部強度 | 溶接接合 | 溶接熱・パス・施工管理 | principle | B | standard_application, prerequisite |
| 68 | 2 | Q021 | structure.steel.lateral-brace-strength-and-stiffness | 中間横補剛材に必要な強度と剛性 | 梁・柱・座屈 | 横補剛・保有耐力設計 | rule | B | standard_application |
| 69 | 2 | Q067 | structure.steel.tack-weld-minimum-bead | 組立溶接のショートビード防止 | 溶接接合 | 溶接熱・パス・施工管理 | rule | A | standard_application |
| 70 | 2 | Q023 | structure.steel.higher-strength-requires-more-uniform-bracing | 鋼材強度と均等配置横補剛数 | 梁・柱・座屈 | 横補剛・保有耐力設計 | principle | A | standard_application |
| 71 | 2 | Q070 | structure.steel.preheat-lower-bound-vs-interpass-upper-bound | 予熱温度管理とパス間温度管理の違い | 溶接接合 | 溶接熱・パス・施工管理 | principle | B | standard_application |
| 72 | 2 | Q028 | structure.steel.width-thickness-limit-meaning | 幅厚比制限の意味 | 梁・柱・座屈 | 局部座屈・幅厚比・スチフナ | identification | B | standard_application, prerequisite, basic_identification |
| 73 | 2 | Q025 | structure.steel.lateral-local-buckling-interaction | 横座屈変形と局部座屈・耐力低下 | 梁・柱・座屈 | 局部座屈・幅厚比・スチフナ | principle | A | standard_application |
| 74 | 2 | Q029 | structure.steel.width-thickness-limit-decreases-with-strength | 基準強度と幅厚比上限 | 梁・柱・座屈 | 局部座屈・幅厚比・スチフナ | principle | A | standard_application |
| 75 | 3 | Q033 | structure.steel.ordinary-bolt-clearance-loosening | 普通ボルト孔のクリアランスと緩み | ボルト接合 | 接合形式・普通ボルト | principle | A | integrated_judgment |
| 76 | 3 | Q054 | structure.steel.full-penetration-weld-effective-length | 完全溶込み溶接の有効長さ | 溶接接合 | 完全溶込み溶接 | rule | B | exception_detail |
| 77 | 3 | Q074 | structure.steel.vertical-horizontal-brace-roles | 鉛直ブレースと水平ブレースの配置面別役割 | ブレース・耐震 | ブレースの役割・荷重経路・配置 | identification | B | exception_detail |
| 78 | 3 | Q092 | structure.steel.beam-end-strength-section-loss-and-tube-deformation | 角形鋼管柱・H形鋼梁仕口の梁端最大耐力 | 柱脚・仕口・継手 | 柱梁仕口・梁端 | principle | A | exception_detail |
| 79 | 3 | Q006 | structure.steel.high-strength-steel-beam-deflection-check | 高強度鋼で小断面化した梁のたわみ確認 | 梁・柱・座屈 | 高強度化・断面縮小・たわみ | principle | B | exception_detail |
| 80 | 3 | Q034 | structure.steel.ordinary-bolts-prohibited-for-repeated-load | 振動・衝撃・繰返し応力部のボルト選定 | ボルト接合 | 接合形式・普通ボルト | rule | B | integrated_judgment |
| 81 | 3 | Q051 | structure.steel.weld-continuous-stress-flow | 溶接接合の連続性と応力集中 | 溶接接合 | 溶接の種類・構成・特徴 | principle | A | exception_detail |
| 82 | 3 | Q078 | structure.steel.brace-side-fillet-weld-force-transfer | 筋かいとガセットプレートの側面すみ肉溶接 | ブレース・耐震 | ブレース・トラス接合 | principle | B | exception_detail |
| 83 | 3 | Q094 | structure.steel.sn490-beam-column-joint-overstrength | SN490B柱梁仕口の最大曲げ強度 | 柱脚・仕口・継手 | 柱梁仕口・梁端 | rule | A | integrated_judgment |
| 84 | 3 | Q011 | structure.steel.h-section-column-weak-axis-governs-buckling | H形断面圧縮材の座屈軸 | 梁・柱・座屈 | 圧縮材・全体座屈・細長比 | principle | A | exception_detail |
| 85 | 3 | Q037 | structure.steel.friction-joint-post-slip-rupture-model | 高力ボルト摩擦接合の破断耐力時の伝力機構 | ボルト接合 | 高力ボルト摩擦接合の機構 | principle | A | integrated_judgment |
| 86 | 3 | Q056 | structure.steel.weld-backing-bar-root-gap | 裏あて金の役割と必要条件 | 溶接接合 | 完全溶込み溶接 | rule | B | exception_detail |
| 87 | 3 | Q081 | structure.steel.brace-eccentric-joint-effects | 筋かい接合の偏心 | ブレース・耐震 | 偏心・有効断面 | principle | B | exception_detail |
| 88 | 3 | Q095 | structure.steel.beam-flange-web-force-sharing | 梁継手のフランジ・ウェブ応力分担 | 柱脚・仕口・継手 | 柱梁仕口・梁端 | principle | B | exception_detail |
| 89 | 3 | Q020 | structure.steel.wider-flange-reduces-bracing-demand | フランジ幅と横座屈・横補剛数 | 梁・柱・座屈 | 横補剛・保有耐力設計 | principle | A | integrated_judgment |
| 90 | 3 | Q038 | structure.steel.high-strength-bolt-slip-rigidity | 高力ボルト摩擦接合の滑りと剛性 | ボルト接合 | 高力ボルト摩擦接合の機構 | principle | B | exception_detail |
| 91 | 3 | Q055 | structure.steel.weld-back-gouging-purpose | 裏はつりの目的と順序 | 溶接接合 | 完全溶込み溶接 | principle | A | exception_detail |
| 92 | 3 | Q082 | structure.steel.double-angle-brace-reduces-eccentricity | 山形鋼筋かいの両側対称配置 | ブレース・耐震 | 偏心・有効断面 | principle | A | integrated_judgment |
| 93 | 3 | Q096 | structure.steel.horizontal-haunch-reduces-beam-end-stress | 水平ハンチと梁端接合部応力度 | 柱脚・仕口・継手 | 柱梁仕口・梁端 | principle | B | exception_detail |
| 94 | 3 | Q012 | structure.steel.built-up-column-non-solid-axis-slenderness-increase | 組立圧縮材の非充腹軸座屈 | 梁・柱・座屈 | 圧縮材・全体座屈・細長比 | principle | B | exception_detail |
| 95 | 3 | Q043 | structure.steel.f14t-clamping-force-reduces-bolt-count | F14T級超高力ボルトと接合部の小型化 | ボルト接合 | ボルト製品・締付け・検査 | principle | A | exception_detail |
| 96 | 3 | Q064 | structure.steel.weld-defect-blowhole | ブローホールの識別 | 溶接接合 | 溶接記号・欠陥・非破壊検査 | identification | A | exception_detail, prerequisite |
| 97 | 3 | Q089 | structure.steel.brace-hysteresis-by-slenderness | 筋かい細長比による履歴特性の差 | ブレース・耐震 | 履歴特性・特殊ブレース・地震応力 | principle | B | integrated_judgment |
| 98 | 3 | Q101 | structure.steel.joint-splice-location-fabrication | 仕口・継手の位置と製作場所 | 柱脚・仕口・継手 | 柱・梁の継手、工場・現場接合 | identification | B | exception_detail |
| 99 | 3 | Q022 | structure.steel.first-stage-bending-check-not-plastic-bracing-check | 一次設計の許容曲げ検討と保有耐力横補剛の区別 | 梁・柱・座屈 | 横補剛・保有耐力設計 | principle | A | integrated_judgment |
| 100 | 3 | Q045 | structure.steel.aluminum-friction-joint-galvanized-bolts | アルミニウム合金材の高力ボルト選定 | ボルト接合 | ボルト製品・締付け・検査 | rule | A | exception_detail |
| 101 | 3 | Q061 | structure.steel.weld-defect-undercut | アンダーカットの識別 | 溶接接合 | 溶接記号・欠陥・非破壊検査 | identification | B | exception_detail |
| 102 | 3 | Q090 | structure.steel.eccentric-k-brace-energy-dissipation | 偏心K形筋かいのエネルギー吸収 | ブレース・耐震 | 履歴特性・特殊ブレース・地震応力 | principle | A | exception_detail |
| 103 | 3 | Q104 | structure.steel.column-splice-minimum-design-strength | 柱継手の最低設計耐力 | 柱脚・仕口・継手 | 柱・梁の継手、工場・現場接合 | rule | A | exception_detail |
| 104 | 3 | Q026 | structure.steel.stiffener-role-by-position-and-stress | スチフナの配置と局部座屈防止の役割 | 梁・柱・座屈 | 局部座屈・幅厚比・スチフナ | identification | B | exception_detail |
| 105 | 3 | Q046 | structure.steel.torshear-bolt-rotation-marking-inspection | トルシア形高力ボルトの共回り・軸回り検査 | ボルト接合 | ボルト製品・締付け・検査 | rule | A | exception_detail |
| 106 | 3 | Q065 | structure.steel.weld-defect-pit | ピットの識別 | 溶接接合 | 溶接記号・欠陥・非破壊検査 | identification | B | exception_detail |
| 107 | 3 | Q091 | structure.steel.brace-share-seismic-stress-amplification | 筋かい水平力分担率による地震時応力割増し | ブレース・耐震 | 履歴特性・特殊ブレース・地震応力 | rule | B | exception_detail |
| 108 | 3 | Q105 | structure.steel.exposed-base-rc-analogy-for-axial-and-bending | 軸力・曲げを受ける露出柱脚のRC柱類似設計 | 柱脚・仕口・継手 | 露出柱脚 | principle | B | exception_detail |
| 109 | 3 | Q027 | structure.steel.thin-section-buckling | 薄い鋼部材と座屈 | 梁・柱・座屈 | 局部座屈・幅厚比・スチフナ | principle | A | exception_detail |
| 110 | 3 | Q069 | structure.steel.weld-pass-and-multipass-identification | 1パスと多パス溶接 | 溶接接合 | 溶接熱・パス・施工管理 | identification | A | integrated_judgment |
| 111 | 3 | Q106 | structure.steel.anchor-bolt-resistance-types | アンカーボルトの引張支持抵抗形式 | 柱脚・仕口・継手 | 露出柱脚 | identification | A | exception_detail |
| 112 | 3 | Q030 | structure.steel.column-web-width-thickness-stricter-than-beam | 柱・梁のウェブ幅厚比上限の差 | 梁・柱・座屈 | 局部座屈・幅厚比・スチフナ | principle | B | integrated_judgment |
| 113 | 3 | Q110 | structure.steel.exposed-base-plate-minimum-thickness | 露出柱脚ベースプレートの厚さ | 柱脚・仕口・継手 | 露出柱脚 | rule | A | exception_detail |
| 114 | 3 | Q111 | structure.steel.encased-base-bottom-pin-moment-transfer | 根巻き柱脚最下部の曲げモーメント負担 | 柱脚・仕口・継手 | 根巻き柱脚 | principle | B | exception_detail |
| 115 | 3 | Q112 | structure.steel.wrapped-base-ductile-failure-mode | 根巻き柱脚の望ましい破壊モード | 柱脚・仕口・継手 | 根巻き柱脚 | principle | A | exception_detail |
| 116 | 3 | Q114 | structure.steel.wrapped-base-shear-q2-greater-than-q1 | 根巻き柱脚の上部・根巻き部せん断力の関係 | 柱脚・仕口・継手 | 根巻き柱脚 | principle | B | exception_detail |
