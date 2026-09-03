---
id: 0040
scope: project/dining-radar
status: 承認済み
date: 2026-09-03
approved_by: "人間裁定（2026-09-03 チャット: 本番を確認し『作りかけ。見て判断できるところまで
  作りこんでほしい』と述べた。ADR-0035決定2が定めた会スコープ契約の4分割（第1弾=会の作成と
  日程調整／第2弾=店の絞り込み連携／第3弾=承認投票／第4弾=確定）のうち、未着手のまま残っていた
  第2〜4弾を、1本の契約スライスへ統合して起草するよう明示指示した。分割の判断そのもの
  （ADR-0035決定2）を誤りとして撤回するのではなく、実装方針としてこれを上書きする統合の指示
  である。）"
supersedes: []
superseded_by: null
relates_to: [P-02, P-06, P-08, ADR-0013, ADR-0023, ADR-0034, ADR-0035, ADR-0036, ADR-0038]
---

# ADR-0040: 店の絞り込み連携・承認投票・確定・確定後表示を1本の契約スライスへ統合する

> **承認者向けサマリ**: 会スコープ契約第1弾「会の作成と日程調整」の本番デプロイ・入口追補
> （ADR-0038）を人間が確認し、「作りかけ。見て判断できるところまで作りこんでほしい」と述べた
> （2026-09-03チャット）。`ADR-0035`決定2が定めた4スライス分割のうち、未着手だった第2〜4弾
> （店の絞り込み連携・承認投票・確定）を、本ADR・本改訂で1本の契約スライスへ統合して起草する。
> `gathering-scheduling-api.yaml`をv0.3.0→v0.4.0へ拡張し、`gathering-scheduling.feature`へ
> TDR-GTH-26〜35を追加した。**browser-interface契約はまだ起こさない**（`ADR-0013`の順序を
> 維持する）——designerが並行して、5件選定の導線・参加者の確定後画面・幹事の確定後画面という
> まだ描かれていない3点を描いており、人間が画面骨格を承認した後に追随させる。
>
> **設計判断の要点**: (1) 「この5件で投票する」操作は`Gathering.phase`を進めない
> ——product-brief.md §2の文言と3値のまま確定済みの`GatheringPhase`enumの間にある食い違いを、
> enumを増やさない側で解消した（FR-028として報告、下記参照）。(2) D7（投票開始後の差し替え）の
> ための分母は店ごとに持つ（`ShortlistedShop.respondedParticipantCount`）——`Vote.dc.html`が
> 店ごとに異なる分母（「回答した8人のうち」／「入れたあとに答えた1人のうち」）を描いているため。
> (3) 確定は幹事の明示選択であり、最多得票を自動採用しない（票は決定の材料であって決定
> そのものではない、product-brief.md §2）。(4) 確定後の拒否は既存の`GATHERING_FINALIZED`
> （409）を再利用する——依頼どおり新しいコードを増やさない。(5) 会一覧の「名前」data属性ギャップ
> （監査指摘）は本ファイルの変更範囲外であることを確認し、次にbrowser-interfaceを起こす際に
> 追加する前提を本ADRへ予告として記録する。
>
> **2026-09-03追記（同日、`ADR-0041`が下記の未決事項1の状態を更新）**: 本ADR自体の決定・検討した
> 代替案・帰結の本文はP-06に従い変更していない。未決事項1（FR-028として報告した、
> product-brief.md §2の文言と3値enumの食い違い）は、同日続く選択肢UIで人間が下した裁定（P6）に
> より決着した——enum側を動かさず、§2の文言を実態に合わせる形で解消された。詳細は`ADR-0041`を
> 参照する。

## 文脈

### 1. 何が起きたか

会スコープ契約第1弾「会の作成と日程調整」は、本番デプロイ（PR #181）・実機フィードバックへの
対応（ADR-0038、入口画面群、PR #183〔入口追補〕）を経て、人間が実機を確認した。人間の所見は
「作りかけ。見て判断できるところまで作りこんでほしい」であり、`ADR-0035`決定2が定めた残る
3スライス（第2弾=店の絞り込み連携、第3弾=承認投票、第4弾=確定）を、個別のスライスとしてではなく
**1本の契約スライスに統合して**起草するよう明示指示した。

`ADR-0035`決定2は、この統合を「検討した代替案」として明示的に却下していた（P-02の縦切り原則、
`ADR-0034`決定8の踏襲を理由に）。今回の人間裁定は、その却下の判断が誤りだったと訂正するもの
ではなく、当時の判断を実装方針として上書きする、後発の明示的な人間の意思決定である——本ADRは
これをそのまま記録する。

### 2. 入力

- `product-brief.md` §2（承認投票・確定・D1/D7を含む、既に人間承認済みの記述）。
- `adr/0034`〜`adr/0039`（会スコープの経緯・既決事項）。
- designerのキャンバス板 `E:\AWS\dsg-out\party\Organizer.dc.html`（A②「店を選び中・投票実施中」）
  ・`Vote.dc.html`（B-2「店の投票（承認投票）」）。
- 既存契約一式（`gathering-scheduling-api.yaml` v0.3.0・`gathering-scheduling.feature`
  TDR-GTH-01〜25・`gathering-scheduling-browser-interface.yaml` v0.4）。

これらのキャンバスは、`ADR-0036`が第1弾の画面骨格として人間裁定を得た際の同じ回のキャンバス
一式に含まれていたものであり（`E:\AWS\dsg-out\party\`配下）、`Organizer.dc.html`のA②・
`Vote.dc.html`は当時から「承認投票・確定は次スライス以降」として参照だけされ、契約化されて
いなかった。本ADRはこれを契約化する。

### 3. `activeContext.md`が記録していた既知のギャップ

第1弾ラウンドの申し送りは次の2点を「第2弾の契約作業で拾う」としていた。

1. FINALIZED局面の観測面ギャップ: APIは`GATHERING_FINALIZED`(409)を定義済みだったが、確定後
   画面・確定操作そのものは次スライスの範囲だった。
2. 会一覧の「名前」のdata属性（監査指摘、契約未定義のまま）: `gathering-list-item`（会の一覧の
   行）に会の名前を機械観測する属性が無い。

本ADRは(1)をAPI面で解消する（`finalizeGathering`・`ParticipantView.decision`の新設、下記
決定4・5）。(2)は本ファイルの変更範囲外である——`gathering-scheduling-browser-interface.yaml`
の課題であり、本ADRはこれを次にそのファイルを改訂する際に追加する前提として予告するにとどめる
（下記帰結）。

## 決定

### 決定1. 第2〜4弾を1本の契約スライスへ統合する

`gathering-scheduling-api.yaml`をv0.3.0→v0.4.0へ、`gathering-scheduling.feature`へ
TDR-GTH-26〜35を追加する形で、店の絞り込み連携・承認投票・確定・確定後表示を一度に契約化する。
分割していた理由（依存関係の自然な順序、P-02）そのものは今回も成り立っている——会・候補日・
参加者リンクの永続データに対し、絞り込み→投票→確定は素直にこの順で積み上がる——が、人間が
明示的に「まとめて見て判断したい」と指示したため、契約成果物としては1回の改訂にまとめる。
実装スライス自体をこの契約単位のまま1つにするか、developer側でさらに分けて実装するかは、本ADRの
範囲外である。

### 決定2. 「この5件で投票する」は局面を進めない（FR-028として報告）

`product-brief.md` §2は次の3操作を「局面を進める、幹事が行う3つの操作」として列挙している。

1. 「この日にする」（日程を聞き中→店を選び中）
2. 「この5件で投票する」（承認投票を開始する）
3. 「確定する」（店を選び中→確定）

しかし`GatheringPhase`のenumは`ADR-0035`起草時から一貫して3値
（`SCHEDULING`/`SELECTING_SHOP`/`FINALIZED`）であり、2回の遷移（1→2、2→3の間）しか表現でき
ない。操作2「この5件で投票する」が文字どおり局面を進める（4つ目のenum値、例えば
`VOTING`を新設する）と、`Organizer.dc.html`が②を「店を選び中・投票実施中」という**1つの局面
ラベルの下で**描いている実態、および`ADR-0038`のD10が「局面は3つ」と確定したばかりの決定と
食い違う。

**これはFR-028として報告する食い違いである**: product-brief.md §2の文言（3操作すべてを
「局面を進める操作」として並列に列挙する書き方）と、確定済みの3値enum（局面遷移は2回しか
無い）は、文字どおりには両立しない。architectはどちらが「正しい」かを人間の代わりに裁定せず、
**enum側（3値のまま、ADR-0035・ADR-0038で既に2度確定している）を動かさない**という保守的な
選択をした——`shopIds`を選ぶ操作（`setShortlistedShops`）は`Gathering.phase`を変えず、代わりに
`Gathering.votingStartedAt`（null→非null）という独立したサブ状態フィールドで「投票を開始した
かどうか」を表現する。この選択の根拠は、enumを増やす代替（決定7の検討した代替案を参照）が
`Organizer.dc.html`の描写・D10の確定内容の両方と正面から矛盾するのに対し、サブ状態フィールドは
どちらとも矛盾しないためである。product-brief.md §2の文言そのものの訂正要否は、本ADRでは
決めない——人間のレビュー対象として明示する。**2026-09-03、続く選択肢UIで人間がこの点を決着
させた——下記未決事項1、および`ADR-0041`を参照する。**

### 決定3. D7の分母は店ごとに持つ

`Vote.dc.html`は、投票開始時からある店の分母（「回答した8人のうち」）と、差し替えで後から
加わった店の分母（「入れたあとに答えた1人のうち」）を、明示的に**異なる値**として描いている。
これを機械的に表現するため、`ShortlistedShop`（組織者向け）・`ParticipantShopVoteOption`
（参加者向け）の両方に、店ごとの`respondedParticipantCount`（この店が`addedAt`されて以降に
投票した参加者数）を持たせた——`Gathering.respondedParticipantCount`（日程回答の分母、D2）とは
別の、新しい第3の分母である。参加者の「まだ答えていません」表示（`yourApproval: null`）は、
その参加者の直近の投票送信時刻がこの店の`addedAt`より前かどうかで判定する——店ごとの個別の
参加者履歴を保持する必要がなく、タイムスタンプの比較だけで済む設計とした。

### 決定4. 確定は幹事の明示選択とし、最多得票を自動採用しない

`finalizeGathering`は`shopId`を必須パラメータとして受け取り、`Gathering.shortlistedShops`の
`approvalCount`から最多得票の店を自動計算して確定するAPIにはしない。product-brief.md §2が
「決定は幹事が行う。承認投票の票は、決定のための材料であって、決定そのものではない」と明記
しているためである。

### 決定5. 確定後の拒否は既存の`GATHERING_FINALIZED`を再利用する

`setShopVotes`・`issueParticipantLinks`が確定後に拒否される際のコードは、`setScheduleResponse`
が既に使っている`GATHERING_FINALIZED`（409）をそのまま再利用し、新しいコードを追加しない
——依頼文の明示指示（「既存エラーコードの活用」）どおりである。確定後の参加者向け表示は
`ParticipantView.decision`（新設、`phase`がFINALIZEDのときだけ非null）として表現し、確定した
候補日と店（生きた投影、`ADR-0034`決定6のとおり永続化しない）を返す。

### 決定6. browser-interface契約はまだ起こさない

`ADR-0013`が確立した「画面が先、契約は追随する」という順序を維持する。依頼文自身が明記する
とおり、designerは並行して次の3点——5件選定の導線、参加者の確定後画面、幹事の確定後画面——を
描いている最中であり、まだ人間の画面骨格承認を経ていない。本ADRは、画面に依存しない業務・データ
契約（`.feature`・`-api.yaml`）の部分だけを先に確定する——`previewOpenShopsForCandidateDate`
（既存、汎用）をそのまま5件選定の下見にも再利用できることを確認し、新しいbrowse用エンドポイントは
追加していない。

### 決定7. 会一覧の「名前」data属性ギャップの解消を予告する

`activeContext.md`が記録していた監査指摘（`gathering-list-item`に会の名前の機械観測手段が
無い）は、本ADR・本改訂の変更範囲（API・feature）の外にある——`gathering-scheduling-browser-
interface.yaml`側の課題である。本ADRはこれを解消しない。次にそのファイルを改訂する機会
（決定6が定める、designerの5件選定・確定後2画面の承認後）に、`gathering-list-item`へ
`data-gathering-title`相当の属性を追加する前提を、ここに予告として記録する。

## 検討した代替案

- **`GatheringPhase`に4つ目の値（例: `VOTING`）を追加し、「この5件で投票する」を文字どおり
  局面を進める操作にする**: 却下（決定2）。`Organizer.dc.html`は②を「店を選び中・投票実施中」
  という1つの局面として描いており、`ADR-0038`のD10は「局面は3つ」を2026-09-01に確定した
  ばかりである。ここで4つ目を足すと、直近の確定事項と正面から矛盾する。
- **投票開始・差し替えのたびに`Gathering.phase`をSELECTING_SHOPのまま据え置く代わりに、
  専用の`votingSubPhase`enum（NOT_STARTED/OPEN）を新設する**: 検討したが不採用。
  `votingStartedAt`という単純なnullable timestampのほうが、決定3の店ごと分母計算
  （`addedAt`との比較）ともそのまま噛み合い、余分な語彙を増やさない。
- **D7の分母を店ごとに持たず、会全体で1つの「投票済み人数」だけを公開する**: 却下（決定3）。
  `Vote.dc.html`が店ごとに異なる分母を明示的に描いており、これを1つの値に潰すと、差し替えで
  後から加わった店に対する「まだ答えていません」の表現ができなくなる。
- **最多得票の店を`finalizeGathering`が自動選択する（`shopId`を省略可能にする）**: 却下
  （決定4）。product-brief.md §2が「決定は幹事が行う」ことを明記している。
- **確定後の拒否に専用の新しいコード（例: `SHOP_VOTE_REJECTED_FINALIZED`）を導入する**: 却下
  （決定5）。依頼文が明示的に既存コードの再利用を求めており、`GATHERING_FINALIZED`は既に
  「確定後は受け付けない」という同じ意味を持つ。
- **browser-interface契約も本ADRで先取りして起草する**: 却下（決定6）。`ADR-0013`の順序
  （画面が先）を逆転させ、`ADR-0035`決定2の「検討した代替案」が却下した理由（まだ実機
  レビューを経ていないキャンバスのDOM構造を先取りして固定するリスク）がそのまま当てはまる。

## 帰結

- `contracts/gathering-scheduling-api.yaml`（更新、`version` 0.3.0→0.4.0、ステータス:
  承認待ち）: `setShortlistedShops`（`PUT /gatherings/{gatheringId}/shortlisted-shops`）・
  `finalizeGathering`（`POST /gatherings/{gatheringId}/finalize`）・`setShopVotes`
  （`PUT /participant-links/{token}/shop-votes`）を新設。`Gathering`へ`votingStartedAt`・
  `shortlistedShops`・`finalizedShopId`を追加。`ParticipantView`へ`shopVoteQuestions`・
  `decision`を追加。`issueParticipantLinks`に409（`GatheringFinalized`）を追加。新エラー
  コード`GATHERING_NOT_IN_SELECTING_SHOP_PHASE`・`SHOP_VOTING_NOT_STARTED`・
  `INVALID_SHOP_SELECTION`を追加し、`GATHERING_FINALIZED`は決定5のとおり再利用のみで新設
  しない。
- `contracts/gathering-scheduling.feature`（更新）: TDR-GTH-26〜35を追加した。既存シナリオ
  （TDR-GTH-01〜25）の本文は変更していない。
- `contracts/gathering-scheduling-browser-interface.yaml`は本ADRでは変更しない（決定6）。
  次の改訂機会に、決定7が予告する`gathering-list-item`への名前属性追加もあわせて行う。
- `product-brief.md`は変更しない——§2は既にADR-0034・0035の時点で承認投票・確定・D1/D7を
  織り込み済みであり（依頼文が確認済みと明記するとおり）、本ADRの範囲では追加の改訂を要しない。
  ただし決定2のFR-028報告（§2の文言と3値enumの間の食い違い）は、§2の文言そのものを人間が
  今後訂正するかどうかの判断材料として残す。
- `ARCHITECTURE.md`・`design.md`は変更しない——本ADRは既存スライスの契約拡張であり、モジュール
  境界・依存方向を変えていない。

## 未決事項（次工程・人間への申し送り）

1. ~~**決定2のFR-028報告**: product-brief.md §2の「局面を進める3操作」という文言と、3値のまま
   確定済みの`GatheringPhase`enumが、文字どおりには両立しない。architectはenumを動かさない
   側で解消したが、§2の文言自体を訂正するかどうかは人間の判断待ちとする。~~
   **決着（2026-09-03、同日続く選択肢UI、`ADR-0041`決定P6）**: 人間はenumを動かさない側を
   支持し、product-brief.md §2の文言を「局面を進める操作は2つ（この日にする・確定する）。
   『この5件で投票する』は幹事の重要操作だが局面を進めない」へ改訂した。`gathering-scheduling-
   api.yaml`の`GatheringPhase`descriptionもこの決着に合わせて更新済みである。詳細は`ADR-0041`
   を参照する。
2. **決定7の予告**: `gathering-list-item`への`data-gathering-title`相当の属性追加は、次の
   browser-interface改訂（decision 6が定めるとおり、designerの5件選定・確定後2画面の承認後）
   まで未着手のまま残る。
3. **`ADR-0035`から持ち越し、引き続き未決**: 会データの保持期間・削除方針、署名付きリンクの
   有効期限日数・レート制限の具体値（いずれも根拠の薄い暫定値）。
