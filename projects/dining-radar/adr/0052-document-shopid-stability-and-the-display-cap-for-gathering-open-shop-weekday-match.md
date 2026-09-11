---
id: 0052
scope: project/dining-radar
status: 提案中
date: 2026-09-11
approved_by: null
supersedes: []
superseded_by: null
relates_to: [P-04, P-05, P-08, ADR-0037, ADR-0049]
---

# ADR-0052: `GATHERING_OPEN_SHOP_WEEKDAY_MATCH`のshopId特定を、新しいseamではなく契約の文書化で決定的にする

> **承認者向けサマリ**: tester が TDR-GTH-31・32（幹事が5件のうち1件を新しい店へ差し替える）の
> 受け入れ検査を組み立てる中で、「確定した日に開いている店」と「開いていない店」を区別して
> Given状態を作る既存の技法——候補日を変えて2回問い合わせ、結果の差分から閉店店舗を推定する
> （`identify_a_shop_closed_on_the_confirmed_date`。水曜日を選ぶと閉店が2件になり
> `assertEqual(len(closed_ids), 1, ...)`が実際に落ちた）——が、偶発的に破綻しうる設計のまま
> 残っていることを報告した。
>
> 調べたところ、この脆さの根はもう一段深い。`adr/0049`が幹事の店選びを
> `gathering-scheduling-api.yaml`の`previewOpenShopsForCandidateDate`（かつては開いている店の
> 一覧を返した）から`candidate-search-api.yaml`の`proposeCandidates`の会モード（表示上限
> **5件**・加重ランダム抽出を経由する）へ一本化したことで、`GATHERING_OPEN_SHOP_WEEKDAY_MATCH`が
> 定める6件の合成母集団は、木・金・土（6件全店が開店）において表示上限を上回るようになった。
> さらに`Candidate.shopId`は会モードでのみ非nullであり、会モードの対象母集団は定義上「その日に
> 開いている店」だけに絞られるため、**閉まっている店のshopIdは、その店が閉まっている当の会
> からは決して読み取れない**。
>
> **決定**: 新しいtest-support seamは追加しない。母集団はすでに公開境界
> （`candidate-search-api.yaml`の`proposeCandidates`）から発見可能であり、`adr/0037`決定1・
> `adr/0049`の判断と同じ理由でseamの追加は正当化できない——脆かったのは状態そのものではなく
> 発見の技法だった。代わりに`test-support-api.yaml`の`GATHERING_OPEN_SHOP_WEEKDAY_MATCH`説明文・
> `randomSeed`説明文へ、(1) shopIdはこの状態が選択されている間、どの`proposeCandidates`呼び出し・
> どの会をまたいでも安定しているという契約上の保証、(2) 6件全部のshopIdが要る場面（木・金・土）
> では表示上限5件との衝突があり、`randomSeed`固定＋`shownProviderPageUrls`の2回呼び出しで
> 6件目を確実に見る技法、の2点を追記した。これにより「別の曜日で確定した別の会から、閉まって
> いる店のshopIdを読み取って転用する」という決定的な発見手順が契約として成立する。
>
> あわせて、`OpenShopPreviewItem.shopId`（TDR-GTH-26/27）・`OpenShopPreviewItem`/
> `ParticipantShopVoteOption`（TDR-GTH-38/39）を参照したままの記述が、`adr/0049`決定2による
> `OpenShopPreviewItem`削除後もstaleな参照として残っていたことを発見した。本ADRはこれを
> **解消せず申し送る**（FR-028の流儀）——TDR-GTH-26〜41全体のGiven-state構築手段の棚卸しは、
> これらのシナリオが実装される回の対象であり、本ADRの範囲を超える。

## 文脈

### 0. 検証の申告（meta/adr/0039）

本ADRが前提とする契約記述は、`test-support-api.yaml`（v1.5.5、本ADRと同一作業で1.5.6へ改訂）・
`candidate-search-api.yaml`（`gatheringId`・`Candidate.shopId`/`isShortlisted`の記述、
adr/0049決定1）・`gathering-scheduling-api.yaml`（`previewOpenShopsForCandidateDate`が
`adr/0049`決定2で件数のみへ縮小され`OpenShopPreviewItem`が削除された記述）を実際に読んで
確認した。あわせて`tests/acceptance/dsl/gathering_scheduling_browser.py`の
`identify_a_shop_closed_on_the_confirmed_date`・`fetch_confirmed_date_open_shop_ids`と、
`tests/acceptance/test_gathering_scheduling_acceptance.py`のTDR-GTH-08・09・27・31・32を
実装コードとして読んだ——architectは実装コードを書かないが、Given状態の技法がどう組まれているか
を理解するために読むことは禁止事項に当たらない（読むのは実装の正しさの検証ではなく、契約の
弱点を特定するための調査である）。TDR-GTH-31・32自体は現状Thursday（6件全店開店）を使い、
このADRが扱う「複数閉店」の脆さを直接踏んではいない——tester が踏んだのは、これらのシナリオを
`adr/0049`後のgatheringモード経由で再構築しようとした際の技法検討中だったと判断した
（`identify_a_shop_closed_on_the_confirmed_date`のassertEqual(len==1)前提が、6件中で閉店数が
2件になるWednesdayで崩れる、という一般的な脆さの実例として）。実装コードそのものを直したか
どうかは確認していない——architectの禁止事項どおり、実装の修正は本ADRの範囲外である。

### 1. 何が起きたか

`adr/0037`決定3は、`CandidateProposalAcceptanceState.mode`に`GATHERING_OPEN_SHOP_WEEKDAY_MATCH`
を新設し、6件の合成候補（月のみ閉店・水のみ閉店・火水両方閉店・日閉店・不定休・null）で
曜日ごとの既知件数（月5/火5/水4/木6/金6/土6/日5）を確定させた。この母集団の個々の店の
shopIdは、当時（2026-08-30〜09-04）は`gathering-scheduling-api.yaml`の
`previewOpenShopsForCandidateDate`が返す`OpenShopPreviewItem`一覧から直接読めた——この操作は
表示上限を持たず（監査記録によれば実装は10件のキャップだったが、6件の母集団には届かない）、
サンプリングも行わない、単純な一覧だった。

`adr/0049`（2026-09-08〜09人間裁定、承認済み）はこの構造を変えた。決定2は
`previewOpenShopsForCandidateDate`を件数のみ（`openShopCount`）に縮小し、`OpenShopPreviewItem`
スキーマ自体を削除した。決定1は、店の選択そのものを`candidate-search-api.yaml`の
`proposeCandidates`の「会モード」（`gatheringId`を渡すと、確定候補日で開いている店だけに
母集団を絞る）へ一本化した。`proposeCandidates`は表示上限**5件**・加重ランダム抽出という
既存のアルゴリズムを会モードでもそのまま使う——`Candidate.shopId`は会モードでのみ非nullになる
（`adr/0049`決定1、`candidate-search-api.yaml`）。

この2つの変更の組み合わせが、`test-support-api.yaml`が2026-08-30時点で前提としていた
「この母集団は表示上限を上回らない」という記述（`randomSeed`説明文の一文）を、木・金・土
（6件全店開店）について誤りにした。また、「shopIdは開いている店にしか付かない」という新しい
性質は、「閉まっている店のshopIdを、その店が閉まっている当の会から読み取る」という
既存の発見技法（`identify_a_shop_closed_on_the_confirmed_date`）を、原理的に不可能にした
——閉まっている店は、その会のレスポンスに一度も現れないため、shopId自体を持たない。

### 2. tester の報告

tester は、TDR-GTH-31・32相当のGiven状態（幹事が5件を選び、投票が始まっている状態から
1件を新しい店へ差し替える）を`adr/0049`後の会モード経由で組み立てる過程で、既存の
`identify_a_shop_closed_on_the_confirmed_date`技法——候補日を変えて2回問い合わせ、差分から
閉店店舗を推定する——を再利用しようとし、`assertEqual(len(closed_ids), 1, ...)`が
Wednesday（この母集団では閉店2件）で実際に落ちることを確認した。これはこの技法自身が
自己申告していた前提（`reviews/audit-gathering-shortlist-vote-steps.md`の観点5「暗黙の前提」
が既に記録済み——「候補日の開店店舗集合の差分が必ずちょうど1件になる」という、このテストデータ
固有の前提）の破れであり、握りつぶしではなく正しく失敗した。tester はこれを「受け入れテストの
前提の弱さ」としてarchitectへ報告した（FR-028の流儀——解消せず報告する）。

## 決定

### 決定1. 新しいtest-support seamは追加しない

`GATHERING_OPEN_SHOP_WEEKDAY_MATCH`が確定させる「どの店がどの曜日に閉まるか」という状態は、
`candidate-search-api.yaml`の`proposeCandidates`（会モード）という公開境界から、原理的には
発見可能である——ある店が閉まっている確定日だけからは見えなくても、その店が開いている
**別の**確定日（別の会）からは見える。したがって`adr/0037`決定1・`adr/0049`の判断
（「この母集団はすでに公開境界から発見できるため、二重の制御経路を持つ新しいseamを立てない」）
と同じ理由で、新しいseamを追加する根拠は無い。脆かったのは状態そのものではなく、2回の
問い合わせを「同じ量」だと決め打ちしていた発見の技法である。

`meta/verification.md`が定める「DB直接操作はGiven専用のseamとして明示的に定義した箇所のみ
許可」という原則に照らしても、この状態はDB直接操作でしか作れないものではない——公開APIの
組み合わせで確実に発見できる。

### 決定2. shopIdの安定性を契約として明記する

`test-support-api.yaml`の`GATHERING_OPEN_SHOP_WEEKDAY_MATCH`説明文へ、この状態が選択されている
間、6件の合成候補それぞれのshopIdは、どの`proposeCandidates`呼び出し・どの会をまたいでも
同一である（状態選択時に一度だけ割り当てられ、リクエストごと・会ごとに再割り当てされない）と
明記した。この保証が無ければ、「別の会から読み取ったshopIdを目的の会へ転用する」という発見
手順自体が成立するかどうかが契約上不明のままになる。

具体的な発見手順として、月曜（5件開店、月のみ閉店の1形を除く残り5形すべてが開店）で確定した
会が、この母集団が他のどの1曜日で閉める店も開示すること、火曜（同じく5件開店）で確定した会が
月曜自身の閉店店舗（月のみ閉店の形）を開示することを記載した。この2つの参照日の組み合わせで、
本モードが定義する曜日ごとの閉店パターンはすべて、少なくとも1つの参照日から発見できる
（いずれの参照日も、自分自身が閉める1形以外のすべての形を開示するため）。

### 決定3. 表示上限5件との衝突を契約として明記する

`randomSeed`説明文の既存の一文（「この母集団は表示上限を上回らないため、randomSeedはこのモードが
文書化する件数に影響しない」）は、`previewOpenShopsForCandidateDate`の`openShopCount`
（`adr/0049`決定2以降も件数のみ・サンプリングなし）についてのみ今なお正しい。しかし店の選択
そのものが`proposeCandidates`の`candidates`配列（表示上限5件・加重ランダム抽出）を経由する
ようになった以上、木・金・土（6件全店開店）はこの母集団が唯一表示上限を上回る曜日であり、
1回の呼び出しでは6件中5件しか見えない。

この衝突を、既存の一文を書き換えず追記の形で明記し（P-06の「古い記述を書き換えず新しい決定で
置き換える」の精神——ただし本件は契約の記述の追補であり、決定そのものの上書きではない）、
6件全部が要る場面（TDR-GTH-45の5件到達後の6件目拒否検査など）向けに、randomSeed固定＋
`shownProviderPageUrls`の2回呼び出しで6件目を確実に見る手順を記載した。この手順は
`SHOWN_POOL_PRIORITY`が既に文書化している分割の仕組み（未表示分割）をそのまま再利用しており、
新しい仕組みを持ち込んでいない。

### 決定4. staleな参照は解消せず、staleだと明記するに留める

`GATHERING_OPEN_SHOP_WEEKDAY_MATCH`説明文が、TDR-GTH-26/27について`OpenShopPreviewItem.shopId`
を、TDR-GTH-38/39について`OpenShopPreviewItem`/`ParticipantShopVoteOption`を読むと記述した
くだりは、`adr/0049`決定2による`OpenShopPreviewItem`削除より前に書かれたもので、削除後も
更新されないまま残っていた。本ADRはこの記述を書き換えない——TDR-GTH-26〜41全体の
Given-state構築手段（廃止された幹事ダッシュボード内の店選び一覧`shortlistSelection`を前提に
したまま残っている可能性がある）の棚卸しは、これらのシナリオが実装される回でまとめて行うべき
作業であり、本ADRが答える問い（週次パターンの発見手段）とは別の問いである。FR-028の流儀に
従い、staleである事実だけを明記し、解消は次工程へ申し送る。

## 検討した代替案

- **新しいtest-support seamを追加し、6件それぞれのshopIdと閉店パターンを直接返す
  （例: `getGatheringOpenShopWeekdayMatchAssignments`）**: 却下。この状態はすでに公開境界
  （`proposeCandidates`の会モード、決定2の発見手順）から確実に発見できるため、`adr/0037`決定1・
  `adr/0049`が繰り返し立ててきた「公開境界で作れる状態には新しいseamを足さない」という判断と
  矛盾する。この母集団の制御経路をこれ以上増やすと、複数の独立した制御経路が食い違うリスク
  （`adr/0037`が検討し却下した代替案と同種）も生む。
- **母集団を6件から5件（表示上限以下）へ縮小する**: 却下。曜日ごとの既知件数
  （月5/火5/水4/木6/金6/土6/日5）はTDR-GTH-08/09・TDR-GTH-26/27/38/39・TDR-CS-17/18/19・
  TDR-GTH-44/45が直接参照する確定した契約値であり、母集団を縮小すればこれらすべてを
  作り直す必要が生じる。これは今回報告された脆さ（発見技法の一般化不足）よりはるかに大きい
  影響範囲を持ち、「変更は最小限に」という本ラウンドの制約にも反する。
- **会モードの表示上限を、通常のランチ候補画面より緩める（あるいは撤廃する）**: 却下。
  これは受け入れテストの都合ではなく、実際の製品挙動（幹事が会のために店を選ぶ際に何件まで
  一度に見せるか）を変える提案であり、`adr/0049`が既に「1つの候補モデルで両画面をまかなう」
  という設計を人間裁定として確定させている。architectが単独で、テストの便宜のために本番の
  UX上限を変えることは、契約とモデルの番人としての範囲を超える——変えたいなら別途、人間の
  意図の聞き取りから始める必要がある。
- **`identify_a_shop_closed_on_the_confirmed_date`のassertEqual(len==1)を単に緩める
  （実装・テストコード側の修正）**: これは有効な修正だが、architectの禁止事項（実装・テスト
  コードを書かない）の範囲外であり、また今回発見した「shopIdは会モードでのみ・開いている店にしか
  付かない」という、より根本的な性質を説明しない。契約側の保証（決定2・3）を先に確立すること
  で、次にこの技法を書き直すdeveloper/testerが、根拠を毎回実験で再発見せずに済む。

## 帰結

- `contracts/test-support-api.yaml`（改訂、v1.5.5→v1.5.6）: `GATHERING_OPEN_SHOP_WEEKDAY_MATCH`
  説明文へshopId安定性の保証（決定2）とstale参照の申し送り（決定4）を追記し、`randomSeed`
  説明文へ表示上限5件との衝突と2回呼び出しの発見手順（決定3）を追記した。新しいoperationId・
  新しいスキーマ・新しいシナリオIDはいずれも追加していない——`x-acceptance-scenarios`各listは
  無変更である。ヘッダコメントに2026-09-11追補6を追加し、本ADRへの参照を記録した。
- `candidate-search-api.yaml`・`gathering-scheduling-api.yaml`・
  `gathering-scheduling-browser-interface.yaml`・`candidate-search.feature`・
  `gathering-scheduling.feature`: いずれも変更していない——本ADRはacceptance層の文書化のみを
  対象とする。
- `ARCHITECTURE.md`・`design.md`: 変更しない——新しいモジュール境界を生まない。

## 未決事項（次工程・人間への申し送り）

1. **本ADR自体の承認**: `status: 提案中`のまま起草した（`meta/adr/0064`決定1の書式、
   `adr/0037`・`adr/0039`の先例と同じくarchitectの技術判断として`approved_by: null`）。
2. **TDR-GTH-26〜41全体のGiven-state構築手段の棚卸し**（決定4で解消せず申し送った件）:
   `adr/0049`が廃止した幹事ダッシュボード内の店選び一覧（`shortlistSelection`）・
   `OpenShopPreviewItem`を前提にした記述が、`test-support-api.yaml`以外の契約ファイル
   （`gathering-scheduling-browser-interface.yaml`・`gathering-scheduling.feature`）にも
   残っている可能性がある。これらのシナリオ（TDR-GTH-26〜41のうち会モード一本化の影響を
   受けるもの）が次に実装される回で、architectが棚卸しを行う必要がある。
3. **決定2・3が記載する発見手順が、実装コードとして本当に成立するか**は未検証——architectは
   実装コードを書かないため、developer/testerが実際にこの手順でTDR-CS-17/18/19・
   TDR-GTH-44/45・（再構築されるなら）TDR-GTH-31/32を組み立てる段で、手順自体の実行可能性
   （特にshopIdの安定性という契約上の保証が、実装のシード生成ロジックと矛盾しないか）を
   確認する必要がある。矛盾が見つかった場合はFR-028の流儀で報告されることを期待する。
