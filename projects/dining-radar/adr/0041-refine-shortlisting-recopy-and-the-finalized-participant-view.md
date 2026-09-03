---
id: 0041
scope: project/dining-radar
status: 承認済み
date: 2026-09-03
approved_by: "人間裁定（2026-09-03 チャット選択肢UI、ADR-0040の統合契約案を見た直後の続き。
  6件（P1〜P6）: P1=5件選定は幹事ダッシュボード内で完結する（案A）。P2=`SetShortlistedShopsRequest`
  の下限は1件（0件・6件以上は拒否）。P3=承認投票の対象一覧に絞り込み条件（ジャンル等）を持ち込ま
  ない。P4=確定後もrecopyParticipantLinkは拒否されない（issueParticipantLinksの409とは対照的）。
  P5=確定後の参加者画面に、参加者自身の出欠回答と自分が『行ってもいい』と選んだ店を表示する
  （他の参加者の回答・票は含めない）。P6=ADR-0040未決事項1（product-brief.md §2の『局面を進める
  3操作』という文言と3値のままのGatheringPhase enumの食い違い、FR-028）を、enumを動かさず
  §2の文言を実態に合わせる形で決着させる。"
supersedes: []
superseded_by: null
relates_to: [P-06, P-08, ADR-0013, ADR-0034, ADR-0035, ADR-0036, ADR-0038, ADR-0040]
---

# ADR-0041: 5件選定・再コピー・確定後の参加者画面を精緻化する（ADR-0040の細部6件、P1〜P6）

> **承認者向けサマリ**: `ADR-0040`が起草した統合契約（店の絞り込み連携・承認投票・確定）を人間が
> 確認し、同日続く選択肢UIで細部6件（P1〜P6）を裁定した。契約への実質的な影響を持つのはP2
> （境界の明記）・P4（確定後の再コピー可否の明示）・P5（確定後の参加者画面の拡張）・P6
> （`ADR-0040`未決事項1の決着）の4件であり、P1・P3は既存設計の確認にとどまる（契約の実体は
> 変更しない）。`gathering-scheduling-api.yaml`をv0.4.0→v0.5.0へ、`gathering-scheduling.
> feature`へTDR-GTH-36を追加し、`product-brief.md`§2をP6に合わせて改訂した。
>
> **設計判断の要点**: (1) P5の「確定後に振りかえられる自分の記録」は、他の参加者の回答・票を
> 一切含めないという人間の明示的な条件を、`ParticipantView.decision`の新規2フィールド
> （`yourScheduleResponse`・`yourApprovedShops`）として、この参加者自身のデータだけから
> 導出できる形で設計した——集計値・他者の識別子を一切参照しない。(2) 表示用の店情報を
> `LiveProjectedShop`という共有スキーマへ切り出し、`decision.shop`と`decision.
> yourApprovedShops`の両方で再利用した。(3) P4は、`ADR-0036`決定7・本契約が元々
> `recopyParticipantLink`に対して`Gathering.phase`の制約を書いていなかった（禁止する記述が
> 無かっただけ）という状態を、人間の明示裁定によって「意図して禁止しない」という確定した設計へ
> 格上げした——起草時点の不作為と、人間裁定を経た明示的な許可は法的効力が異なる、という区別を
> 契約コメントに残した。(4) 本ADR作業中、`setShopVotes`が参照する`SetShopVotesRequest`
> スキーマが前回の改訂（`ADR-0040`）で定義漏れ（宙に浮いた`$ref`）になっていたことに
> architect自身が気づき、あわせて修正した——今回の人間裁定とは独立した自己監査による修正である。

## 文脈

### 1. 何が起きたか

`ADR-0040`が起草した統合契約案（`gathering-scheduling-api.yaml` v0.4.0・`gathering-scheduling.
feature` TDR-GTH-26〜35）を人間が確認し、同日（2026-09-03）続く選択肢UIで6件を裁定した。

1. **P1（確認のみ）**: 5件選定は幹事ダッシュボード内で完結する（案A）。
2. **P2（最小1件、境界の明記）**: `SetShortlistedShopsRequest`の下限を1件にする
   （`INVALID_SHOP_SELECTION`の境界を明記する）。
3. **P3（確認のみ）**: 承認投票の対象一覧に絞り込み条件（ジャンル等）を持ち込まない。
4. **P4（確定後も再コピー可）**: `recopyParticipantLink`が`Gathering.phase`に関わらず
   （FINALIZED後も）拒否されないことを契約上明示する——`issueParticipantLinks`が確定後に
   `GATHERING_FINALIZED`で拒否されるのとは対照的である。
5. **P5（確定後の参加者画面に自分の記録を表示）**: `ParticipantView.decision`に、その参加者
   自身の出欠回答と、自分が「行ってもいい」と選んだ店を含める形へスキーマ拡張する。人間の意図は
   「投票後に振りかえられる」ことである。他者の票は含めない。
6. **P6（`ADR-0040`未決事項1の決着）**: `product-brief.md`§2を、「局面を進めるのは2操作
   （この日にする・日と店を確定する）。『この5件で投票する』は幹事の重要操作だが局面は進めない
   （店を選び中の中で投票が始まる）」へ改訂する。

### 2. P1・P3が「確認のみ」である理由

P1: `ADR-0040`が起草した`setShortlistedShops`は、当初から`previewOpenShopsForCandidateDate`
（既存、汎用）を再利用する設計であり、専用の別画面・別エンドポイントを一切導入していなかった
——同じ幹事ダッシュボードの中で完結する前提と、人間が選んだ案Aは最初から一致していた。

P3: `setShortlistedShops`・`ShortlistedShop`・`ParticipantShopVoteOption`のいずれにも、
ジャンル・徒歩時間などの絞り込みパラメータは元から存在しない——候補は「その日に開いている店」の
母集団全体であり、承認投票の対象一覧に対して追加のフィルタを適用する設計にはなっていなかった。

両者とも、architectの既存設計が人間の意図と一致していたことの確認であり、スキーマ変更を伴わない。

## 決定

### 決定1（P2）. `SetShortlistedShopsRequest`の下限1件を人間裁定として確定する

`SetShortlistedShopsRequest.shopIds`は起草時から`minItems: 1, maxItems: 5`だった——この値は
architectの設計判断（会をつくるには候補日が1つ以上必要という既存の流儀に倣った）だったが、
今回の人間裁定（P2）により正式に追認された。`InvalidShopSelection`レスポンスの説明文へ、
「0件、または6件以上はいずれも拒否される」という境界を明記した。

### 決定2（P4）. `recopyParticipantLink`が`Gathering.phase`を問わず拒否されないことを明示する

`recopyParticipantLink`は起草時点から`Gathering.phase`に基づく拒否を一切定義していなかった
——これは「禁止する記述が無かった」という不作為であり、「確定後も使えることを意図して確定した」
という積極的な設計ではなかった。今回の人間裁定（P4）は、この振る舞いを積極的に確定させる
——`issueParticipantLinks`（新規発行）が確定後に`GATHERING_FINALIZED`で拒否されるのとは
対照的に、`recopyParticipantLink`・`revokeParticipantLink`（いずれも新規発行を伴わない管理
操作）は確定後も引き続き使える。契約本文（`recopyParticipantLink`のdescription、
`GatheringFinalized`レスポンスのdescription）へこの対照を明記し、新規シナリオTDR-GTH-36
（`gathering-scheduling.feature`）を追加した。

**この決定の意味するところ**: 確定後にリンクを紛失した参加者がいても、幹事は既存のリンクを
再コピーして再送できる——確定後のリンクは「決定内容だけを見せる」ものになる（D1）が、その
決定内容へアクセスする手段そのものは締め切らない、という一貫した設計になる。

### 決定3（P5）. 確定後の参加者画面へ、参加者自身の記録を追加する

`ParticipantView.decision`（`ADR-0040`が新設、`phase`がFINALIZEDのときだけ非null）へ、次の
2フィールドを追加する。

- `yourScheduleResponse`（nullable）: 確定した候補日そのものに対する、この参加者自身の日程
  回答。`scheduleQuestions`のうち`Gathering.confirmedCandidateDateId`に一致する項目と同じ値。
- `yourApprovedShops`（配列）: この参加者が確定時点で「行ってもいい」と選んでいた店の一覧
  （`ParticipantShopVoteOption.yourApproval`が`true`だった店に限る——まだ投票の機会が
  無かった店・明示的に選ばなかった店は含めない）。

**他の参加者の回答・投票は一切含めない**——両フィールドとも、この参加者自身が既に持っている
データ（`scheduleQuestions`・`shopVoteQuestions`）から導出できる値であり、集計や他者の識別子を
一切参照しない設計にした。これは人間の意図（「投票後に振りかえられる」という個人的な振り返り
であり、他者の選択の開示ではない）を、スキーマのレベルで機械的に保証するためである——将来の
実装が誤って他者の値を混入させれば、この2フィールドの定義（「この参加者自身の」）に反する
ことが契約上明らかになる。

表示用の店情報（`name`・`genre`・`capacityTier`・`nonSmokingStatus`・`dinnerBudgetTier`）は、
新設した共有スキーマ`LiveProjectedShop`へ切り出し、`decision.shop`（確定した店）と
`decision.yourApprovedShops`の各要素の両方で再利用した——`ADR-0034`決定6の「生きた投影、
永続化しない」という設計をこの2箇所で重複させずに表現するためである。

### 決定4（P6）. `ADR-0040`未決事項1を決着させる

`ADR-0040`が起草時点でFR-028として報告した食い違い——product-brief.md §2の「局面を進める
3操作」という文言と、3値のまま確定済みの`GatheringPhase`enumが、文字どおりには両立しない——を、
人間はenum側を動かさず、§2の文言を実態に合わせる形で決着させた。§2を「局面を進める操作は2つ
（この日にする・確定する）。『この5件で投票する』は幹事の重要操作だが局面は進めない」へ改訂
した。`gathering-scheduling-api.yaml`の`GatheringPhase`のdescriptionも、この決着を反映する
形で更新した（enum自体・列挙値は変更していない）。`ADR-0040`本体の決定・検討した代替案・帰結の
本文はP-06に従い変更せず、`ADR-0040`の未決事項節だけをこの決着で更新した。

### 決定5（自己発見）. `SetShopVotesRequest`スキーマの定義漏れを修正する

本ADRの作業中、`gathering-scheduling-api.yaml`の`setShopVotes`操作が参照する
`SetShopVotesRequest`スキーマ（`$ref: '#/components/schemas/SetShopVotesRequest'`）が、
`ADR-0040`の前回改訂で定義自体を書き忘れていた（宙に浮いた参照）ことにarchitectが気づいた。
`approvedShopIds`（文字列配列、`minItems: 0`、重複不可）として定義を追加した——これは今回の
人間裁定とは独立した、architect自身の監査による修正である。

## 検討した代替案

- **P4を明示せず、現状の「禁止する記述が無い」ままにしておく**: 却下。依頼文が明示的にこの点を
  契約上明示するよう求めており、「意図して許可されている」ことと「たまたま禁止されていない」
  ことを区別できないままにしておくのは、`ADR-0039`が是正したのと同種の曖昧さを残すことになる。
- **`yourApprovedShops`を`shopId`の配列だけにする（店の表示情報を含めない）**: 却下。参加者が
  確定後の画面で「自分がどの店を選んだか」を振り返るには、店名等の表示情報が要る——
  `shopVoteQuestions`側で既に同じ店の情報を返しているため、`decision`側でも同じ形（表示可能な
  形）で返すほうが、browser-interface契約が後から個別に`shopVoteQuestions`と突き合わせる
  手間を要求しない。
- **`yourScheduleResponse`を全候補日ぶんの配列にする（確定日だけでなく）**: 却下。人間の意図は
  「確定した日に自分が行けると言っていたかどうか」という単一の問いへの回顧であり、確定しなかった
  候補日への回答は`decision`の文脈では意味を持たない（`scheduleQuestions`に残っており、
  必要であればそちらから参照できる）。
- **`LiveProjectedShop`を導入せず、`decision.shop`と`decision.yourApprovedShops`の各要素に
  同じ5フィールドをそれぞれインライン定義する**: 却下。同一の店表示形状を2箇所（実質的には
  yourApprovedShopsの配列要素も含めれば複数回）へ重複させるより、共有スキーマを1つ切り出す
  ほうが、将来この形状が変わったときの修正点を1箇所に保てる。

## 帰結

- `contracts/gathering-scheduling-api.yaml`（更新、`version` 0.4.0→0.5.0、ステータス:
  承認待ち）: `LiveProjectedShop`スキーマを新設。`ParticipantView.decision`へ
  `yourScheduleResponse`・`yourApprovedShops`を追加。`SetShortlistedShopsRequest`・
  `InvalidShopSelection`の説明文へP2の境界を明記。`recopyParticipantLink`・
  `GatheringFinalized`の説明文へP4の対照を明記。`GatheringPhase`のdescriptionをP6の決着に
  合わせて更新（enum自体は変更なし）。定義漏れだった`SetShopVotesRequest`スキーマを追加
  （決定5、自己発見の修正）。
- `contracts/gathering-scheduling.feature`（更新）: TDR-GTH-34を改訂し（確定後、参加者自身の
  出欠回答・選んだ店の観測を追加、他の参加者の回答・投票は示されないことを明記）、新規
  TDR-GTH-36（確定後も幹事は既存のリンクを再コピーできる）を追加した。TDR-GTH-01〜33・35の
  本文は変更していない。
- `product-brief.md`: §2の「局面を進める操作」を3つから2つへ改め（P6）、「幹事ダッシュボード」・
  「参加者の回答と店の承認投票」の各節へP5・P6の反映を追加した。§6・§8・§9に本改訂の経緯を
  追記した。
- `adr/0040-merge-shop-narrowing-voting-and-finalization-into-one-slice.md`: 未決事項1
  （FR-028報告）を、本ADRへの参照とともに決着として記録した（決定・検討した代替案・帰結の本文は
  P-06に従い変更していない）。
- `contracts/gathering-scheduling-browser-interface.yaml`は本ADRでは変更しない——`ADR-0040`
  決定6の順序（画面が先）を維持する。designerの5件選定の導線・参加者の確定後画面・幹事の確定後
  画面が承認された後、これらの新フィールド（`yourScheduleResponse`・`yourApprovedShops`等）に
  対応する観測面を追補する。
- `ARCHITECTURE.md`・`design.md`は変更しない——本ADRは既存スライスの契約精緻化であり、モジュール
  境界・依存方向を変えていない。

## 未決事項（次工程・人間への申し送り）

1. **browser-interface契約への反映**: `decision.yourScheduleResponse`・
   `decision.yourApprovedShops`・`recopyParticipantLink`のFINALIZED後の観測面は、
   `gathering-scheduling-browser-interface.yaml`がまだ起こされていないため未反映である
   （`ADR-0040`決定6の順序どおり、designerの画面承認後に追補する）。
2. **`ADR-0035`から持ち越し、引き続き未決**: 会データの保持期間・削除方針、署名付きリンクの
   有効期限日数・レート制限の具体値（いずれも根拠の薄い暫定値）。
3. **`ADR-0040`から持ち越し**: `gathering-list-item`への`data-gathering-title`相当の属性
   追加は、次のbrowser-interface改訂まで未着手のまま残る。
