# 鉄骨出題補完カードの配置メモ

確認日: 2026-10-06。補完 95 件の最終配置を記録する。39 章はファイル上の保存単位であり、閲覧画面に「本試験知識（横断）」の巨大な小項目を作るものではない。各カードは具体的な小項目へ配属する。

## 骨格・標準・発展

骨格は各小項目の代表を 1 件とし、全小項目を少量ずつ見渡せる状態を維持する。95 件内の配分は 骨格 10 件・標準 60 件・発展 25 件。数値の細部や条件付き例外を原則として標準・発展に配置する。難しい公式出題であっても、その前提概念は骨格に置けるため、過去問の難しさだけで層を決めない。

## 新規小項目の骨格代表

| 小項目 | 代表 | 狙い |
| --- | --- | --- |
| 鋼材の種別・材料規格 | `SN-C-THICKNESS` | 用途に応じた材料種別選択を、板厚方向性能から学ぶ |
| 構造計算ルート・耐震規定 | `ROUTE1-CO` | ルート1の地震力割増しを計算ルートの入口にする |
| 冷間成形角形鋼管の設計 | `COLD-ROUTE1` | 通常のルートの地震力割増しと冷間成形柱の追加確認を区別する |
| 合成梁・合成床 | `COMPOSITE-STUD` | 鉄骨と床スラブが一体で働く力の伝達を押さえる |
| CFT柱 | `CFT-BUCKLING` | 充填コンクリートが鋼管の局部座屈を抑える機構を押さえる |
| SRC部材・柱脚 | `SRC-BENDING` | 鉄骨とRCの抵抗を累加する基本形を押さえる |
| 混構造の力の伝達 | `MIXED-RC-S-TRANSFER` | 異種部材の境界でも力を確実に伝える原則を押さえる |
| 鋼材ダンパー・制振 | `DAMPER-PLASTICITY` | 繰返し塑性変形によるエネルギー吸収を入口にする |
| 振動特性・耐震改修 | `STEEL-PERIOD` | 鉄骨造の略算周期の扱いと精算の違いを押さえる |
| 鋼材の環境負荷 | `EAF-CARBON` | 必要性能と製造段階の環境負荷を分けて評価する |

## 学習の接続

カードを単独で開いても判断に必要な条件を読めるようにしているため、95 件の `prerequisites` は必須依存としては空にした。以下は先に見ると理解しやすい対応であり、回答や表示をロックする依存ではない。

| 補完カード群 | 先に確認するとよい既存・基礎カード |
| --- | --- |
| SN490-F40・SN-THICKNESS-F・SUS-F | `structure.steel.f-value-definition` |
| SN-YIELD-RANGE・BCR-YIELD-RATIO | `structure.steel.yield-ratio-smaller-preferred` |
| CFT-BUCKLING・CFT-WIDTH-THICKNESS | `structure.steel.member-local-buckling-width-thickness` |
| ROUTE-BRACE-END・COLD-ROUTE2-RATIO | `structure.steel.brace-capacity-design-joint-overstrength`（先行降伏と接合部破断の区別） |
| DAMPER-CONNECTION・DAMPER-FATIGUE | `structure.steel.exam-damper-plasticity` |
| COMPOSITE-FULL・COMPOSITE-STUD-FORCE | `structure.steel.exam-composite-stud` |
| SRC-SHEAR・SRC-EMBEDDED-MIN | `structure.steel.exam-src-bending`（累加の対象を区別する入口） |

## 95 件の対応表

ID の接頭辞は `S-K6-EXAM-`、公開コードは `structure.steel.exam-` に続けて下記キーを小文字にしたもの。正本は taxonomy.yaml と coverage-tiers.yaml であり、このメモは確認時点のスナップショットである。

| キー | 閲覧小項目 | 層 | 内容の型 |
| --- | --- | --- | --- |
| `SN-A-USE` | 鋼材の種別・材料規格 | 標準 | identification |
| `SN-C-THICKNESS` | 鋼材の種別・材料規格 | 骨格 | identification |
| `SN-YIELD-RANGE` | 鋼材の種別・材料規格 | 標準 | principle |
| `SN-CHARPY-GRADE` | 鋼材の種別・材料規格 | 標準 | rule |
| `SN490-SYMBOL` | 基準強度・材料強度・許容応力度 | 標準 | identification |
| `SN490-F40` | 基準強度・材料強度・許容応力度 | 標準 | rule |
| `SN-THICKNESS-F` | 基準強度・材料強度・許容応力度 | 標準 | rule |
| `SN-TOLERANCE` | 鋼材の種別・材料規格 | 発展 | rule |
| `STEEL-ANISOTROPY` | 鉄骨構造・鋼材特性 | 標準 | rule |
| `CHARPY-ENERGY` | 鉄骨構造・鋼材特性 | 標準 | identification |
| `CHARPY-TEMPERATURE` | 鉄骨構造・鋼材特性 | 標準 | rule |
| `CARBON-WELDABILITY` | 鉄骨構造・鋼材特性 | 標準 | rule |
| `SULFUR-TOUGHNESS` | 鉄骨構造・鋼材特性 | 標準 | rule |
| `PHOSPHORUS-TOUGHNESS` | 鉄骨構造・鋼材特性 | 発展 | rule |
| `COLD-FORMING` | 鋼材の種別・材料規格 | 標準 | principle |
| `BCR-BCP-PROCESS` | 鋼材の種別・材料規格 | 標準 | identification |
| `BCR295-SYMBOL` | 鋼材の種別・材料規格 | 標準 | identification |
| `BCR-YIELD-RATIO` | 鋼材の種別・材料規格 | 発展 | rule |
| `BCP325-STRENGTH` | 鋼材の種別・材料規格 | 発展 | rule |
| `TMCP-THICK-PLATE` | 鋼材の種別・材料規格 | 標準 | identification |
| `SUS-OFFSET` | 鋼材の種別・材料規格 | 発展 | rule |
| `SUS-F` | 基準強度・材料強度・許容応力度 | 発展 | rule |
| `STEEL-HEAT-YIELD` | 高温時挙動・火災荷重 | 標準 | rule |
| `ROUTE11-SCALE` | 構造計算ルート・耐震規定 | 標準 | rule |
| `ROUTE12-SCALE` | 構造計算ルート・耐震規定 | 標準 | rule |
| `ROUTE12-ONE-STORY` | 構造計算ルート・耐震規定 | 発展 | rule |
| `ROUTE13-HEIGHT` | 構造計算ルート・耐震規定 | 標準 | rule |
| `ROUTE1-CO` | 構造計算ルート・耐震規定 | 骨格 | rule |
| `ROUTE2-CO` | 構造計算ルート・耐震規定 | 標準 | rule |
| `ROUTE11-CHECKS` | 構造計算ルート・耐震規定 | 標準 | rule |
| `ROUTE12-ECCENTRICITY` | 構造計算ルート・耐震規定 | 標準 | rule |
| `ROUTE12-BRACING` | 構造計算ルート・耐震規定 | 標準 | rule |
| `ROUTE13-DRIFT` | 構造計算ルート・耐震規定 | 発展 | rule |
| `ROUTE2-ASPECT` | 構造計算ルート・耐震規定 | 標準 | rule |
| `ROUTE2-STIFFNESS` | 構造計算ルート・耐震規定 | 標準 | identification |
| `COLD-ROUTE1` | 冷間成形角形鋼管の設計 | 骨格 | rule |
| `COLD-ROUTE2-RATIO` | 冷間成形角形鋼管の設計 | 標準 | rule |
| `COLD-ROUTE3-LOCAL` | 冷間成形角形鋼管の設計 | 発展 | rule |
| `ROUTE-BRACE-END` | 構造計算ルート・耐震規定 | 標準 | rule |
| `ROUTE-CEILING` | 構造計算ルート・耐震規定 | 標準 | rule |
| `DS-MEMBER` | 構造計算ルート・耐震規定 | 標準 | rule |
| `PANEL-DS` | 柱梁仕口・梁端 | 発展 | rule |
| `COMPOSITE-STUD` | 合成梁・合成床 | 骨格 | principle |
| `COMPOSITE-FULL` | 合成梁・合成床 | 標準 | identification |
| `COMPOSITE-WIDTH` | 合成梁・合成床 | 標準 | rule |
| `COMPOSITE-TOP-FLANGE` | 合成梁・合成床 | 標準 | principle |
| `COMPOSITE-BOTTOM-FLANGE` | 合成梁・合成床 | 標準 | principle |
| `DECK-INPLANE` | 合成梁・合成床 | 標準 | principle |
| `CFT-BUCKLING` | CFT柱 | 骨格 | principle |
| `CFT-CONFINEMENT` | CFT柱 | 標準 | rule |
| `CFT-CIRCLE` | CFT柱 | 標準 | principle |
| `CFT-WIDTH-THICKNESS` | CFT柱 | 標準 | principle |
| `CFT-FIRE` | CFT柱 | 標準 | principle |
| `CFT-TRANSFER` | CFT柱 | 標準 | principle |
| `SRC-BENDING` | SRC部材・柱脚 | 骨格 | rule |
| `SRC-SHEAR` | SRC部材・柱脚 | 標準 | rule |
| `SRC-CRACK-STIFFNESS` | SRC部材・柱脚 | 標準 | principle |
| `SRC-WEB-TYPE` | SRC部材・柱脚 | 標準 | principle |
| `SRC-TENSION-BASE` | SRC部材・柱脚 | 標準 | principle |
| `SRC-NONEMBEDDED-DS` | SRC部材・柱脚 | 発展 | rule |
| `SRC-EMBEDDED-MIN` | SRC部材・柱脚 | 発展 | rule |
| `SRC-NONEMBEDDED-SUM` | SRC部材・柱脚 | 発展 | rule |
| `MIXED-RC-S-TRANSFER` | 混構造の力の伝達 | 骨格 | principle |
| `MIXED-CORE` | 混構造の力の伝達 | 標準 | rule |
| `DAMPER-PLASTICITY` | 鋼材ダンパー・制振 | 骨格 | identification |
| `DAMPER-YIELD-SEQUENCE` | 鋼材ダンパー・制振 | 標準 | principle |
| `DAMPER-LY225` | 鋼材ダンパー・制振 | 標準 | principle |
| `DAMPER-HIGH-STRENGTH-FRAME` | 鋼材ダンパー・制振 | 標準 | principle |
| `DAMPER-CONNECTION` | 鋼材ダンパー・制振 | 標準 | principle |
| `DAMPER-LAYOUT` | 鋼材ダンパー・制振 | 標準 | rule |
| `DAMPER-FATIGUE` | 鋼材ダンパー・制振 | 標準 | rule |
| `DAMPER-PANEL-ANGLE` | 鋼材ダンパー・制振 | 発展 | rule |
| `DAMPER-RESIDUAL` | 鋼材ダンパー・制振 | 発展 | rule |
| `FLOOR-FREQUENCY` | 高強度化・断面縮小・たわみ | 標準 | principle |
| `LIGHT-BUILDING-WIND` | 特殊荷重・付帯設備 | 標準 | principle |
| `STEEL-PERIOD` | 振動特性・耐震改修 | 骨格 | rule |
| `STEEL-DAMPING` | 振動特性・耐震改修 | 標準 | rule |
| `PILE-CORROSION` | 腐食・防錆 | 発展 | rule |
| `ROUTE-DIRECTION` | 構造計算ルート・耐震規定 | 標準 | rule |
| `ROUTE-UPPER-SELECTION` | 構造計算ルート・耐震規定 | 標準 | rule |
| `SRC-ALLOWABLE-SHEAR` | SRC部材・柱脚 | 標準 | rule |
| `SRC-WEB-HOLE` | SRC部材・柱脚 | 発展 | rule |
| `SRC-ELASTIC-STIFFNESS` | SRC部材・柱脚 | 発展 | principle |
| `MIXED-VERTICAL-DS` | 混構造の力の伝達 | 発展 | rule |
| `MIXED-DIRECTION-RULES` | 混構造の力の伝達 | 発展 | rule |
| `STEEL-RETROFIT` | 振動特性・耐震改修 | 標準 | identification |
| `COMPOSITE-STUD-FORCE` | 合成梁・合成床 | 発展 | rule |
| `DECK-DEFORMATION` | 合成梁・合成床 | 発展 | rule |
| `ALUMINUM-EXPANSION` | 鉄骨構造・鋼材特性 | 標準 | rule |
| `CONCRETE-EXPANSION` | 鉄骨構造・鋼材特性 | 発展 | rule |
| `DAMPER-BRACE-STUD` | 鋼材ダンパー・制振 | 標準 | principle |
| `FATIGUE-STEEL-GRADE` | 繰返し荷重・疲労 | 標準 | rule |
| `HEAT-TENSILE-F` | 高温時挙動・火災荷重 | 発展 | rule |
| `PANEL-EARLY-YIELD` | 柱梁仕口・梁端 | 発展 | rule |
| `EAF-CARBON` | 鋼材の環境負荷 | 骨格 | rule |

## 統合済みの重複

- `DAMPER-SUPPORT-MODEL` は `DAMPER-CONNECTION` に統合。取付剛性の意味を有効変形の数値例で問う。
- `COMPRESSION-BRACING-FORCE` は既存の `structure.steel.lateral-brace-strength-and-stiffness` に統合。強度だけでなく剛性も問う。

今後の追加は、別の条件判断や適用技能を新たに問える場合を優先する。文章を反対にするだけのカード増殖は避ける。
