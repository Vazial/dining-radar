---
id: 0056
scope: project/dining-radar
status: 承認済み
date: 2026-09-12
approved_by: "人間裁定（2026-09-12 チャット選択肢UI、第1束〜第5束）: 5束の板が申し送った
  『契約に足りない要素』（20件）のうち、画面の構成（ADR-0054）でも既存決定の反転（ADR-0055）
  でもなく、この製品にまだ存在しない値・観測面を新しく持たせる必要があるもの——誰が・どの候補日に
  ・何と答えたかを幹事へ運ぶ値、候補日を消す操作、月送り矢印と選択日削除の宣言済み操作、地図
  ピンの会員状態属性、投票タリー画面の店の機械可読情報、『あとから入りました』の印、5件到達理由、
  会モード時のcandidate-gathering-entryの振る舞い、参加者向けの会の総人数、確定後の店の場所を
  見せる観測面、削除後・発行終了を示す面、確定の確認に置く『変わることの表』、会の保持期間の
  決着（手で消すまで残る）。各項目の要旨は本ADR各決定に記載のとおり。すべて確定・再交渉不可。"
supersedes: []
superseded_by: null
relates_to:
  [P-02, P-04, P-05, P-06, P-08, P-11, ADR-0018, ADR-0034, ADR-0035, ADR-0044,
   ADR-0046, ADR-0049, ADR-0050, ADR-0054, ADR-0055, FR-033, FR-036,
   TDR-GTH-08, TDR-GTH-38, TDR-GTH-39, TDR-GTH-44, TDR-GTH-45, TDR-GTH-48]
---

# ADR-0056: 会の画面群に、これまで存在しなかった値・観測面を追加する

> **承認者向けサマリ**: `ADR-0054`（画面の構成・導線）・`ADR-0055`（既存決定の反転）と同じ
> 2026-09-12の一連の裁定のうち、**この製品にまだ存在しない値・観測面を新しく持たせる**必要が
> ある決定をまとめる（性格(c)）。5束の板が申し送った「契約に足りない要素」20件のうち、
> `ADR-0054`・`ADR-0055`が扱わない残り13件がここに入る。
>
> **決定の要点**: (1) 幹事ダッシュボードへ、参加者ごと・候補日ごとの回答を運ぶ表の値
> （`ADR-0055`決定4が開いた境界の実体）を新設する——これが5束を通じて最大の不足だった。
> (2) 候補日を削除する操作（`removeCandidateDate`）を新設する——足せるが取り除けない現状を
> 埋める。(3) カレンダーの月送り矢印・選んだ日一覧の削除（×）を、宣言済みの操作的コントロール
> として追加する——これが宣言されていないこと自体が、FR-033が記録した「年が更新されない」
> 不具合の副作用の根だった。(4) 候補検索の地図ピンに、カードと同じ会員状態の属性を追加する。
> (5) 幹事の投票タリー画面（`ADR-0055`決定5が地図・店情報を足すと決めた画面）の具体的な観測面
> （名前・徒歩・地図・ピン・店のページの各testId）を定める。(6) 「あとから入りました」の印を
> 幹事・参加者共通の観測面として追加する。(7) 5件到達時にその理由を言う要素を追加する。
> (8) 会モードにおける`candidate-gathering-entry`の振る舞いを定義する。(9) 参加者向けの応答へ
> 会の総人数を運ぶ値を追加する。(10) 参加者の確定後画面に店の場所を見せる観測面を追加する
> ——**APIの変更は不要**、値は既に`LiveProjectedShop`/`ParticipantView.searchOrigin`にある。
> (11) 会の削除・確定に付随する3つの面（削除後の一覧遷移は`ADR-0054`が決定済み、リンク発行
> 終了の面、確定の確認に置く「変わることの表」）を追加する。(12) 会の保持期間の未決を決着させる
> ——「手で消すまで残る」。

## 文脈

### 0. 検証の申告（meta/adr/0039）

本ADRが前提とする既存契約の記述は、`gathering-scheduling-api.yaml`（v0.10.0）・
`gathering-scheduling-browser-interface.yaml`（contractVersion 0.11.0）・
`candidate-search-api.yaml`（v1.3.0）・`candidate-search-browser-interface.yaml`
（contractVersion 1.8.0）を実際に読んで確認した——`ParticipantLinkSummary`・
`CandidateDate`のいずれにも「誰が・どの候補日に・何と」を結ぶ値が無いこと、
`organizerGatheringCreate`/`addCandidateDateForm`のカレンダーがいずれも月送り・削除操作を
`allowedPurposes`に持たないこと（両方とも「この契約はカレンダーの表示月範囲を固定しない」と
明記するのみ）、`candidate-map-marker`に`data-gathering-shortlisted`相当の属性が無いこと
（カードの`candidate-card`だけが持つ）、`ParticipantView`に会全体の人数を運ぶフィールドが
無いこと（`respondedParticipantCount`はいずれも1候補日・1店に閉じた分母）を、それぞれ実際の
記述として確認した。designerの板（`b1-create`・`b2-schedule`・`b3-shops`・`b4-vote`・
`b5-final`、とくに`b5-final/Main.dc.html`の申し送り表）と`activeContext.md`を読んだ。
確認していないのは実装コードの挙動そのものである。

## 決定

### 決定1（第2束）. 幹事ダッシュボードへ、誰が・どの候補日に・何と答えたかを運ぶ値を新設する

`ADR-0055`決定4が開いた境界（幹事に個人の回答を見せてよい）を実現する値を、
`gathering-scheduling-api.yaml`へ新設する。`ParticipantLinkSummary`（`id`・`issuedAt`・
`hasResponded`・`revoked`・`displayName`）へ、新規フィールド`scheduleResponses`
（配列、各要素`{candidateDateId, status}`、`status`は`ScheduleResponseStatus`と同型、未回答の
候補日は配列に含めない）を追加する——**候補日の集計側（`CandidateDate`）を個人単位に分解する
のではなく、リンク側に本人の全候補日への回答をぶら下げる**設計とする。理由は、第2束の板が
示した表（行が人、列が候補日）を1回の`listParticipantLinks`呼び出しで構成できるようにする
ため——候補日ごとに参加者一覧を問い合わせる往復を増やさない。

**店の投票は含めない**——本決定は日程回答（第2束の表）に限る。店の投票を幹事の個人単位の表に
含めるかどうかは、第3・4束の裁定がこの表の存在に言及していないため、本ADRでは決定しない
（下記未決事項）。

### 決定2（第2束）. 候補日を削除する操作を新設する

`gathering-scheduling-api.yaml`に新しい操作`removeCandidateDate`
（`DELETE /gatherings/{gatheringId}/candidate-dates/{candidateDateId}`）を新設する。
`addCandidateDates`で足せるが取り除けない現状（板の指摘、B2-2）を埋める。**確定済みの候補日
（`CandidateDate.isConfirmed`が真、すなわち開催日として確定した候補日）は削除できない**——
新しいエラーコード`CANDIDATE_DATE_CONFIRMED`で拒否する。**局面が`SCHEDULING`でなくなった後
（`SELECTING_SHOP`・`FINALIZED`）は候補日の集合そのものが意味を失っているため、削除操作自体を
`GATHERING_NOT_IN_SCHEDULING_PHASE`で拒否する**（新しいエラーコード）。この操作を呼んだ結果、
候補日が0件になることは許容する——会の作成には候補日1つ以上が必要という制約
（`ADR-0035`決定1）は作成時にのみ適用され、作成後の削除には及ばない（同じ非対称は
`revokeParticipantLink`が既にリンクの取り消しと発行数の関係で持っている）。

### 決定3（第1束）. カレンダーの月送り矢印・選択日削除（×）を宣言済みの操作として追加する

`gathering-scheduling-browser-interface.yaml`の`organizerGatheringCreate.calendar`・
`addCandidateDateForm.calendar`（それぞれ`ADR-0051`・`ADR-0049`決定3が新設したカレンダー）へ、
次の新規要素を追加する。

- **月送り矢印**: `gathering-create-candidate-date-month-previous`/`-next`（会をつくる画面）・
  `gathering-add-candidate-date-month-previous`/`-next`（候補日を足す画面）。新設purpose
  `gathering-*-candidate-date-month-navigate`を`allowedPurposes`へ追加する。活性化すると
  表示中の月が1か月前・後に変わる（クライアント側の表示状態のみ、公開操作は呼ばない）。
- **選んだ日一覧の削除（×）**: `gathering-create-candidate-date-remove-selected`/
  `gathering-add-candidate-date-remove-selected`（新設purpose）。選んだ日の一覧（見えていない
  月に選んだ日も含む）から、押した日を選択解除する——`gathering-*-candidate-date-day`本体を
  再度押すのと同じ効果（選択済みの状態を解く）だが、その日を表示する月へ移動しなくても解除
  できる、という別の入力経路を提供する。

**これがFR-033の根を断つ**——`ADR-0054`決定3が記録したとおり、月送り矢印が
`allowedPurposes`に宣言されていなかったことが、「年が更新されない」不具合を回避するために
年表示を静的化した副作用の遠因である。本決定でこれを正式な操作的コントロールとして宣言する
ことにより、この種の回避策自体が不要になる。

### 決定4（第3束）. 候補検索の地図ピンへ会員状態の属性を追加する

`candidate-search-browser-interface.yaml`の`candidate-map-marker`へ、`candidate-card`が既に
持つ`data-gathering-shortlisted`と同じ意味の属性（`data-gathering-shortlisted`、会モード時
のみ非null）を追加する——カードとピンの相互強調表示（`candidate-search-browser-interface.yaml`
既存の規則）に、会に入れた状態の視覚的対応も揃える。

### 決定5（第3・4束）. 幹事の投票タリー画面（`shortlistedShopVotes`）の具体的な観測面

`ADR-0055`決定5が「地図・店の情報を足す」と決めたことを受け、`gathering-shortlisted-shop-item`
へ次の属性・子要素を追加する——参加者側の`shopVoteQuestion`が既に持つものと同じ形にする。

- `name`（店名、`data-shop-name`）
- `walkingTimeMinutes`（徒歩の目安、`data-walking-time-minutes`）
- 地図: `gathering-shortlisted-shop-map`／`gathering-shortlisted-shop-map-marker`
  （店のピンのみ、`ADR-0046`決定2が参加者側に定めた「検索基点は出さない」制約をここでも維持
  する——本画面は幹事の認証済み画面であり検索基点は既に別の場所で開示されているため、この
  制約は開示を防ぐためではなく、地図の役割をこの画面では「店どうしの位置関係」に絞るためで
  ある）
- `providerPageUrl`への線: `gathering-shortlisted-shop-page-link`

これらは`ADR-0044`決定4が幹事の選定画面・参加者の投票画面へ既に追加した同種の要素と同じ設計
（表示のたびに引き直す生きた投影、会のレコードへは永続化しない）を踏襲する。

### 決定6（第3・4束）. 「あとから入りました」の印を幹事・参加者共通の観測面として追加する

`gathering-shortlisted-shop-item`（幹事側）・`shopVoteQuestion`の各選択肢（参加者側）へ、
新規属性`data-added-after-voting-started`（真偽値）を追加する——`Gathering.votingStartedAt`が
非nullになった後に`setShortlistedShops`で新しく加わった店を`true`とする。D7（差し替え時の
振る舞い、`ADR-0035`）が既に定める業務規則（新しく加えた店は、その時点で投票済みの参加者には
未回答のまま残る）の可視化であり、新しい業務規則を持ち込むものではない。幹事・参加者で
**同じ言葉**を使う（人間裁定）——文言は実装/L5の裁量だが、この属性名自体は両画面で共有する。

### 決定7（第3束）. 5件到達時にその理由を言う要素を追加する

候補検索の会モードの帯（`ADR-0049`決定1の`gatheringContext`表示）へ、新規属性
`data-shortlist-limit-reached`（真偽値、`shortlistedShopCount >= maxShortlistedShops`と
一致）を追加する——`candidate-card`の「この会に入れる」が非活性になる理由
（`ADR-0049`決定8）を、帯の側からも機械観測可能にする。

### 決定8（第3束）. 会モードにおける`candidate-gathering-entry`の振る舞いを定義する

`ADR-0054`決定1が常設化した`candidate-gathering-entry`は、会モードで開かれているときは
「いま入っている会」を示す状態（`data-active-gathering-id`、会モード時のみ非null）を持つ
——通常モード（会と無関係にこの画面を開いたとき）ではこの属性は不在のままとする
（`ADR-0049`決定1が既に定める「会モードでないときは帯もボタンも一切出ない」という原則を、
このナビゲーション要素にも一貫して適用する）。

### 決定9（第4束）. 参加者向けの応答へ会の総人数を運ぶ値を追加する

`ParticipantView`へ新規フィールド`totalActiveParticipantCount`（整数、`Gathering.
activeParticipantLinkCount`と同値）を追加する——票の帯を「全員の人数」で固定し、票の薄い店が
帯の短さで分かるようにする、という第4束の裁定に必要な分母である。**この値は「共有リンクを
何人が開いたか」ではない**——`product-brief.md`§2が既に確立している「共有リンクを何人が
開いたかを製品側は把握できない」という制約はそのまま維持する。`activeParticipantLinkCount`は
幹事が発行し取り消していないリンクの数であり、実際に参加する人数の保証ではない——この性質の
違いを`ParticipantView`のフィールド説明に明記する。

### 決定10（第5束）. 参加者の確定後画面に店の場所を見せる観測面を追加する——APIの変更は不要

`finalizedView.decision`へ、地図（`gathering-participant-decision-map`）・
ピン（`gathering-participant-decision-map-marker`、決まった店の位置）・
基点の印（`gathering-participant-decision-origin-marker`）・
徒歩の目安（`data-walking-time-minutes`）・店のページへの線
（`gathering-participant-decision-page-link`）を追加する。**値は既に契約上に存在する**——
`decision.shop`（`LiveProjectedShop`型、`location`/`walkingTimeMinutes`/`providerPageUrl`を
既に持つ、`ADR-0044`決定4）と`ParticipantView.searchOrigin`（確定後も非null、`ADR-0045`決定1）
であり、**API層（`gathering-scheduling-api.yaml`）の変更は要らない**——ブラウザ契約
（`gathering-scheduling-browser-interface.yaml`）に観測面を追加するだけである。**2点を結ぶ線は
描かない**——決まった店のピンと基点の印は別々のマーカーとして地図に置き、両者を結ぶ経路線は
一切描画しない。理由は、この製品が経路検索サービスへ問い合わせない（`product-brief.md`§3が
既に確立している境界）ため、道なりの正確な経路を主張する情報を持っていないからである。持って
いないものを絵で言わない。同じ理由で、徒歩の同心リング（比べる相手がいない一点だけの表示に
輪を描く意味がない）もこの画面には描かない。

### 決定11（第4・5束）. 削除・確定に付随する残りの観測面

- **確定の確認に「変わることの表」を置く**: `gathering-finalize-submit`の確認面
  （`ADR-0054`決定5が構造を定めた`-confirm-dialog`）へ、`gathering-finalize-confirm-changes`
  （3行の表: 回答リンク／参加者の画面／日と店、それぞれ「前」→「後」の変化）を追加する。
  文ではなく矢印の表で示す——「承認のための説明文を画面に置かない」という`ADR-0055`決定3の
  方針に触れない形（読ませる文ではなく、見て分かる形）。
- **「発行はおわり」を示す面**: `participantLinkList`は確定後に`gathering-participant-link-copy`
  が不在になることを既に定めているが、不在になったこと自体を示す印が無い。
  `participantLinkList`パネルの見出しへ`gathering-participant-link-issuance-closed`
  （確定後のみ存在する短い札）を追加する。
- **削除後の遷移先**は`ADR-0054`決定6が既に決定済みであり、本ADRでは繰り返さない。

### 決定12（第5束）. 会の保持期間の未決を決着させる——手で消すまで残る

`product-brief.md`§8が2026-08-29から抱えていた未決事項「会データの保持期間・削除方針」を、
本ADRで決着させる。**消さなかった会は、手で消すまで残る**——自動的な有効期限・自動削除の
仕組みは持たない。人間の問い「永久に残っちゃう？」への答えは「消すまでは残る」である。
`ADR-0050`決定4（会を削除できるようにする）が「手で消せる」ことを可能にしたことで、初めて
「自動で消す仕組みが要るか」を独立に問えるようになった——本ADRは「自動で消す仕組みは、いま
この時点では要らないと判断する」という消極的な決定であり、将来トラフィックや運用実態を見て
再検討することを妨げない。この決定は**契約に新しい観測面を要求しない**（削除操作自体は
`ADR-0050`決定4で既に契約化済み）——`product-brief.md`§8の記述を確定させるだけの製品判断
である。

## 検討した代替案

- **決定1で、候補日側（`CandidateDate`）に参加者ごとの回答配列を持たせる**: 却下。候補日の
  数は会ごとに可変（追加・削除、決定2）であり、参加者側に個人の回答をぶら下げる方が
  `listParticipantLinks`1回の呼び出しで表が組み上がる。候補日側に持たせると、参加者数×候補日数
  の呼び出し、または深くネストした応答が必要になる。
- **決定1へ店の投票も含める**: 見送り。第3・4束の裁定は幹事の個人単位の表について明示的に
  言及していない——含めるかどうかは次工程で人間に確認する（下記未決事項）。
- **決定2で、確定済み・局面変化後の候補日も削除を許可する**: 却下。確定済みの候補日は
  「決まった開催日」という別の意味を帯びており、これを削除すると`Gathering.
  confirmedCandidateDate`（`finalizeGathering`が既に確定した値）の整合性が崩れる。
- **決定4を見送り、ピンの状態はカードだけで足りるとする**: 却下。板の指摘（B3-2）どおり、
  地図とカードの相互強調という既存の設計原則に、会員状態の視覚的対応だけが抜けている状態を
  放置する理由が無い。
- **決定10で、徒歩経路の直線を「あくまで目安」と明記した上で描く**: 却下。「あくまで目安」と
  断っても、線を描くこと自体が道順の主張になる——`product-brief.md`§3の既存の方針
  （「徒歩経路と現在地は表示しない……外部の経路探索通信を要し」）と同じ理由で、この製品は
  持っていない情報を絵で言わない。
- **決定12で、90日等の具体的な自動削除期限を今回定める**: 却下。板自身が「『90日で消えます』
  のような断りを置くと、実装が伴わないのに約束したことになる」と正しく指摘している——今回
  決めるのは「自動削除は今は無い」という現状の追認であり、将来の期限設定は別の人間の決定と
  ADRを要する。

## 帰結

- `contracts/gathering-scheduling-api.yaml`（改訂、現行v0.10.0）: `ParticipantLinkSummary`へ
  `scheduleResponses`を追加（決定1）。新規操作`removeCandidateDate`と新規エラーコード
  `CANDIDATE_DATE_CONFIRMED`・`GATHERING_NOT_IN_SCHEDULING_PHASE`を追加（決定2）。
  `ParticipantView`へ`totalActiveParticipantCount`を追加（決定9）。**具体的なYAML編集は
  次工程で行う**（`contracts/REVISION-PLAN.md`参照）。
- `contracts/gathering-scheduling-browser-interface.yaml`（改訂、現行0.11.0）: 決定3・5・6・7・
  8・10・11の各観測面を追加する。**具体的なYAML編集は次工程で行う。**
- `contracts/candidate-search-browser-interface.yaml`（改訂、現行1.8.0）: 決定4
  （`candidate-map-marker`への属性追加）・決定8（`candidate-gathering-entry`の会モード時属性）
  を追加する。**具体的なYAML編集は次工程で行う。**
- `contracts/gathering-scheduling.feature`: TDR-GTH-08（候補日の件数表示）はD6反転
  （`ADR-0055`）と決定1・3の組み合わせに合わせた見直しが要る。新規シナリオ（候補日の削除、
  月送り操作、5件到達理由、参加者の総人数、確定後の店の場所表示等）を次工程で追加する。
- `contracts/candidate-search.feature`: 会モードのピン属性（決定4）・帯の振る舞い（決定7・8）
  に関する新規シナリオを次工程で追加する。
- `product-brief.md`（本PRで改訂済み）: §2（幹事に個人回答を見せる、確定後の5点、店ごとの票を
  見られるままにする）・§5（参加者への総人数開示）・§8（保持期間の決着）を改訂した。

## 未決事項（次工程・人間への申し送り）

1. **決定1の表に店の投票を含めるかどうか**は本ADRでは決定しない——第3・4束の裁定がこの表への
   言及を持たないため。次に幹事ダッシュボードの表を実装する回で、architectが人間に確認する
   必要がある。
2. `shopId`の候補探索会モードへの開示がADR-0018に触れるかどうかという`adr/0049`未決事項2は、
   本ADRでも解決しない——持ち越す。
3. 決定2（候補日の削除）が、削除された候補日に既についていた日程回答をどう扱うか
   （回答ごと消える、という設計を暗黙の前提としている）は、次工程のYAML編集時にarchitectが
   明記する。
4. 決定9（`totalActiveParticipantCount`）の値が、参加者の投票開始前（`shopVoteQuestions`が
   nullの局面）にも見えるべきかは、次工程で人間に確認する——本ADRは投票画面での使用を前提に
   決定したが、日程回答画面での使用は範囲外とした。
5. 寸法・実測（決定5の地図サイズ、決定11の表の折り返し等）は`meta/adr/0059`決定5どおり
   orchestratorの領分。
