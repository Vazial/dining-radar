---
id: 0069
scope: project/dining-radar
status: 承認済み
date: 2026-10-04
approved_by: "人間裁定（2026-10-04 PR #14 のマージを承認とする旨を、人間が調整役とのチャットで明言したと調整役 ken-18-d8 が伝達。マージ者は GitHub アカウント Vazial）"
supersedes: []
superseded_by: null
relates_to:
  [P-02, P-06, P-08, ADR-0054, ADR-0056, ADR-0059, ADR-0062, ADR-0063, ADR-0066]
---

# ADR-0069: 候補検索画面の右上チップをやめて行き先を≡の中だけにし、確定後の幹事画面の見出しと地図を板 d4r G1/G2 の形へ戻す

> **承認者向けサマリ**: `adr/0066`が記録した板と実装の突き合わせ（`audit-board-vs-implementation-2026-09-22.md`）
> のうち、(a) 人間が提示した選択肢のうち「案2」を採る裁定（候補検索画面の右上チップ
> `candidate-gathering-entry`をやめ、ランチ会への行き先は≡の中だけにする。≡の右上に、進行中の会が
> あることを示す点を付ける。板 `party2/f1` N1-b）と、(b) 確定後の幹事画面の見出し・地図を板
> `party2/d4r` G1/G2 へ戻す件（監査 D6・D7）を、契約に書く。決定は4点。
> **決定1**: チップ（と件数バッジ）を全画面で廃止する。**決定2**: 旧バッジの件数属性は新設の点
> `candidate-primary-nav-menu-dot`が、旧`data-active-gathering-id`は`menuDestinationGathering`が
> そのまま引き継ぐ。点は会の画面群の中では出さない（旧チップと同じ扱い、板G1で≡に点が無い）。
> **決定3**: 確定後の幹事画面の見出しを、戻り道「‹ ランチ会」→会の名前の順に並べ、会の名前を画面で唯一の
> レベル1見出しにし、汎用見出し「会の日程調整」を外す（`headingBar`をFINALIZEDにも広げ、戻り道
> `gathering-dashboard-back`を新設）。**決定4**: 確定後の地図を、見出しの下から端から端まで埋め、
> 外側の余白・枠・角丸を持たない形にする。**決定5**: `adr/0059`・`adr/0054`・`adr/0066`との
> 矛盾箇所を、部分的な置き換え（覆す）として表で明記する。
> **人間が承認する点**は末尾の「確認事項」に3つ挙げた。とくに、板に描かれていない2点
> （「確定」の札を会の名前の横に置く／「この会を削除」を見出し行の右に置く）は、指示どおり人間の承認点
> として明記し、契約のMustにはしていない。回答タブの表（監査 D5）は KEN-42 の範囲で、本ADRは触らない。

## 文脈

### 0. 検証の申告（meta/adr/0039）

次を実際に`Read`した: `activeContext.md`、`adr/0059`・`0062`・`0063`・`0066`（本文）、
`contracts/gathering-scheduling-browser-interface.yaml`（0.25.0）の`organizerDashboard`の
`headingBar`・`finalizedSummary`・`unavailableControls.formControlExemptTestIds`、
`contracts/candidate-search-browser-interface.yaml`（1.14.0）の`gatheringEntry`節全体・
`browserActions.openGatheringEntry`/`returnToGatheringFromEntry`、`audit-board-vs-implementation-
2026-09-22.md`、板 `.orca/drops/dsg-out/party2/d4r/G1-PcFinal.dc.html`・`G1-SpFinal.dc.html`・
`G2-PcFinal.dc.html`・`party2/f1/N1-b-PcCandidates.dc.html`・`N1-c-PcCandidates.dc.html`
（HTMLのCSSと文字列を読んだ。板は画像として開いてはいない）。
確認していないもの: 実装コード・テスト（本タスクの範囲外で、読んでもいない）。そのため、チップや
`candidate-gathering-entry`を参照する既存テストがいくつあるかは、本ADRは数えていない。developerの
実装スライスで洗い出すこと。

### 1. 経緯

- **チップ**: `adr/0059`決定2は、≡（`candidate-primary-nav-menu-toggle`）の隣に、進行中の会があるときだけ
  チップ`candidate-gathering-entry`を出すと決めた。`adr/0066`決定3は、その位置（≡の左隣）を
  `primaryNavigationGeometry`のMustにした。その後、人間が実機で「ランチ会への行き先が2つある」と
  指摘し（`activeContext.md`「人間の判断待ち」1）、選択肢3つ（案1 いまの決まりどおり／案2 チップを
  やめる／案3 ≡はアカウント専用）が提示された。**人間は案2を採った。**板は`party2/f1`のN1-b
  （「チップをやめ、行き先は≡の中だけ」）で、≡の右上に8pxの緑の点が描かれている。
  会の画面群のほうには、チップは既に無い（`adr/0059`決定2、契約`entry.requirement`の存在条件）。
- **確定後の幹事画面**: 板 d4r G1/G2 は、上部バー（左に「ランチ会」、右に≡）の下に、「‹ ランチ会」の
  戻り道と会の名前（例「9月のランチ会」）を置き、その下から地図を端から端まで埋める
  （地図は`inset: 0; border: 0; border-radius: 0`）。実装は、≡が左上、ページ見出し「会の日程調整」、
  「確定」の札、会の名前が別の行、地図は余白と角丸の枠の中、になっている（監査 D6・D7）。
  契約側は、`headingBar`がSELECTING_SHOPにだけあり（`adr/0063`決定2）、FINALIZEDの見出しは
  契約に何も書いていなかった。`adr/0066`決定2が定めた一般方針（板が裁定した位置・並びは契約のMust）に
  従えば、これも契約に書かれているべきだった。

## 決定

### 決定1. チップ`candidate-gathering-entry`（と`candidate-gathering-entry-badge`）を全画面で廃止する

`candidate-search-browser-interface.yaml`の`gatheringEntry.entry`は廃止の記録だけを残し、
`requiredTestIds.entry`を外す。`candidate-gathering-entry`・`candidate-gathering-entry-badge`は、
候補検索画面（通常・会モード）・会の画面群のどこにも出現してはならない
（`browserEntry.authenticatedInitialOutcome.absent`へ追加する）。デスクトップの会への行き先は
≡のパネル内の`menuDestinationGathering`の1つだけになる。モバイルは元からチップを持たず、下部ナビ
`mobileBar`は無変更。`browserActions.openGatheringEntry`・`returnToGatheringFromEntry`の`input`は
`[candidate-primary-nav-gathering, candidate-primary-nav-menu-gathering]`の2つになる（排他・網羅の関係は
無変更）。

### 決定2. 進行中の会の印を≡右上の点にし、旧チップの観測値を移す

- 新設`gatheringEntry.menuDot`（testId`candidate-primary-nav-menu-dot`、表示専用、purpose宣言なし）。
  `menuToggle`の右上の角に重なる。`twoColumnLayout`成立中・進行中の会の数が1以上・現在の画面が
  会の画面群（`organizerGatheringList`・`organizerGatheringCreate`・`organizerDashboard`）の中では
  ないときだけ出現する。数が0のときは出ない。
- 点は属性`data-in-progress-gathering-count`（10進整数文字列）を持つ。値と「1以上のときだけ出現」の規則は、
  廃止する`candidate-gathering-entry-badge`のものをそのまま移したもの。これでチップなしでも件数が
  機械的に観測できる。
- 旧`entry.activeGathering`の`data-active-gathering-id`（会モードのときだけ非null、通常画面では属性自体が
  無い。`adr/0056`決定8）は`menuDestinationGathering`へ移す。規則は無変更。
- 点を会の画面群の中で出さないのは、旧チップが同じ画面群から外されていた2026-09-16の人間裁定に揃え、
  かつ板G1/G2が会の画面の≡に点を描いていない事実に合わせたもの。これは板から読み取った**解釈**であり、
  人間に確認する（確認事項2）。
- `primaryNavigationGeometry.twoColumnLayout`から「チップは≡の左隣」の1文を外し、「点は≡の右上の角」に
  置き換える。`mapPrimaryTouchLayout`側は無変更。

### 決定3. 確定後の幹事画面の見出しを板 d4r G1/G2 の形にする（契約の変更）

`gathering-scheduling-browser-interface.yaml`の`organizerDashboard.headingBar`について:

1. **FINALIZEDにも出す。** 出現はSELECTING_SHOPとFINALIZED。SCHEDULINGでは出ない（無変更）。
2. **`title`**（`gathering-dashboard-title`）は両局面で出る。FINALIZEDでは、これが画面で唯一の
   レベル1見出し（`<h1>`）で、他にレベル1見出しを描かない。現行実装の汎用見出し「会の日程調整」を
   外すのがこの規則。
3. **`backLink`を新設**（testId`gathering-dashboard-back`）。FINALIZEDでだけ出る、会の一覧への
   平叙な`<a href>`（板の「‹ ランチ会」）。文書順・表示位置とも会の名前の上。`formControlExemptTestIds`へ
   登録する（purpose宣言は要らない）。SELECTING_SHOPには出さない——その局面の見出しには戻り道を
   裁定した板が無いため（確認事項3）。
4. **`confirmedDate`はSELECTING_SHOPだけに狭める。** 板G1/G2の見出しに日付は無い。FINALIZEDで決まった日は
   パネルの大きな日付（`decisionBanner`の`data-confirmed-candidate-date`）が持つ。
5. **上部バー**（左に「ランチ会」、右に≡）は板に描かれているが、≡は共有ナビ（`adr/0059`決定6・
   `crossFileSharedNavigation`）が既に3画面で常設し、`primaryNavigationGeometry`が右端をMustにしている。
   バーの文字「ランチ会」は表示文言で、契約は固定しない。`adr/0066`決定3の「画面上端の行（この画面の
   見出しを載せる行）」は、G1/G2では**この上部バー**を指すものと読む（会の名前の行ではない）。
   これは`adr/0066`の読み替えであり、変更ではない。

**板に描かれていない2点**（人間の指示により、契約のMustにせず、人間が承認する点として明記する）:

- 「確定」の札（`gathering-phase-indicator`。FINALIZEDで出る、無変更）を、会の名前の**横**に置く。
  板G1/G2に札は無く、同等の「決まりました」はパネル内にある。
- 「この会を削除」ボタン（`gathering-delete-open`、無変更）を、見出し行の**右**に置く。`adr/0063`が
  SELECTING_SHOPで同じ置き方を人間の裁定で決めている。

### 決定4. 確定後の地図を、見出しの下で端から端まで埋める（契約の変更）

`finalizedSummary.decisionBanner.map`（`gathering-decision-shop-map`）へ`layout`を新設する。
地図は見出し（`headingBar`）の下端から、画面の内容領域の下端（モバイルは`mobileBar`の上端、ほかは
ビューポートの下端）まで、ビューポートの全幅に広がる。左右の端がビューポートの端に一致し、外側の余白・
見える枠・角丸（computed `border-radius` が0）を持たない。見出しと地図の間に他の要素を挟まない。
浮かせたパネル（`adr/0062`決定4）は地図に重なり、地図の箱の一部ではないので、パネル自身の余白・角丸は
無変更。高さの具体値・パネルの大きさは契約が固定しない視覚の選択のまま。

### 決定5. 既存ADRとの矛盾箇所と、置き換えの範囲

本リポジトリの慣行（`adr/0059`・`adr/0062`・`adr/0066`がそうしたように、一部を覆すADRは
`supersedes: []`のまま本文で明記する。`supersedes`に挙げるとgovlintは相手を丸ごと`superseded`
扱いにするため）に従い、front matterの`supersedes`は空とし、覆す範囲を次の表で定める。
覆されない部分は、各ADRの決定のまま有効。

| 既存ADR | 覆す範囲（本ADRが優先） | 覆さない範囲 |
|---|---|---|
| `adr/0059`決定2 | 「既存の`candidate-gathering-entry`（チップ）は、進行中の会があるとき、会の画面群の中ではないとき、≡の隣に出る」の部分（チップの存在そのもの）。 | ≡・パネル・行き先2つの新設。会の画面群で≡が常設であること。モバイルの決定1。 |
| `adr/0059`決定4 | `browserActions.openGatheringEntry`/`returnToGatheringFromEntry`の入力のうちチップ。 | 2つのactionの排他・網羅の関係と、会モード中の行き先。 |
| `adr/0054`決定1（`adr/0059`決定2が一部を覆した残り） | 「`candidate-gathering-entry`は候補検索画面に常設」「会モードでも非nullの`data-active-gathering-id`を持つ」の主語がチップである部分。 | 「会に入ると出られない」を作らないという関心（≡と下部ナビが担う）。 |
| `adr/0056`決定8 | `data-active-gathering-id`の置き場所（チップから`menuDestinationGathering`へ）。 | 属性の値と出現規則。 |
| `adr/0066`決定3 | `primaryNavigationGeometry.twoColumnLayout`の「チップは≡の左隣」。 | ≡の行内右端・パネルが≡の下で右端を揃えて開きビューポートに収まること・モバイルの3項目とシート。 |
| `adr/0063`決定2 | `headingBar`が「SELECTING_SHOP局面の間だけ」であること。`confirmedDate`の出現範囲は変えない（SELECTING_SHOPのみ）。 | 局面の札の落とし方、見出しの会の名前・日時、削除ボタンの置き方。 |
| `adr/0062`決定4 | FINALIZEDの見出し・地図の位置・形について契約が何も書いていなかった空白を埋める（覆すものはない）。 | 確定後を「決まった店だけ」にする決定、パネルとタブ/開閉行。 |

`adr/0066`は本ADRの時点で`提案中`。本ADRは0066の承認とは独立に読めるが、0066のYAML（1.14.0）は既に
契約に入っているため、上の置き換えは契約の現行版に対して行っている。

## 検討した代替案

- **`supersedes: [0059]`として0059を丸ごと置き換える**: 不採用。0059は下部ナビ・≡・小窓・帯の格下げなど、
  本ADRが触らない決定が大半で、丸ごと`superseded`にすると有効な決定が無効に見える（`adr/0062`・`0066`が
  同じ理由で部分的に覆す書き方を選んでいる）。
- **チップを残し、会の画面群の外だけで点を併用する**: 不採用。人間の裁定は「行き先は≡の中だけ」。
- **点を会の画面群の中でも出す**: 不採用（現時点）。板G1/G2に点が無い。人間が違う読みなら確認事項2で。
- **旧バッジの件数を`menuDestinationGathering`の属性にする**: 不採用。そこはパネルが閉じているとDOM上に
  無い実装がありうる。点は閉じていても出るので、旧バッジの観測性を保てる。
- **FINALIZEDの見出しの並び・`<h1>`を契約に書かない**: 不採用。`adr/0066`決定2が、板の裁定した並びは
  契約のMustとしており、書かなかったことが今回の見逃しの上流の原因だった。
- **「確定」の札・削除ボタンの位置もMustにする**: 不採用。板に描かれておらず、人間の指示でも承認点とされている。

## 帰結

- `contracts/candidate-search-browser-interface.yaml`（1.14.0→1.15.0）: 追補コメント、`entry`の廃止記録、
  `menuDot`新設、`menuDestinationGathering.activeGatheringId`、`absent`への2件追加、2つのactionの
  `input`、`primaryNavigationGeometry`・`verificationAllocation`の文言。
- `contracts/gathering-scheduling-browser-interface.yaml`（0.26.0→0.27.0）: 追補26コメント、
  `headingBar`の出現範囲・`backLink`新設・`title`のh1規則・`confirmedDate`の狭め、
  `deleteButtonPlacement`の注記、`decisionBanner.map.layout`新設、
  `formControlExemptTestIds`へ`gathering-dashboard-back`。
- `.feature`・`allowedPurposes`・`verifiesScenarios`・`design.md`・`ARCHITECTURE.md`: 変更しない。
  構造と配置の決定で、新しい業務規則も新しいpurpose（押せる部品）も増えない。
- 次の実装スライス（developer。KEN-42の回答タブの表とは別）: (1) チップの除去と、点・
  `data-active-gathering-id`の移設。(2) 確定後の見出しと地図を決定3・4のとおりに。(3) `adr/0066`が
  申し送った`primaryNavigationGeometry`のL5アサーションに、点の位置（≡の右上）を足す。
  (4) 撮影して板G1/G2・N1-bと並べて見る（`adr/0066`決定4）。
- ルート／プロジェクトの`activeContext.md`の「人間の判断待ち」1（案1/2/3）は、案2で決着として更新が
  要る。これは本ADRの所有範囲外なので、orchestratorへの申し送りとする。

## 確認事項（人間に確認されたい）

1. **板に描かれていない2点**（上記）: 「確定」の札を会の名前の横に、「この会を削除」を見出し行の右に置く。
   このままでよいか。
2. **点は会の画面群の中では出さない**でよいか（旧チップと同じ扱い。板G1/G2は点なし）。
3. **SELECTING_SHOPの見出しにも戻り道「‹ ランチ会」を足すか。** 本ADRはFINALIZEDだけに限った
   （板が無いため）。足すなら板が要る。
4. 汎用見出し「会の日程調整」を外すだけでなく、会の名前を`<h1>`とするMustにしたのは、板の構造を機械で
   確かめられる形にするための起草者の判断。意図と違えば指摘されたい。
