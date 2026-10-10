---
id: 0076
scope: project/dining-radar
status: 承認済み
date: 2026-10-10
approved_by: "人間裁定（KEN-48 監査 A-3 を KEN-50 として Todo へ移した操作＝板 party2/b2 Q5-a に戻す選択、2026-10-08〜10）"
supersedes: []
superseded_by: null
relates_to: [P-02, P-06, P-08, ADR-0066, ADR-0071, ADR-0072, ADR-0075]
---

# ADR-0076: 日程を聞いている幹事画面の残りの差（候補日の見出し帯・表の幅・回答リンクの行）を板 Q5-a に戻す

起草者: architect（KEN-50）。

> **承認者向けサマリ**: 2026-10-08 の再突き合わせ（`audit-board-vs-implementation-2026-10-08.md`）の A-3 を、
> 板 party2/b2 Q5-a に戻す。位置・並び・形だけを契約にし、色・寸法・文言は固定しない（ADR-0066 決定2）。
> **決定1**: 「候補日 N日」の節に見出し帯を置き、「＋候補日を足す」を帯の右の通常ボタンにする
> （いまは札の列の末尾の点線の札）。**決定2**: 人×日の表を白いカードの外に出して画面幅いっぱいにする。
> PC は日付列の見出しが読める間隔、スマホは右が切れず名前の列と日付の列が読める。
> **決定3**: 回答リンクの節に見出し帯（「回答リンク N本」＋右に「＋回答リンクを発行」）を置き、PC の行を
> 「名前｜答えた/まだ｜コピー｜取り消す」の1行にする。**決定4**: ADR-0072・0071・0075 との境界を表で明記。
> `.feature`・ARCHITECTURE.md は変更しない。契約は 0.31.0→0.32.0（追補31）。

## 文脈

### 0. 検証の申告（meta/adr/0039）

`Read` したもの: `.claude/agents/architect.md`、HANDOFF.md、監査 A-3 の節（`audit-board-vs-implementation-2026-10-08.md`）、
ADR-0072 全文・ADR-0075 全文、契約 0.31.0 の `schedulingLayout`・`candidateDateList`・`addCandidateDateOpen`・
`participantLinkCopy`・`participantLinkList`（`item`・`recopy`・`revoke`）・`responseTable.layout`、
板 Q5-a の描画画像（PC・SP。`board-q5a-pc.png`、`board-q5a-sp.png`）。
**確認していないもの**: 板の回答リンク行のスマホの描画（スマホ画像は表と「候補日」帯までで、回答リンクの節は
見えていない。LK-3 を最小にした理由）。実装のコード・既存テストは読んでいない（実装の影響は申し送りで推定）。
実行（テスト・撮影）はしていない。`.spec/conformance.spec` はこの worktree に無かったので、YAML の編集は
逐語の FIND/REPLACE を直接適用し、適用後に YAML として読めることだけを確かめた。

### 1. 板の形（Q5-a）

- **候補日の節**: 薄い緑の見出し帯。左に「候補日」と「20日」、右に枠つきの通常ボタン「＋候補日を足す」。
  その下の白い面に日の札（日付と×）が折り返して並ぶ。
- **表**: PC の描画では表は出ていない（下まで送った図）。スマホは画面の左右いっぱいで、「だれ」列＋日付列、
  右端は薄れて続く。白いカードの中ではない。
- **回答リンクの節**: 見出し帯「回答リンク 9本」、右に枠つきボタン「＋回答リンクを発行」。行は PC で
  名前｜答えた/まだ｜コピー（枠つき）｜取り消す（「まだ」の行だけ）の1行。

### 2. 実装の現状（監査 A-3）

「候補日を足す」は札の列の末尾の点線の札。表は白いカードの中にあり、PC では日付列の見出しが詰まって
隣の文字と接する。スマホは右が切れる。回答リンクは名前の下に「答えた」を積む形。

## 決定

### 決定1. 候補日の節に見出し帯を置き、「候補日を足す」を帯の右のボタンにする

契約 `schedulingLayout.candidateDateHeading`（新設の表示専用要素 `gathering-candidate-date-heading`）。
SCHEDULING のみ。幾何条件（H=帯、L=`candidateDateList`、A=`addCandidateDateOpen`、border box、許容 1px）:

| ID | 条件 |
|---|---|
| CH-1 | 帯が札の上: H.bottom ≤ L.top+1、H.top < L.top。H と L は入れ子にならない。 |
| CH-2 | A は H の中・右: A は H の子孫で矩形が H の中、A.right ≥ H.right−24、A の縦の中心が H の縦の範囲内。A は札の中でも L の中でもない。 |
| CH-3 | ラベルが左: H の中の A 以外の文字の塊はすべて A.left 以前で終わり、A と同じ行。 |
| CH-4 | 通常のボタン: A の border-style が dashed でも dotted でもなく、幅 1px 以上（色は固定しない）、高さ 44px 以上。 |
| CH-5 | 帯と面が別: H と L の background-color が異なる。 |

`addCandidateDateForm` の存在規則と「`candidateDateList` の中に開く」は無変更（動くのは開くボタンだけ）。

### 決定2. 人×日の表を白いカードの外に出し、画面幅いっぱいにする

契約 `schedulingLayout.responseTableWidth`。SCHEDULING のみ（FINALIZED のカードの中の表は無変更）。
T=表を横に滑らせる入れ物（無ければ表自身）、V=画面の幅（`document.documentElement.clientWidth`）。

| ID | 条件 |
|---|---|
| RT-1 | 全幅: T.left ≤ 1 かつ T.right ≥ V−1（1440px・390px とも）。 |
| RT-2 | カードの外: T の border-radius は 0、左右の枠なし。ダッシュボードの根までの祖先に枠・角丸・影が無い。 |
| RT-3 | PC: 日付列の見出しセルの幅 ≥ 44px（板の列の間隔）、文字が自分のセルの中に収まる。日が 20 あってもページ自体は横に滑らない。 |
| RT-4 | スマホ: T.right ≤ V、ページは横に滑らず、T は横に滑ってよい。scrollLeft 0 で名前の列が T の中に完全に入り、最初の日付の見出しセルも完全に入る。 |

名前の列を固定するか・右端を薄れさせるかは固定しない（ADR-0071 確認事項3 のまま、確認事項2）。

### 決定3. 回答リンクの節に見出し帯を置き、PC の行を1行にする

- **見出し帯** `schedulingLayout.participantLinkHeading`（新設の表示専用要素 `gathering-participant-link-heading`）。
  SCHEDULING のみ。H'=帯、PL=`participantLinkList`、P=`participantLinkCopy`。PH-1（帯が一覧の上）、
  PH-2（P は H' の中・右）、PH-3（ラベルが左）、PH-4（帯と一覧の背景が別、P は枠 1px 以上で点線でない）。
  CH-1〜CH-5 と同じ形（A→P）。
- **行** `schedulingLayout.participantLinkRow`。I=`gathering-participant-link-item`、R=`recopy`、V=`revoke`。
  testId は足さず、I の中の R・V 以外の見える文字（名前・答えた/まだ）を「文字の塊」と呼ぶ。

| ID | 条件 |
|---|---|
| LK-1 | PC（`twoColumnLayout`）で1行: I.height ≤ R.height+24、I の文字の塊・R・V の縦の中心がすべて R の縦の範囲内。 |
| LK-2 | PC で左から右: 文字の塊が DOM 順に左→右で重ならず、最後の塊は R.left 以前で終わり、V があれば V.left ≥ R.right−1。 |
| LK-3 | スマホ: 答えた/まだは名前の下に積んでよい。R・V は I の中、I の中身がページを横に溢れさせない。これだけを固定する。 |

V を出す行（まだで取り消し前の行）は無変更。

### 決定4. 既存 ADR との境界

慣行（ADR-0069 決定5、ADR-0075 決定3）に従い `supersedes: []` のまま、本文で覆す範囲を明記する。

| 既存ADR・契約 | 覆す範囲（本ADRが優先） | 覆さない範囲 |
|---|---|---|
| ADR-0072 決定1 `schedulingLayout.order` (6)(7) | (6)「`candidateDateList` の後に `addCandidateDateOpen`」→ 見出し帯（右に `addCandidateDateOpen`）の後に `candidateDateList`。(7)「`participantLinkList`」の前に見出し帯（右に `participantLinkCopy`）を置く。 | (1)〜(5) の並び、「日程」見出しの廃止、ADR-0075 が足した「バー行→戻り道→会の名前」。 |
| ADR-0072 決定2 `candidateDateAppearance` | 末尾に足す形だった追加の入口が「札の列の末尾の点線の札」であること。 | 札は日付と×だけ、44px、折り返し、ページを溢れさせない。 |
| ADR-0071 決定1 `responseTable.layout.overflow` | SCHEDULING で表が「白いカードの中に収まる幅」であること（全幅にする）。 | 行＝人・列＝日、セルの1文字、見出しセルの中身、塗る列、○の数、`gathering-response-table` 以下の testId・属性、FINALIZED の表。 |
| ADR-0075 決定2 | なし（矛盾しない。見出し帯は会の名前の h1 の下の本文側）。 | 全部。 |

## 検討した代替案

- **表だけ全幅にしてカードは残す（カードの中で左右の余白を負にする）**: 幾何条件は満たせるが、カードそのものが
  板に無いので、カードを外すほうが単純。不採用。
- **testId を足さずに帯を文字列で測る**: 「候補日」の文言は固定しないので、位置を機械が測れない。帯に表示専用の
  testId を足す（`allowedPurposes` に影響しない）。
- **行の名前・答えた/まだにも testId を足す**: 板に無い区別を増やさない。文字の塊で十分に左右の並びが測れる。
- **板に無い説明2行も今回消す**: 人間が選んだ範囲外。確認事項1。

## 帰結

- 契約: `gathering-scheduling-browser-interface.yaml` 0.31.0→0.32.0（追補31コメント、`schedulingLayout` に
  `candidateDateHeading`・`responseTableWidth`・`participantLinkHeading`・`participantLinkRow` と `order`・
  `candidateDateAppearance` の改め、`addCandidateDateOpen.position`・`participantLinkCopy.position`、`requiredTestIds`
  に2件）。candidate-search 側は触らない。
- **`.feature` は変更しない**: 位置・並び・形は UI の構造で、業務規則を足さない（ADR-0066 決定6、ADR-0072・0075 の先例）。
  `allowedPurposes`・`formControlExemptTestIds`・`verifiesScenarios` も無変更（新設の2要素は表示専用。押せる部品は
  増えない）。ARCHITECTURE.md・design.md も変更しない（モジュール境界・データフローは動かない）。
- 新規 testId: `gathering-candidate-date-heading`、`gathering-participant-link-heading`（いずれも表示専用）。

## 申し送り（次工程。実装コードはここでは書かない）

### 実装（developer）で気をつけること

1. `gathering.js` の SCHEDULING の描画（`schedulingLayout` の (6)(7)）と `organizer.css` が対象。`gathering-add-candidate-date-open`
   を札の列の末尾から出し、帯の中へ。帯は新 testId。ボタンは枠つき（点線にしない）、高さ 44px。
2. 表は白いカード（`.gth-card` 相当）の外へ。FINALIZED の床パネルの中の表は触らない。横の滑りは表の入れ物の中だけ
   で、`html` を滑らせない（ADR-0066 決定1）。PC は列幅の下限 44px（`min-width`）。
3. 回答リンクの行は PC で `display:flex`＋`align-items:center` の1行に、スマホは縦に積んでよい。取り消すの出現規則
   （まだの行だけ）に触らない。
4. キャッシュバスター（`?v=`）を上げる。撮影して板 Q5-a と並べる（ADR-0066 決定4）。PC・スマホ両方。

### 更新が要りそうなテスト（数えていない。洗い出しは developer/tester）

- `tests/ui_invariants/test_layout_sanity.py` に CH・PH・RT・LK の standalone を足す。
- 「候補日を足す」の位置を前提にした acceptance の DSL（札の列の末尾を探す箇所）。
- 表がカードの中にある前提の CSS 文字列検査（`tests/test_static_assets.py`）。

## 確認事項（人間に確認されたい）

1. **板に無い説明2行**（「1人が回答（うち…）」「有効なリンク 1本・まだ 0人」）は今回は変えない。残すなら板を直す（小事）。
2. **表の名前の列の固定・右端の薄れ**は契約で必須にも禁止にもしない（板のスマホは薄れて続くが、実装の自由度を残す）。
   必須にするなら別途。
3. **「画面幅いっぱい」を画面（viewport）の幅と読んだ**。PC の板は表が描かれていないので、PC でも画面の左右の端まで
   とした。PC で本文の幅に収めたい場合は RT-1 を改める。
4. **回答リンクの行のスマホ**は板の画像で確認できていない（LK-3 は「積んでよい」だけ）。板を見て詳しくするなら起票が要る。
