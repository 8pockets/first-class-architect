# 一級建築士学習設計

2027年の一級建築士学科試験に向けて、本番で使える理解を作り、働きながら継続できる学習方法を設計するプロジェクトです。

教材の鉄骨章と、本試験の鋼材・合成構造・耐震設計などの関連論点を、311件の自作2択カードへ整理しています。骨格47・標準149・発展115件を組み合わせ、分野を繰り返し見渡せます。答えと、内容別の三点（原理／規定／識別）は個別又は表示中の全件で開閉できます。

[鉄骨構造 原理台帳（GitHub Pages）](https://8pockets.github.io/first-class-architect/)

旧来の根拠確認中100件は、出典・条件の確認と必要な訂正を経て学習カードへ移行しました。旧調査ページの固定リンクは移行案内として残します。Google検索は補助的な資料探しであり、公開根拠の代わりにはしません。

A/Bの初回回答をブラウザ内に保存し、要復習・重点復習・未回答で抽出できます。答えを見た日の練習は独力の成績と区別し、問題改訂前の履歴も保存します。JSONバックアップ・復元統合に対応し、ログインや履歴のサーバ送信、端末間自動同期はありません。

2026-10改訂の詳細と確認範囲は[改訂記録](./docs/steel-catalog-release-2026-10.md)を参照してください。GitHub Pagesへの反映はデプロイ後です。

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
- [耐火・特殊荷重8項目の根拠監査](./docs/research/steel-fire-special-source-review.md)
- [旧Wayfinderからの移行記録](./docs/migration.md)

## 意思決定の進め方

計画の正本はGitHub IssuesのWayfinder地図です。

- [Wayfinder地図を表示する](https://github.com/8pockets/first-class-architect/issues?q=is%3Aissue+label%3Awayfinder%3Amap)
- 1回の対話では1つの意思決定チケットだけを解決する。
- 解決内容の詳細はチケットに置き、地図には要点とリンクだけを残す。
- 開いていて、依存先が解決済みで、担当者のいないチケットが次の候補となる。

## 教材について

試験教材のPDFやPowerPointは、容量と権利上の理由からリポジトリへ保存しません。ローカルの保存場所と対象範囲だけを[教材一覧](./docs/materials.md)で管理します。
