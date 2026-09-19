---
id: 0064
scope: project/dining-radar
status: 承認済み
date: 2026-09-19
approved_by: "人間裁定（2026-09-19、designerの板 E:/AWS/dsg-out/party2/e1/E1-a-*・E2-a-*
  〈描画済み画像はスクラッチパッドscratchpad/e1/E1-a-SpCandidates.png等〉を見て決定、
  orchestrator経由でarchitectへ伝達）。決定は2点。(1)「もう一度探す」を「別の候補を出す」に
  変える——人間の言葉「『もう一度探す』というラベルが動作を説明していない」。動作（いまの条件の
  まま、まだ見せていない店を優先して引き直す）と置き場所（条件の行・帯の右端）は変えない。文言を
  「別の候補を出す」に変え、スマホも丸いアイコンだけの形をやめて文字を付ける。断った案: 一覧の
  末尾に置く（最後まで送らないと気づけない、送れる面がカード以外を含むことになる）、件数の横に
  置く（スマホで地図の上に浮きスワイプ面に近い）。「まだ見せていない店を優先」は画面に書かない
  （ADR-0024決定4のまま）。(2) 定休日を詳細の枠の中へ——人間の言葉「定休日の記載が見にくい」。
  カード末尾の「定休日」の行をやめ、席数・禁煙・夜予算の枠の中（空いていたます目）に同じ読み方の
  1項目として並べる。値は提供元の文そのまま、無いときは「情報なし」（いまと同じ）。断った案:
  店名の近くの札（スマホで行が混む）、今日との関係を札で出す（product-brief §3の「普段の候補
  画面では曜日で判定しない」を改める必要があり、札が無いことを「今日は営業」と誤読されるおそれ）。
  この裁定はUI形状と業務規則のみを定めたものであり、契約上の具体化（どの既存の値で足りるか・
  新しいtestId/purposeが要るか・presenceRuleの書き方・.featureシナリオの要否）はarchitectの
  裁量に委ねられた——本ADRの決定1・2がその具体化にあたる。束Eの3件目（徒歩◯分の見直し）は
  実測待ちのため本ADRの対象外である。"
supersedes: []
superseded_by: null
relates_to:
  [P-01, P-04, P-06, P-08, P-11, ADR-0023, ADR-0024, ADR-0025, ADR-0038,
   ADR-0059, TDR-CS-02, TDR-CS-11, TDR-CS-14]
---

# ADR-0064: 「もう一度探す」を「別の候補を出す」に改称し、定休日をカード詳細の枠へ移す

> **承認者向けサマリ**: 実機フィードバック第1便の積み残し「束E（店を絞る画面）」3件のうち、実測
> 待ちの徒歩◯分を除く2件を、designerの板（`party2/e1`）を見て人間が2026-09-19に裁定した
> （approved_by参照）。**(1)** 候補提案の再検索ボタンの可視ラベルを「もう一度探す」から「別の候補を
> 出す」へ変え、モバイルでも丸いアイコンだけの形をやめて文字を持たせる——動作・置き場所は変えない。
> **(2)** カード末尾で詳細リンクと横並びだった「定休日」の行を、総席数・禁煙対応・予算感と同じ枠
> （既に空いていたます目）の中へ、同じ読み方の1項目として移す——値・無いときの表記はいずれも無変更。
>
> 契約への反映は3ファイル: `candidate-search-browser-interface.yaml`（`contractVersion` 1.12.0 ->
> 1.13.0、新規`searchAgainControl`・新規`cardDataAttributes.detailGroup`）、
> `candidate-search.feature`（TDR-CS-11・TDR-CS-14が引用する可視ラベル名の更新のみ、業務規則は
> 無変更）、`product-brief.md`（同じ可視ラベル名を引用する4箇所の文言更新）。いずれも具体的な
> YAML/Markdown編集は本ADRと同じ提出物（`projects/dining-radar/.spec/bundle-e.spec`のdiff指定）を
> 参照する——architect自身は`contracts/`・`product-brief.md`へ直接書き込まない。

## 文脈

### 0. 検証の申告（meta/adr/0039）

本ADRが依拠する事実は出所が異なる。**(a) 現行契約・実装の構造**は、私自身が
`contracts/candidate-search-browser-interface.yaml`（contractVersion 1.12.0）・
`contracts/candidate-search.feature`・`product-brief.md`・`adr/0023`・`adr/0024`・`adr/0025`・
`adr/0038`・`adr/0059`を実際に読んで確認した——`candidate-search-again`の可視文言を固定する契約
記述が現行には一つも無いこと（`browserActions.searchAgain`・`browserControlSurface.proposal.
requiredTestIds.searchAgain`のいずれもtestIdと振る舞いだけを定め、visible labelのMustを持たない）、
`candidate-card-regular-holiday`が`cardDataAttributes.requiredFields`の他の3項目
（totalSeats・nonSmokingStatus・dinnerBudgetTier）と同じ形（`labelObservation`・
`valueStateAttribute`）で観測されているがDOM上の配置（グルーピング）を機械観測する仕組みを
一つも持たないこと、`filterPanel.controlGrouping`（`adr/0024`決定2）と
`gatheringEntry.entry.requirement`（`adr/0059`）が、それぞれ「DOM上の共有コンテナ」「可視ラベルの
非空」という同種の性質を機械観測可能にした先例であることを、私自身が実際の記述として確認した。

**(b) designerの板とその判断**（`party2/e1/E1-a-*`・`E2-a-*`、断った案とその理由）は、
orchestratorがタスク依頼文で供給したものであり、私自身は画像を見る手段を持たない。

**(c) 人間の判断そのもの**（2点の裁定、断った案の理由、束Eの3件目を対象外とする明記）も、
orchestratorがタスク依頼文で供給した原文である。approved_bysummaryはこの原文をそのまま転記した。

### 1. 何が起きたか

`activeContext.md`の「実機フィードバック第1便（2026-09-12から未着手）」節が積み残していた束E
（店を絞る画面）3件のうち、1・2はdesignerが板を描き、人間が2026-09-19にチャット選択肢UIで裁定
した。3件目（徒歩◯分の実態乖離）は、人間の実測値（アプリの表示値と地図の値の対）が1〜2件届いて
から着手する方針のまま未着手であり、本ADRは踏み込まない。

## 決定

### 決定1. 「もう一度探す」を「別の候補を出す」に改称し、モバイルでも可視ラベルを必須にする

`browserControlSurface.proposal`へ新規`searchAgainControl`（testId `candidate-search-again`、
既存purpose `candidate-search-again`を再利用——`unavailableControls.allowedPurposes`は無変更）を
新設し、この要素の可視ラベルテキストが、この契約が名指すどの`renderModes`（`twoColumnLayout`・
`mapPrimaryTouchLayout`）の下でも非空であることをMustにする——モバイル幅で文字を消してアイコンだけ
にする実装は、この契約の下でもう許されない。**ラベルの具体的な文言（「別の候補を出す」）・
フォントサイズ・アイコンの有無自体は、この契約が固定しない実装選択のまま残す**
（`walkingTimeEstimateWording`・`gatheringEntry.entry`の可視ラベルMustと同じ様式）。動作
（`browserActions.searchAgain`が定める、適用中の絞り込み条件のまま`shownPoolPriority`に従って
未表示を優先し引き直す）と配置（条件の行の帯の右端）はいずれも人間裁定により変更対象外であり、
この契約もその2点を固定する記述を元々持っていない——変更を要しない。

「まだ見せていない店を優先している」ことを画面の文言で明かさないという既存の判断
（`adr/0024`決定4項目7、可視の開示を追加しない）は本決定でも維持する——`searchAgainControl`の
Mustは「ラベルが非空であること」だけを求め、ラベルの中身にこの内部機構への言及を求めない。

### 決定2. 定休日をカード詳細の共有コンテナへ移す

`cardDataAttributes`へ新規`detailGroup`を新設し、`requiredFields`のうち
`regularHoliday`（`candidate-card-regular-holiday`）・`totalSeats`
（`candidate-card-total-seats`）・`nonSmokingStatus`（`candidate-card-non-smoking`）・
`dinnerBudgetTier`（`candidate-card-dinner-budget`）の4項目が、カード内の他のどの
`requiredFields`項目（name・genre・description・walkingTimeMinutes・providerPageLink）の
コンテナとも異なる、1つの共有DOMコンテナ内に置かれることをMustにする——`filterPanel.
controlGrouping`（`adr/0024`決定2）が確立した「グルーピングをDOM上の共有コンテナとして機械観測
可能にする」という様式を、フィルタパネルのコントロール間からカードのフィールド間へはじめて
広げたものである。**各項目自身の`labelObservation`・`valueStateAttribute`・（宣言されている
場合の）`rawValueAttribute`規則はいずれも無変更**——本決定が追加するのは共有コンテナという配置の
性質だけであり、値・ラベル・生値の規則を書き換えない。`regularHoliday`自身の可視値（providerの
`regularHoliday`自由文をそのまま示すか、既存の`data-value-state=unavailable`時の実装非拘束の
「情報なし」相当の表記）も無変更のまま——人間の言葉「値は提供元の文そのまま、無いときは『情報
なし』（いまと同じ）」は、既存の`nullBehavior`が既に定めている規則の確認であり、新しい規則では
ない。

## 検討した代替案

- **決定1で、ラベルの具体的な文言（「別の候補を出す」）を契約でMust化する**: 却下。
  `walkingTimeEstimateWording`・`gatheringEntry.entry`が既に確立した「内容の性質だけをMustにし、
  正確な文言は実装選択に残す」という様式から外れる理由がない——正確な文言をGherkinで固定しない
  のと同じ判断（下記「候補となる契約変更」§3参照）。
- **決定1で、モバイル向けに専用のtestId（例: `candidate-search-again-mobile`）を新設する**:
  却下。既存の`candidate-search-again`は`renderModes`のどちらのモードのtestIds配列にも属さない
  共通要素であり（`searchAgain: candidate-search-again`は`requiredTestIds`直下）、モード別に
  分岐させる理由が無い——`gatheringEntry.mobileBarGathering`のように「同じ行き先の別形」を
  必要とする場合とは異なり、この要素はモード間で行き先・動作を一切変えない。
- **決定1で、一覧の末尾・件数の横への再配置を契約へ書く**: 却下（人間裁定）。人間はいずれも
  断っており、置き場所は現状（条件の行・帯の右端）のまま変えないことが裁定そのものである。
- **決定2で、定休日専用の新しいtestId（例: `candidate-card-regular-holiday-grid`）を新設する**:
  却下。既存の`candidate-card-regular-holiday`はDOM上の位置を変えるだけであり、値・ラベル・
  生値の規則は一切変わらない——同じ要素の配置替えに新しい識別子を与える理由がない
  （`filterPanel.controlGrouping`が`candidate-filter-include-izakaya-bar`を移した際も既存の
  testId・purposeを再利用したのと同じ判断）。
- **決定2で、店名の近くへ定休日の札を出す案・今日との関係を札で出す案を契約化する**: 却下
  （人間裁定）。前者はスマホで行が混むという理由、後者は`product-brief.md` §3「普段の候補画面
  では曜日で判定しない」の改訂を要し、札の不在が「今日は営業」と誤読されるおそれがあるという
  理由で、人間が明示的に断っている。

## 帰結

- `contracts/candidate-search-browser-interface.yaml`（改訂、contractVersion 1.12.0 -> 1.13.0）:
  決定1（新規`browserControlSurface.proposal.searchAgainControl`）、決定2（新規
  `cardDataAttributes.detailGroup`）を反映する。`allowedPurposes`・`browserActions.searchAgain`・
  `requiredFields`の各エントリはいずれも無変更。**具体的なYAML編集は本ADRと同じ提出物
  （`projects/dining-radar/.spec/bundle-e.spec`のdiff指定）を参照。**
- `contracts/candidate-search.feature`: TDR-CS-11（Scenario見出しと`When`手順が引用する
  「もう一度探す」）・TDR-CS-14（`When`手順が引用する同じ語）を「別の候補を出す」へ更新する
  ——この2シナリオが引用してきたのは可視ラベルの名前そのものであり（`adr/0024`帰結が「TDR-CS-11
  の文言は現行のまま両立する」と明示的に確認した先例と同じ理由づけで、今回は逆に語自体が変わる
  ため追随させる）、業務規則本文（同じ絞り込み条件のまま再検索する、既に見せていない候補を優先
  する等）はいずれも無変更。TDR-CS-02のカード列挙（「定休日」を含む）は業務言語で書かれており
  DOM上の配置を語っていないため、決定2に対応する変更を要しない。新規シナリオは追加しない——
  いずれの決定も既存の業務事実の再配置・再命名であり、新しい業務事実を導入しない。**具体的な
  差分は同diff指定を参照。**
- `product-brief.md`: 「もう一度探す」を引用する4箇所（承認者向けサマリ、§「候補を絞る」手順4、
  §8未決事項の既決記録、§8受け入れの目安）を「別の候補を出す」へ更新する。製品方針・境界の記述
  そのものは変えない。**具体的な差分は同diff指定を参照。**
- `contracts/candidate-search-api.yaml`・`contracts/test-support-api.yaml`: 変更しない——
  決定1・2のいずれも、既に公開されている値（`Candidate.regularHoliday`等）とDOM上の見た目だけで
  構築・検証できる変更であり、新しいAPIフィールド・新しいGiven状態を要求しない。
- `ARCHITECTURE.md`・`design.md`: 変更しない——本ADRは1画面内の契約観測面の変更であり、モジュール
  境界を変えない。

## 未決事項（次工程・人間への申し送り）

1. **束Eの3件目（徒歩◯分の実態乖離）は本ADRの対象外のまま残る。** `activeContext.md`が記す
   とおり、アプリの表示値と地図の値の対が1〜2件届いてから着手する。
2. **決定1の実装上の確認**: モバイル幅で「丸いアイコンだけ」の実装を「アイコン＋文字」または
   「文字のみ」へ変える際、44px下限（`adr/0020`決定4(e)）を維持したまま可視ラベルを追加できるか
   の実測は、`activeContext.md`の慣行どおりorchestratorの領分として残す。
