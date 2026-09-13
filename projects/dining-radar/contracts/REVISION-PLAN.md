# 契約の改訂計画（2026-09-12、ADR-0054・ADR-0055・ADR-0056の第2段）

> **この文書は計画であり、実行ではない。** `contracts/**`配下のいずれのファイルも、本計画の作成
> 作業では1文字も変更していない——architectの役割定義が禁じる契約の確定（`.claude/agents/
> architect.md`「契約を確定しない」）と、本ラウンドの依頼「契約ファイルには一切触らないこと」を
> 守るためである。第1段（`ADR-0054`〜`0056`、`product-brief.md`改訂）と第2段（本計画に基づく
> 実際のYAML/.feature編集）を分けたのは、1回の実行で契約を全文再生成させるとFR-031（既存
> シナリオの消失）を再発させるおそれがあるためである（`activeContext.md`の指示）。

各節は対象ファイル・現在のバージョン・変更点・根拠ADR・影響するシナリオIDの順で記す。**着手時に
シナリオ数を突き合わせること**——本計画のどの変更も既存シナリオを削除しない（TDR-GTH-08の記述
変更を除き、いずれも追加または属性の追記であり、既存シナリオ本文を書き換えるものではない）。

## 0. 着手前に必ず検算すること

依頼文が名指しした5点は、いずれも本orchestratorが契約を実際に読んで検算済みである（下記の
各節に検証結果を記載）。次にこのファイルを扱う者は、実装着手前にもう一度読み直すこと——本計画の
作成からYAML編集までの間に契約が別スライスで動く可能性があるためである。

1. **`shortlistedShopVotes`の「地図も店のページへの線も足さない」明記**:
   `gathering-scheduling-browser-interface.yaml`1454〜1461行に実在する。`product-brief.md`§2
   「幹事ダッシュボード」（投票結果の画面にも地図・店情報を示すという記述）と正面から食い違う。
   `ADR-0055`決定5・`ADR-0056`決定5で「説明書が正、契約が誤り」として解消する。
2. **`finalizedView`の内部矛盾**: `decision.requirement`（2307〜2319行、「店の生きた集計は
   確定によって不変」と明記）と`replacesQuestionSurfaces`（2320〜2326行、「`gathering-shop-
   vote-question`は確定後は不在」と明記）が両立しない。`ADR-0055`決定8で「見える」側に解消する。
3. **参加者向け応答に会の総人数が無い**: `ParticipantView`のいずれのフィールドにも、会全体の
   参加人数（`Gathering.activeParticipantLinkCount`相当）を運ぶものが無い——確認済み
   （`respondedParticipantCount`はいずれも1候補日・1店に閉じた分母）。`ADR-0056`決定9で
   `totalActiveParticipantCount`を新設する。
4. **「誰が・どの候補日に・何と答えたか」を運ぶ道が無い**: `ParticipantLinkSummary`
   （`id`・`issuedAt`・`hasResponded`・`revoked`・`displayName`のみ）と`CandidateDate`
   （`goingCount`/`maybeCount`/`notGoingCount`という集計のみ）の間に、両者を結ぶ値が無い——
   確認済み。`ADR-0056`決定1で`ParticipantLinkSummary.scheduleResponses`を新設する。
5. **`data-current-leader`の0票・同票時の扱い**: `shortlistedShopVotes.list.item.
   attributes.currentLeader`（1503〜1536行）は、既存の並び順の先頭1件を無条件に`true`とする
   ——0票のときも同様に真になる。`ADR-0055`決定6で是正する。

## 1. `contracts/gathering-scheduling-api.yaml`（現行 v0.10.0 → 提案 v0.11.0）

| # | 変更 | 根拠 | 影響シナリオ |
|---|------|------|--------------|
| 1 | `ParticipantScheduleQuestion`から`openShopCount`を削除する | ADR-0055決定1 | TDR-GTH-08（記述変更） |
| 2 | `ParticipantLinkSummary`へ`scheduleResponses`（配列、`{candidateDateId, status}`）を追加する | ADR-0056決定1 | 新規（幹事ダッシュボードの表を検査するシナリオ、番号は次工程で採番） |
| 3 | 新規操作`removeCandidateDate`（`DELETE /gatherings/{gatheringId}/candidate-dates/{candidateDateId}`）、新規エラーコード`CANDIDATE_DATE_CONFIRMED`・`GATHERING_NOT_IN_SCHEDULING_PHASE`を追加する | ADR-0056決定2 | 新規 |
| 4 | `ParticipantView`へ`totalActiveParticipantCount`（整数）を追加する | ADR-0056決定9 | 新規、および既存の投票関連シナリオへの属性追記 |
| 5 | `shortlistedShopVotes`相当のスキーマ（`ShortlistedShop`）へ`name`・`location`・`walkingTimeMinutes`・`providerPageUrl`を追加する——`ParticipantShopVoteOption`が既に持つものと同型 | ADR-0055決定5 / ADR-0056決定5 | TDR-GTH-38・39（記述変更） |
| 6 | `ShortlistedShop`（または対応スキーマ）へ`addedAfterVotingStarted`（真偽値）を追加する | ADR-0056決定6 | 新規 |

**バージョン付番の根拠**: 破壊的変更（`openShopCount`の削除）を含むため、マイナー以上のbumpが
要る。既存の`v0.X.0`系列の付番慣行（`ADR-0044`・`0049`等がいずれもマイナーbumpで破壊的変更を
扱ってきた）に揃え、v0.11.0を提案する。

## 2. `contracts/gathering-scheduling-browser-interface.yaml`（現行 contractVersion 0.11.0 → 提案 0.13.0）

| # | 変更 | 根拠 | 影響シナリオ |
|---|------|------|--------------|
| 1 | `participantLinkList.item.revoke.presenceRule`を新設し、`data-has-responded`/`data-revoked`が真の行では要素そのものを不在にする（現行の`disabledState`のみの規則を置き換える） | ADR-0055決定2 | TDR-GTH-20（記述変更） |
| 2 | `answerLater.requiredOutcome`を、散文の確認から「この参加者がここまでに行った回答の一覧を表示する」への差し替え | ADR-0055決定3 | 新規（FR-034是正の検査） |
| 3 | `shortlistedShopVotes`の除外記述（1454〜1461行）を削除し、`gathering-shortlisted-shop-item`へ`data-shop-name`・`data-walking-time-minutes`・地図要素（`gathering-shortlisted-shop-map`/`-map-marker`）・`gathering-shortlisted-shop-page-link`を追加する | ADR-0055決定5 / ADR-0056決定5 | TDR-GTH-38・39（記述変更） |
| 4 | `shortlistedShopVotes.list.item.attributes.currentLeader`の`requirement`を、0票時は`false`固定・同票時は同票全店`true`へ書き換える | ADR-0055決定6 | 新規 |
| 5 | `finalizedView.decision`から`yourScheduleResponse`/`data-your-schedule-response`を削除する | ADR-0055決定7 | TDR-GTH-34（記述変更） |
| 6 | `finalizedView.replacesQuestionSurfaces`から`gathering-shop-vote-question`（および対応する`gathering-shop-vote-tally`）を除外する——`gathering-schedule-question`・`gathering-participant-progress`は不在のまま維持する | ADR-0055決定8 | TDR-GTH-34隣接（記述変更） |
| 7 | `finalizedView.decision`へ地図（`gathering-participant-decision-map`/`-map-marker`/`-origin-marker`）・`data-walking-time-minutes`・`gathering-participant-decision-page-link`を追加する。2点を結ぶ経路線・同心リングは追加しない | ADR-0056決定10 | 新規 |
| 8 | `organizerGatheringCreate.submit.requiredOutcome`へ「送信成功後、作成した会の幹事ダッシュボードへ遷移する」ことを追記する | ADR-0054決定2 | 新規 |
| 9 | `organizerDashboard`へ、参加者ごと・候補日ごとの回答を表示する新規要素（表構造、testIdは次工程で命名）を追加する | ADR-0056決定1 | 新規 |
| 10 | `organizerGatheringCreate.calendar`・`addCandidateDateForm.calendar`へ月送り矢印（`*-month-previous`/`-next`、新設purpose）・選択日削除の×（`*-remove-selected`、新設purpose）を追加し、`allowedPurposes`へ反映する | ADR-0054決定3 / ADR-0056決定3 | 新規（FR-033是正の検査） |
| 11 | `addCandidateDateForm`・`organizerGatheringCreate`のカレンダーへ範囲選択（ドラッグ／anchor+click／Shift+click）の観測面を追加する。1日ずつの選択は無変更 | ADR-0054決定3 | 新規 |
| 12 | 候補日削除操作（`removeCandidateDate`呼び出し）に対応する新規UI要素（`gathering-candidate-date-remove`等）を追加する | ADR-0056決定2 | 新規 |
| 13 | `gathering-finalize-submit`を`-open`/`-confirm-dialog`/`-confirm`/`-cancel`の4要素へ改める。確認面へ「変わることの表」（`gathering-finalize-confirm-changes`、回答リンク／参加者の画面／日と店の3行、前→後）を追加する | ADR-0054決定5 / ADR-0056決定11 | 新規 |
| 14 | `deleteGathering`の削除後遷移先（会の一覧）を`requiredOutcome`へ明記する | ADR-0054決定6 | TDR-GTH-48（記述変更） |
| 15 | `participantLinkList`パネルへ、確定後のみ存在する`gathering-participant-link-issuance-closed`（発行終了の札）を追加する | ADR-0056決定11 | 新規 |
| 16 | `gathering-shortlisted-shop-item`（幹事側）・`shopVoteQuestion`の各選択肢（参加者側）へ`data-added-after-voting-started`を追加する | ADR-0056決定6 | 新規 |
| 17 | `candidate-gathering-entry`の会画面群での常設化・モバイル幅でのテキスト非表示規則の撤回を反映する記述を追加する（本体は`candidate-search-browser-interface.yaml`側、この契約からは参照のみ） | ADR-0054決定1 | 新規 |

**バージョン付番の根拠**: 17件のうち複数が既存要素の除去・presenceRule変更という破壊的変更
（項目1・3・4・5・6）を含む。直近の`0.10.0→0.11.0`（`ADR-0051`）が1件の入力面統一で1段
bumpしていることに鑑み、本計画は複数の破壊的変更をまとめて0.13.0（2段bump）を提案する——
実際の値は次工程で編集時に確定する。

## 3. `contracts/candidate-search-browser-interface.yaml`（現行 contractVersion 1.8.0 → 提案 1.9.0）

| # | 変更 | 根拠 | 影響シナリオ |
|---|------|------|--------------|
| 1 | `candidate-gathering-entry`を会の画面群でも常設の要素として扱えるよう記述を広げ、モバイル幅の`display: none`規則を撤回する | ADR-0054決定1 | 新規（店を絞る画面第1便・報告4の是正） |
| 2 | `candidate-map-marker`へ`data-gathering-shortlisted`（会モード時のみ非null）を追加する | ADR-0056決定4 | 新規（TDR-CS-17隣接） |
| 3 | 会モードの帯へ`data-shortlist-limit-reached`（真偽値）を追加する | ADR-0056決定7 | 新規（TDR-CS-19隣接） |
| 4 | `candidate-gathering-entry`へ会モード時の`data-active-gathering-id`（会モード時のみ非null）を追加する | ADR-0056決定8 | 新規 |
| 5 | 会モードから会へ戻る動線（帯自体が兼ねる）の`requiredOutcome`を追記する | ADR-0054決定4 | 新規（B1-3/B3-1の解消） |
| 6 | 会モードのカードへ「あとから入りました」印の観測面（`data-added-after-voting-started`）を追加する | ADR-0056決定6 | 新規 |

**バージョン付番の根拠**: いずれも既存要素への属性追加・記述の緩和であり、破壊的変更を含まない
——マイナーbump（1.9.0）を提案する。

## 4. `contracts/candidate-search-api.yaml`（現行 v1.3.0）

本ラウンドが確定した決定は、いずれも観測面（ブラウザ契約）側の追加であり、API層の新しい値を
要求しない——`data-gathering-shortlisted`はカード側で既に`isShortlisted`から導出済みであり、
`data-shortlist-limit-reached`は`gatheringContext.shortlistedShopCount`/`maxShortlistedShops`
から導出できる。**このファイルの変更は不要と判断する**。次工程で実際にYAMLへ触れる際、この
判断が正しいか改めて確認すること。

## 5. `contracts/gathering-scheduling.feature`

| # | 変更 | 根拠 |
|---|------|------|
| 1 | TDR-GTH-08を、参加者向けの件数表示を含まない記述へ書き換える | ADR-0055決定1 |
| 2 | TDR-GTH-20（取り消しの境界）を、未回答の行にだけ取り消しが存在するという記述へ書き換える | ADR-0055決定2 |
| 3 | TDR-GTH-34（確定後の記録）を、日程回答1行も含まない記述へさらに簡素化する | ADR-0055決定7 |
| 4 | TDR-GTH-38・39（投票タリー画面の観測範囲）を、地図・店情報を含む記述へ書き換える | ADR-0055決定5 |
| 5 | 新規シナリオ: 幹事が個人単位の回答表を見られる | ADR-0056決定1 |
| 6 | 新規シナリオ: 候補日を削除できる・確定済みの候補日は削除できない | ADR-0056決定2 |
| 7 | 新規シナリオ: 5件到達時に理由が分かる | ADR-0056決定7 |
| 8 | 新規シナリオ: 参加者に会の総人数が示される | ADR-0056決定9 |
| 9 | 新規シナリオ: 確定後、参加者は店の場所を見られる（経路線・同心リングは無い） | ADR-0056決定10 |
| 10 | 新規シナリオ: 確定に確認の一段があり、確認面に変化の表が示される | ADR-0056決定11 |
| 11 | 新規シナリオ: 票が0のとき最有力の印が出ない・同票のとき全店に印が付く | ADR-0055決定6 |
| 12 | 既存シナリオ（TDR-GTH-01〜07・09〜19・21〜33・35〜37・40〜48）は**本文を変更しない** | — |

**シナリオ数の突き合わせ**（着手前後で必ず数えること）: 現行の`TDR-GTH`シナリオ数に対し、
本計画は3件の既存シナリオ本文変更（TDR-GTH-08・20・34。TDR-GTH-38・39は記述の追加であり
Given/Thenの構造自体は変えない）と、新規7件程度（項目5〜11、正確な件数は次工程の採番時に
確定）を見込む。**既存シナリオの削除は1件も無い。**

## 6. `contracts/candidate-search.feature`

新規シナリオ: 会モードで、店を会に入れるとピンにも状態が反映される（ADR-0056決定4）。5件到達
時の帯の理由表示（ADR-0056決定7）。既存シナリオ（TDR-CS-00〜19）は本文を変更しない。

## 7. `contracts/test-support-api.yaml`（現行 v1.5.7）

新規シナリオぶんのGiven状態構築手段（幹事への個人回答開示、候補日の削除、5件到達理由等）を
検査するのに、既存の`x-acceptance-scenarios`一覧・状態モードで足りるか、次工程で確認する。
`ADR-0052`が申し送った「TDR-GTH-26〜41全体のGiven-state構築手段の棚卸し」（`OpenShopPreviewItem`
削除後のstaleな参照）は、本計画の対象外のまま持ち越す——性質の異なる作業である。

## 8. 実装しない・見送りの確認

- `candidate-search-api.yaml`は変更不要と判断した（4節）。
- `product-brief.md`§8「候補日を削除したとき、その日についていた既存の日程回答をどう扱うか」
  （未決事項）は、`removeCandidateDate`の実装がその候補日への回答を一緒に削除することを前提と
  している——この前提はAPI仕様のスキーマではなく操作の説明文（`description`）に明記すべき
  性質であり、1節の表の変更点3に含めた。
- `ADR-0018`（durable provider ID採用の保留）との関係（`shopId`開示、`adr/0049`未決事項2）は、
  本計画でも解決しない——次にこの論点を扱う者への申し送りのまま維持する。

## 9. 着手順序の提案（実行しないが、次工程のための下書き）

1. `gathering-scheduling-api.yaml`（1節）——他のファイルが参照する値の土台。
2. `gathering-scheduling-browser-interface.yaml`（2節）——分量が最大、破壊的変更を含むため
   1ファイルとして独立させる。
3. `candidate-search-browser-interface.yaml`（3節）——2との依存は`data-active-gathering-id`等
   一部のみ。
4. `gathering-scheduling.feature`・`candidate-search.feature`（5・6節）——スキーマ・観測面が
   固まってからシナリオ本文を書く。
5. `test-support-api.yaml`（7節）——新規シナリオのGiven状態が既存の状態モードで足りない場合の
   み追記する。

各段の完了ごとに、**着手前後のシナリオ数を突き合わせること**（FR-031の再発防止）。
