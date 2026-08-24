---
id: 0030
scope: project/dining-radar
status: 承認済み
date: 2026-08-24
approved_by: "本PRのマージをもって承認（meta/adr/0035 方式(i)。meta/adr/0061 の分類では制約——契約にMustを足し実装の自由を縛るため。人間裁定 2026-08-24 chat: 本番を触って『何本かある輪がどの範囲かわかりません』と指摘し、0件画面の導線は押せるボタンにすると決めた。承認しない場合はマージしないこと）"
supersedes: []
superseded_by: null
relates_to: [P-01, P-02, P-03, P-04, P-05, TDR-CS-02, TDR-CS-05, ADR-0020, ADR-0025]
---

# ADR-0030: 徒歩圏リングに読める分数ラベルを必須にし、0件案内を押せる操作にする

> **承認者向けサマリ**: designerが本番実測から報告した契約の穴——
> `contracts/candidate-search-browser-interface.yaml`の`walkingRadiusRings`は「輪の本数・半径は実装の
> 選択」としか定めておらず、輪が何分圏を表すかを画面上で示す要素そのものが契約に無かった。本番は輪4本を
> 1pxの破線・色`#8da093`で描き、分数は`data-walking-radius-minutes`属性の中だけにあって画面には出て
> いなかった——契約が「分数が読めること」を一度も要求していなかったため、実装がラベルを出さなくても
> 受け入れ検査は通り、誰も気づかなかった。人間の指摘は「何本かある輪がどの範囲かわかりません」。
> 本ADRは2点を決める。**(1)** 各リングは、既存の`data-walking-radius-minutes`属性の値と一致する分数を、
> 画面上で読める形（可視テキストまたはアクセシブルラベル）で示すことをMustにする。文言・単位表記・
> 配置は実装の選択のまま残す。輪の本数・半径は`ADR-0025`決定9のとおり無制約のまま変えない。**(2)** 0件
> のときの案内（`TDR-CS-05`「絞り込み条件を変更するよう案内される」）を、押すと絞り込みパネルが開く
> 操作にする（人間裁定2026-08-24）。designerが挙げた残り2件——輪と徒歩の上限の連動、地図リボンの高さ・
> 役割——は本ADRでは決めない。理由は決定3・4に分けて書く。
>
> 払うもの: リングの見た目（本数・半径・色・線種）は今回も凍結しない。契約が縛るのは「分数が読める
> こと」だけであり、それをどう描くかは実装に残る。

## 文脈

### 1. 何が起きたか

designerが`design/wireframes/Legend.dc.html`で`walkingRadiusRings`の`presenceRule`を読み、「本数と
半径は実装の選択」としか書かれておらず、**ラベルという要素そのものが契約に存在しない**ことを報告した。
本番を実測すると、輪は4本（10/15/20/30分）、線は1px破線・色`#8da093`で、分数は
`data-walking-radius-minutes`属性の中だけにあり、画面には出ていなかった。人間の指摘は「何本かある輪が
どの範囲かわかりません」。

`walkingRadiusRings`の`presenceRule`（`adr/0025`決定1が承認した表示物の契約への翻訳）は「各リングは
基点を中心とし徒歩時間帯を表す」と述べるだけで、その帯が**読める形で示されること**を一度も要求して
いなかった。分数を出さない実装でもacceptanceは通る——本番でいま起きているのがまさにそれである。

### 2. なぜ今まで機械が気づかなかったか

`meta/adr/0059`決定4・`adr/0027`が示す線引きは、**検証手段を持てるものだけを契約に載せる**という
ものである。ここではその逆が起きていた——検証手段（`data-walking-radius-minutes`という機械可読な
属性）は実装側が既に自発的に持っていたが、契約はそれを要求しておらず、かつ「画面上で読めること」と
いう別の性質を一切要求していなかった。属性はあってもラベルは無い実装が緑のまま出荷された理由はここに
ある。

### 3. designerが挙げた残り3点

designerは本番実測とは別に、契約に無く機械で守られていないものを3つ挙げた。

- 輪と「徒歩の上限」の連動（選択中の上限の輪を強調し「15分まで」と出す）
- 地図のリボンの高さ・役割（リストの上に常時出る88pxの小さい地図。人間が実物を見てからリボン有り
  無しを比較する予定であり、本ADRが前提とする契約はリボン有りの構成を前提に書く——比較の結果が
  変われば改訂が要る）
- 44pxのタップ標的

決定3・4・5でそれぞれ扱いを決める。

## 決定

### 決定1. 徒歩圏リングに読める分数ラベルを必須にする

`mapObservations.walkingRadiusRings`に`bandAttribute`（`data-walking-radius-minutes`——本番が既に
使っている属性名をそのまま契約化する）と`bandLabel`を新設する。各リングは、`bandAttribute`の値と
一致する分数を、可視テキストまたはアクセシブルラベルとして持たなければならない（Must）。文言・単位
表記（分／分圏／min）・配置は実装の選択のまま残す——`walkingTimeEstimateWording`が徒歩のめやす時間の
文言を縛らないのと同じ様式。属性値だけを機械可読にして画面に出さない実装は、この要求を満たさない。

輪の本数・半径には触れない。`ADR-0025`決定9が「制約を置かない」と決めており、人間は「補正後の見た目を
見てから決める」としている（2026-08-24裁定）ので、本ADRはその決定を変えない。

### 決定2. 0件案内を押せる操作にする

`browserControlSurface.empty`に`reviseFiltersControl`を新設する。`candidate-no-results`は、押すと
`openFilterPanel`と同じ結果（絞り込みパネルを開く）を起こす要素を1つ持たなければならない（Must、
人間裁定2026-08-24）。`TDR-CS-05`の「絞り込み条件を変更するよう案内される」は従来、文章で案内する
だけの実装でも満たせていた——designerが`design/wireframes/EmptyError.dc.html`で「押せるものにするか」を
未決として残していた論点そのものである。

既存の`candidate-filter-open`（画面上部のツールバーの絞り込みボタン）はこの状態でも引き続き到達可能
であり（`empty.absent`のメンバーではない）、新設のtest idはそれとは別に、案内文自身に専用の操作面を
持たせるためのものである。

### 決定3. 輪と徒歩の上限の連動は、今回は契約に載せない

**不採用ではなく保留。** 理由は3つ。

1. 人間が実際に困ったと報告したのは「輪が何を表すか読めない」ことであり、連動（強調表示・「15分まで」
   の文言）はdesignerが挙げた着想であって、人間からの指摘ではない（`meta/PRINCIPLES.md` P-05:
   ドキュメントは摩擦が発生した時だけ足す）。決定1がその摩擦を塞げば、連動が無くても「どの輪が何分か」
   は読める
2. 連動を機械観測可能にするには、フィルタの選択状態を表す属性が要る。ところがこの契約には、ジャンル・
   予算感チップの「選択中」状態を機械観測する属性が現状どこにも定義されていない
   （`filterPanel.constraints`は「carries selected state」と散文で述べるのみで、`data-selected`の
   ような属性名を持たない）。連動を契約化すると、この既存の穴まで一緒に塞ぐ設計が要り、本ADRの範囲を
   大きく超える
3. 載せすぎれば実装の自由が減り、改訂のたびに費用が乗る。輪の本数・半径すら「補正後の見た目を見てから
   決める」と保留している段階で、その上に載る強調表示の仕様を固めるのは早い

人間が実物を見たあとも「どの輪が上限か分からない」という同種の指摘を出したら、そのときに`filterPanel`
の選択状態の機械観測を含めて設計する。

### 決定4. 地図リボンの高さ・役割は契約に載せない

**理由はP-03（実行可能 > 機械検証可能 > 人間可読）とこのプロジェクト自身の先例による。** 88pxという
数値は描画後の幾何であり、`ADR-0020`が「レンダー後の幾何・操作面は`browserControlSurface`ではなく
L5のレンダー不変条件が扱う」と既に線を引いている。`ADR-0020`決定4はL5の不変条件を4つ（狭幅での地図
到達可能性・キーボード到達性・操作面44px・内部enum非露出）に絞っており、リボンの高さはそのいずれにも
当たらない——新しい不変条件を足すかどうかは`ADR-0020`の改訂であり、本ADRの範囲ではない。

加えて、**リボン有り無しは人間が比較のうえで選ぶ予定であり、まだ選ばれていない**（2026-08-24「実物を
見てから決めたい」）。P-02（契約はスライス単位で先に確定する。全体を先に設計しない）に照らすと、選ば
れていない構成の寸法を先に契約へ固定するのは順序が逆になる。

**ただし本ADRは、この契約がリボン有りの構成を前提に書かれていることを明記する。**
`authenticatedInitialOutcome.present`は初期表示に`candidate-map`の存在を引き続き要求しており
（無変更）、これはリボンが本物の地図であるために初期表示から`candidate-map`が実在する場合にのみ
無条件に満たされる。リボン無しの案が選ばれた場合、初期表示に地図が無くなり、この条文に触れる——
`design/wireframes/Legend.dc.html`のD2として既に記録されている論点であり、本ADRはそれを解決しない。
比較の結果が変われば、`authenticatedInitialOutcome`の改訂が別途要る。

### 決定5. 44pxのタップ標的は、新設の要素を正しく登録すれば既存のゲートがそのまま覆う

新しい契約は追加しない。決定2で新設する`candidate-no-results-revise-filters`を
`unavailableControls.allowedPurposes`に`candidate-no-results-open-filter`として登録すれば、
`allCandidateScreenFormControlsMustDeclarePurpose`（既存Must）によりこの要素は
`data-candidate-control-purpose`を持つことになり、`ADR-0020`決定4(e)の44px不変条件が自動的にこの
要素も測る——同決定は「control surfaceのすべての活性化可能要素」を対象にすでに書かれており、対象を
広げる新しい文言は要らない。決定1のリングは活性化しても状態を変えない表示専用要素
（`unavailableControls.locationRangeControlProhibition.displayOnlyOriginException`の対象）であり、
操作面ではないため44pxの対象にならない——これは`adr/0025`が既に確立した区別（要素の種類ではなく
振る舞いで線を引く）のままである。

## 検討した代替案

- **輪の連動・リボンの寸法・44pxも含めて一括で契約化する**: 不採用（決定3・4・5参照）。載せすぎは
  改訂のたびに費用が乗り、選ばれていない構成を先に固定することになる
- **ラベルの文言・単位表記まで契約で固定する（例:「N分」に統一）**: 不採用。`walkingTimeEstimateWording`
  や`budgetTierNoteObservation`が既に確立した様式（内容だけをMustにし、文言は実装に残す）から外れる
  理由が無い
- **リングの`bandAttribute`を新設せず、可視テキストの検証だけを求める**: 不採用。可視テキストだけを
  Mustにすると、acceptanceは「非空である」ことしか機械的に確認できず、表示された数字が実際にその
  リングの半径と対応しているかを証明できない。`bandAttribute`（既に実装済み）を機械的な正解値として
  残し、可視ラベルの先頭桁がそれと一致することを求める形にすることで、`cardDataAttributes`の
  `rawValueAttribute`と同じ「生の値は機械正確、可視文言は実装の選択」という既存の様式を再利用できる

## 帰結

- `contracts/candidate-search-browser-interface.yaml`を`1.4.0`へ改訂する（本PRに同梱）。
  `mapObservations.walkingRadiusRings.bandAttribute`/`bandLabel`、`browserControlSurface.empty.
  reviseFiltersControl`、`unavailableControls.allowedPurposes`への`candidate-no-results-open-filter`
  追加、`browserActions.openFilterPanel.input`への第2入力の追加
- `contracts/candidate-search.feature`の`TDR-CS-02`・`TDR-CS-05`に、業務の言葉で1行ずつThenを足す
  （技術用語・test id・属性名は書かない）
- 実装は`candidate.js`で(a)各リング要素に可視ラベル（または`aria-label`）を追加し、
  `data-walking-radius-minutes`と桁が一致するようにする、(b) `candidate-no-results`のセクション内に
  `candidate-filter-open`と同じ挙動を起こすボタンを追加し
  `data-candidate-control-purpose="candidate-no-results-open-filter"`を設定することが要る。いずれも
  Django/pipelineのPythonコードには触れない見込み
- testerは`TDR-CS-02`・`TDR-CS-05`のstep定義を、本ADRの新しい観測（`bandAttribute`/`bandLabel`の
  数値一致、`reviseFiltersControl`の活性化と`openFilterPanel`要求結果の一致）に合わせて拡張する必要が
  ある
- `design/wireframes/Legend.dc.html`のB1（同心リングの本数と半径）は実線へ移らない——決まったのは
  ラベルの有無であって本数・半径ではない。D1の「絞り込みを見直すを押せるものにするか」は本ADRの決定2で
  決着する
- designerが挙げた輪と徒歩の上限の連動、地図リボンの高さ・役割は宿題として残る。前者は`filterPanel`の
  選択状態の機械観測が無いという既存の穴と絡むため、後者はリボン有り無しの人間比較が決着してから、
  それぞれ別ADRで扱う
