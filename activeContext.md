# activeContext.md（ルート） — dining-radar リポジトリ

> P-11: このファイルは常に「現在」だけを映す。更新は上書き。歴史はgitとADRが持つ。
> このリポジトリはプロジェクトが1つだけなので、ここはリポジトリ全体の状態とテンプレとの同期だけを持つ。
> プロジェクト内部の状態は `projects/dining-radar/activeContext.md` が持つ。

## このリポジトリ

- 2026-09-26、テンプレ（`Vazial/ai-driven-dev-template`）から履歴ごと切り出した（テンプレ側 `meta/adr/0067`）。
  **切り出し前のコミット SHA は変わっている。**記録の中の SHA（例: `094f323`）はテンプレのリポジトリの
  SHA として読む。
- 共有ファイル（`meta/` ほか）はテンプレの写し。写した元は `TEMPLATE_SYNC` の `commit`。
  取り込みは `scripts/template-pull.sh`、規程を直すならテンプレ側へ PR。
- `meta/` の中のテンプレ全体の記述（他プロジェクト・ルートの activeContext を指すもの）は、
  テンプレのものとして読む。このリポジトリには dining-radar しか無い。

## プロジェクト

| プロジェクト | 担当 | 詳細 |
|---|---|---|
| dining-radar | Claude | `projects/dining-radar/activeContext.md` |

## 切り出しの残作業

1. Render のサービスをこのリポジトリへつなぎ替える（人間。ダッシュボード）。本番の `/healthz` を確かめる
2. テンプレ側から dining-radar を消し、ここへのポインタを残す
3. テンプレの govlint に `TEMPLATE_SYNC` のハッシュ検査を足し、ここへ取り込む
