---
id: 0057
scope: project/dining-radar
status: 承認済み
date: 2026-09-13
approved_by: "人間裁定（2026-09-13 チャット選択肢UI）: orchestratorが問うた『会に入れた店が残り1件に
  なると、その店のトグルを押しても何も起きません（店は最低1件という以前の決定のため）。利用者
  にはどう見えるようにしますか？』に対し、人間は選択肢『押せない見た目にして理由を出す』
  （選択肢の説明文: 『残り1件の店のトグルは押せない見た目になり、そばに「最低1件は残します」と
  出ます。会から店が0件になることはありません。』）を選んだ。却下された代替案は、最後の1件の
  削除を許可すること（adr/0041決定P2の反転）——P2/minItems: 1はそのまま維持される。"
supersedes: []
superseded_by: null
relates_to:
  [P-06, ADR-0041, ADR-0049, ADR-0055, ADR-0056, TDR-CS-19, TDR-CS-20,
   TDR-CS-21, TDR-CS-22, TDR-GTH-44, TDR-GTH-45]
---

# ADR-0057: 会に入れた店が残り1件のとき、外すトグルを非活性にして理由を示す

> **承認者向けサマリ**: 会モードの候補画面で、会に入れた店の残りがちょうど1件になると、その店の
> カードのトグル（`gatheringMode.cardToggle`）は活性のままなのに、押しても何も起きない
> ——`setShortlistedShops`が`minItems: 1`（P2、2026-09-03、adr/0041）を要求し、空配列を送る
> 結果になる操作をサーバーが拒否するためである。2026-09-13のチャットで人間がこの実機の挙動を
> 見て、「押せない見た目にして理由を出す」ことを選んだ——最後の1件を外せるようにする案
> （P2の反転）は明示的に却下された。
>
> **決定の要点**: (1) `cardToggle.disabledState`を拡張し、`data-gathering-shortlisted="true"`
> のカードは`shortlistedShopCount`が1以下（＝残り1件）のときも非活性にする——これは
> `adr/0049`決定8の「入れた状態のカードは件数によらず常に活性のまま」という文を、残り1件の
> 場合に限って反転する。(2) 新規属性`data-gathering-toggle-disabled-reason`
> （`"limit-reached"`/`"last-shop"`）で2つの非活性理由を機械的に区別する。(3) 新規要素
> `candidate-card-gathering-last-shop-notice`（非操作要素）で、残り1件が理由の非活性のときに
> 限り「最低1件は残します」の意を伝える。(4) P2（`minItems: 1`）そのものは変更しない——
> `gathering-scheduling-api.yaml`の`SetShortlistedShopsRequest`は無変更。付随して、同ファイルの
> `votingStartedAt`の説明文に残っていた「shortlistedShopsが再び空になりうる」という、この裁定と
> 矛盾する古い記述を是正する。(5) `candidate-search.feature`のTDR-CS-20と
> `gathering-scheduling.feature`のTDR-GTH-44——いずれも「会に入れた店の件数を明記しないまま、
> 追加した1件をそのまま外す」という同型の前提の欠落を持っていた——を、外す対象がその1件だけに
> ならないようGivenを改めることで、本ADRの範囲内で是正する。

## 文脈

### 0. 検証の申告（meta/adr/0039）

本ADRが前提とする既存契約の記述は、`candidate-search-browser-interface.yaml`
（contractVersion 1.10.0）の`gatheringMode.cardToggle.disabledState`（現行、adr/0049決定8由来）・
`gatheringMode.band.limitReached`（adr/0056決定7）、`gathering-scheduling-api.yaml`
（現行v0.14.0）の`SetShortlistedShopsRequest.shopIds`（`minItems: 1`）・`Gathering.
shortlistedShops`の説明文・`Gathering.votingStartedAt`の説明文、`gathering-scheduling-
browser-interface.yaml`（contractVersion 0.19.0）の`profiles.localAcceptance.
verifiesScenarios`（TDR-GTH-44を既に含む）を、それぞれ実際に読んで確認した。`product-brief.md`
のトグル・5件・外す操作に関する記述（§2・関連箇所）も検索し、本裁定と矛盾する記述が無いことを
確認した。`candidate-search.feature`のTDR-CS-19〜21、`gathering-scheduling.feature`の
TDR-GTH-44〜45、`test-support-api.yaml`のTDR-CS-17〜21・TDR-GTH-44/45関連の登録箇所も読んだ。
確認していないのは実装コードの挙動そのものである。

### 1. 問題の所在

`gatheringMode.cardToggle.disabledState`（現行）は、5件到達時に**未選択**のカードだけを非活性に
すると定め、「`data-gathering-shortlisted="true"`のカードは件数によらず常に活性のまま」と明記
していた（adr/0049決定8）——理由は「5件目を外して別の店を選び直す動線を塞がない」ためだった。
しかしこの活性状態は、会に入れた店がちょうど1件のときには**見た目と実際の挙動が食い違う**
——`setShortlistedShops`は起草時から`minItems: 1`を要求しており（P2、2026-09-03、adr/0041で
確定）、その1件を外そうとする呼び出しは常に空配列を送ることになり、`INVALID_SHOP_SELECTION`
で拒否される。`toggleCardGatheringShortlist`の`errorOutcome`は「拒否された呼び出しは
cardToggleとbandを活性化前の値のまま変えない」と定めているため、利用者から見ると「押しても
何も起きないボタン」になる。人間が2026-09-13にこの実機の挙動を見て、対処を選んだ。

### 2. 既存シナリオの点検——candidate-search.feature・gathering-scheduling.feature双方に同型の欠落

`candidate-search.feature`のTDR-CS-20（新規、2026-09-13、ADR-0056決定4）は、`Given`節が
会に入れた店の件数を明記しないまま「候補の店を1つ、会に入れる」→「その店をもう一度、会から
外す操作をする」という流れを検査していた——もし会に入れた店がその1件だけだった場合、外す
操作はP2の`minItems: 1`により拒否されるため、シナリオが検査しようとしている「ピンから会員
状態の表示が消える」という結果は本来起こり得ない。

同じ点検を`gathering-scheduling.feature`のTDR-GTH-44（2026-09-08、ADR-0049決定1）にも広げた
ところ、同型の欠落が見つかった——「幹事が開催日を決めた『店を選び中』の会を持っている」
（会に入れた店の件数を明記しない）→「その日に開いている店の1つを会に入れる」→「その店を
もう一度、会から外す操作をする」という流れであり、TDR-GTH-44自身はTDR-CS-20より先
（2026-09-08）に書かれたシナリオである。TDR-GTH-44がGivenで会に入れた店の件数を書いていない
以上、この矛盾はP2確定（2026-09-03、adr/0041）より後に潜在していた可能性があるが、決定1が
`cardToggle.disabledState`を拡張した今、両シナリオはもはや潜在的な矛盾ではなく、**契約その
ものと直接矛盾する**——TDR-GTH-44はブラウザ契約を経由しない`setShortlistedShops`への直接呼び
出しとして書かれてはいるが、その呼び出し自体がP2の`minItems: 1`により拒否される点は
TDR-CS-20と全く同型である。本ADRはこの矛盾を、両シナリオとも外す操作の前提を「すでに他に
1件を会に入れている」（外した後も1件残る）へ改めることで、本ADRの範囲内で解消する——
下記帰結・`.spec`参照。

## 決定

### 決定1. `cardToggle.disabledState`を拡張し、残り1件のカードも非活性にする——adr/0049決定8の一部反転

**元の決定とその理由**（adr/0049決定8）: `data-gathering-shortlisted="true"`のカードのボタンは、
5件到達後も外す操作として引き続き活性のままにする——理由は「5件目を外して別の店を選び直す動線を
塞がないため」だった。この理由は5件到達時の話であり、残り1件の場合を想定していなかった。

**反転する理由**: 残り1件のとき、この活性状態は「押せるのに何も起きない」という利用者から見た
不具合を生む。2026-09-13、人間が実機を見てこれを問題として認識し、「押せない見た目にして理由を
出す」ことを選んだ。本ADRは`data-gathering-shortlisted="true"`のカードについて、
`shortlistedShopCount`が1以下（＝このカードが最後の1件）のときに限り非活性へ改める——
adr/0049決定8の文は「`shortlistedShopCount`が2以上のときは件数によらず常に活性のまま」という
形に縮小される。5件到達時の未選択カードの非活性（adr/0049決定8の残りの部分）は無変更。

### 決定2. 2つの非活性理由を機械的に区別する属性を新設する

新規属性`data-gathering-toggle-disabled-reason`（`cardToggle`本体が持つ、値は`"limit-reached"`
または`"last-shop"`、非活性のときのみ存在）を追加する。決定1により`cardToggle`の非活性理由が
2つに増えたため、`shortlistedShopCount`とこのカード自身の`data-gathering-shortlisted`を
毎回再計算しなくても、acceptance（および将来同じ観測面を読む実装コード）がどちらの理由かを
直接読めるようにする。

### 決定3. 残り1件の理由を示す、カード単位の非操作要素を新設する

新規要素`candidate-card-gathering-last-shop-notice`（`formControl: false`、非操作要素）を
`candidate-card`ごとに追加する。`data-gathering-toggle-disabled-reason`が`"last-shop"`の
カードにだけ存在し、それ以外（非活性でない、または理由が`"limit-reached"`）では不在とする。
可視文言は「最低1件は残します」の意を伝えれば足り、正確な文言は実装の裁量とする（人間裁定の
選択肢説明文の言葉遣いをそのまま契約のMustにはしない——このパターンは`band`の日付表示・
`walkingTimeEstimateWording`など、この契約が既に持つ「内容だけを固定し文言は固定しない」
Mustの流儀と同じ）。5件到達の理由は既に帯（`gatheringMode.band.limitReached`、adr/0056決定7）
が持っているため、この新設要素は**残り1件の理由に限る**——2つの理由に同じ場所を割り当てない。

この要素は活性化可能なコントロールではない——`formControl: false`と明記し、
`unavailableControls.allCandidateScreenFormControlsMustDeclarePurpose`のスキャン対象から外す
（`candidate-gathering-mode-band`のナビゲーション要素・`candidate-gathering-entry`が既に持つ
「非操作要素は`allowedPurposes`を要さない」という前例と同じ扱い）。また、この文言は利用者本人の
ためだけのものであり、レビュアー向けの承認材料の説明文ではない——本番画面に承認プロセスの
説明文を置かないという標準方針（`no-approval-prose-in-shipped-ui`、`ADR-0055`決定3と同じ原則）
に触れない。

### 決定4. P2（`minItems: 1`）は変更しない——最後の1件を外せるようにする案を却下する

人間裁定で明示的に却下された代替案（下記参照）のとおり、`SetShortlistedShopsRequest.shopIds`の
`minItems: 1`（P2、2026-09-03、adr/0041）はそのまま維持する。`gathering-scheduling-api.yaml`は
本ADRにより変更しない——変わるのはブラウザ契約の観測面（見た目と理由）だけである。

### 決定5. `gathering-scheduling-api.yaml`の`votingStartedAt`説明文にある、この裁定と矛盾する
古い記述を是正する

`Gathering.votingStartedAt`の説明文は「店を外すだけで再び追加しなければ`shortlistedShops`が
再び空になりうる。これをこの契約は特に妨げない」という趣旨の一文を持っていた——これは同じ
スキーマの数行下、`shortlistedShops`自身の説明文が既に訂正済みの誤り（「実際には
`minItems: 1`によりこの配列が再び空になることは無い」）と同じ矛盾を、`votingStartedAt`側にも
残したままにしていたものである。本ADRの裁定（「会から店が0件になることはありません」）は
この誤った記述をそのまま残せる余地を無くすため、`votingStartedAt`の説明文も同じ訂正を反映する
よう是正する——`SetShortlistedShopsRequest`・`shortlistedShops`自体のスキーマ・制約は変更しない
（文言の是正のみ）。この改訂は`gathering-scheduling-api.yaml`自身の追補10・11が既に確立した
前例（人間のチャット裁定を経ない、architectの技術判断によるstale記述の是正）と同じ手続きで行う。

### 決定6. `gathering-scheduling.feature`のTDR-GTH-44も、TDR-CS-20と同じ理由・同じ形で是正する

文脈2節が示したとおり、TDR-GTH-44は`candidate-search.feature`のTDR-CS-20と同型の前提の欠落
（会に入れた店の件数を明記しないまま、追加した1件をそのまま外す）を持つ。決定1が
`cardToggle.disabledState`を拡張したことで、この欠落は潜在的な矛盾から契約そのものとの
直接の矛盾になった——本ADRの範囲に含め、TDR-CS-20と同じ修正（Givenへ「すでに別の1件を会に
入れている」を加える）を適用する。シナリオIDは変えない——`gathering-scheduling-browser-
interface.yaml`の`profiles.localAcceptance.verifiesScenarios`、`test-support-api.yaml`の
各`x-acceptance-scenarios`はいずれもTDR-GTH-44を既に登録済みであり、シナリオ本文だけを
書き換えるこの改訂はこれらの登録に影響しない——版数変更も不要である。

## 検討した代替案

- **最後の1件を外せるようにする（P2を反転し、`minItems: 0`にする）**: 却下。人間が2026-09-13の
  チャット選択肢UIで明示的に却下した——選ばれたのは「押せない見た目にして理由を出す」であり、
  「会から店が0件になることはありません」という文言自体が、この代替案を採らないことを明言して
  いる。会が店0件のまま投票が続く状態を生まないという既存の業務保証（P2）を保つ。
- **ボタンを消す（要素ごと非表示にする）**: 却下。この契約が一貫して採る「境界条件では非活性に
  する、要素を消さない」という流儀（adr/0049決定8自身、`deckNavigation.disabledState`、
  `gathering-schedule-response-select`等、多数の前例）から外れる理由が無い——今回もこの流儀を
  維持する。
- **理由を帯（`gatheringMode.band`）側だけに表示し、カード単位の新設要素を置かない**: 却下。
  5件到達の理由（`band.limitReached`）は「あと何件入れられるか」という会全体の状態であり帯に
  適するが、残り1件の理由は「このカード（この店）は外せない」という特定のカードに固有の状態
  である。帯だけに表示すると、複数のカードのうちどれが理由を持つ対象なのかを利用者が読み取れない
  ——理由は該当するカード自身に添える。
- **`data-gathering-toggle-disabled-reason`を新設せず、`shortlistedShopCount`とこのカードの
  `data-gathering-shortlisted`から理由を毎回再計算させる**: 却下。この契約は`band.limitReached`
  でも同種の再計算を避けて専用の属性を新設した前例（adr/0056決定7、「帯の側からも機械観測可能に
  する」）を持つ——同じ理由で今回も専用の属性を新設する。
- **`gathering-scheduling-api.yaml`の`votingStartedAt`の記述是正を見送る（本ADRの範囲外とする）**:
  検討したが採らなかった。この記述はブラウザ契約の変更とは独立に、本ADRが確定させる業務不変条件
  （店0件にはならない）と直接矛盾する記述であり、放置すると次にこのファイルを読む者へ誤った
  前提を残す。API自体のスキーマ・制約は変えていないため、指示文が定める「(likely none)」の
  想定範囲をわずかに超えるが、文言修正のみであり公開契約の意味は変えない。
- **TDR-GTH-44の是正を次工程へ申し送る（当初案）**: 却下。決定1が`cardToggle.disabledState`を
  拡張した以上、TDR-GTH-44は本ADRのまさにこの決定によって契約そのものと直接矛盾するように
  なる——TDR-CS-20だけを直し、同型の矛盾を持つTDR-GTH-44を放置するのは一貫性を欠く。両者とも
  本ADRの範囲内で是正する。

## 帰結

- `contracts/candidate-search-browser-interface.yaml`（改訂、現行1.10.0 → 1.11.0）:
  `gatheringMode.cardToggle.disabledState`を拡張（決定1）。`cardToggle.disabledReason`
  （決定2）・`cardToggle.lastShopNotice`（決定3）を新設。`gatheringMode.requiredTestIds`へ
  `cardToggleLastShopNotice`を追加。`profiles.localAcceptance.verifiesScenarios`へ
  `TDR-CS-22`を追加。具体的な差分は`contracts/.spec/last-shop-candidate-search-
  browser-interface.txt`のFIND/REPLACE指定のとおり——architect自身はcontracts/配下のYAMLへの
  直接編集を行わない。
- `contracts/candidate-search.feature`: 新規シナリオTDR-CS-22（残り1件のときトグルは押せない
  見た目になり理由が示され、2件目を入れると両方のトグルが押せる見た目に戻り理由が消える）を
  追加する。TDR-CS-20（決定1が扱う境界条件の前提を欠いていた、上記文脈2節）を、外す操作の前提を
  「すでに他に1件を会に入れている」へ改めて修正する。具体的な差分は`contracts/.spec/last-shop-
  candidate-search.feature.txt`のとおり。
- `contracts/gathering-scheduling.feature`: TDR-GTH-44（決定6、上記文脈2節）を、TDR-CS-20と
  同じ形で是正する——Givenへ「すでに別の1件を会に入れている」を加え、外す対象がその1件だけに
  ならないようにする。シナリオID・版数（`gathering-scheduling-browser-interface.yaml`の
  `verifiesScenarios`、`test-support-api.yaml`の`x-acceptance-scenarios`のいずれもTDR-GTH-44を
  既に登録済み）は変更しない。具体的な差分は`contracts/.spec/last-shop-gathering-
  scheduling.feature.txt`のとおり。
- `contracts/gathering-scheduling-browser-interface.yaml`・`contracts/test-support-api.yaml`:
  決定6はTDR-GTH-44のシナリオ本文だけを書き換え、シナリオIDを増減させないため、いずれのファイル
  も`.spec`差分は不要と判断した（`verifiesScenarios`・`x-acceptance-scenarios`は既にTDR-GTH-44を
  含んでおり、登録済みのIDが指す本文が変わるだけである）。
- `contracts/gathering-scheduling-api.yaml`（改訂、現行0.14.0 → 0.15.0）:
  `SetShortlistedShopsRequest`・`Gathering.shortlistedShops`のスキーマ・制約は無変更。
  `Gathering.votingStartedAt`の説明文のみを決定5のとおり是正する。具体的な差分は
  `contracts/.spec/last-shop-gathering-scheduling-api.txt`のとおり。
- `product-brief.md`: 本裁定と矛盾する記述は見当たらなかった（見出し数不変、差分なし）。
- `contracts/test-support-api.yaml`（改訂、現行1.5.9 → 1.5.10）: TDR-CS-19が既に使っている、
  確定日程を持つ「店を選び中」の会を作る経路（`GATHERING_OPEN_SHOP_WEEKDAY_MATCH`＋実際の
  `setShortlistedShops`呼び出し）で「会に入れた店がちょうど1件」の状態も組み立てられる——
  新規seamは不要。ただし`setCandidateProposalAcceptanceState`・
  `resetCandidateProposalAcceptanceState`・`resetGatheringSchedulingAcceptanceState`の
  各`x-acceptance-scenarios`一覧と`info.description`のシナリオ範囲表記へ`TDR-CS-22`を登録する
  差分は要る——TDR-CS-20・21が新設時に同じ一覧へ登録されたのと同じ扱い。具体的な差分は
  `contracts/.spec/last-shop-test-support-api.txt`のとおり。TDR-GTH-44の是正（決定6）はこの
  ファイルへの追加登録を要しない（既に登録済み、上記参照）。

## 未決事項（次工程・人間への申し送り）

1. `.spec`ファイルの適用（実際のYAML/feature編集）は次工程で行う——architect自身は適用しない。
