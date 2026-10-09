---
id: 0075
scope: project/dining-radar
status: 承認済み
date: 2026-10-09
approved_by: "人間裁定（2026-10-09 Linear KEN-53 のコメント: 監査 B-2「板どおり。PC では ≡ と見出しを同じ行に置く」、B-3「店選び中・日程を聞いている幹事画面にも『‹ ランチ会』の戻り道を足す」を選択。確認事項1=A（バー左は汎用の「ランチ会」）・付随3点=既定どおり、を人間が2026-10-09にチャットで選択（調整役ken-18-28経由）。確認事項4は契約で必須にも禁止にもしない）"
supersedes: []
superseded_by: null
relates_to: [P-02, P-06, P-08, ADR-0059, ADR-0063, ADR-0066, ADR-0069, ADR-0072]
---

# ADR-0075: PC の上部バーを「左に画面名・右に≡」の1行にし、日程を聞いている／店選び中の幹事画面にも「‹ ランチ会」の戻り道を足す

> **承認者向けサマリ**: 2026-10-08 の再突き合わせ（`audit-board-vs-implementation-2026-10-08.md`、KEN-48）の
> B-2 と B-3 に、人間が KEN-53 のコメントで裁定した（B-2 板どおり／B-3 戻り道を足す）。
> **決定1**: PC（`twoColumnLayout`）で≡が出る全画面は、最上段を「左に画面名・右に≡」の**1本のバー行**にする。
> いまは≡だけの行があり、その下の行に見出しがある。ADR-0066 決定3 の「画面上端の行（この画面自身の見出しを
> 載せる行）」は、この2行でも文面上は満たされていた——それを幾何条件 TB-1〜TB-4 で閉じる。
> **決定2**: 戻り道 `gathering-dashboard-back` を、確定後だけでなく日程を聞き中・店選び中にも出す
> （`headingBar` を3局面に広げる）。会の名前（`gathering-dashboard-title`）は3局面とも画面唯一の `<h1>` にする。
> **決定3**: ADR-0069・0063・0066 との矛盾箇所を、部分的な置き換えとして表で明記する。
> **決定4**: `.feature` は変更しない。実装の影響範囲は末尾の「申し送り」。
> **契約**: 候補画面の観測面 1.15.0→1.16.0、会の観測面 0.30.0→0.31.0。YAML 編集は逐語 FIND/REPLACE
> （`.spec/conformance.spec`）で同梱する。

## 文脈

### 0. 検証の申告（meta/adr/0039）

実際に `Read`・`Grep` したもの: `activeContext.md`、`adr/0066`・`0069`・`0072` の全文、監査 2026-10-08
（`git show c419080:…` はBashが無く使えなかったため、同じ内容が入っている兄弟 worktree ken-48 の
ファイルを**読むだけ**した。変更はしていない）の B-2・B-3・A-1、`contracts/candidate-search-browser-interface.yaml`
（1.15.0）の `gatheringEntry` 全体と `primaryNavigationGeometry`、`contracts/gathering-scheduling-browser-interface.yaml`
（0.30.0）の `headingBar`・`schedulingLayout`・`confirmDate`・`crossFileSharedNavigation`、
実装の `home.html`・`organizer_gathering_list.html`・`organizer_gathering_create.html`・`organizer_dashboard.html`・
`gathering.js` の見出し周り、既存テスト `test_render_invariants.py`（見出しの局面別テスト）・`test_layout_sanity.py`
（`test_primary_navigation_geometry`）。板は `.orca/drops/dsg-out/party2/` の `d7/S4-PcSelect`・`S4-SpSelect`、
`b2/Q5-a-PcDetail`・`Q1-a-PcCreate`、`d4r/G1-PcFinal`、`f1/N1-b-PcCandidates` の HTML の文字列と構造を
読んだ（画像として開いてはいない）。**実行（テスト・撮影）はしていない。**
確認していないもの: 会の一覧の板（`organizerGatheringList` の上部バーを描いた板を、この調査では特定できなかった。
他の4画面と同じバーだと**読んだ**）。ADR 番号は、0073・0074 が他ブランチで使用済みなので 0075。

### 1. 板が描いている形

どの板でも、PC の最上段は同じ1本のバー（`.bar`）で、左に画面名（`.hd`）、右に≡（`.ibtn`）が並ぶ。
- 候補画面（f1 N1-b）: バー左は「ランチ候補をさがす」。これがその画面の見出しそのもの。
- 会をつくる（b2 Q1-a）・日程を聞き中（b2 Q5-a）・店選び中（d7 S4）・確定後（d4r G1）: バー左は汎用の
  「ランチ会」。**その下に**「‹ ランチ会」の戻り道、さらにその下に会の名前（または「ランチ会をつくる」）が
  ある。会の名前は、バーの文字とは別の、大きい見出し。

### 2. 実装の現状（監査 B-2・B-3）

- 候補画面・会の一覧・会をつくるは、先頭に≡だけの行があり、その下の行に h1 がある（`home.html` は `<nav>` が
  `<header>` の外、organizer 系は `.app-header` の中で include の次に h1）。
- 幹事画面は、日程を聞き中・店選び中に **h1 が無い**（店選び中の会の名前は `<span>`、日程を聞き中は
  testId の無い `<div>`。ADR-0069 が汎用 h1「会の日程調整」を外した結果）。確定後だけが h1＋戻り道。

## 決定

### 決定1（B-2）. PC の上部バーを「左に画面名・右に≡」の1行にする

契約 `candidate-search-browser-interface.yaml` の `gatheringEntry.primaryNavigationGeometry.topBar` を新設する
（規範源は候補画面側の1か所。ADR-0059 決定6 の共有ナビの流儀）。

- **対象**: `twoColumnLayout` が成立し `menuToggle` が出る全画面——候補画面（通常・会モード）、会の一覧、
  会をつくる、幹事画面の3局面。≡が出ない画面（サインイン・パスワード変更）とスマホは対象外。
- **画面名の要素（S）**: 候補画面・会の一覧・会をつくるはその画面の `<h1>`。幹事画面は新設の
  `gathering-dashboard-top-label`（表示専用の `<span>`、h1 ではない。文言は固定しない、板は「ランチ会」）。
  幹事画面の h1 は会の名前のまま、バー行の下（決定2）。理由: ADR-0069 決定3-5 が、G1/G2 の「上部バー」と
  「会の名前の行」を別の行と読み、会の名前を唯一の h1 と決めている。板もそう描いている（バー左は汎用の
  「ランチ会」、会の名前はその下）。会の名前の h1 をバー行に入れると、板の「‹ ランチ会」（バーと名前の間）の
  置き場がなくなる。
- **幾何条件**（T = `menuToggle`。矩形は描画後の border box、許容 1px）:
  - **TB-1 同じ行**: S と T の矩形が縦に重なり、S の中心 y が T の縦の範囲に入る。
  - **TB-2 画面名が左**: S が T の完全に左（S.right ≤ T.left）。
  - **TB-3 バー行の上に何も無い**: 自分の文字を持つか操作できる可視要素で、下端が min(S.top, T.top) 以上に
    上にあるものが無い（≡だけの行を禁じる）。
  - **TB-4 h1 は1つ**: 画面に `<h1>` がちょうど1つ。幹事画面では `gathering-dashboard-title`（S ではない）。
- 既存の「≡は行の右端」「点は≡の右上」「パネルは≡の下に右端を揃えて開く」は無変更。
- サイズ・色・フォント・バーの高さと余白は固定しない（ADR-0066 決定2 のとおり、位置・隣接・向きだけを固定）。

### 決定2（B-3）. 戻り道を3局面に出し、会の名前を3局面とも唯一の h1 にする

`gathering-scheduling-browser-interface.yaml` の `organizerDashboard.headingBar` を、SELECTING_SHOP・FINALIZED から
**SCHEDULING・SELECTING_SHOP・FINALIZED の3局面**に広げる。局面ごとの違いは次だけ。

| 要素 | SCHEDULING | SELECTING_SHOP | FINALIZED |
|---|---|---|---|
| `backLink`（`gathering-dashboard-back`） | 出る（新） | 出る（新） | 出る（無変更） |
| `title`（`gathering-dashboard-title`、h1） | 出る（新・h1） | 出る（h1に） | 出る（無変更） |
| `confirmedDate` | 出ない | 出る | 出ない |

- 戻り道の形は確定後と同じ（会の一覧への `<a href>`、押しても会の記録は変わらない、文言は固定しない、
  `formControlExemptTestIds` 登録済み・変更なし）。
- **戻り道の位置**（幾何条件。L = 戻り道、N = `title`）:
  - **BL-1 名前の上**: L.bottom ≤ N.top、かつ L の中心 y が N の中心 y より上（全局面・全幅）。
  - **BL-2 名前と左端が揃う**: |L.left − N.left| ≤ 4px。
  - **BL-3 バーの下**（`twoColumnLayout` のとき）: L.top ≥ max(`gathering-dashboard-top-label`.bottom, T.bottom) − 1。
  - 文書順で `title` の直前（ADR-0069 のまま）。44px の操作面の下限は他の操作要素と同じく適用（免除は足さない）。
- 「確定」の札・削除ボタン・統計行の位置は引き続き Must にしない（板に描かれていない／ADR-0069 の承認点のまま）。
- 日程を聞き中の `schedulingLayout.order` は、(1)「日を決める」の**上**に「バー行→戻り道→会の名前」が来る
  と注記する（(1) は本文中のブロック見出しで h1 ではない。ADR-0072 は無変更）。

### 決定3. 既存 ADR との矛盾箇所と置き換えの範囲

慣行（ADR-0069 決定5）に従い `supersedes: []` のまま、本文で覆す範囲を明記する。

| 既存ADR | 覆す範囲（本ADRが優先） | 覆さない範囲 |
|---|---|---|
| `adr/0069`決定3 項目3 | `backLink` が「FINALIZED でだけ出る」「SELECTING_SHOP には出さない」の部分。 | 戻り道の形（会の一覧への `<a>`）・会の名前の上という位置・FINALIZED での出現。 |
| `adr/0069`決定3 項目2 | 「FINALIZED では h1」の局面限定（他局面にも広げる）。 | 他に h1 を描かないこと、汎用見出し「会の日程調整」を出さないこと。 |
| `adr/0069`確認事項3 | 「SELECTING_SHOP に戻り道を足すか。足すなら板が要る」→ 板 d7 S4 ができ、人間が足すと裁定した。 | — |
| `adr/0063`決定2 | `headingBar` が「SELECTING_SHOP 局面の間だけ」であること（のちに ADR-0069 が FINALIZED へ広げた）→ SCHEDULING にも出す。`confirmedDate` の出現範囲は変えない。 | 見出しの会の名前・日時の関係、削除ボタンの置き方、`phaseIndicatorAttributes` の出現（SCHEDULING・FINALIZED）。 |
| `adr/0066`決定3 | `primaryNavigationGeometry.twoColumnLayout` の「画面上端の行（この画面自身の見出しを載せる行）」の読み。TB-1〜TB-4 で「同じ1行」と確定する。 | ≡の行内右端・点の位置・パネルの向きと収容・スマホの3項目とシート。 |
| `adr/0069`決定3 項目5 | 「上部バー」の読み（会の名前の行ではない）を、幾何条件にした（読みの追認であり変更ではない）。 | — |

### 決定4. `.feature` への影響: 変更しない

位置・並び・戻り道の有無は UI の構造で、業務規則を足さない（ADR-0066 決定6、ADR-0069、ADR-0054 決定4 の先例）。
`candidate-search.feature`・`gathering-scheduling.feature` は無変更。TDR-GTH-67「会の名前が示される／確定した開催日時が
示される」は、店選び中について無変更で成り立つ。`allowedPurposes`・`formControlExemptTestIds`・
`verifiesScenarios` も無変更（`gathering-dashboard-top-label` は表示専用の `<span>`、戻り道は登録済みの testId）。
`design.md`・`ARCHITECTURE.md` も変更しない（モジュール境界・データフローは動かない。プロジェクトには未作成のまま）。

## 検討した代替案

- **現状を板にする（B-2 の選択肢2）**: 人間が不採用。
- **幹事画面で会の名前の h1 をバー行に入れる**: 板の「バー→‹ ランチ会→会の名前」の順序と合わない。戻り道の置き場が
  バーの上になるか、戻り道を名前の横に動かすことになる。不採用（確認事項1）。
- **バー左の画面名を幹事画面でも h1 にし、会の名前を h2 にする**: ADR-0069 の「会の名前は画面唯一の h1」を覆す。
  見出しの意味づけ（スクリーンリーダの最上位が汎用の「ランチ会」になる）が弱くなる。不採用。
- **SCHEDULING には戻り道を足さず店選び中だけにする**: 人間の指示は「店選び中・日程を聞いている」の両方。
- **`headingBar` を広げず、戻り道だけを3局面に足す**: 戻り道の位置の基準（会の名前）が SCHEDULING に testId つきで
  存在しないため、位置を機械が測れない。`title` を3局面に出すほうが単純。
- **会の一覧・会をつくるの画面名も `gathering-…-top-label` のような別要素にする**: 板の会をつくる（Q1-a）は
  バー＋戻り道＋大見出しの形だが、その戻り道と大見出しは A-4（KEN-51）の範囲。今回は既存の h1 をバー行に入れるだけに
  とどめ、新しい testId を増やさない（確認事項2）。

## 帰結

- 契約（YAML編集は `.spec/conformance.spec` の OP 1〜11）:
  `candidate-search-browser-interface.yaml` 1.15.0→1.16.0（追補コメント、`primaryNavigationGeometry.topBar` 新設）。
  `gathering-scheduling-browser-interface.yaml` 0.30.0→0.31.0（追補30コメント、`topBarLabel` 新設、`headingBar` の
  出現範囲・`backLink` の出現と位置 BL-1〜BL-3・`title` の h1 規則の拡張、`schedulingLayout.order` の注記、
  `crossFileSharedNavigationNoteAdr0075`）。
- `.feature`・`design.md`・`ARCHITECTURE.md`: 変更なし（決定4）。
- ルート／プロジェクトの `activeContext.md`: 本ADRの所有範囲外（現在地の更新は orchestrator）。

## 申し送り（次工程。実装コードはここでは書かない）

### 実装（developer）の影響範囲

1. **候補画面**（`src/dining_radar/web/templates/web/home.html`）: ≡（`<nav>`/`.primary-nav-desktop`、約1366行）が
   `<header>` の外に先にあり、h1（約1463行、`.app-header`）が別の行。PC では h1 と≡を同じ行（フレックスの1行）に
   する。`header[data-testid="authenticated-application-shell"] .app-header` の CSS（約65・71行、約950行の h1 サイズ）と
   `.primary-nav-menu-toggle-wrap` 周辺の CSS を触る。**`home.html` を変えたらサーバ再起動が要る**（FR-025）。
   スマホ（`mapPrimaryTouchLayout`）の見え方は変えない。
2. **会の一覧・会をつくる**（`gathering/templates/gathering/organizer_gathering_list.html`・`organizer_gathering_create.html`、
   `organizer_primary_nav.html`）: `.app-header` の中で include の次に h1 の並び。同じ行にする。CSS は
   `gathering/static/dining_radar/gathering/organizer.css` の `.app-header`（約69行）・`.app-header h1`（約74行）・
   `body:has(#gathering-app) .app-header`（約184行）周辺。**キャッシュバスター**（`?v=`）を各テンプレートで上げる。
3. **幹事画面**（`organizer_dashboard.html` と `gathering.js`）: h1 は JS の描画（`#gathering-app`）で作られるため、
   バー行の画面名（`gathering-dashboard-top-label`）と≡（`<header>` 内）をどう同じ行に置くかが設計の要点
   （テンプレート側の `.app-header` に画面名を置いて CSS で≡と並べるか、JS で描くか。契約は幾何条件だけを固定）。
   `gathering.js`: `render()` の見出し分岐（約3234〜3251行）を3局面とも `headingBar` にそろえる——
   `renderShopSelectHeadingBar`（約1364行、会の名前を `<span>`→`<h1>`、戻り道を足す）、`renderFinalizedHeadingBar`
   （約1389行）、SCHEDULING の `gth-header`（約3240〜3250行、testId の無い会の名前 `<div>` を `gathering-dashboard-title` の
   `<h1>` に、戻り道を足す）。SCHEDULING では `confirmedDate` を出さない。`organizer.css` の `.gth-heading-bar`・
   `.gth-heading-back`・`.gth-title`・`.gth-header`。`gathering.js`・`organizer.css` の `?v=` を上げる。
4. 板との並べ確認（ADR-0066 決定4）: 候補画面（通常・会モード）、会の一覧、会をつくる、幹事画面3局面の PC を撮影して
   f1 N1-b・b2 Q1-a/Q5-a・d7 S4・d4r G1 と並べる。スマホの戻り道の見え方（S4-SpSelect）も確認する。

### 既存テストで更新が要りそうなもの（数えていない。洗い出しは developer/tester）

- `tests/ui_invariants/test_render_invariants.py` `test_gathering_dashboard_heading_bar_replaces_phase_indicator_only_while_selecting_shop`
  （約3481〜3548行）: **SCHEDULING で `gathering-dashboard-title` が 0 件という assert（約3500行）は偽になる**（3局面で出る）。
  SELECTING_SHOP の title を h1 とする assert、全局面で `page.locator("h1").count() == 1`、戻り道が3局面で出ること、
  `confirmedDate` が SCHEDULING で 0 件のままであることを足す。テスト名の「only_while_selecting_shop」も実態とずれる。
- `tests/ui_invariants/test_layout_sanity.py` `test_primary_navigation_geometry`（約1314行）: TB-1〜TB-4 の standalone assertion を
  足す（候補画面[通常・会モード]、会の一覧、会をつくる、幹事画面3局面。1440×900）。BL-1〜BL-3 は幹事画面3局面で。
  現在の `xfail(strict=True)` 9件のうち「h1 直前 0px 間隔」を理由に挙げるもの（`test_candidate_normal_and_menu_open` ほか）は、
  本実装で理由が変わりうる——直ったものから外す（ADR-0066 決定5）。h1 とバー行の間隔の検査 (n) は、
  同じ行になると「h1 直前の要素」が別物になるので、挙動を確認すること。
- `tests/acceptance/test_gathering_scheduling_acceptance.py`（`test_tdr_gth_67_…`、`test_gth_finalized_dashboard_has_the_contract_heading_structure`、
  約1982〜2013行）と、DSL `tests/acceptance/dsl/gathering_scheduling_browser.py`（`GATHERING_DASHBOARD_TITLE`・`GATHERING_DASHBOARD_BACK`、
  約67〜75行、約1218〜1223行の「SELECTING_SHOP の見出しの代替読み」、約1298〜1343行）、`steps/gathering_scheduling_steps.py`（約816行）:
  SCHEDULING での title・戻り道の読み方、`phaseIndicator` 不在の代わりに title を読むフォールバックの前提が変わらないかを確認。
- `tests/test_gathering.py`（約6130行 `test_dashboard_heading_shows_the_gathering_title`）、`tests/test_static_assets.py`
  （テンプレート・CSS の文字列を見る検査。ナビ周りの約690〜830行）: 文字列／構造の検査が見出しの並びに触れていないか確認。
- L5 の 44px 検査（戻り道が SCHEDULING・SELECTING_SHOP でも対象になる）。

### orchestrator への申し送り

- `.spec/conformance.spec` の適用（記法は推測。区切りが `apply_spec.py` と違えば直す。FIND が各1回一致することを確認）。
- `activeContext.md` の現在地（B-2・B-3 の決着、KEN-53）の更新は所有範囲外。
- 監査 B-1（絵文字→線画）・B-4（候補画面の中身）は本ADRの範囲外。A-4（KEN-51）の会をつくるの戻り道・大見出しも範囲外。

## 確認事項（人間に確認されたい）

承認済みの裁定（B-2・B-3）を契約に翻訳する際の、起草者の読みである。違えば改訂する。

1. **幹事画面のバー左は「ランチ会」の汎用ラベルで、h1 ではない。h1 は会の名前（バーの下）**。裁定の字面は「≡ と
   見出し(h1)を同じ行」だが、板（G1・S4・Q5-a）は「バー（ランチ会／≡）→‹ ランチ会→会の名前」の順で、ADR-0069 は会の名前を
   唯一の h1 と決めている。この板と ADR-0069 を保つ読み。代償: 幹事画面だけ「バーの文字」と「h1」が別の要素になる。
2. **会をつくる・会の一覧は、既存の h1 をバー行に入れるだけ**。会をつくるの板（Q1-a）はバー＋戻り道＋大見出し
   「ランチ会をつくる」の形だが、その戻り道と大見出しは A-4（KEN-51）に回す。
3. **日程を聞き中・店選び中の会の名前を、確定後と同じく h1 にする**（いまはこの2局面に h1 が無い）。
4. **スマホでのバー左の画面名**は契約で必須にも禁止にもしない（板は描いているが、スマホの導線は下部ナビ）。
   戻り道の位置（BL-1・BL-2）は全幅で固定する。
