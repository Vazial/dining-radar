---
id: 0071
scope: project/dining-radar
status: 承認済み
date: 2026-10-05
approved_by: "人間裁定（2026-10-05 PR #22 のマージを承認とする旨を、人間が調整役とのチャットで選択したと調整役 ken-18-d8 が伝達。マージ者は GitHub アカウント Vazial）"
supersedes: []
superseded_by: null
relates_to:
  [P-02, P-06, P-08, ADR-0056, ADR-0060, ADR-0062, ADR-0063, ADR-0066, ADR-0069]
---

# ADR-0071: 確定後の幹事画面の回答タブを板 Q5-a と同形の人×日の表に戻し、その表を確定前の日程画面と同じ部品にする

> **承認者向けサマリ**: `adr/0066`が記録した板と実装の突き合わせ
> （`audit-board-vs-implementation-2026-09-22.md`）の **D5**（確定後の幹事画面の回答タブの中身が、
> 板 `party2/d4r` G1 の「人×日の表」ではなく、集計の行・「日程」のカード・「誰が・どの日に答えたか」の
> 一覧になっている）を、契約に書く。KEN-42。決定は5点。
> **決定1**: 表の形を契約のMustにする（行=人・列=候補日の格子、1マス=○△×の1字、「○の数」の最下行、
> 表自身の見出し行なし）。**決定2**: 塗る列を1つ持つ（確定前は有力な日、確定後は確定済みの日）。
> **決定3**: 最下行「○の数」を新設する。**決定4**: 確定後の「回答」タブの中身を表だけにする
> （集計の行・日程のカードはDOMに残し、画面では見せない。「決める」ボタンは出さない。
> 「回答リンク N本」は触らない）。**決定5**: この表は確定前の日程画面（監査B3）と**もう同じ部品**
> である（コードで確認済み）ので、決定1〜3はB3の表にも及ぶ。B3の残り（候補日の札・「決める」
> ボタン・見出し）は本ADRの範囲外。
> 契約の差分は `gathering-scheduling-browser-interface.yaml` 0.27.0→0.28.0（追補27）。`.feature`は
> 変更しない。**人間が承認する点**は末尾の「確認事項」に5つ挙げた。契約はドラフトで、確定していない。

## 文脈

### 0. 検証の申告（meta/adr/0039）

実際に`Read`したもの: `HANDOFF.md`、`.claude/agents/architect.md`、`projects/dining-radar/activeContext.md`、
`audit-board-vs-implementation-2026-09-22.md`、`adr/0066`（見出し・サマリ・決定2・決定4）、
`adr/0069`（全文。書き方の先例）、`contracts/gathering-scheduling-browser-interface.yaml`（0.27.0）の
`responseTable`・`shopSelectionPanel`・`confirmDate`・`finalizedSummary`全体、
`src/dining_radar/gathering/static/dining_radar/gathering/gathering.js`の`renderResponseTable`・
`renderDecisionAnswersLinksGroups`・`render`・`renderShopSelectTabContent`の呼び出し箇所・
`renderResponseSummary`・`renderUnansweredSummary`、板 `.orca/drops/dsg-out/party2/b2/Q5-a-PcDetail.dc.html`・
`Q5-a-SpDetail.dc.html`、`party2/d4r/G1-PcFinal.dc.html`・`G1-SpFinalMore.dc.html`・`G2-SpFinal.dc.html`・
`G2-PcFinal.dc.html`（HTMLのCSSと文字列を読んだ。板は画像として開いてはいない）。
確認していないもの: コードのCSS（`.gth-response-*`の寸法）、テスト・L4のDSLの中身（`RESPONSE_TABLE_*`の
定数が`tests/acceptance/dsl/gathering_scheduling_browser.py`に、セルの形を見る検査が
`tests/ui_invariants/test_render_invariants.py`にあることまでしか見ていない）。実行は一切していない。
ADR番号は、全ローカル・リモートのブランチの`projects/dining-radar/adr/`を見て最大が0069であることを確かめたが、同時に出たKEN-36のPR #21が0070を先に取っていたため
、0071を取った。

### 1. 板と実装の差（監査D5）

- **板**（`d4r` G1・Q5-a）: 見出しの「だれ」の列と日付の列（月・日・曜日）、行は人、マスは○△×の1字、
  最下行に「○ の数」。決まった日（G1は10/8）の見出しのセルが塗られる。Q5-aではさらに有力な列の
  本文のマスにも薄い色（`#EAF4EE`）が付く。表の上に表自身の見出しは無い。確定後のタブの中は
  この表だけ。
- **実装**: タブの中に、集計の行（「N人が回答」「有効なリンク N本」）、「日程」のカード（候補日1件ずつ）、
  「誰が・どの日に答えたか」の見出し、その下に表が並ぶ。表の中も、人ごとの行に「9/17(木) 行ける」という
  文字入りのセルが並ぶだけで、日の列にそろった格子ではない。
- **契約側**: `responseTable`は行・セル・見出しのセルの存在と属性は決めていたが、「この表の見た目の配置は
  決めない」と明記していた（セルの`requirement`）。`adr/0066`決定2が一般方針とした「板が裁定した形は契約の
  Must」に従えば、これも書かれているべきだった。

### 2. 先にコードで確かめたこと: 確定後の表と確定前の表は、同じ部品か（指示）

**同じ部品である。** `gathering.js`の`renderResponseTable(leaders)`は1つの関数で、呼び出し箇所は
次の4つ（局面と置き場所だけが違う）:

| 局面 | 呼び出し | 置き場所 |
|---|---|---|
| SCHEDULING | `render()`の`sections.push(renderResponseTable(...))` | 日程のカードの下に常設（監査B3の画面） |
| SELECTING_SHOP | `renderShopSelectTabContent` | 「回答」タブの中 |
| FINALIZED（PC） | `renderDecisionAnswersLinksGroups`の`activePane` | 「回答」タブの中（集計の行・日程のカードと並ぶ） |
| FINALIZED（スマホ） | 同関数の`disclosure-panel` | 「回答を見る」の行の中 |

契約側も、`responseTable`の存在規則は3局面で無条件、testIdも局面ごとに分かれていない
（`gathering-response-table`・`-header`・`-header-cell`・`-row`・`-cell`が1組）。
局面で変わるのは、(a)`leaderSummary`が`phase === "SCHEDULING"`のときだけ出る、(b)ヘッダのセルの塗りが
`leaders`（有力な日）で決まる、の2点だけである。

**含意**: 表の形を直すと確定前の日程画面（B3）の表も同時に変わる。これは避けるべき副作用ではなく、
B3の板（Q5-a）が確定後と**同じ表**を描いている（監査D5の文言が「Q5-a と同じ表」）ことと一致する。
B3は他で進行していない（指示）ので、表の部分だけが先に揃う。B3のうち**表以外**（日の見出し「日を決める 候補日N日・
回答N人」・「有力」の札・「N/N に決める」ボタン・候補日の小さな札と「候補日を足す」）は、別の部品
（`schedulePane`・`renderCandidateDate`・`renderConfirmDate`）で、本ADRは触らない。

ただし1点だけ、表を共有するために部品側へ要る変更がある: **塗る列の決め方が局面で違う**
（SCHEDULING=有力、確定後=確定済みの日）。現行の`renderResponseTable`は`leaders`だけで塗っており、
確定後は有力な日（確定済みの日と一致するとは限らない）が塗られてしまう。決定2がこれを契約に書く。

## 決定

### 決定1. 表の形を板 Q5-a / G1 に揃え、契約のMustにする

`responseTable.layout`を新設する（`adr/0066`決定2に従い、板が裁定した構造は契約に書く）。

1. **格子**: 行=人（`gathering-response-table-row`）、列=候補日（`-header-cell`のDOM順＝日付の昇順、無変更）、
   先頭に名前の列（板「だれ」）。各セルは自分の`data-candidate-date-id`の列に置かれ、同じ日のセルは
   行をまたいで縦にそろう。回答が無い日は`gathering-response-table-cell`を置かない（存在規則は無変更）が、
   格子の位置は空白で残す。
2. **セルの中身**: 見える文字は1字だけ。GOING=○、MAYBE=△、NOT_GOING=×。日付も「行ける」などの語も
   セルの中に置かない。
3. **見出しのセル**: 日・曜日（月は最初の列と月が変わる最初の列だけ）。文言と12:00は固定しない。
4. **表自身の見出し行を置かない**（現行の「誰が・どの日に答えたか」を外す）。
5. **はみ出し**: 列が多くて幅を超えるときは、表の入れ物の中で横にスクロールする。ページ全体は
   横にあふれない（`adr/0066`決定1のはみ出しの検査がそのまま効く）。名前の列を固定するかは板に無いので
   固定しない（確認事項3）。

行の単位（1リンク=1行、取り消した人も行として残る、未回答の人も行がある）は**変えない**。板は回答済みの
7人だけを描いており（リンクは9本）、契約の「1行=1リンク」とずれるが、これは確認事項5で聞く。

### 決定2. 塗る列を1つ持つ。確定前は有力な日、確定後は確定済みの日

`responseTable.paintedColumn`を新設する。SCHEDULINGでは`data-current-leader="true"`の日（`adr/0060`決定7、
無変更。同点なら複数）、SELECTING_SHOPとFINALIZEDでは`data-confirmed="true"`の日の列を塗る。
塗られた列は、見出しのセル・本文のセル・空白の格子位置・「○の数」のマスのすべてで、背景色（computed）が
同じ行の他の列と違う。どの列かは、同じ`data-candidate-date-id`の`gathering-candidate-date`の属性から読み、
表の側に属性を足さない（`adr/0060`決定7の「真実の置き場を2つにしない」判断のまま）。`adr/0066`の
文字と背景の見分けやすさ（4.5／3.0）が塗られたセルにも掛かる。

板との差が2点ある（どちらも確認事項）: (a) G1（確定後）は見出しのセルだけが塗られ本文は塗られないが、
Q5-aは本文も塗る。本ADRはQ5-aに揃えて列全体を塗る（確認事項1）。(b) SELECTING_SHOPの回答タブに板は無い。
決まった日が1つあるのでFINALIZEDと同じにした（確認事項2）。

### 決定3. 最下行「○の数」を新設する

`responseTable.goingCountRow.cell`（testId `gathering-response-table-going-count-cell`、表示専用、purpose宣言なし、
日ごとに1つ）。見える文字は、同じ日の`gathering-candidate-date`の`data-going-count`と等しい10進整数だけ
（その列のGOINGのセルの数にも等しい）。属性は増やさない（`candidateDateList`が持つ値を複製しない）。
行の見出し（板「○ の数」）の文言は固定しない。

### 決定4. 確定後の「回答」タブの中身を表だけにする

`finalizedSummary.answersContent`を新設する。`answersOpen`が見せるのは`responseTable`だけ。集計の行
（`gathering-responded-summary`・`-unanswered-summary`）、「日程」のカード（`gathering-candidate-date-list`と
各`gathering-candidate-date`）、旧見出し「日程」「誰が・どの日に答えたか」は、DOMに残したまま画面では見せない
（`adr/0063`が店を選び中の集計の行を`visually-hidden`で残した先例。これらの`data-confirmed`・
`data-going-count`などを契約の他の箇所が読んでいるため、存在規則は変えない）。「決める」操作は確定後に元から
無い（`confirmDate`は`SCHEDULING`だけ）ので足さない。**「回答リンク N本」（`linksOpen`・`participantLinkList`）
には触らない。**

### 決定5. 表は確定前の日程画面（B3）と同じ部品であると契約に書き、B3の範囲を切る

上の「先にコードで確かめたこと」のとおり、`responseTable`は3局面の1部品である。契約には、決定1〜3が
局面を問わず表に及ぶこと、B3の残りは本追補の外であることを追補27のコメントに書いた。B3の起草は別の
スライスで、そのときは本ADRの`layout`・`paintedColumn`・`goingCountRow`を前提にしてよい。

なお、B3で人間が指摘した「縦に伸びて見にくい」の原因は表ではなく候補日のカードの縦並びなので、
本ADRが表をそろえても、B3のその症状は直らない。

### 決定6. 既存ADRとの関係

本リポジトリの慣行（`adr/0059`・`0062`・`0066`・`0069`）に従い、`supersedes: []`のまま、覆す範囲を次の表で定める。

| 既存ADR | 覆す範囲（本ADRが優先） | 覆さない範囲 |
|---|---|---|
| `adr/0056`決定1 | 表の見た目を契約が固定しないという扱い（セルの`requirement`の最後の文）。 | 行=人・列=候補日、行・セルの存在規則、`data-response-status`の語彙、未回答のセルを置かない規則。 |
| `adr/0062`決定4 | 確定後の「回答」タブに集計の行・日程のカードが同居する現行の構成。 | 確定後を「決まった店だけ」にする決定、パネル、タブ/開閉行、`answersOpen`/`linksOpen`の存在とaria状態。 |
| `adr/0063`決定3 | 回答タブの中身を`responseTable`の可視化とだけ書いていた部分に、形の規則を足す（覆すものはなく補う）。 | 4つのタブ、店タブが既定、`visually-hidden`で集計の行を残すこと。 |
| `adr/0060`決定7 | 塗る列の決め方を確定後は確定済みの日にする点（確定前は無変更）。 | 有力な日の定義、`leaderSummary`、`data-current-leader`。 |

## 検討した代替案

- **確定後の表だけを新設し、確定前のB3の表は旧形のまま残す**: 不採用。部品が1つで、板もB3と確定後を
  同じ表として描いている。2種類を持つと同じ`testId`が局面で違う形になる。
- **行ける・たぶん・むりの語をセルに残し、○△×は補助にする**: 不採用。板は1字だけで、1字にしないと
  44px幅の列に20日が収まらない。ただし1字のみだと読み上げに情報が無くなるので確認事項4。
- **塗る列を属性（`data-painted`など）で表に持たせる**: 不採用。`adr/0060`決定7が真実の置き場を増やさない判断を
  している。computedの背景色の差で機械的に確かめられる。
- **集計の行・日程のカードを確定後のDOMから外す**: 不採用。`data-confirmed`・`data-going-count`を
  契約の他の箇所が読む。見せないだけにする。
- **B3の残りも本ADRで描き直す**: 不採用。指示の範囲外で、候補日の札・「決める」ボタンは別の部品と
  別の板（Q5-a の上半分）の話。

## 帰結

- `contracts/gathering-scheduling-browser-interface.yaml`（0.27.0→0.28.0）: 追補27コメント、
  `responseTable.layout`・`paintedColumn`・`goingCountRow`の新設、`finalizedSummary.answersContent`の新設。
- `.feature`・`allowedPurposes`・`formControlExemptTestIds`・`verifiesScenarios`・`design.md`・
  `ARCHITECTURE.md`・API契約: 変更しない。押せる部品も業務規則も増えない構造と配置の決定。
- **次の実装スライス（developer。承認後）**: (1)`renderResponseTable`を格子・1字・塗り・最下行に。局面別の
  塗る列。(2)`renderDecisionAnswersLinksGroups`の回答側から`statsRow`・`schedulePane`を外して不可視で残す。
  (3)`test_render_invariants.py`・L4のDSLのうち、セル文言「行ける」や表の見出しを見ている箇所の更新
  （本ADRは数えていない）。(4)撮影して板 Q5-a・G1と並べて見る（`adr/0066`決定4）。
- **testerに申し送り**: 新しい業務シナリオは無い。セルの1字・塗りの差・「○の数」は
  `verifiesScenarios`の既存シナリオ（TDR-GTH-49の表）の観測の変更として扱うか、L5で見るかは
  testerの判断（本ADRはシナリオを足さない）。
- ルート／プロジェクトの`activeContext.md`の「KEN-42」の記述は、承認後の更新が要る。所有範囲外なので
  orchestratorへの申し送り。

## 確認事項（人間に確認されたい）

1. **塗る範囲**: 確定後はG1どおり見出しのセルだけか、Q5-aどおり列全体か。本ADRは列全体にした。
2. **店を選び中の回答タブ**で塗るのは確定済みの日でよいか（板が無いので本ADRの読み）。
3. **名前の列を横スクロール中も固定する**か。板には描かれていない（固定しない形で書いた）。
4. **○△×の1字だけのセルに、読み上げ用の名前（行ける／たぶん／むり）を持たせる**か。契約は見える文字だけをMustにした。
5. **未回答のリンクの行**: 板は回答済みの7人だけを行にしている（リンクは9本）。契約は「1リンク=1行」
   （未回答・取り消し済みも行）のまま。板に合わせて回答済みだけにするなら、`row`の`requirement`の変更が要る。
