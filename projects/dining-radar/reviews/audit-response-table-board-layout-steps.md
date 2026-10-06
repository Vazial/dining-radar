# 独立監査: 回答表の板レイアウト検査（KEN-42、契約0.28.0 追補27 / ADR-0071）

- **監査対象**: `git diff origin/main -- projects/dining-radar/tests/acceptance`（Draft PR #26、worktree HEAD `3475eb0` の
  tests/acceptance 部分）。3ファイル・+183行: `dsl/gathering_scheduling_browser.py`（+177）、
  `steps/gathering_scheduling_steps.py`（+3）、`test_gathering_scheduling_acceptance.py`（+3）。
- **依拠した基準**: `contracts/gathering-scheduling-browser-interface.yaml` 0.28.0（追補27、`responseTable.layout`・
  `paintedColumn`・`goingCountRow`、`finalizedSummary.answersContent`）、`adr/0071`（決定1〜4）、
  `contracts/gathering-scheduling.feature` TDR-GTH-49。
- **独立性**: 先にコード（DSL・step・テスト）を読み、docstring・コメントは「コードが何をしているか」の記述としてのみ参照した。
  コミットメッセージ・tester の意図説明は判断材料にしていない。`src/**` はヘッダ文言の所在確認で1回 grep しただけで、
  実装の読解はしていない。テストは**実行していない**（静的監査）。
- **役割確認**: `reviewer.md` の `tools:`（Read, Grep, Glob, Write, Bash）は実際に渡されている。

## 結論（先頭サマリ）

**Critical: 0件。Major: 2件。Minor: 5件。** 契約と矛盾する・誤って緑になる検査は見つからないが、
追補27が Must とした項目のうち、確定後の塗り列と「列が決まらない」場合の2分岐が**どのテストからも実行されない**（Major 1）。
また契約が書いた形の規則の一部が見出し行の文言までしか見ていない（Major 2）。承認判断は人間。

## 1. 対訳表（コードが実際にやること → シナリオ/契約）

| # | 新規・変更されたもの | コードが実際に行うこと（コードから書き起こし） | 契約・シナリオ上の根拠 | 突き合わせ |
|---|---|---|---|---|
| 1 | step `response_table_has_board_layout` / TDR-GTH-49 に1行追加 | 既存の `response_table_matches` の直後に、DSL の `assert_response_table_has_board_layout` を呼ぶ。引数なし | TDR-GTH-49「参加者ごとに、どの候補日へ何と答えたかが一覧で示される」。シナリオ文は「一覧で示される」のみで、格子・○△×・塗り・○の数には触れない（ADR-0071 帰結の「tester判断」） | 疑義D1 |
| 2 | `_RESPONSE_GRID_PROBE_JS` | 表要素内で、見出しセル・行・○の数セルを testid で集め、見出し列ごとに: 見出し矩形、見出し中心点の実効背景色、各行の同日セル（文字・`data-response-status`・中心X・中心点の実効背景色）、セルが無い行は見出し中心X×行中央の点の背景色（blank）、○の数セル（文字・中心X・top・背景色）を測る。最後に最下行の bottom、○の数セル総数、ページの横あふれを返す。点は `elementFromPoint`、背景色は祖先をたどった最初の不透明 `background-color` | layout.grid / paintedColumn / goingCountRow（DOMの描画状態のみ読む） | 一致 |
| 3 | `assert_response_table_has_board_layout` (1) 文字 | 各セルの `innerText.trim()` が `data-response-status` に対応する ○/△/× に完全一致するか | layout.cellContent | 一致 |
| 4 | 同 (2) 列そろえ | 各セルと○の数セルの中心Xが、同じ日の見出しセルの `[left-1, right+1]` に入るか | layout.grid「同じ日のセルは縦にそろう」 | 一致（空白位置の整列は直接は見ていない。Minor m3） |
| 5 | 同 (3) ○の数 | ○の数セルが各見出しにちょうど1つ（総数=列数）／`top+1 >= 最終人行bottom`／文字が「その列の GOING セル数」かつ `gathering-candidate-date` の `data-going-count` に等しい | goingCountRow.cell | 一致 |
| 6 | 同 (4) 塗り | 局面を DOM から読み、SCHEDULING なら `data-current-leader="true"`、他は `data-confirmed="true"` の候補日 id を塗る列とする。塗り列がありかつ塗らない列もあるとき、塗り列の全背景（見出し・○の数・セル・空白位置）が「塗らない列の全背景の集合」に含まれないこと。塗り列が無いときは全列の**見出し背景**が1列目と同じであること | paintedColumn.requirement | 概ね一致。分岐ごとの不足は Major 1・Minor m1/m2 |
| 7 | 同 (5)(6) | 表内に旧見出し「誰が・どの日に答えたか」のテキストが0件。ページが横にあふれない | layout.noHeading / overflow | 部分一致（Major 2・m4） |
| 8 | `assert_answers_group_shows_only_the_response_table`（新規） | `responseTable` が visible。tally2種・日程リスト・日程カード先頭が「DOMに attached かつ not visible」。ページ上の旧見出し「誰が・どの日に答えたか」が not visible。`gathering-confirm-date-select` が0件 | answersContent.requirement | 一致（Major 2・m5） |
| 9 | 8 を `assert_finalized_answers_and_links_entrance_is_functional` のタブ型・開閉行型の双方で、回答側を開いた直後に呼ぶ | FINALIZED の PC幅・スマホ幅の既存テスト（`test_gth_organizer_decision_answers_and_links_entrance_is_functional`）に乗る。リンク側を開いたあとは再検査しない | 追補27 決定4 | 一致 |
| 10 | `_candidate_date_flags` / `_candidate_date_going_counts` | `gathering-candidate-date` の属性を DOM から読むだけ（表側に属性を足さない契約どおり） | paintedColumn「表に属性を足さない」 | 一致 |

## 2. レビューチェックリスト（5観点）

1. **過不足**: 契約 Must の格子・1字・○の数・塗り・answersContent の主要部は検査している。不足は下記 Major 1/2、Minor m1〜m5。過剰（契約に無い要求）: 「塗り列の背景が**全ての**塗らない列の全行の背景と重ならない」は契約（同じ行の他列と違う）より強く、行の縞模様等があると誤って落ちる恐れ（m1）。
2. **Given の正当性**: TDR-GTH-49 の Given は既存。2人×2日で link_one=A:GOING/B:NOT_GOING、link_two=B:MAYBE のため、リーダーは日A（GOING 1 対 0）で、塗り列・塗らない列・空白位置（link_two×日A）・○の数（1 と 0）がすべて意味のある値で現れる。問題なし。ただし**この Given は SCHEDULING のみ**（Major 1）。
3. **Then の検証対象**: 描画状態（文字・矩形・computed 背景）を直接見ており、属性だけで済ませていない点は良い（ADR-0065/tester.md の DOM のみに沿う）。弱い箇所: 背景色 `null` が素通りする（m2）、塗り列なしの検査が見出し背景のみ（m1）。
4. **失敗の握りつぶし**: `try/except`・条件付き skip は無い。ただし (a) `_RESPONSE_GLYPH_BY_STATUS[status]` は想定外の status で `KeyError`（失敗にはなるが assert 失敗ではなく例外）、(b) `bgAt` が `null` を返す場合に `assertNotIn(None, …)` が素通りしうる（m2）、(c) 旧見出し検査が表の内側に限られ空振りになりうる（Major 2）。
5. **暗黙の前提**: viewport は既存の既定値（デスクトップ）に依存し、横あふれ検査は2列では実質発火しない（m4）。`_read_gathering_phase_from_dom` の結果に塗り属性の選択を委ねている。ヘッダ幅内に収まる判定は±1px許容。いずれも明記は無いが致命的でない。

## 3. 契約↔テスト対応の監査

| 契約の Must（追補27） | 検査 | 実行されるテスト |
|---|---|---|
| layout.grid（列そろえ） | ○ | TDR-GTH-49（SCHEDULING のみ） |
| layout.cellContent（○△×） | ○ | 同上。△ と ○ と × が全て現れる（A:GOING/B:NOT_GOING/B:MAYBE） |
| layout.headerCellContent（日・曜日・月の出し方） | **✗ 空でないことだけ** | — |
| layout.noHeading | △ 表内のテキスト1語のみ | 同上（SCHEDULING）。FINALIZED はページ全体で not visible（別関数） |
| layout.overflow | △ ページ横あふれのみ（容器内スクロールは見ない） | 2列では実質無意味 |
| paintedColumn（SCHEDULING・リーダー有り） | ○ | TDR-GTH-49 |
| paintedColumn（同点で複数） | ✗ | — |
| paintedColumn（リーダー無し＝塗らない） | △ 分岐はあるが**誰も通らない**、かつ見出しのみ | — |
| paintedColumn（SELECTING_SHOP / FINALIZED＝確定済みの日） | **✗ 分岐はあるが誰も通らない** | `assert_response_table_has_board_layout` の呼び出しは TDR-GTH-49 の1箇所のみ |
| paintedColumn（4.5/3.0 のコントラスト） | ✗（ADR-0066 の検査に委ねる前提か。判断できない） | — |
| goingCountRow（SCHEDULING） | ○ | TDR-GTH-49 |
| goingCountRow（SELECTING_SHOP / FINALIZED） | ✗（「3局面で present」は未検査） | — |
| answersContent（FINALIZED、PC・スマホ両形） | ○ | 既存の entrance テスト |
| answersContent（DOM 属性が無変更） | 本変更では検査せず（他箇所が `data-confirmed` 等を読むので間接的に担保） | 既存テスト群 |

**孤児 step**: なし（追加 step 1つは TDR-GTH-49 から呼ばれる）。**同義 step の重複**: なし（`response_table_matches` は属性、新 step は描画、観測軸が別）。
**未実装シナリオ**: 追補27 は `.feature` を変えていないため、シナリオ単位の未実装は無い。

## 4. 指摘一覧

### Critical: 0件

### Major

- **M1. 確定後・店選び中の「塗る列」と「塗る列なし」の分岐が、どのテストからも実行されない。**
  `assert_response_table_has_board_layout` は `phase == "SCHEDULING"` 以外で `CONFIRMED_ATTR` を読み、`painted` が空のとき別検査に入る
  コードを持つが、呼び出し元は TDR-GTH-49（SCHEDULING でリーダー有り）の1箇所だけ。したがって追補27 決定2の
  「確定済みの日の列を塗る」（ADR-0071 確認事項1・2で人間が判断する点そのもの）は**検証ゼロ**で、
  実装が確定後に有力な日を塗り続けても（ADR-0071 文脈2が指摘した現行実装の欠陥）、このテスト群は緑のまま。
  ○の数行・○△×・列そろえも FINALIZED/SELECTING_SHOP では未検査。
  **差し戻し先: tester。** 例: 既存の確定後テスト（`..._answers_and_links_entrance_is_functional` の PC幅）の中、または
  確定済みの日がリーダーと食い違う Given を持つ確定後の観測から同 DSL を呼ぶ。
- **M2. 契約が Must とした「形の規則」の一部が、文言・存在の検査に留まるか、空振りしうる。**
  (a) `headerCellContent`（日・曜日、月は最初と月替わりの列だけ）は `headerText != ""` のみ。月替わりを跨ぐ候補日を持つ Given も無い。
  (b) `noHeading` の検査は `table.get_by_text("誰が・どの日に答えたか")`（表要素の内側限定・部分一致）で、
  旧見出しが表の外のペイン見出しだった場合は常に0件になり空振りする。契約が列挙する旧見出し「日程」は定数に入っていない。
  ページ全体の旧見出し検査は FINALIZED の別関数にだけある。
  (c) 契約は「表自身の見出し行を置かない」を局面共通の Must としているが、SCHEDULING・SELECTING_SHOP では見出しの
  再混入を検出できる経路が弱い。
  **差し戻し先: tester**（検査を足すか、足さない理由を人間が承認するか）。

### Minor

- **m1.** 塗り分けの比較が契約より強い／弱い両方向にずれる: 強い側は「全ての塗らない列の全行の背景」との集合比較（縞模様の行や
  名前列の背景が同色だと誤って落ちる）。弱い側は「塗る列なし」で全列の**見出し背景のみ**を比較（本文・○の数・空白位置が塗られても通る）。
- **m2.** `bgAt` は `elementFromPoint` が表外・null のとき `null` を返し、`null` 同士／`null` と他の組合せを検査が区別しない
  （塗り列の測定点が別要素に覆われた場合に `assertNotIn` が素通りしうる）。`scrollIntoView` で緩和されているが、`None` を明示的に失敗にしていない。
- **m3.** 空白位置（セルの無い格子位置）は「見出し中心X×行中央」の点を測るだけで、そこに実際に格子の枠が存在するか
  （契約 grid「位置は空白で残す」）は検査していない。列そろえはセルが在る位置でしか確かめられていない。
- **m4.** 横あふれ検査は2列の表では発火しない（契約 overflow の本旨は列が多いとき）。表の入れ物の内側スクロールも見ていない。
  塗りの文字/背景コントラスト（契約が ADR-0066 に委ねる 4.5/3.0）がこの変更のどこで担保されるか、この差分からは**判断できない**。
- **m5.** `assert_answers_group_shows_only_the_response_table` は日程カードを `.first` だけ、日程リストの属性不変は見ていない。
  `CONFIRM_DATE_SELECT` の不在のみで「日を決める操作が無い」を代表させている（契約の根拠は `confirmDate.presenceRule`、
  確定ボタン類の別 testid は見ていない）。リンク側を開いた後の「表だけ」再検査もしない（契約の要求外）。

### 疑義（人間判断）

- **D1.** 検査が TDR-GTH-49（「参加者ごとに…一覧で示される」）に相乗りしている。シナリオ文は新 Must に触れておらず、
  見た目の崩れが業務シナリオの失敗として現れる。ADR-0071 帰結が「tester の判断（相乗りか L5）」と明記しているため
  逸脱ではないが、人間が相乗りを承認するか、専用の契約Must検査として切り出すかを決める必要がある。
- **D2.** ADR-0071 確認事項4（○△×に読み上げ名を持たせるか）の結論次第で、セル文字検査（`innerText` 完全一致）が
  `visually-hidden` の語を含んで落ちる。現時点では契約が「見える文字だけが Must」なので矛盾しないが、4の方針を変える場合は
  この検査も直す必要がある。

## 5. 差し戻し・エスカレーション

- シナリオと対訳表の**不一致**は検出していない（上表のとおり、コードの行うことは契約の記述と整合）。差し戻しは上の M1・M2（tester 宛）。
- シナリオ自体の欠陥の疑いは無い。D1 は人間判断事項として PR に載せる。
