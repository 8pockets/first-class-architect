# 一級建築士学習設計

2027年の一級建築士学科試験に向けて、本番で使える理解を作り、働きながら継続できる学習方法を設計するプロジェクトです。

現在は、鉄骨部材の座屈と塑性変形能力を題材にした構造パイロットを進めながら、PDF P158〜P215の鉄骨構造を知識単位で台帳化しています。GitHub Pagesでは、自作2択問題とA/Bを表示し、正解と内容別の三点（原理は結論・理由・条件、規定は規定・適用範囲・数値／例外、識別は定義・識別条件・混同注意）は初期状態が閉じた開示要素から必要なときに参照できます。

[鉄骨構造 原理台帳（GitHub Pages）](https://8pockets.github.io/first-class-architect/)

## 現在の方針

- 本質的な理解は、資料なしで理由を説明でき、条件変更後の結論を予測でき、数日後にも再現できる状態とする。
- 主教材は一つに絞り、過去問は得点練習ではなく理解不足を見つける診断問題として使う。
- ChatGPTは、自分の説明後に条件や矛盾を問う対話コーチとして使う。
- Codexは、ローカル教材から学習セットを作り、記録とGitHub上の計画を管理する教材担当として使う。
- NotebookLMは通常の学習ループに含めない。

## ドキュメント

- [用語集](./CONTEXT.md)
- [朝30分の基本学習ループ](./docs/morning-study-loop.md)
- [学習科学の調査レポート](./docs/research/learning-science-principles.md)
- [疲れた日でも翌日に戻れる学習運用](./docs/sustainable-study-operation.md)
- [誤答を次の学習へ変える最小記録](./docs/error-record.md)
- [2週間の構造パイロット検証基準](./docs/pilot-evaluation.md)
- [構造から他科目へ展開する条件](./docs/cross-subject-expansion.md)
- [毎朝の学習セット自動準備](./docs/morning-study-set-automation.md)
- [教材とパイロット範囲](./docs/materials.md)
- [鉄骨構造の原理台帳](./docs/principle-catalog.md)
- [鉄骨構造台帳の内容レビュー](./docs/steel-catalog-content-review.md)
- [鉄骨構造の導入層監査](./docs/steel-coverage-tier-audit.md)
- [旧Wayfinderからの移行記録](./docs/migration.md)

## 意思決定の進め方

計画の正本はGitHub IssuesのWayfinder地図です。

- [Wayfinder地図を表示する](https://github.com/8pockets/first-class-architect/issues?q=is%3Aissue+label%3Awayfinder%3Amap)
- 1回の対話では1つの意思決定チケットだけを解決する。
- 解決内容の詳細はチケットに置き、地図には要点とリンクだけを残す。
- 開いていて、依存先が解決済みで、担当者のいないチケットが次の候補となる。

## 教材について

試験教材のPDFやPowerPointは、容量と権利上の理由からリポジトリへ保存しません。ローカルの保存場所と対象範囲だけを[教材一覧](./docs/materials.md)で管理します。
