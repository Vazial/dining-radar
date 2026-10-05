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

1. ~~Render のサービスをこのリポジトリへつなぎ替える~~ 済み（2026-09-26、人間）。本番の `/healthz` の確認と、
   このリポジトリの main へのマージで自動デプロイが走ることの確認がまだ
2. テンプレ側から dining-radar を消し、ここへのポインタを残す（テンプレのルート `activeContext.md` が持つ）
3. テンプレの govlint に `TEMPLATE_SYNC` のハッシュ検査を足し、`scripts/template-pull.sh` で取り込む
4. ~~テンプレに出ていた dining-radar の ADR 7本の承認記録（テンプレ PR #208）を、こちらへ出し直す~~ 済み（KEN-23。adr/0037・0039・0043・0046・0048・0065・0066）
