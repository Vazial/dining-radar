# 独立監査: 日程を聞いている幹事画面の板レイアウト検査（KEN-13、契約0.29.0 追補28 / ADR-0072）

- **監査対象**: `git show bd71eb0 -- projects/dining-radar/tests/acceptance`。3ファイル・+227行:
  `dsl/gathering_scheduling_browser.py`（+165）、`steps/gathering_scheduling_steps.py`（+12）、
  `test_gathering_scheduling_acceptance.py`（追加3件）。
- **依拠した基準**: `contracts/gathering-scheduling-browser-interface.yaml` 0.29.0（追補28、`organizerDashboard.schedulingLayout`・
  `candidateDateList.candidateDate`の見た目・`confirmDate.target`/`disabledState`・`tentativeSelectionAndPreview.trigger`）、`adr/0072`（決定1〜4）。
- **独立性**: 先にDSL・step・テストを読み、docstring・コメントは「コードが何をしているか」の記述としてのみ参照した。
  コミットメッセージ・tester の意図説明は判断材料にしていない。**実装（`gathering.js`・CSS）は読んでいない**。
- **実行**: 追加3件だけ実行し **3 passed**（`.venv/bin/python -m pytest ... -k` 3件指定、7.87s）。実装の改変（変異注入）は
  所有範囲外のため**実行していない**。ADR-0065 の fault injection は §4 に「この変異ならどの行で落ちるか」の机上評価で記す。
- **役割確認**: `reviewer.md` の `tools:`（Read, Grep, Glob, Write, Bash）は実際に渡されている。

## 結論（先頭サマリ）

**Critical: 0件。Major: 2件。Minor: 6件。** 誤って緑になる検査は見つからず、追加3件の緑は契約と矛盾しない。
ただし契約が Must とした「対象なしになる条件」のうち**有力が同点で複数のとき**が、どのテストからも実行されない（Major 1）。
また「有力な日が1つ」というテストの Given が、DOM属性だけを物差しにしていて**有力がどの日か自体は断言されていない**（Major 2）。
承認判断は人間。

## 1. 対訳表（コードが実際にやること → シナリオ/契約）

| # | 新規・変更されたもの | コードが実際に行うこと（コードから書き起こし） | 契約上の根拠 | 突き合わせ |
|---|---|---|---|---|
| 1 | step `scheduling_layout_follows_the_board` → `assert_scheduling_layout_follows_the_board` | DOM上の局面が SCHEDULING であることを確かめる。ロール heading 名に「日を決める」を含む最初の見出しを取り、その文字列に「`gathering-candidate-date` の個数」と「`gathering-responded-summary` の `data-responded-count`」の数字が（前後が数字でない形で）含まれることを確かめる。次に 見出し→leaderSummary→responseTable→confirmDate→（あれば）open-shop-preview→candidateDateList→addCandidateDateOpen→participantLinkList の各要素について、`getElementsByTagName('*')` 上の位置が**厳密に増える**こと、画面上の top が**以下**（≦）であることを隣同士で確かめる。最後に名前が完全一致「日程」の見出しが1件も visible でないことを確かめる | schedulingLayout.order（1)〜(7)・旧「日程」見出し除去 | 一致。疑義 m1・m2 |
| 2 | step `candidate_dates_are_small_chips` → `assert_candidate_dates_are_small_chips` | 候補日が2件以上あることを確かめ、各 `gathering-candidate-date` について: visible／文字に自分の M/D(曜)（DSLが送った開始時刻から計算）が含まれる／「行ける」「たぶん」「むり」が文字に無い／高さ≥44px／右端がビューポート幅+1以内／内側に remove 部品がちょうど1つあり、その矩形がチップ矩形に収まる（±1px）。最後に `round(y/高さ)` を行の代用として集め、行の種類数が候補日数より小さい（全チップが別の行ではない）ことを確かめる | candidateDateAppearance（札・内訳なし・44px・折り返す行・はみ出さない） | 一致。疑義 m3・m4 |
| 3 | step `confirm_date_follows_its_target` → `assert_confirm_date_follows_its_target` | 決めるボタンを取り、対象を `_expected_confirm_target`（`data-tentative-selected="true"` の日があればそれ。無ければ `data-current-leader="true"` の日がちょうど1つならそれ。それ以外は None）で求める。None ならボタンが disabled で文言に「日を選んでください」を含む。対象があれば enabled で、文言に対象日の M/D(曜) と「に決める」を含む | confirmDate.target・disabledState | 一致。Major 1・2 |
| 4 | step `organizer_confirms_the_target_date` → `confirm_the_target_date` | 対象が None でないことを確かめ、既存の `confirm_tentatively_selected_date`（ボタンを押して見出しバーの出現を待つ）を呼び、確定後に `data-confirmed="true"` の日が `[対象]` ちょうど1つであることを確かめる | confirmDate.target「押すと対象を確定する」・requiredOutcome | 一致。m5（既存stepとほぼ重複） |
| 5 | 既存 `tentatively_select_candidate_date` の変更 | 札（`gathering-candidate-date`）をクリックする。クリック位置は札の中で remove 部品から遠い側の中央（remove が無ければ札の中央）。クリック後、札の `data-tentative-selected` が "true" になるのを待つ | tentativeSelectionAndPreview.trigger（札を押す） | 一致 |
| 6 | テスト `test_gth_scheduling_screen_follows_the_board_and_confirms_the_sole_leader` | 3候補日。参加者1人が日A=GOING・日B=MAYBE と答える。幹事画面を開き、step 1・2・3・4 を順に実行、局面が SELECTING_SHOP になることを確かめる。**仮選択はしない** | 専用シナリオなし（契約 Must）。target「有力が1つだけ」 | Major 2 |
| 7 | テスト `..._confirm_target_prefers_the_tentative_chip` | 3候補日。参加者1人が日A=GOING。幹事が日Bの札を押して仮選択 → step 3 → step 4 → SELECTING_SHOP | target「仮選択が優先」・決定4 | 一致。m6 |
| 8 | テスト `..._confirm_has_no_target_without_a_leader` | 3候補日、回答なし。幹事画面を開き、有力な日の集合が空であることを確かめ、step 3（None 分岐）を実行 | disabledState「対象なしで無効」 | Major 1（同点分岐が無い） |

## 2. レビューチェックリスト（5観点）

1. **過不足**
   - 足りない: 同点の有力が複数のときの対象なし（Major 1）。有力が無くても仮選択すれば有効になる分岐（m6）。
     leaderSummary 自体が無い（有力なし）画面の並び（8番テストは並びを見ない）。
   - 過剰: なし。`round(y/height)` の行判定は契約より強くも弱くもなりうる（m3）。
2. **Given の正当性**
   - 6番: 日Aが GOING 1 で日Bが MAYBE。ほかに回答は無いので日Aだけが有力になるはずだが、**テストはそれを断言していない**（Major 2）。
   - 7番: 同上。仮選択（日B）と有力（日A）が別の日であることが優先の検査の肝なのに、有力が日Aであることを断言していない（Major 2）。
   - 8番: 回答ゼロ。`candidate_date_current_leaders_are(set())` で有力が空と断言しており、Given は正当。
3. **Then の検証対象**: 描画状態（見出し文字・DOM順・top・矩形・disabled・ボタン文言）を直接見ており、属性だけで済ませていない。
   一方、決める対象の物差し `_expected_confirm_target` は実装が出す `data-*` 属性そのもの。契約の `target` 定義が属性で書かれているので契約には沿うが、
   **属性の正しさは別の場所で保証されている必要がある**（Major 2）。
4. **失敗の握りつぶし**: `try/except`・条件付き skip は無い。`open-shop-preview` が無いとき並び検査から外すのは契約の「when present」どおり。
   `.first` で最初の1件だけを見る箇所（見出し・各 testId）が複数一致を見逃しうる（m2）。
5. **暗黙の前提**: ビューポートは既定（デスクトップ）だけ。スマホ幅（板 Q5-a-SpDetail が原典の一つ）は検査していない（m4）。
   `_chip_date_parts` はDSLが送った `startAt` の曜日を使い、`datetime.fromisoformat` の時差の扱いは既存 `_expected_header_parts` と同じ。

## 3. 契約↔テスト対応の監査

| 契約の Must（追補28） | 検査 | 実行されるテスト |
|---|---|---|
| schedulingLayout.order（見出し→有力→表→決める→札→リンク） | ○（DOM順・画面top） | 6番（有力あり） |
| 見出しに候補日数・回答数 | ○ ただし数字が含まれるだけ（m1） | 6番 |
| 旧「日程」見出しの除去 | ○ visible でないことのみ（DOMに残っても可。契約は「removed」） | 6番 |
| candidateDateAppearance（札・内訳なし・44px・折り返す行） | ○（デスクトップのみ。m4） | 6番 |
| 札に remove 部品が入る | ○ | 6番 |
| confirmDate.target ＝ 仮選択 | ○ | 7番 |
| confirmDate.target ＝ 有力が1つ | ○（有力の特定は属性任せ。Major 2） | 6番 |
| confirmDate.target ＝ 有力が同点で複数 → なし・disabled | **✗** | — |
| confirmDate.target ＝ 有力なし → なし・disabled・「日を選んでください」 | ○ | 8番 |
| 仮選択のみ（有力なし）で有効 | **✗** | —（m6） |
| 仮選択の入口は札を押す操作 | ○ | 7番（および既存全テスト） |
| 孤児step | なし。追加4stepはすべて呼ばれる | |
| 同義step重複 | `organizer_confirms_the_target_date` と既存 `organizer_confirms_the_tentatively_selected_date`（m5） | |

## 4. Fault injection（ADR-0065。DSL の主張が本当に落ちるか。机上評価・実装は変異していない）

| # | 実装がこう壊れたら | どの検査で落ちるか | 判定 |
|---|---|---|---|
| F1 | 決めるボタンが札の列の下に出る | step 1 の DOM順 `confirmDate < candidateDateList` | 落ちる |
| F2 | 有力の札（leaderSummary）が表の下 | 同 `leaderSummary < responseTable` | 落ちる |
| F3 | 見出しが旧「日程」のまま | 「日を決める」見出しが無く `expect(...).to_be_visible()` で失敗 | 落ちる |
| F4 | 見出しの候補日数が実際と違う | 数字の包含検査 | **落ちるが弱い**: 数字は見出しのどこにあってもよく、候補日数と回答数を取り違えても通る（m1） |
| F5 | 候補日が1件ずつの全幅カードで縦並び | step 2 の「全チップが別の行」 | 落ちる |
| F6 | 札に内訳（行ける…）が残る | 文字の `assertNotIn` | 落ちる |
| F7 | 札が44px未満 | 高さ検査 | 落ちる |
| F8 | 札の remove が札の外 | 矩形包含 | 落ちる |
| F9 | 決めるボタンが仮選択を無視して常に有力の日を指す | 7番: ボタン文言が日Bでない | 落ちる（ただし有力が日Aである前提。Major 2） |
| F10 | 決めるボタンが有力を無視して仮選択だけを見る（旧仕様） | 6番: 仮選択がなく target=有力日だが、ボタンが disabled | 落ちる |
| F11 | 同点で先頭の日を対象にする | **どのテストも落ちない** | **すり抜ける（Major 1）** |
| F12 | 有力なしでボタンが有効のまま | 8番 | 落ちる |
| F13 | 文言が日付なしの「この日にする」 | 3の文言検査 | 落ちる |
| F14 | ボタンの対象と実際に確定する日が違う | step 4 の `confirmed == [target]` | 落ちる |
| F15 | 札を押しても仮選択にならない | `tentatively_select_candidate_date` の `to_have_attribute(..."true")` | 落ちる |
| F16 | 有力の属性が全く付かない／日Bに付く | 6番: 属性が無ければ target=None で step 4 が失敗。日Bに付けば**通ってしまう** | **一部すり抜ける（Major 2）** |
| F17 | 札が右にはみ出す | 右端検査（3件・デスクトップ幅のみ。m4） | 弱い |

## 5. 指摘一覧

### Major

- **Major 1: 有力が同点で複数のときの「対象なし」が未検査**（契約 `confirmDate.target` の「exactly one carries it; else none」、ADR-0072 決定3・確認事項3）。
  追加3件は「有力1つ」「仮選択」「回答ゼロ」しか作らない。実装が同点のとき先頭の日を対象にする（確認事項3で人間が退けた案）に壊れても全件緑のまま（F11）。
  推奨: 参加者2人で日Aと日Bに同数の GOING を付け、`candidate_date_current_leaders_are({A, B})` を断言したうえで、ボタンが disabled ・「日を選んでください」であることを確かめるテストを足す。

- **Major 2: 「有力な日がどれか」を断言せず、対象の物差しを実装の `data-*` 属性だけに置いている**（6番・7番）。
  契約の `target` 定義が属性で書かれているのでこの読み方自体は契約に沿うが、6番のdocstringが言う「1日目だけが有力」、
  7番が前提とする「有力（日A）≠仮選択（日B）」は、テストのどこにも断言が無い。有力の属性が誤った日に付く実装でも、
  ボタンはその日を名指しして確定し、6番は緑になる（F16）。7番も、有力が日Bに誤付与されていれば「優先」の検査が空振りする。
  推奨: 6番・7番に `self.steps.candidate_date_current_leaders_are({date_a})` を足す（8番が使っている既存stepで足りる）。

### Minor

- **m1**: 見出しの数字は、候補日数と回答数が「文字列のどこかに現れる」だけを見る。「候補日N日」「回答N人」の対応は見ない。
  今のGivenは候補日3・回答1で数が違うため取り違えは現れうるが、「3」「1」が別の箇所（日付等）に含まれても通る。契約が「wording not fixed」なので、許容範囲だが弱い。
- **m2**: 並びの検査は画面 top が `≤`（同値可）、見出し・各 testId は `.first` のみ。重なっていても通る。旧「日程」見出しは visible でなければよく、DOMに残ってもよい（契約は「removed」）。
  また leaderSummary が無い画面（有力なし）の並びは、どのテストも見ない。
- **m3**: 「行」を `round(y/高さ)` で近似している。高さの違うチップが混ざる・折り返し位置が高さの整数倍に載らない場合に、誤判定しうる。3件では「全部別の行」だけを弾く弱い検査。
- **m4**: 札のはみ出し・折り返しはデスクトップ幅・3件でしか見ない。契約は「Chips never overflow the page horizontally」で、板は20件・スマホ幅の図。多件数・スマホ幅の実行テストが無い。
- **m5**: `organizer_confirms_the_target_date` は既存 `organizer_confirms_the_tentatively_selected_date` に確定結果の断言を足しただけで、同義に近い。名前も「仮選択でなくても使える」ことを示す。
- **m6**: 「有力が無くても札を押せば仮選択でボタンが有効になる」分岐はテストが無い。ADR-0072 決定3の「仮選択＞有力」の仮選択側が、有力なしの局面で働くかは未実行。

## 6. 差し戻し・エスカレーション

- シナリオと対訳表の不一致: なし。
- 契約自体の欠陥の疑い: なし。ただし追補28の3つのMustにシナリオ（`.feature`）が無く、`verifiesScenarios` にも載らない。ADR-0072 が `.feature` 無変更と決めているので意図どおりだが、
  承認者は「これらの検査はシナリオではなく契約のMustだけに根拠がある」ことを知ったうえで承認されたい。
- 判断できなかった箇所: 実機の見た目（板 Q5-a と並べた目視）は本監査の範囲外。実装を読んでいないので、F4・F16 の弱さが実際に起きるかは分からない。

## 7. 再監査（commit 490ecaa: 同点テストと有力の断言の追加）

- **監査対象**: `git show 490ecaa -- projects/dining-radar/tests/acceptance`（`test_gathering_scheduling_acceptance.py` +21行のみ。DSL・stepの変更なし）。
  使うstep `candidate_date_current_leaders_are` は既存（`gathering_scheduling_steps.py:403` → DSL `assert_candidate_date_current_leaders`）で、
  全候補日の `data-current-leader` を集合として等値比較する（過剰印も不足印も落ちる）。
- **独立性**: 前回と同じ。テストとDSLのみを読み、実装（`gathering.js`・CSS）は読んでいない。コミットメッセージは判断材料にしていない。
- **実行**: 6・7・8番と新規の同点テストを `-k` で実行し **5 passed**（11.15s。`sole_leader` 等のパターンが既存の別テスト1件にも一致したため5件）。実装の変異注入は所有範囲外のため行っていない。

### 再監査の結論

**Critical: 0件。Major: 0件（前回の2件とも解消）。新規の Critical/Major: なし。** Minor は前回の m1〜m6 が据え置き（下記）。承認判断は人間。

### 前回 Major の解消確認

| 前回 | 対応 | 判定 | 根拠（コードから） |
|---|---|---|---|
| Major 1 同点で有力が複数→対象なし | 新規 `test_gth_scheduling_confirm_has_no_target_when_leaders_tie` | **解消** | 参加者2人が日Aと日Bにそれぞれ GOING。`candidate_date_current_leaders_are({date_a, date_b})` で有力が正確に2つと断言し、仮選択はせず `confirm_date_follows_its_target`。`_expected_confirm_target` は仮選択なし・有力2件で None を返し、None 分岐が「ボタン disabled・『日を選んでください』」を確かめる。 |
| Major 2 有力がどの日かを断言していない | 6番・7番に `candidate_date_current_leaders_are({date_a})` を追加 | **解消** | どちらも Given（日A=GOING 1／日B=MAYBE、日A=GOING 1）から有力は日Aだけ。断言は幹事画面を開いた直後・以降の操作の前にある。7番は有力日A≠仮選択日B が前提として固定された。 |

### Fault injection の再評価（机上）

| # | 実装がこう壊れたら | どの検査で落ちるか | 判定 |
|---|---|---|---|
| F11 | 同点で先頭の日を対象にする | 同点テスト: 有力は{A,B}のまま（属性は変わらない）で期待対象 None だが、ボタンが enabled になり disabled の断言で失敗 | **落ちる**（前回: すり抜け） |
| F16 | 有力の属性が日Bに付く／付かない | 6番・7番: `leaders_are({date_a})` の集合比較で失敗 | **落ちる**（前回: 一部すり抜け） |
| F9 | ボタンが仮選択を無視し常に有力の日を指す | 7番: 有力=日Aが確定したうえで、ボタン文言が日Bでないため失敗 | 落ちる（前提が断言で担保された） |
| 同点で disabled だが文言が「日を選んでください」でない | 同点テストの None 分岐の文言検査 | 落ちる |

### 新たな疑義の確認（Critical/Major に当たるものは無し）

- **誤って緑になる検査**: 同点テストの期待対象は DOM の `data-*` から導出されるが、有力の集合は Given から独立に断言されているため、導出と実態のズレは先に落ちる。循環はない。
- **失敗の握りつぶし・孤児step・重複**: 追加は既存stepの組み合わせのみ。try/except・skip なし。孤児・新規の同義重複なし。
- **同点の作り方**: GOING 1 対 GOING 1 の単純な同数のみ。MAYBE を含む重み付けの同点などは見ない（契約の定義が属性ベースなので許容。Minor m7）。

### 据え置きの Minor（前回の m1〜m6 は未変更）と新規

- m1〜m5: 変更なし（数字の包含検査の弱さ／`.first`・`≤` の緩さ／行の近似／デスクトップ幅のみ／同義step）。
- **m6**（有力なしで仮選択すれば有効になる分岐）は今回も未検査。追加は同点テストと断言のみ。
- **m7（新規）**: 同点テストは仮選択を伴わない。同点の局面で札を押せば有効になる経路（仮選択＞同点）は m6 とあわせて未実行。
- 以上、いずれも Critical/Major ではない。
