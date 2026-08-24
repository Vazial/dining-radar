---
id: 0028
scope: project/dining-radar
status: 承認済み
date: 2026-08-24
approved_by: "本PRのマージをもって承認（meta/adr/0035 方式(i)）。人間裁定 2026-08-24: `ADR-0003` の
  レビュー専用receiver `design-preview` を廃止する（提示した3択——(a) 廃止する／(b) 残して条文を直す／
  (c) いまは触らない——のうち (a) を選んだ）"
supersedes: [0003]
superseded_by: null
relates_to: [P-01, P-04, P-05, P-06, P-10, ADR-0003, ADR-0025, ADR-0027]
---

# ADR-0028: レビュー専用receiver `design-preview` を廃止する

> **承認者向けサマリ**: `ADR-0003` は候補提案画面を実装前にレビューするための隔離受け皿
> `projects/dining-radar/design-preview/`（React/TypeScriptで合成データだけを描く、Djangoにも
> providerにも繋がらないreceiver）を定めた。この受け皿は`meta/adr/0050`が外部AI（Gemini）依存の設計
> 経路を全廃してから使われておらず、CIも一度も動かしていない。人間は2026-08-24、この受け皿を廃止する
> ことを選んだ。決定は3点。
>
> 1. `design-preview`を廃止し、`ADR-0003`決定1・2を置き換える。決定3・4は中身がすでに全社共通の
>    designer役割契約（`meta/adr/0050`）へ移っており、プロジェクト固有に残すものが無いため引き継がない
> 2. 削除対象を列挙する（architect自身は削除できないため、人間が実施する）
> 3. 画面設計の成果物は今後`design/wireframes/`に置く。すでに`meta/adr/0050`の経路で1件の実例がある
>
> 払うもの: `design-preview`が残していた「合成データだけで動くreceiver」という検証環境は失われる。
> 画面のレビューは`/design`が発行するArtifactと`design/wireframes/`の静的ファイルに限られる。

## 文脈

### 1. `design-preview`はいま何をしているか

`ADR-0003`は2026-08-01、候補提案画面を実装前に人間がレビューできるよう、Django本体・外部通信・
非公開runtime dataから隔離したTSX受け皿`design-preview/`を定めた。当時のdesignerは自ら発案する道具を
持たず、Claudeは外部AI（Gemini）へブリーフを発注し、Codexは自分でTSXを書く、という runtime 別の経路
（`ADR-0003`決定4）で成果物をこの受け皿へ置いていた。

`meta/adr/0050`（2026-08-22）が designer を「`/design`スキル（Claude Designのキャンバス）の実行者」へ
再定義し、外部AI経路をすべて廃止した。designer は Claude・Codex 共通の同じ役割契約
（`meta/agent-runtime-mapping.md`）のもとで `/design` を使い、成果物をArtifactとして発行する。
`ADR-0003`決定4が想定していたruntime別の作成経路は、この時点で実体を失った。

`meta/adr/0050`決定8は「各プロジェクトの受け皿（`design-preview/`等）と成果物形式の扱いは、プロジェクト
のADRが定める」とこの判断をプロジェクト側へ送っている。本ADRがその受け皿である。

### 2. 使われていない事実

`design-preview/`は12ファイル・約77KBで、`.github/workflows/ci-dining-radar.yml`を実測すると
`design-preview`という文字列は一度も現れない——このプロジェクトのCIはL1〜L5のどの段でもこの受け皿を
検査していない。似た名前の受け皿が`ci-reservation-frontend.yml`に出るが、これは別プロジェクト
（`reservation-frontend`）自身の`src/design-preview/`を指しており、無関係である。

2026-08-23に designer が `/design` で作成した`design/wireframes/`（`meta/adr/0050`の経路を通った
最初の成果物）が、`design-preview`を経由せず既に人間のレビューを受けている。受け皿としての役割はここで
実質的に移っていた。

### 3. `ADR-0003`決定2の条文が対象を失っていた

`activeContext.md`はこの矛盾を「未決」として記録していた。`ADR-0003`決定2は`design-preview`に
「検索基点」「数値距離」を置くことを禁じるが、`ADR-0025`（2026-08-24マージ）で検索基点マーカーと
徒歩時間（`walkingTimeMinutes`）が製品の承認済み表示物になった。禁止条文は元々「実座標・実測距離」を
指すものだったが、`ADR-0025`後は「合成値としての基点・徒歩時間」まで無修飾に禁じているように読める
状態になっていた。本ADRで受け皿自体を廃止すれば、この条文は適用対象を失い、矛盾は解消する。

## 決定

### 決定1. `design-preview`を廃止し、`ADR-0003`を置き換える

`projects/dining-radar/design-preview/`とその起動経路を廃止する。`ADR-0003`の4つの決定を次のとおり
切り分ける。

- **決定1（レビュー専用receiver）・決定2（合成表示と通信禁止）**: 本ADRが置き換える（superseded）。
  受け皿そのものが無くなるため、その存在を前提にした規則は成立しない。
- **決定3（契約との照合境界）**: 引き継がない。この決定が求めていた「設計成果物は契約と突き合わせる」
  という原則は、いまは受け皿に限らず全プロジェクト共通で designer の役割契約が持つ
  （`.claude/agents/designer.md`責務(b)「契約との突き合わせ」、`meta/adr/0050`）。プロジェクト固有に
  残すべき中身は無い。
- **決定4（runtime別のデザイン作成経路）**: 引き継がない。外部AI経路の廃止（`meta/adr/0050`決定3）で
  Gemini発注・Codexの自作という区別自体が消えており、Claude・Codexは同じ designer 役割契約の下で
  `/design`（またはCodex側の対応する実行手段）を使う。プロジェクト固有の残余は無い。

`ADR-0003`のfrontmatterは`status: superseded`・`superseded_by: 0028`へ更新する。本文は編集しない
（P-06、承認後のADR本文編集禁止）。

### 決定2. 削除対象

architectはgit操作を持たないため、次を人間が削除する。

1. `projects/dining-radar/design-preview/`一式（12ファイル）: `.gitignore`、`index.html`、
   `package-lock.json`、`package.json`、`src/main.tsx`、`src/screens/CandidateSearchPreview.tsx`、
   `src/styles.css`、`src/vite-env.d.ts`、`tsconfig.app.json`、`tsconfig.json`、`tsconfig.node.json`、
   `vite.config.ts`
2. `.claude/launch.json`の`dining-radar-design-preview`エントリ（`runtimeExecutable: npm`、
   `projects/dining-radar/design-preview`をprefixに`run dev -- --port 5174`を起動する設定）

以下は**削除しない**（決定3参照）。

### 決定3. 残すもの

- `projects/dining-radar/design/reconciliation/**`（`candidate-search.md`・
  `candidate-card-refinement.md`）: 過去の契約突き合わせ記録であり、歴史として残す。`meta/adr/0050`
  帰結が同種の記録（`design-briefs/`）を「履歴として残す。削除しない」と明記した判断と同じ扱いにする
- `projects/dining-radar/design-briefs/**`（3本）: `meta/adr/0050`帰結が名指しで履歴として残すと
  既に決めている。本ADRは重ねて確認するだけで、新たな判断は加えない
- `projects/dining-radar/design/explorations/**`: `activeContext.md`の別の未決（ラフの由来問題）で
  人間が既に「探索資料のまま置く」と決めており、本ADRのスコープ外
- `projects/dining-radar/reviews/audit-pre-live-data.md`ほか、`design-preview`に言及する既存のレビュー・
  friction-logの記述: 過去の観測の記録であり、書き換えない

### 決定4. 画面設計の成果物の今後の置き場所

画面設計の成果物は今後`projects/dining-radar/design/wireframes/`に置く。designerが`/design`で発行した
Artifactの元データ（`.dc.html`・`canvas.json`）をここへコミットし、`README.md`に由来・承認状態・
未決を記録する型は`design/wireframes/README.md`に既に実例がある（2026-08-23作成、`meta/templates/
wireframe.md`の雛形の元になった）。`design-preview`のような合成データ駆動の対話的receiverは持たない
——`/design`のArtifact自体が人間のブラウザ上でレビュー可能な成果物であり、別受け皿での再現を必要と
しない。

## 検討した代替案

- **(b) 残して条文を直す**: `ADR-0003`決定2の禁止を「実座標・実測距離」に限定する修飾を加える案。
  不採用——受け皿自体が2026-08-22以降使われておらず、CIも検査していない死んだコードを、条文だけ
  生かして保守し続ける理由が無い。修飾を加えても、`design-preview`が実際に更新される見込みが無い
  以上、次に矛盾が起きたときも同じ読み直しが要る
- **(c) いまは触らない**: 未決のまま先送りする案。不採用——`activeContext.md`の未決(2)として既に
  1回、`design/wireframes/README.md`にも同じ矛盾の指摘が残っており、次に画面へ手を入れるたびに
  同じ確認が繰り返される。使われていない受け皿を残す費用（`activeContext.md` Next work 4の
  依存パッケージ不一致の宿題を含む）に対して、廃止の費用（ファイル削除とlaunch.json 1行）が
  明らかに小さい

## 帰結

- `ADR-0003`は`status: superseded`・`superseded_by: 0028`になる
- `activeContext.md`の未決(2)（`ADR-0003`決定2と`ADR-0025`の条文衝突）と、未決(1)の残り
  （画面作業をdesigner経由でやり直す件、2026-08-23に完了済み）の両方をこのADRで済みとして閉じる
- `activeContext.md` Next work 4（`design-preview`の依存パッケージ不一致の宿題）は受け皿ごと消えるため
  moot になる
- `design/wireframes/README.md`が持つ「`ADR-0003`決定2との関係（未決）」節は、本ADRにより解決済みの
  記述へ書き換えが要る。design配下のREADMEは designer が起動時に読み書きする文書であり、本ADRは
  内容だけを解決として記録し、ファイルの書き換えは次にその領域へ手を入れる役へ委ねる
- 実装コード・契約・テストへの影響は無い。`design-preview`は本番配信ルート・ビルド・受け入れ契約の
  いずれにも接続していなかった（`ADR-0003`決定1）
