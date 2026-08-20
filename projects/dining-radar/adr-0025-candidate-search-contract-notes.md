# ADR-0025 契約改訂 作業メモ（architect、2026-08-20）

> 対象: `contracts/candidate-search.feature`・`contracts/candidate-search-api.yaml` を
> `adr/0025-disclose-search-origin-and-walking-time-to-the-authenticated-screen.md`（status: 提案中）に
> 合わせて改訂した作業の記録。両ファイルは既に `adr/0024`（status: 提案中）のドラフト差分を上に重ねた
> 状態にあったため、本改訂はその上へさらに層を重ねる形で行った。ADR-0025本文は編集していない。
> product-brief.md も編集していない（§2の絞り込み条件列挙に関する未対応の指摘は下記「人間に確認すべき点」）。
>
> **2026-08-20 追記**: orchestratorが下記6節の指摘1・2を処理済み（`product-brief.md` §2への追加、
> `ADR-0025`決定1・2の「してよい」→「する」表現の是正）。指摘3・4は本メモの続き（7節）でarchitectが
> 対応した。指摘5は「人間が決める」という指示のもと、論点の整理のみを7節に記す。

## 1. シナリオIDの棚卸し（TDR-CS-00〜TDR-CS-14）

判定基準: `grep`で`検索地点|検索基点|経路|現在地|徒歩`を`candidate-search.feature`に当てた結果
（本文中の実測結果）と、ADR-0025の決定1・2・3・6・8を突き合わせた。

| ID | 判定 | 根拠 |
|---|---|---|
| TDR-CS-00 | 無変更 | 未サインインの訪問者は絞り込み・地図を一切見られないという主張のみで、基点・徒歩の記述がない。ADR-0025は認証済み画面だけを対象にするため無関係。 |
| TDR-CS-01 | **改訂** | `And 非公開の検索地点や探索条件の詳細は示されない` が「検索地点は示さない」を含んでいた。ADR-0025決定1で基点マーカーの表示がMayになったため、この行を「地図には検索基点のマーカーが示される」（新規、肯定）と「探索範囲そのものの値は示されない」（従来どおり否定、範囲=半径は非開示のまま）に分割した。 |
| TDR-CS-02 | **改訂** | `And 非公開の検索地点、経路、現在地、徒歩時間は示されない` が今回の変更の中心。基点・徒歩時間は決定1・2により肯定側へ反転、経路・現在地は決定6により否定のまま。カード列挙に「徒歩のめやす時間」を追加し、「推定であり実測経路ではない」という決定2のMustを別行のThenとして明示した。地図側に「検索基点マーカーと徒歩圏の同心リング」を追加。探索範囲そのものの値の非開示は別行として残した。 |
| TDR-CS-03 | **改訂** | Whenの絞り込み条件列挙（ジャンル・居酒屋バー・禁煙・カード払い・予算感）に「徒歩の上限」を追加。決定3「他の絞り込み条件と同じく」を受けた機械的な追加で、Then節の内容は変えていない。 |
| TDR-CS-04 | **改訂** | 「検索地点や探索範囲そのものを入力・指定できない」はADR-0025でも真だが（決定1は表示のMay、入力を開く決定ではない——決定の代替案節が「基点をブラウザから設定できるようにする」を明示的に不採用としている）、基点が地図に見える以上、「表示しない」と「入力・指定できない」を読者が混同しないよう、区別を明示する行を1本追加した。 |
| TDR-CS-05 | 無変更 | 0件結果の案内。基点・徒歩の記述なし。 |
| TDR-CS-06 | 無変更（検討のうえ） | `非公開の検索地点や内部の事情は示されない` が残る。この文は「取得失敗時に画面へ何も描かれない」失敗経路の記述であり、地図自体が表示されない状態を指す。ADR-0025は成功経路（地図が描ける状態）の開示だけを変えるため、失敗経路のこの非開示要求とは独立に有効と判断した。 |
| TDR-CS-07 | 無変更（廃止のまま） | 既に`adr/0023`で廃止済みのプレースホルダコメント。再利用しない（後述の慣行を参照）。 |
| TDR-CS-08 | 無変更（TDR-CS-06と同じ理由） | rate-limit時も失敗経路であり同じ判断。 |
| TDR-CS-09 | 無変更 | 居酒屋・バーの既定除外。基点・徒歩の記述なし。 |
| TDR-CS-10 | **改訂** | Then最終行の「幹事が明示的に指定した他の絞り込み（ジャンル・禁煙・カード払い・予算感）」という列挙に「徒歩の上限」を追加した。決定3が徒歩の上限を他の絞り込みと同格に扱うと明言しており、ADR-0023決定6のフォールバック不緩和原則が新しい条件にも及ぶのは論理的帰結であり、ADR-0025が特に免除していない。 |
| TDR-CS-11 | 無変更 | 「もう一度探す」のランダム性文言。基点・徒歩の記述なし、影響なし。 |
| TDR-CS-12 | 無変更 | カード払い不可の注意表示。無関係。 |
| TDR-CS-13 | **無変更（意図的）** | ソフト絞り込み（禁煙・カード払い・予算感）の一覧に「徒歩の上限」を加えるべきか検討し、**加えない**と判断した。理由: `walkingTimeMinutes`は基点と候補座標という常にサーバー側に存在する2点から算出するため、providerの取得漏れに起因する「情報なし」が構造的に存在しない。ADR-0023決定2のソフト絞り込みは「確認できない」という状態がある条件のためのものであり、対象外。新規TDR-CS-15でこの非対称性を明示的に述べた。 |
| TDR-CS-14 | 無変更 | 既表示優先度の記憶。基点・徒歩の記述なし、影響なし。 |
| **TDR-CS-15** | **新規追加** | 徒歩の上限による絞り込み自体を検証する、既存のどのシナリオにも無かった業務要求（決定3）。既存の「1条件=1シナリオ」の粒度（TDR-CS-09=居酒屋バー、TDR-CS-12=カード払い注意、TDR-CS-13=ソフト絞り込み順序）に倣った。 |

**IDの再利用可否について**: 本プロジェクトの既存慣行を確認した。`TDR-CS-07`は`adr/0023`で廃止された後、
コメントのプレースホルダとして残され、**再利用されていない**。新規シナリオ（`TDR-CS-13`・`TDR-CS-14`）は
いずれも当時の最大番号の続き番号で追加されている。この慣行に倣い、新規シナリオは`TDR-CS-15`とし、
`07`のような欠番の再利用は行わなかった。

## 2. `populationAttributes` の設計判断（最も壊れやすい箇所）

### 何が壊れる可能性があったか

`candidate-search-api.yaml`の`populationAttributes`は、行が店舗を同定しないこと・座標や距離を持たない
ことを明示的に禁止する記述を持つ（`adr/0022`）。ADR-0025決定3は「距離帯を加える場合も、行が店舗を
同定しない性質を壊してはならない——距離帯は粗い区分として加え、候補との対応順序を持たせない」と
条件付きで許可しており、この条件を字義通り満たさないと`adr/0022`の核心を壊す。

### 採った設計

1. **`Candidate.walkingTimeMinutes`は正確な整数（分）のまま**にした。ADR-0025の「検討した代替案」節が
   「粗い距離帯（3段階）だけを出す」を明示的に不採用にしており（理由: 昼休みの判断に効くのは正確な
   分数だから）、カード表示用の値をここで粗くすると人間の判断そのものを覆すため、ここは正確値とした。
2. **`PopulationAttribute.walkingTimeBand`は別の、粗い整数**にした。「候補ごとに一意になり得る正確な
   分数」を匿名の行にそのまま載せると、他の識別情報が一切無くても**値そのものによる相関**が成立して
   しまう——たとえば母集団中で徒歩7分の候補が1件しかなければ、`populationAttributes`に`7`という行が
   1件あるだけで、カードに表示されている「徒歩7分」の候補と1対1に対応付けられる。これは順序を使わない
   点で`adr/0022`の「対応順序を持たせない」という条件文だけを読むと見落としやすい、**値の一意性による
   相関**という別経路の再識別リスクである。`walkingTimeBand`は「ブラウザが現在提示している
   `walkingTimeMaxMinutes`のプリセット値のうち、この行がなお該当する最小の値（該当なしはnull）」という
   バケツ化された値にし、複数の候補が同じ値を共有する前提を保つ設計にした。
3. **`walkingTimeMaxMinutes`（フィルタ）と`walkingTimeBand`（母集団属性）は同じプリセット集合を
   共有する前提**にした。これにより、ブラウザは他の絞り込み（例: `dinnerBudgetTier`と`budgetTiers`の
   対応）とまったく同じやり方でローカルに件数予告ができる。この対応関係はスキーマでは強制できず、
   実装責任として明記した（両フィールドのdescriptionに記載）。
4. **プリセットの具体的な分数・段階数はこの契約で決めていない**。`genres`が`availableGenres`との
   組み合わせで閉じた選択をUI側だけで実現している既存パターンに倣い、`walkingTimeMaxMinutes`の
   スキーマ自体はどんな正の整数も受理する（閉じた選択はUI/ブラウザ契約側の責務）。これは
   `capacityTier`・`dinnerBudgetTier`のしきい値が「非拘束の推奨」として実装・実データレビューに
   委ねられてきた既存の先例（`adr/0019`）に倣った判断であり、指示4「算出方式には踏み込まない」の
   趣旨をプリセット粒度にも一貫させたものである。

### 禁止列の書き換え

旧: 「...coordinates, search origin/range, distance, route, walking time, current location, ...」
（`walking time`を一括禁止）

新: 「...coordinates, search origin, configured search range, exact distance, walking route,
current location, ..., with exactly one deliberate exception: `walkingTimeBand` below, which
adr/0025 decision 3 permits precisely because it is a coarse bucket, not an exact distance, and
carries no candidate-correspondence order」

`distance`と`route`という2語を素朴に「walking time」へまとめず、`exact distance`（禁止のまま）と
`walking route`（禁止のまま、決定6）を分けて明記し、`walkingTimeBand`だけを名指しの例外にした。

## 3. `Candidate`・`ShopLocation`・トップレベル記述の改訂箇所

`grep`で`search origin|walking time|route|current location|distance`を`candidate-search-api.yaml`に
当てた結果、「基点・徒歩時間を返さない」旨の記述は次の3箇所にあった。

- `info.description`（冒頭）: 「The location, configured radius, credentials, provider identifiers,
  and provider images are never accepted or returned」——`location`が検索基点を指す一括りの否定文
  だったため、基点座標（`searchOrigin`）と設定範囲（radius）を明確に分けて書き直した。
- `paths./candidate-proposals.post.description`: 「The configured search origin and its exact radius
  are server-only and are not request parameters.」——これは**入力（request）**についての記述であり
  ADR-0025は入力を変えないため元の文はそのまま残し、「ただしレスポンスの`searchOrigin`として座標は
  含まれる」という一文を追加した。
- `PopulationAttribute`の禁止列（前節）。

`Candidate`スキーマ自体（`candidateRef`等の各プロパティ）には基点・徒歩時間を返さない旨の記述は
無かった——検索した3箇所はいずれも`Candidate`の外側（トップレベル記述・`ShopLocation`・
`populationAttributes`）にあった。`ShopLocation`（候補店舗の座標専用スキーマ）は「検索基点を表さない」
というMustを含み、これは**店舗座標については今も真**なので無変更とし、基点座標は別スキーマ
`SearchOriginLocation`を新設して分離した。

## 4. 徒歩時間の値の形式についての判断

指示は「推定であり実測経路ではない」という性質と、値の形式（分単位の整数か、区分か）だけを定め、
算出方式（直線距離か道のり基準か）には踏み込まないことを求めていた。

- `Candidate.walkingTimeMinutes`は**分単位の整数**とし、`nullable: false`（`null`を許さない）にした。
  ADR-0025の代替案検討が粗い区分を明示的に退けていることに加え、`location`（基点・候補とも）は
  サーバー側で常に既知であり、provider由来の他フィールドのような「取得できなかった」場合が構造的に
  存在しないため、他のnullableなカードフィールドとは性質が異なると判断した。
- 「推定であり実測経路ではない」というMustは、可視値の**提示のされ方**（断定的に読めないこと、
  たとえば近似を示す言い回し）への要求として`Candidate.walkingTimeMinutes`のdescriptionとGherkin
  （TDR-CS-02の新規Then行）の両方に明記した。具体的な文言（「約」「推定」等のどちらを使うか、
  カード内のどこに置くか）は実装側の裁量に残した——ADR-0025の代替案検討にもこの点の具体的な
  UIモックへの言及はなく、`予算感の1行注記`（`adr/0023決定10`）のような人間承認済みの具体的な
  UIパターンが存在しないため、architectが勝手に固定しなかった。
- 直線距離／道のり基準のどちらであるかを推測させる語（「経路」「道のり」等）は、いずれのフィールド
  descriptionにも入れていない。

## 5. 既存契約との差分要約

`contracts/candidate-search-api.yaml`（v1.1.0 → v1.2.0）:
- 追加: `CandidateProposalResponse.searchOrigin`（新規必須、`SearchOriginLocation`）
- 追加: `Candidate.walkingTimeMinutes`（新規必須、integer、not nullable）
- 追加: `CandidateFilters.walkingTimeMaxMinutes`（新規任意、integer、nullable）
- 追加: `PopulationAttribute.walkingTimeBand`（新規必須、integer、nullable、粗いバケツ）
- 追加: `SearchOriginLocation`スキーマ（新設）
- 改訂: `info.description`・`post`の`description`・`populationAttributes`の禁止列・`ShopLocation`の
  description（新スキーマへの参照追加のみ、Must自体は無変更）
- 改訂: `x-default-normalization`（`walkingTimeMaxMinutes: null`を追加）

`contracts/candidate-search.feature`:
- 改訂: TDR-CS-01, 02, 03, 04, 10（前節の表を参照）
- 追加: TDR-CS-15
- 無変更（意図的、理由を表に記載）: TDR-CS-00, 05, 06, 07, 08, 09, 11, 12, 13, 14

未編集（当初のスコープ外として着手時点では見送り、7節で対応済み）:
- `contracts/candidate-search-browser-interface.yaml`
- `contracts/test-support-api.yaml`

未編集（一貫して対象外。指示により実施していない）:
- `product-brief.md`（着手時点で§2は未改訂だったが、7節のとおりorchestratorが処理済み）

## 6. 人間に確認すべき点（着手時点の記録。処理状況は7節を参照）

1. **`product-brief.md` §2の絞り込み条件列挙に「徒歩の上限」が無い。** §3（地図節）はADR-0025に
   合わせて改訂済みだが、§2「絞り込み条件」の箇条書き（ジャンル・居酒屋バー・禁煙・カード払い・
   予算感）は徒歩の上限を含んでいない。ADR-0025決定3は徒歩の上限を`CandidateFilters`の一条件として
   明記しているため、§2との不整合が残っている。指示により追加改訂は実施していない——§2への1行追加が
   要るかどうかの判断を仰ぎたい。
   **→ 2026-08-20、orchestratorが§2へ追加し解決済み。**
2. **ADR-0025の文言（してよい/May）とproduct-brief改訂後の文言（表示する/Will）の強さの違い。**
   ADR-0025本文は決定1「表示してよい」・決定2「返してよく、カードは表示してよい」と許可（Want寄り）で
   書かれているが、既に改訂済みのproduct-brief §2・§3は「表示する」「示す」と確定的に書かれている。
   Gherkinは選択可能な挙動を自然に表現できないため、本改訂は**brief側の確定的な読みを正**として
   契約を書いた（TDR-CS-01・02のThenを必須の観測として追加）。この読み替えが人間の意図と一致するか
   確認されたい——もしADR-0025が本当に「実装しなくてもよい」程度の許可を意図していたなら、TDR-CS-01・
   02の新規Then行は要求を強めすぎている。
   **→ 2026-08-20、orchestratorがADR-0025決定1・2の「してよい」を「する」へ是正し解決済み。
   architectの解釈（brief側の確定的な読みを正とする）が結論として正しかったと確認された。**
3. **`contracts/candidate-search-browser-interface.yaml`への実質的な影響。**
   **→ 2026-08-20、architectが改訂した。詳細は7節A。**
4. **`contracts/test-support-api.yaml`にも新規Givenが要る。**
   **→ 2026-08-20、architectが改訂した。詳細は7節B。**
5. **同心リングの本数・境界がリング＝設定探索範囲の推測材料にならないか。**
   **→ 論点整理のみ7節Cに記載。architectは決定していない——orchestratorの指示どおり人間の判断を待つ。**

## 7. 続報（2026-08-20、orchestratorのchat指示への対応）

orchestratorから、6節の指摘のうち1・2は処理済み（`product-brief.md` §2追加、ADR-0025決定1・2の
「してよい」→「する」是正）との連絡を受けた。残る指摘3・4・5について、次のとおり対応した。

### A. `contracts/candidate-search-browser-interface.yaml` を改訂した

6節指摘3の3点をすべて反映した（contractVersion 1.1.0 → 1.2.0）。

- **`candidate-origin-marker`をforbiddenからallowedへ**: `mapObservations.forbiddenTestIds`から外し、
  `mapObservations.searchOriginMarker`（新設）と`browserControlSurface.proposal.requiredTestIds.
  searchOriginMarker`・`authenticatedInitialOutcome.present`・`initialProposal.success.present`へ
  追加した。`disclosureObservations.bodyMustNotExposeTestIds`からも外した。`candidate-route`・
  `candidate-current-location`・`private-search-origin`は3箇所とも無変更のまま禁止を維持している
  （決定6・ADR-0002は無変更のため）。徒歩圏リング用に`mapObservations.walkingRadiusRings`
  （`candidate-walking-radius-ring`、0件以上）も新設した。
- **カード・フィルタの新規test ID**: `cardDataAttributes.requiredFields.walkingTimeMinutes`
  （`candidate-card-walking-time`）を追加し、新設の`walkingTimeEstimateWording`で「推定であり実測
  経路ではないと分かる文言」をMustにした（rawValueAttributeは持たせていない——可視値と生の応答値が
  同じ数値であり、totalSeats等のような粗い変換が存在しないため）。フィルタパネル側は
  `candidate-filter-walking-time-max-option`（`data-walking-time-max-value`、専用の
  `walkingTimeGroup`）を新設し、`allowedPurposes`に`candidate-filter-walking-time-max-selection`を、
  `changePendingFilter.input`にこのコントロールを追加した。プリセットの具体的な値・個数はここでも
  固定していない（`genres`と同じ扱い）。
- **`unavailableControls.locationRangeControlProhibition`のスコープ付き例外**:
  `displayOnlyOriginException`を新設した。orchestratorの指示どおり、線を要素の種類（tabindexの
  有無・DOMタグ・test id）ではなく**振る舞い**で引いた——「活性化しても、提案リクエスト・設定された
  検索基点・設定された探索範囲のいずれも変えない」ことを条件とし、対象となるスコープは
  `candidate-origin-marker`・`candidate-walking-radius-ring`の2つの表示専用要素に限定した。
  Leafletのマーカーが既定で`tabindex="0"`を持つとしても、それ自体はこの例外の対象条件ではないと
  明記し、フォーカス可能性と状態変更可能性を区別した。既存の禁止が守る性質
  （幹事が基点・探索範囲を*変更*できないこと、`adr/0008`決定4・`adr/0025`決定7）は例外の説明文中で
  明示的に「この例外は縮めない」と書き、`verificationAllocation.L4`にも、activation後に
  「提案リクエストが送られない・表示中の候補/マーカー/条件サマリが一切変わらない」ことをL4が
  実際に駆動して確認する旨を追加し、要素の識別子だけで例外を成立させない設計にした。

### B. `contracts/test-support-api.yaml` を改訂した

6節指摘4に対応し、TDR-CS-15の決定的Givenとして`WALKING_TIME_LIMIT_EXCLUDES`モードを新設した
（contractVersion 1.1.0 → 1.2.0）。既存の`CARD_PAYMENT_CAUTION_VISIBLE`（母集団を表示上限以下に
抑え、無作為抽出に依存せず全件を確定的に表示させる設計）と同じ手法を踏襲した。

- 合成の徒歩上限しきい値を「12」に固定した（現実の製品が最終的に提示するプリセット値とは無関係の、
  テスト決定性だけのための恣意的な合成値であることをdescriptionに明記した）。
- しきい値未満・しきい値ちょうど（境界値、「上限を超える」という除外条件は含まないため候補に残る
  べき）・しきい値超過の3種の候補を最低1件ずつ持たせ、境界条件を明示的に検証できるようにした。
- `searchOrigin`の座標そのものをGiven側で選択可能にする新しいプロパティは**追加しなかった**——
  TDR-CS-01・TDR-CS-02は「地図上のマーカーが、その回のレスポンス自身の`searchOrigin`と一致するか」
  という自己整合性の検証で足り、独立した既知定数と突き合わせる必要が無いと判断した。これにより
  `CandidateProposalAcceptanceState`への座標プロパティ追加を避け、既存のGiven seamの慣行
  （`mode`という閉じた列挙で決定的形状を選ぶ、座標のような生の合成値は極力持たせない）を保った。
- 既存モード（`NORMAL_WITH_WEIGHTED_SAMPLING`等）については、`walkingTimeMinutes`の具体値を規定
  する記述を追加していない——schema上必須になった（v1.2.0）ため実装は何らかの正の整数を割り当てる
  必要があるが、TDR-CS-00〜TDR-CS-14のどのシナリオもその具体値を主張しないため、mode enumの共通
  説明文に1文で「すべてのmodeがv1.2.0のsearchOrigin・walkingTimeMinutesを満たす」という一般規定を
  置くにとどめた。

### C. 指摘5（同心リングが探索範囲の推測材料になりうるか）——論点整理のみ、architectは判断していない

orchestratorの指示どおり、この点は**architectが決めず**、事実関係だけを次のとおり整理する。

**確立している事実**:
- `ADR-0025`決定4・`product-brief.md` §4は、検索基点の実座標と**既定探索距離**を環境変数で与え、
  Gitに置かないと定めている。これは公開リポジトリ（Git）に対する非開示であり、`ADR-0002`の枠組みに
  従う。
- `ADR-0025`決定1は、認証済み画面が検索基点をマーカーとして表示し、基点を中心とする徒歩圏の同心
  リングを描くことを定める。
- `ADR-0025`は、リングが表す「徒歩圏」と、providerへの検索に使う「設定探索範囲（半径）」を、文面上
  別の概念として扱っている——決定1はリングの根拠として徒歩時間を挙げ、設定範囲を挙げていない。

**ADR-0025が明示していない論点**:
- 「Gitに置かない」＝「利用者（認証済みの幹事）に一切見せない」を意味するかどうかは、ADR-0025は
  明示的に述べていない。決定1が基点そのものの表示は明示的に許可した以上、**探索範囲だけ**を
  利用者から隠す理由が残っているのかどうかは、ADR-0025を読んでも一意に決まらない。
- 実装上、同心リングの本数・各リングの半径をどう選ぶかによっては、**最外周のリングが結果的に
  設定探索範囲の値と一致または近似する**描き方になり得る。その場合、利用者はリングを見るだけで
  設定探索範囲をおおよそ推測できてしまう可能性がある。これが起きるかどうかは実装の選び方次第であり、
  ADR-0025はリングの本数・境界値を指定していない。
- 仮に「設定探索範囲を利用者に見せてよい」という判断であれば、リングの設計に制約はなく、むしろ
  「設定探索範囲そのものを示す最外周リング」を意図的に描いてよいことになる。逆に「探索範囲は
  利用者からも隠すべき」という判断であれば、リングの設計（本数・間隔・最外周の値）が設定探索範囲と
  混同されない・一致しないように、実装スライスで明示的な制約を契約に足す必要がある。
- 現行の改訂契約（`candidate-search-api.yaml`・`candidate-search-browser-interface.yaml`）は、
  「設定探索範囲の値そのものはAPI応答・DOMのどこにも一切現れない」というMustを維持したままである
  （`walkingRadiusRings`の半径は、応答から返る具体的な数値ではなく、実装が選ぶ表示上の値であり、
  この契約はその値の出どころ・意味を規定していない）。したがって**契約の文言上は「範囲を直接
  返さない」というMustを破っていない**——論点は、間接的な推測可能性という、契約の文言では捕捉
  しきれない性質の問題である。

**決着（人間裁定 2026-08-20 chat「aですね」。orchestratorが追記）**: 下記の **(a) を採用**した。
`ADR-0025` に決定9として記録済み。リングの本数・半径の選び方に制約は置かない。ただし許容するのは
**間接的な推測可能性**であって値の直接的な露出ではなく、設定探索範囲の値そのものをAPI応答・DOM・
公開URL・ログ・traceへ出さないMustと、決定4のGit非開示は無変更である。したがって本節が
「契約の文言上はMustを破っていない」と整理した状態が、そのまま最終形になる——現行の改訂契約に
追加の制約は要らない。

**選択肢（判断時の整理。architectはどちらも推奨していなかった）**:
- (a) 探索範囲の間接的な推測可能性を許容する。リングの本数・半径の選び方に制約を設けない。
- (b) 探索範囲の間接的な推測可能性を避ける設計を明示的に要求する（例: リングの半径は固定の
  実装定数とし、設定探索範囲の値とは独立に選ぶ、または最外周リングが設定探索範囲と数値的に一致
  しないことをテストで確認する）。この場合、次の実装準備スライスで契約に制約を追記する必要がある。
