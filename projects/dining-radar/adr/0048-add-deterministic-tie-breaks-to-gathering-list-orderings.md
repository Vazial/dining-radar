---
id: 0048
scope: project/dining-radar
status: 提案中
date: 2026-09-06
approved_by: null
supersedes: []
superseded_by: null
relates_to: [P-01, P-03, P-08, ADR-0013, ADR-0035, ADR-0038, ADR-0040, ADR-0041,
  ADR-0044, ADR-0045, ADR-0046, TDR-GTH-07, TDR-GTH-37, TDR-GTH-40, TDR-GTH-43]
---

# ADR-0048: 得票同点時の並びを、決定的な二次キーで固定する

> **承認者向けサマリ**: 受け入れテストの全件実行で、`gathering-schedule-question`が見つからない
> 失敗が実行のたびに違う組み合わせで発生した（3回の実行で6件／0件／3件）。実測すると、同じ
> リクエストで作られた4件の候補日の`created_at`が完全に同一値になっていた（4件中distinctな値は
> 1件のみ、データベースの時刻分解能に由来）。`Gathering.candidateDates`は「得票数の降順、同点は
> 作成順」と定義していたが、その作成順の基準（`created_at`）自体が同点で定まらないため、参加者
> 画面が一問一答で描く「最初の候補日」が実行のたびに変わっていた。実利用でも、得票が同数の間は
> ダッシュボードを開くたびに並びが変わりうる——これは人間が別の実機フィードバックで嫌った「並びが
> 動く」現象（`adr/0044`が修正した参加者の店の並び不具合）と同じ種類の劣化である。本ADRは
> `candidateDates`に`startAt`昇順の決定的な二次キーを与え、同じ構造の問題を持つ他の3つの一覧
> （`ShortlistedShop`・参加者リンク一覧・会一覧）にも一貫した方針で二次キーを与える。人間のチャット
> 裁定を経ない、architectの技術判断による決定である（`meta/adr/0064`の作法により`status: 提案中`・
> `approved_by: null`とする。`adr/0037`・`adr/0039`の先例に倣う）。

## 文脈

### 0. 検証の申告（meta/adr/0039）

本ADRの起点となった実測はorchestratorが行い、architectはその報告を受け取った。architectが実際に
確認したのは以下——`grep`で`src/dining_radar/gathering/models.py`の`CandidateDate`・
`ShortlistedShop`・`ParticipantLink`・`Gathering`各モデルの定義を読み、`id`フィールドがいずれも
`models.UUIDField(default=uuid.uuid4, editable=False)`（ランダム値であり、挿入順・作成順のいずれ
とも相関しない）であること、`Meta.ordering`がそれぞれ`["created_at"]`・`["added_at"]`・
`["issued_at"]`・（`Gathering`は`["created_at"]`のみ確認、明示的な二次キーの記述は無い）である
ことを確認した。`services.candidate_dates_with_tallies`関数の実装コード自体は読んでいない——
architectは実装コードを読まない（`.claude/agents/architect.md`の禁止事項）ため、orchestratorの
実測報告（「同点は作成順、Pythonの安定ソート」というdocstringの記述内容）をそのまま事実として
扱った。

### 1. 実測された事実（orchestratorより）

- `CandidateDate.Meta.ordering = ["created_at"]`、`created_at`は`auto_now_add`。
- 同じリクエスト（`createGathering`、複数の`candidateDates`を同時に受け取る）で作られた4件の
  候補日の`created_at`が完全に同一値になった（実測: 4件中distinctな値は1件のみ）。
- `services.candidate_dates_with_tallies`は「得票数（`going_count`）降順、同点は作成順
  （`created_at`昇順、Pythonの安定ソート）」と説明しているが、その作成順自体が同点で定まらない。
- 症状: 受け入れテストの全件実行で`gathering-schedule-question[data-candidate-date-id=...]`が
  見つからない失敗が、実行のたびに異なる組み合わせで発生した（3回の実行で6件／0件／3件）。参加者
  画面は一問一答で「最初の未回答の候補日」しか描画しないため、順序が実行間で食い違うと、テストが
  狙った候補日がその時点の画面に存在しないことがある。
- 同じ構造（`auto_now_add`のタイムスタンプを、同一リクエスト内で複数レコードに同時に書き込み、
  それを一覧の同点二次キーとして使っている）は、`ShortlistedShop.added_at`（`setShortlistedShops`
  が最大5件を1回のリクエストで同時に設定する）にも当てはまる。`ParticipantLink.issued_at`
  （`issueParticipantLinks`の`count`が2以上の場合。ただし承認済み画面は常に`count: 1`で呼ぶため、
  `adr/0036`決定4の運用下では現時点で実際には発生しない）・`Gathering.created_at`（`listGatherings`
  の同点。会の作成は1リクエストにつき1件のみのため衝突頻度はさらに低い）も、原理としては同じ穴を
  持つ。

### 2. 実利用上の意味

上記はテスト実行の非決定性だけの問題ではない。人間は別の実機フィードバックで「並びが動く」ことを
明確に嫌った先例がある（`adr/0044`が修正した、参加者の店の並びが投票のたびに変わって見える不具合。
`gathering-scheduling.feature`のTDR-GTH-37はこの修正の検査として追加された）。得票が同数の候補日・
店が、幹事や参加者がダッシュボードを開き直すたびに違う順番で表示されるとしたら、テストの都合だけで
直す性質のものではなく、同種のユーザー体験の劣化である。

## 決定

### 決定1. `Gathering.candidateDates`の同点二次キーを`startAt`昇順にする

主基準（`goingCount`降順）は変えない。同点の二次キーを、これまで契約が「実装が選ぶ安定順」と
だけ書いていたところから、`startAt`昇順（早い日が先）へ明記する。

**候補として検討した3案と選ばなかった理由**:

- **`id`昇順**: 決定的だが、`CandidateDate.id`はランダムなUUID（`uuid.uuid4`）であり、挿入順とも
  日付とも無関係な、利用者にとって意味の無い順序になる。しかも「得票が同数」という状態は、日程
  調整の初期（誰もまだ回答していない間）に最も高頻度で観測される——このとき一覧の見え方はほぼ
  全面的にこの二次キーが決める。ここで意味の無い順序を選ぶ代償は、頻度で考えると小さくない。
- **`position`（新設の並び順フィールド）**: 意図は最も明確になるが、スキーマ変更・マイグレーション・
  幹事による並べ替えUIの要否といった新しい設計判断を伴う。今回の目的は「同点を安定させる」ことで
  あり、「幹事が手で並べ替えられるようにする」ことではない——後者は`unavailableControls.
  forbiddenPurposes`の`manual-ordering`が明示的に禁じている範囲でもあり、ここで持ち込むと矛盾する。
- **`startAt`昇順（採用）**: 候補日どうしの得票が同数のとき、開催日が早いほうを先に見せるのは
  利用者にとって自然であり、幹事が候補日一覧を眺める初期状態（全員0票）でもチラつかない実用的な
  順序になる。`startAt`は作成後に変更する操作がこの契約に無く（`addCandidateDate`は新規追加のみ、
  既存候補日の日時変更操作は存在しない）、一度定まれば会の生存期間中ずっと不変な値であるため、
  二次キーとして安全である。

この選択により、`candidateDates`の説明文の「作成順」という意味は失われる——`created_at`ベースの
実装が元々表現しようとしていた「入力した順」という意図は、`startAt`昇順（「早い日が先」）という
別の意図に置き換わる。この意味の変化は、既存のどのMustとも矛盾しないと判断した——
`gathering-scheduling.feature`のTDR-GTH-07は「候補日は行ける人が多い順に並ぶ」とだけ述べ、同点の
扱いには一度も触れていない。

### 決定2. `ParticipantView.scheduleQuestions`が`Gathering.candidateDates`と同じ並び・同じ二次キーを使うことを明記する

`gathering-scheduling-api.yaml`はこれまで`ParticipantView.scheduleQuestions`の並び順を一度も
文章にしていなかった——実装は`Gathering.candidateDates`と同じサービス関数を再利用しているため
実質的に同じ順序だったが、契約上は書かれていなかった。これが今回の受け入れテストの失敗
（`gathering-schedule-question`が見つからない）の直接の発生源である——ブラウザ契約の
`scheduleQuestion`は一問一答のワンダードスタイルの描画を許容しており（`cardinality`参照）、
「最初にどれが出るか」は`scheduleQuestions`配列の先頭要素で決まるが、その並びが契約上どこにも
固定されていなかった。決定1と同じ並び・同じ二次キーであることを明記し、
`gathering-scheduling-browser-interface.yaml`の`scheduleQuestion`へ新しい`orderingInvariant`を
追加した（この観測面はこれまで一度も存在しなかった）。

### 決定3. `Gathering.shortlistedShops`/`ShortlistedShop`の同点二次キーを、検索基点からの距離昇順（近い順）、さらに`shopId`昇順にする

主基準（`wantToGoCount + okToGoCount`降順）は変えない。同点は距離昇順（近い順）で決める——これは
`ParticipantView.shopVoteQuestions`が`adr/0044`決定2で既に採用している基準と同じであり、新しい
概念を持ち込まない。理由は決定1と同型: 5件選定直後（誰もまだ投票していない間）は全店が0票で
並び、この一覧も候補日と同じく「投票が始まったばかりの、最も見られる瞬間」に二次キーが支配的に
なる。

`ShortlistedShop`はこれまで暗黙に`added_at`（同一の`setShortlistedShops`呼び出しで設定された
複数店は完全に同一の値を持つ）を二次キーにしていたと考えられ、`CandidateDate.created_at`と全く
同じ穴を持つ。距離もまれに（同じ建物に入る店等）完全に一致しうるため、最後の砦として`shopId`昇順
を添える——`shopId`はプロバイダ由来の安定した文字列であり、この契約に既に露出しているため新しい
フィールドは要らない。

同じ理由で、`ParticipantView.shopVoteQuestions`（近い順、`adr/0044`）にも同じ`shopId`昇順の
最終防波堤を追記した——構造として同じ穴（距離の完全一致というまれなケース）を持つため、一貫した
方針を適用した。実際に観測された不具合ではなく、予防的な整合の追加である。

### 決定4. `listParticipantLinks`/`ParticipantLinkSummary`の同点二次キーを`id`昇順にする

主基準（`issuedAt`昇順）は変えない。同点は、1回の`issueParticipantLinks`呼び出しで複数リンクを
同時に発行する場合（`count`が2以上）にだけ起こり得る——承認済み画面はこれまで常に`count: 1`で
呼んでいる（`ADR-0036`決定4）ため、現時点でこの構成が実際に踏まれることは無いが、`count`が2以上
の値を受け付けるスキーマ上の余地は残っている。同一バッチで発行された複数のリンクの間には、
決定1・3のような「早い日」「近い店」に相当する意味のある業務上の区別が無い——同じ瞬間に発行
された、互いに交換可能な参加者スロットである。したがってここでは意味を求めず、
`ParticipantLinkSummary.id`（この契約に既に露出している、組織者向けの不透明な識別子）昇順を
採用する。

### 決定5. `listGatherings`/`Gathering`の同点二次キーを`id`昇順にする

主基準（`createdAt`降順）は変えない。同点は2つの会が寸分違わぬ瞬間に作られた場合にのみ起こり
得る——`createGathering`は1呼び出しにつき1件の会しか作らないため、上記の一括作成パターンより
現実の衝突頻度はさらに低い。決定4と同じ理由で意味のある二次基準が無いため、`Gathering.id`昇順を
採用する。

## 検討した代替案

- **4つの一覧すべてに`id`昇順で統一する**: 一貫性は最も高いが、決定1の検討で述べたとおり、
  候補日は「得票同数」の状態を高頻度で経験する一覧であり、そこでランダムなUUID順を採用する代償が
  大きいと判断した。`shortlistedShops`も同様の頻度の高さを持つ。一貫性よりも、実際に利用者が見る
  頻度が高い場面での意味のある順序を優先した。
- **`ShortlistedShop`にも新しい`position`的な概念を導入する**: 不採用。決定1と同じ理由
  （`manual-ordering`禁止との緊張、スコープの逸脱）。
- **何もしない（実装のソートを安定ソートに変えるだけで契約は変更しない）**: 不採用。今回の欠陥の
  核心は「契約が二次キーを固定していなかったこと」自体であり、契約を変えずに実装だけを直しても、
  次に別の実装判断（別のdeveloper、別の言語への移植等）が同じ轍を踏む可能性が残る。P-03
  （実行可能な層で表現する）にも反する——この決定は契約が持つべき情報である。

## 帰結

- `contracts/gathering-scheduling-api.yaml`をv0.8.0→v0.9.0へ改訂した（本ADRと同一PR）。
  - `Gathering.candidateDates`・`ParticipantView.scheduleQuestions`（新規の説明文）: 決定1・2。
  - `ShortlistedShop`・`Gathering.shortlistedShops`・`ParticipantView.shopVoteQuestions`: 決定3。
  - `ParticipantLinkSummary.issuedAt`: 決定4。
  - `Gathering.createdAt`・`GatheringListResponse.gatherings`: 決定5。
- `contracts/gathering-scheduling-browser-interface.yaml`をcontractVersion 0.8.0→0.9.0へ改訂した
  （同一PR）。
  - `organizerDashboard.candidateDateList.orderingInvariant`の「implementation-chosen stable
    tie-break」という文言を、決定1の具体的な二次キーへ置き換えた——これが本ADRの直接の動機である
    受け入れテストの失敗を機械的な意味でも解消する記述である。
  - `participantAnswer.scheduleQuestion`へ新規`orderingInvariant`を追加した（決定2、これまで
    一度も存在しなかった）。
  - `organizerDashboard.shortlistedShopVotes.list.orderingInvariant`・
    `unavailableControls.forbiddenPurposesNote`・`participantAnswer.shopVoteQuestion.
    orderingInvariant`: 決定3の二次キーを追記した。
  - `organizerGatheringList.list.orderingInvariant`・`participantLinkList.orderingInvariant`・
    `unavailableControls.forbiddenPurposesNote`: 決定4・5の二次キーを追記した。
  - `contractVersion`を`0.8.0`→`0.9.0`へ改めた。
- `contracts/gathering-scheduling.feature`へ新規シナリオTDR-GTH-43を追加した——得票が同数の候補日
  でも、並び順は開くたびに変わらないことを検査する。既存シナリオ（TDR-GTH-01〜42）は本文を変更
  していない。
- `product-brief.md`は変更しない——同点時の並びは元々product-briefが踏み込んで定めていた粒度では
  なく、この決定はcontract層だけで閉じる。
- `ARCHITECTURE.md`・`design.md`は変更しない——本ADRは新しいモジュール境界を生まない。

## 未決事項（次工程・人間への申し送り）

1. `startAt`を`candidateDates`の同点二次キーに選んだことで、この契約の「同点は作成順」という
   過去の暗黙の意図（このコメントは契約自体にはなく、実装のdocstringにのみ存在した）が「早い日が
   先」に変わる。この意味の変化そのものは、既存のどのMustとも矛盾しないと判断したが（決定1参照）、
   人間の意図と異なる可能性はゼロではない。
2. `ShortlistedShop`／`shopVoteQuestions`の「距離が完全に一致する場合」の`shopId`昇順は、実際に
   観測された不具合ではなく、本ADRの一貫性の観点から予防的に追加したものである。過剰な予防だと
   判断されれば、この部分だけ切り離して見送ることもできる。
3. TDR-GTH-43は候補日の並び安定性だけを検査する新規シナリオである。`ShortlistedShop`の並び安定性
   （決定3）に対応する並行シナリオは追加していない——TDR-GTH-40が主基準の並びを既に検査しており、
   二次キーだけを狙った追加シナリオは、TDR-GTH-43とほぼ機械的に同型になると判断したため見送った。
   必要であれば人間の指示で追加する。
4. 実装側（`services.candidate_dates_with_tallies`等のソート実装、Djangoモデルの`Meta.ordering`）
   への反映はdeveloperの領分であり、本ADRは契約の改訂のみを扱う。
