---
id: 0078
scope: project/dining-radar
status: 承認済み
date: 2026-10-11
approved_by: "人間裁定（KEN-58 の決定9点と、聞く点への回答。人間が調整役とのチャットで1点ずつ合意し、調整役 ken-18-03 が2026-10-11に伝達）。ADR の起草・承認済み化は担当に委任"
supersedes: []
superseded_by: null
relates_to: [ADR-0038, ADR-0042, ADR-0048, ADR-0059, ADR-0066, ADR-0075]
---

# ADR-0078: ランチ会の一覧を「ホーム」にし、動いている最新の会を大きい枠1枚、ほかを小さな行にする

> **承認者向けサマリ**: KEN-58 の人間の決定 1・2・9 を契約の言葉にする。いまの一覧は「会の行が新しい順に並ぶだけ」で、
> どの会から手を付けるかが読み取りにくい。**決定1**: 動いている会（日程を聞き中・店を選び中）のうち**いちばん新しい1件**を
> 大きい枠にし、日程→店→決まりの印・数・次にやることの主ボタンを出す。ほかの会は下の小さな行にする。
> **決定2**: 小さな行は「名前・札・数」と「開く」だけ（次にやることの文言は付けない）。行全体を押すとその会が開く。
> **決定3**: 一覧の見出しは「ランチ会」（契約は文言を固定しない。変更なし）。
> 大きい枠を先頭に出すと、契約の並びの不変条件（一覧の並び＝作った日の新しい順）と食い違うので、不変条件を
> 「大きい枠を先頭に出し、残りは新しい順のまま」と書き直す（決定1の帰結）。
> **確認事項（Q1〜Q5）は人間が決着させた。** 末尾の回答表と、追加の決定8（サインイン後の最初の画面をこのホームにする）を参照。

## 文脈

### 検証の申告

実際に `Read` したもの: `contracts/gathering-scheduling-browser-interface.yaml`（0.32.0）の `organizerGatheringList` 全体・
`crossFileSharedNavigation`、`contracts/gathering-scheduling-api.yaml`（0.18.0）の `Gathering`・`GatheringListResponse`、
`contracts/gathering-scheduling.feature` の TDR-GTH-21・22・25、`contracts/candidate-search-browser-interface.yaml` の
`browserEntry`・`gatheringEntry`、`contracts/authentication.feature`、キャンバス（KEN-58、Artifact Design 型、公開版
`1791707424-0a91`。依頼文の「版67」との対応は未確認）の付箋と HC・Dense・Empty の各ページの文字。確認していないもの: 実装コード（一覧のテンプレートは見出しが「会の一覧」であることだけ確認）。

### 経緯と現状

- いまの一覧は `gathering-list`（`gathering-list-item` が会の数だけ並ぶ）と `gathering-create-open`。行は名前・局面・数・「開く」。
  並びは `GatheringListResponse.gatherings` と同じ（作った日の新しい順、同時刻は id 昇順。ADR-0048）で、契約の
  `orderingInvariant` が「DOM の並び＝この並び」と固定している。
- 人間はキャンバス（決める点1・2・9）で次を選んだ: 案C（中身は案B）。動いている会のうち最新1件を大きい枠、ほかは小さな行。
  小さな行は名前・札・数と「開く」だけ。見出しは「ランチ会」。
- 契約は見出しの文言を固定していない。そのため実装は「会の一覧」のまま、ナビ・戻り道・上部バーは「ランチ会」という不一致が
  契約を通り抜けている（ADR-0066 が記録した「文言・位置を固定しないと板から外れても緑になる」と同じ型）。

## 決定

1. **一覧の構造**: `gathering-list-item` は引き続き会の数だけ（1会1要素）。各要素に `data-list-role`（`featured` か `row`）を足す。
   `featured` は高々1つで、**API の並びで最初に現れる、局面が SCHEDULING か SELECTING_SHOP の会**。そういう会が無ければ全部 `row`。
   - 退けた案: 大きい枠を別 testId（`gathering-list-item` ではない）にする。`gathering-list-item` の数が「会の数−1」になり、
     TDR-GTH-21・22 の step 定義が数え方を変える必要が出る。要素を共有するほうが変更が小さい。
2. **並びの不変条件を書き直す**: `gathering-list-item` の DOM 順は「`featured` があればそれを先頭に、残りは API の並びのまま」。
   つまり API の並びの**安定した先頭出し**。作った日が新しい決まった会が、動いている会より先に来ることはなくなる。
   手で並べ替える操作は引き続き禁止（`manual-ordering`）。
3. **大きい枠（`featured`）の中身**: (a) 会の名前と局面の札（既存属性）、(b) 日程→店→決まりの印 `gathering-list-steps`（表示専用、
   `data-current-step` は SCHEDULE／SHOP／FINAL）、(c) 数（候補日の数・回答人数・有力な日・店の数・票。属性は契約に書く）、
   (d) 次にやることの主ボタン `gathering-list-next-action`（新設、`data-next-action`。値の決め方は確認事項Q2）、
   (e) 既存の `gathering-list-item-open`（枠の見出し側を押すとその会が開く）。主ボタンも同じ会の画面へ行く。
4. **小さな行（`row`）の中身**: 名前・局面の札・数・「開く」だけ。`gathering-list-next-action` は**出現しない**（決定2の人間の決定）。
   `gathering-list-item-open` が**行全体**を押せるようにする。幾何条件 LR-1: 行の名前・札・数の文字の矩形がすべて open の矩形の中。
5. **数の属性**: 全 `gathering-list-item` に `data-candidate-date-count`・`data-shortlisted-shop-count` を足す。SCHEDULING で有力な日があるとき
   `data-leading-candidate-dates`（有力な候補日の `startAt` を空白で区切る）、FINALIZED のとき `data-finalized-shop-id`。いずれも
   `Gathering`（API）にある値の写しで、API は変えない。
6. **見出し「ランチ会」**: 契約は文言を固定しない（キャンバスの記載どおり変更なし）。実装を「会の一覧」から「ランチ会」へ直すのは
   実装の仕事。固定しないと再び食い違うため、回答Q4=Bで一覧の h1・上部バーの画面名・戻り道を「ランチ会」と固定した。
7. 空の状態（`gathering-list-empty`）・作成ボタン・シナリオ TDR-GTH-22 は変えない。

## 確認事項（起草時の選択肢。回答は末尾の表）

- **Q1 ログイン直後にホームを出すか**。いまのログイン直後は `/`（ランチ候補を探す画面）で、契約の `startPath`・
  `authenticatedInitialOutcome`・TDR-AUTH-02・TDR-CS-01 がそれを固定している。キャンバスの題は「ログイン後の最初の画面」なので、
  ホームにするなら契約が変わる。案: **(A)** `/` は探す画面のまま、ログイン成功の戻り先（次の行き先が無いとき）だけ `/gatherings/` に
  する（影響が小さい。推奨）。**(B)** `/` を一覧にして、探す画面を別のパスへ動かす（受け入れテストの入口が全部動く）。
  **(C)** 変えない（ホームはナビの「ランチ会」から行く画面のまま）。契約の差分案は `contracts/KEN-58-PROPOSAL.md` に置き、YAML には当てていない。
- **Q2 「次にやること」の決め方**。キャンバスの文言は「日を決める」「店を決める」「回答を待つ」。案: **(A)** 局面と数で決める
  （推奨）: SCHEDULING で回答0件→`WAIT_ANSWERS`、1件以上→`DECIDE_DATE`。SELECTING_SHOP で投票未開始→`PICK_SHOPS`、開始後→`DECIDE_SHOP`。
  **(B)** 局面だけ（`DECIDE_DATE`／`DECIDE_SHOP`）。**(C)** 回答の割合のしきい値で切る。`WAIT_ANSWERS` のときも主ボタンは出すか（開く先は同じ）も聞く。
- **Q3 「票 6/9人」の数**。API には店ごとの回答人数（`ShortlistedShop.respondedParticipantCount`）はあるが、会全体の「投票した人」の数は無い。
  案: **(A)** 店ごとの最大値を使う（API 変更なし、少なく見えることがある）。**(B)** `Gathering.votedParticipantCount` を足す
  （API 0.19.0、正確）。**(C)** 票の数を出さない。推奨は (A)、ただし契約には「店ごとの最大」と書く。
- **Q4 見出しの文言を契約の Must にするか**。案: **(A)** 固定しない（変更なし、キャンバスの記載どおり）。**(B)** 一覧の h1 と、上部バー・
  戻り道の画面名を「ランチ会」と固定する（再発防止。推奨）。
- **Q5 空の状態の「会をつくらずに、店だけ探す」** はキャンバス（Empty）にあるが testId が無く、決める点8の案Aのときだけ出る。
  契約の `gathering-list-empty` が許すのは2つ目の `gathering-create-open` だけなので、リンクを足すなら新要素。足すか。

## 帰結

- 契約（ドラフト）: `gathering-scheduling-browser-interface.yaml` 0.32.0→0.33.0 の追補32。`.feature` は TDR-GTH-21・22 を変えず、TDR-GTH-68・69・73 を
  下書きで新設。API は変えない。
- 実装（別チケット）: 一覧のテンプレート・JS・CSS。撮影ツールにホームの状態（複数・1件・空）を足す。
- 契約は確定した（会 0.34.0・候補画面 1.19.0・認証 0.5）。
