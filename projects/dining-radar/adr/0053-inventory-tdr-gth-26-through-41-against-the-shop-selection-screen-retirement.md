---
id: 0053
scope: project/dining-radar
status: 提案中
date: 2026-09-11
approved_by: null
supersedes: []
superseded_by: null
relates_to:
  [P-02, P-04, P-06, P-08, ADR-0037, ADR-0043, ADR-0044, ADR-0049, ADR-0050,
   ADR-0051, ADR-0052, TDR-GTH-26, TDR-GTH-27, TDR-GTH-28, TDR-GTH-29,
   TDR-GTH-30, TDR-GTH-31, TDR-GTH-32, TDR-GTH-33, TDR-GTH-34, TDR-GTH-35,
   TDR-GTH-36, TDR-GTH-37, TDR-GTH-38, TDR-GTH-39, TDR-GTH-40, TDR-GTH-41,
   TDR-GTH-44, TDR-GTH-45, TDR-CS-17, TDR-CS-18, TDR-CS-19]
---

# ADR-0053: TDR-GTH-26〜41を店選び画面の廃止・可視性の反転・カレンダー統一に照らして棚卸しする

> **承認者向けサマリ**: ADR-0052がFR-028の流儀で解消せず申し送った宿題——
> `GATHERING_OPEN_SHOP_WEEKDAY_MATCH`の説明文がTDR-GTH-26/27/38/39について、ADR-0049で
> 削除済みの`OpenShopPreviewItem`スキーマを読めと指示したまま残っていたこと、および
> 「TDR-GTH-26〜41全体を、廃止された幹事ダッシュボード内の店選び一覧（`shortlistSelection`）を
> 前提にしたまま残っている可能性に照らして棚卸しする」こと——に対応する。
>
> **結論**: TDR-GTH-26〜41の16本すべてを1本ずつ確認した結果、**`gathering-scheduling.feature`
> 本文の書き換え・廃止を要したシナリオは1本も無かった**。いずれも業務の言葉（画面名・API名・
> スキーマ名を含まない）で書かれており、店選びの一本化・可視性の反転・カレンダー統一のいずれも、
> これらのシナリオが検査する業務規則そのものを変えていない——変わったのはその業務規則を
> どの画面・どの契約要素が実現するかだけである。**唯一の実害は`test-support-api.yaml`側に
> あった**——受け入れテストがGiven状態を組み立てる技法の説明文が、削除済みスキーマを名指しした
> まま放置されていた。本ADRはその説明文を、実在するスキーマ（`candidate-search-api.yaml`の
> `Candidate`・`gathering-scheduling-api.yaml`の`ParticipantShopVoteOption`）を指す記述へ
> 書き換える。
>
> **副産物**: 棚卸しの過程で、TDR-GTH-26/27/38が、`candidate-search.feature`のTDR-CS-17/18
> および`candidate-search-api.yaml`のGiven-state配線と業務的に重なることを確認したが、この
> 重なりは`gathering-scheduling.feature`・`candidate-search.feature`双方のヘッダコメントが
> 2026-09-08時点で既に「同じ業務規則をこの画面から見た記述」として意図的に設計した対（TDR-GTH-44
> ⇄ TDR-CS-17、TDR-GTH-45 ⇄ TDR-CS-19）の自然な延長であり、新しい矛盾ではない——本ADRは
> これを問題として扱わない。

## 文脈

### 0. 検証の申告（meta/adr/0039）

本ADRが前提とする契約記述は、`gathering-scheduling.feature`（TDR-GTH-01〜48、2026-09-08〜09
追補7まで）・`candidate-search.feature`（TDR-CS-00〜19）・`gathering-scheduling-api.yaml`
（`setShortlistedShops`・`ParticipantShopVoteOption`・`InvalidShopSelection`の記述を含む）・
`candidate-search-api.yaml`（`Candidate`スキーマの`shopId`/`isShortlisted`/`location`/
`walkingTimeMinutes`/`providerPageUrl`/`capacityTier`/`nonSmokingStatus`/`dinnerBudgetTier`
を含む）・`test-support-api.yaml`（v1.5.6、本ADRと同一作業で1.5.7へ改訂）・adr/0049・0050・
0051・0052を実際に読んで確認した。確認していないのは、これらの契約が前提とする実装コードの
挙動そのもの——architectは実装コードを読まない（`.claude/agents/architect.md`の禁止事項）。
ただし、`setShortlistedShops`が「送信された各shopIdは確定候補日の開店母集団に属さなければ
ならず、さもなくば`INVALID_SHOP_SELECTION`で拒否される」と契約が既に明記していることは
`gathering-scheduling-api.yaml`本文（`SetShortlistedShopsRequest.shopIds`の記述）から確認した
——これはTDR-GTH-27の業務規則が新しい画面構成の下でも契約上どこで強制されるかを特定するために
必要な確認であり、実装コードを読むことなく契約だけから判定できた。

### 1. 何が起きたか

ADR-0052は、tester がTDR-GTH-31・32相当のGiven状態を`adr/0049`後の会モード経由で組み立てる
過程で発見した`GATHERING_OPEN_SHOP_WEEKDAY_MATCH`の脆さ（候補日を変えて2回問い合わせ差分を
取る技法が偶発的に破綻しうる）を解決したが、その過程で副次的に、同モードの説明文が
`OpenShopPreviewItem.shopId`（TDR-GTH-26/27向け）・`OpenShopPreviewItem`/
`ParticipantShopVoteOption`（TDR-GTH-38/39向け）という、ADR-0049決定2で既に削除済みの
スキーマを指したまま残っていることを発見した。ADR-0052はこれを**解消せず申し送った**——
「TDR-GTH-26〜41全体のGiven-state構築手段の棚卸しは、これらのシナリオが実装される回の対象で
あり、本ADRの範囲を超える」という理由で、staleである事実だけを明記するに留めていた。

本ADRはその申し送りを引き取り、`gathering-scheduling.feature`のTDR-GTH-26〜41を1本ずつ確認する。

### 2. なぜ1本ずつ確認する必要があったか

ADR-0049・0050・0051は、次の5点で会・候補日・参加者の画面構成とデータモデルを変えた——
(1) 店選びの画面（`shortlistSelection`、`OpenShopPreviewItem`・`previewShops`を含む）が廃止され
`candidate-search`の会モードへ一本化された、(2) 日程段階の店プレビューが件数だけになった、
(3) 参加者の可視性規則が反転した（自分が答える前から他の人の回答が見える）、(4) 確定後の記録から
店ごとの一覧が削られた、(5) 候補日がカレンダーの複数選択に統一された。これらはいずれも
TDR-GTH-26〜41が書かれた時点（2026-09-03〜05）には存在しなかった前提であり、シナリオ本文が
今なお成立するかどうかは、業務の言葉で書かれているという理由だけでは自動的に保証されない
——確認が要る。

## 決定

### 決定1. TDR-GTH-26〜41を1本ずつ判定する（下表）

各シナリオについて、(a)そのまま成立する、(b)文面の改訂が要る、(c)前提が消えたので廃止すべき、
のいずれかを判定した。判定はすべて`gathering-scheduling.feature`本文（業務の言葉）と、それを
実現する契約要素（`-api.yaml`）を突き合わせて行った。

| シナリオ | 判定 | 理由 |
|---|---|---|
| TDR-GTH-26（幹事が開いている店を最大5件選んで投票を始める） | (a) | 「開いている店から5件を選ぶ」という業務規則は、選ぶ操作の主体がランチ候補画面（会モード）に移った後も変わらない。ADR-0049自身が同じ結論を明記済み（本文末尾の2026-09-08〜09追補7）。 |
| TDR-GTH-27（投票にかけられるのはその日に開いている店だけ） | (a) | 「その店は選べない」という業務規則は、UIが閉店中の店をそもそも候補一覧に出さない（母集団絞り込み、ADR-0049決定1）という形でも、`setShortlistedShops`が母集団外のshopIdを`INVALID_SHOP_SELECTION`で拒否する（`gathering-scheduling-api.yaml`既存記述）という形でも、どちらでも満たされる。契約上どちらの経路でも「選べない」が成立するため書き換えは不要——Given状態の組み立て技法（閉店shopIdの入手経路）だけがADR-0052決定2で更新済みである。 |
| TDR-GTH-28（参加者が店ごとに三段階で答える） | (a) | 参加者の投票画面自体は変更対象外。 |
| TDR-GTH-29（可視性、店の投票版） | (a) | ADR-0050決定2により本文が全面改訂済み・現在の規則と一致している。今回はそのまま。 |
| TDR-GTH-30（投票はいつでも変更できる） | (a) | 変更対象外。 |
| TDR-GTH-31（差し替えで残した店の票は引き継がれる） | (a) | 「差し替える」は業務言語であり、実装が単一の置換操作か2回のトグル（外す＋入れる）かを特定しない。`setShortlistedShops`が引き続き完全置換の意味論を持つため（ADR-0049は形状を変えていない）、業務規則は成立する。 |
| TDR-GTH-32（差し替えで加わった店は未回答のまま残る） | (a) | 同上。 |
| TDR-GTH-33（幹事が日と店を確定する） | (a) | 変更対象外。 |
| TDR-GTH-34（確定後の記録） | (a) | ADR-0050決定3により本文が簡素化済み・現在の規則と一致している。今回はそのまま。 |
| TDR-GTH-35（確定後は新しいリンクを発行できない） | (a) | 変更対象外。 |
| TDR-GTH-36（確定後も既存リンクは再コピーできる） | (a) | 変更対象外。 |
| TDR-GTH-37（参加者の店の並びは近い順、投票しても変わらない） | (a) | 参加者の投票画面自体は変更対象外。 |
| TDR-GTH-38（幹事が店を選ぶ画面で地図と店の情報を確認できる） | (a) | 「幹事が店を選ぶ画面」は固有名詞ではなく、その画面が今はランチ候補画面（会モード）を指す。`candidate-search-api.yaml`の`Candidate`スキーマ（会モードで`shopId`/`isShortlisted`が非nullになる同じ要素）は既に`location`/`walkingTimeMinutes`/`providerPageUrl`/`capacityTier`/`nonSmokingStatus`/`dinnerBudgetTier`を持ち、本文が求める内容を満たす。書き換えは不要——ただしこの事実は`candidate-search.feature`側の既存の基盤シナリオ（すべての候補カードが地図・facts一式を持つ）が独立に保証している内容の再確認でもあり、次にこの契約を書き直す回で統合を検討する余地がある（下記「未決事項」参照）。 |
| TDR-GTH-39（参加者が投票する画面で地図と店の情報を確認できる） | (a) | 参加者の投票画面（`ParticipantShopVoteOption`）は`adr/0049`で廃止されていない。変更対象外。 |
| TDR-GTH-40（幹事が三段階の内訳を見て確定する店を選ぶ） | (a) | 幹事ダッシュボードの投票タリー画面（`shortlistedShopVotes`）はADR-0049決定1が明示的に維持している。変更対象外。 |
| TDR-GTH-41（参加者の投票画面の地図に検索基点も示される） | (a) | 変更対象外。 |

**16本すべてが(a)（そのまま成立する）と判定した**。(b)文面の改訂・(c)廃止のいずれを要する
シナリオも見つからなかった。

### 決定2. `test-support-api.yaml`の`GATHERING_OPEN_SHOP_WEEKDAY_MATCH`説明文のstale参照を解消する

ADR-0052が申し送った、TDR-GTH-26/27向けの`OpenShopPreviewItem.shopId`という記述と、
TDR-GTH-38/39向けの`OpenShopPreviewItem`/`ParticipantShopVoteOption`という記述を、次のとおり
書き換える。

- TDR-GTH-26は、対象の会自身の`proposeCandidates`応答（会モード）から
  `candidate-search-api.yaml`の`Candidate.shopId`を直接読む——会モードの母集団は定義上
  その会の確定日に開いている店だけであり、返る候補は常にshopIdを持つ。
- TDR-GTH-27は、閉店している形のshopIdを、その形が開いている**別の曜日で確定した別の会**
  （companion gathering）の`proposeCandidates`応答から読む——ADR-0052決定2が確立した手順を
  そのまま使う。読み取ったshopIdを目的の会の`setShortlistedShops`へ渡すと
  `INVALID_SHOP_SELECTION`で拒否される。
- TDR-GTH-38は、`candidate-search-api.yaml`の`Candidate`スキーマ（会モード）を読む——この
  画面自体がADR-0049決定1でランチ候補画面へ移ったため。
- TDR-GTH-39は、引き続き`gathering-scheduling-api.yaml`の`ParticipantShopVoteOption`を読む
  ——このスキーマはADR-0049で削除されていない。

新しいoperationId・新しいスキーマ・新しいシナリオIDはいずれも追加しない
（`x-acceptance-scenarios`各listは無変更）。`version`を1.5.6→1.5.7へ更新した。

### 決定3. `gathering-scheduling.feature`・`candidate-search.feature`は変更しない

決定1の判定どおり、両ファイルの本文はいずれも変更を要しない。両ファイルへの新しいヘッダ
追補も加えない——ADR-0051が同様に「契約内容は変わるが対象ファイルの本文は変わらない」
判断を下した際、`gathering-scheduling.feature`にヘッダ追補を加えなかった先例（本ファイルに
adr/0051・0052への言及が1件も無いことで確認済み）に倣う。ヘッダ追補は本文が実際に変わった
ときにのみ追加するという、このファイル自身が一貫して守ってきた運用を維持する。

## 検討した代替案

- **TDR-GTH-38を、`candidate-search.feature`側の基盤シナリオへ統合・撤退させる**: 見送った。
  重なりは事実だが、`gathering-scheduling.feature`側の記述は「幹事が店を選ぶ場面でもこの情報が
  見える」という、この機能スライスの視点からの独立した業務要求の表明であり、他スライスの
  シナリオへ吸収させると、`gathering-scheduling.feature`だけを読む者がこの要求の存在に
  気づけなくなる。TDR-GTH-44⇄TDR-CS-17のような意図的な対を持つ設計とも整合する。整理する
  価値はあるかもしれないが、それは契約の可読性の改善であって「成立しない」ことの是正ではなく、
  今回の棚卸しの範囲（成立するかどうかの判定）を超える。
- **TDR-GTH-27の判定を(b)とし、「投票にかけようとする」を「候補一覧に出てこない」という
  記述へ書き換える**: 見送った。業務の言葉としては「その店は選べない」のほうが、UIの実現方法
  （出てこないのか、出てくるが拒否されるのか）を特定しない分だけ頑健である。契約上どちらの
  経路でも成立することを確認した以上、書き換える理由が無い——書き換えるとむしろ実装方法を
  1つに固定してしまい、将来UIが変わるたびに再改訂を要する余計な結合を生む。
- **stale参照を`test-support-api.yaml`側で削除するのではなく、新しい追記として残す
  （adr/0052の流儀を踏襲する）**: 見送った。adr/0052決定4が追記に留めたのは「棚卸しが
  終わっていないため、何が正しい参照かがまだ分からない」ためだった。本ADRで棚卸しが完了し、
  正しい参照（`Candidate`・`ParticipantShopVoteOption`）が判明した以上、誤った参照を文書内に
  残す理由はない——P-06は決定の置き換えを求めるのであって、誤りの保存を求めない。

## 帰結

- `contracts/test-support-api.yaml`（改訂、v1.5.6→v1.5.7、本ADRと同一作業で完了済み）:
  `GATHERING_OPEN_SHOP_WEEKDAY_MATCH`説明文・`setCandidateProposalAcceptanceState`の説明文の
  stale参照を解消した（決定2）。新しいoperationId・スキーマ・シナリオIDは追加していない。
- `contracts/gathering-scheduling.feature`・`contracts/candidate-search.feature`: **変更して
  いない**（決定1・決定3）。TDR-GTH-26〜41の16本すべてが(a)と判定され、書き換え・廃止を
  要するシナリオは無かった。
- `ARCHITECTURE.md`・`design.md`: 変更しない——新しいモジュール境界を生まない。

## 未決事項（次工程・人間への申し送り）

1. **本ADR自体の承認**: `status: 提案中`のまま起草した（`meta/adr/0064`決定1の書式、
   `adr/0037`・`adr/0039`・`adr/0052`の先例と同じくarchitectの技術判断として
   `approved_by: null`）。
2. **TDR-GTH-38と`candidate-search.feature`の基盤シナリオとの重なりの整理**（検討した代替案の
   1点目）は、契約の可読性改善として次にこのファイルを書き直す回で検討する余地がある——本ADRは
   「成立するかどうか」だけを判定し、「整理する価値があるか」には立ち入らない。
3. **決定2が記載する発見手順が、実装コードとして本当に成立するか**は未検証——architectは
   実装コードを書かないため、developer/testerが実際にTDR-GTH-26/27/38/39をこの手順で組み立てる
   段で、手順自体の実行可能性を確認する必要がある（ADR-0052未決事項3と同じ性質の申し送り）。
