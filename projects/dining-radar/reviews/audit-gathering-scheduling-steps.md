# 独立監査: TDR-GTH-01〜20 step定義・DSL（gathering-scheduling）

- 監査対象コミット: `44bfef9`（`origin/impl/gathering-scheduling`、`test/gathering-scheduling-steps` 統合後）
- 監査対象ファイル:
  - `tests/acceptance/dsl/gathering_scheduling_browser.py`
  - `tests/acceptance/steps/gathering_scheduling_steps.py`
  - `tests/acceptance/test_gathering_scheduling_acceptance.py`
- 依拠した契約: `contracts/gathering-scheduling.feature`（TDR-GTH-01〜20）、
  `contracts/gathering-scheduling-api.yaml` v0.2.0、
  `contracts/gathering-scheduling-browser-interface.yaml` v0.2、
  `contracts/test-support-api.yaml` v1.5.0、`adr/0034`〜`0037`。
- 独立性の担保: 対訳表はコードを先に読み、シナリオ文と突き合わせる順で作成した。tester の
  コメント・docstring はコードの記述として引用する場合のみ使用し、意図の弁明としては採用していない。
  `src/**` は読んでいない（判断は契約とテストコードのみに基づく）。

## 結論（先頭サマリ）

**Blocker: 0件。Major: 3件。Minor: 3件。判断保留（架空判断はしない）: 1件。**

検査の核である TDR-GTH-18（失効が未回答分母を減らす）の assertion は契約の式
（`activeParticipantLinkCount - respondedParticipantCount`）どおりに実装されており、
かつ「`totalIssuedParticipantLinks` から直接計算していないか」という契約自身が名指しした
再発防止ポイントを、別属性（`data-responded-count`）からの独立算出で明示的に検査している。
ここは緩められていない。Given状態の作り方も ADR-0037 の原則（公開API境界経由、seamは
期限切れ・レート制限・母集団・reset のみ）に完全に従っている。

一方、契約が明記する複数の Must が **未検査のまま** 残っている（過不足の「不足」側）。
最も重いのは `unavailableControls`（`forbiddenTestIds`／`allowedPurposes`・`forbiddenPurposes`）と
`disclosureObservations`（canary文字列・`bodyMustNotExposeTestIds`）が20シナリオ通じて一度も
検査されていないことで、姉妹契約 `candidate-search-browser-interface.yaml` 側には対応する検査が
`candidate_search_browser.py` に実装済み（`assert_map_has_no_forbidden_surfaces`・
`ALLOWED_CONTROL_PURPOSES` 検査）という**既存の同一プロジェクト内の先例と食い違う**。

## 対訳表（コードから読み取った記述 → シナリオとの突き合わせ）

以下「実際にコードが行うこと」は `test_gathering_scheduling_acceptance.py` の該当テストメソッドと
呼び出す step/DSL を読んで起こしたもので、シナリオ文はその後に契約ファイルから転記して照合した。

| ID | 実際にコードが行うこと | シナリオ文との一致 |
|---|---|---|
| TDR-GTH-01 | サインイン後、`POST /gatherings` を直接叩き（ブラウザのクリックではない）、応答の `phase=="SCHEDULING"`・登録された `candidateDates` の集合一致・`confirmedCandidateDateId is None` を検査する。 | 一致。browser-interface契約の `notVerifiedHere` が本シナリオをAPI/境界レベル検証として明示的に許容しており、逸脱ではない。 |
| TDR-GTH-02 | (1) `gathering-add-candidate-date-open` をクリックし、クリック前後で局面・候補日一覧が不変であることのみ検査（無副作用検査）。(2) 別途 `POST /candidate-dates` をAPI直叩きし、ダッシュボード再読込後に新しい候補日が一覧に現れ局面が `SCHEDULING` のままであることを検査。 | 部分一致。`.feature` のGiven/When/Thenは(2)の組み合わせで満たされる。ただし browser-interface の `addCandidateDateOpen.requiredOutcome`（クリックが「入力面へ到達可能になる」という正の効果）自体は**一度も検査されていない**——(1)は負の効果（副作用が無いこと）だけを見ており、実際に何らかの新しいDOM要素が現れることの確認は無い。詳細は下記「個別論点1」。 |
| TDR-GTH-03 | 幹事画面から2本発行し、token/urlの相互distinctを検査。1本目のリンクで参加者が回答、2本目のリンクを開いて「その日程はまだ未回答」であることを検査。 | 一致。「互いに異なる」「会と参加者の組にだけ有効」は、2リンクの回答状態が独立であることの実証で概ね裏付けられる。 |
| TDR-GTH-04 | 名前欄を経由せずにリンクを開き回答、`data-participant-named=="false"` を検査。幹事ダッシュボードで `respondedCount=1, anonymousRespondedCount=1` を検査。 | 一致。 |
| TDR-GTH-05 | 既に1件回答済みのリンクで名前を付け、`data-participant-named=="true"`・以前の回答値が変わっていないこと・幹事のリンク一覧で `hasResponded=True, named=True` を検査。 | 一致。 |
| TDR-GTH-06 | 同一候補日への回答を GOING→MAYBE で更新し `data-your-response` が更新されることを検査。さらに幹事が確定操作をした**後**でも同じリンクから NOT_GOING に再変更でき、参加者ヘッダの局面表示が `SELECTING_SHOP` になっていることを検査。 | 一致、かつ最小要求より広く検査している（局面遷移後の変更可能性を明示的に実証）。 |
| TDR-GTH-07 | 3本発行、うち2本が別々の候補日に回答、1本は無回答のまま。`unanswered_summary(total=3, revoked=0, active=3, unanswered=1)` と各候補日のタリーを検査、`going`降順であることをプロパティとして検査（DOM値をsortしたものと比較、固定値への決め打ちではない）。 | 一致。 |
| TDR-GTH-08 | `GATHERING_OPEN_SHOP_WEEKDAY_MATCH` を選択し、月曜の候補日を仮選択、`openShopCount==5`（契約が明記する既知値）、局面不変、未確定であることを検査。DOM表示店名の並びがAPI応答の `previewShops` の並びと一致することを検査。 | 一致（件数・局面不変）。ただし「近い順」であること自体は API 応答順を DOM がそのまま反映しているかの**自己整合性**検査であり、その API 応答順が真に近い順であることの独立検証ではない。下記「個別論点2」。 |
| TDR-GTH-09 | 水曜の候補日を含む会で未回答のまま参加者ビューを開き、`data-open-shop-count==4`（契約の既知値）と、店名・その他店舗属性が一切DOMに存在しないことを検査。 | 一致。 |
| TDR-GTH-10 | 候補日Aを仮選択→確定、局面が `SELECTING_SHOP` になることを検査。別の候補日B確定をAPI直叩きで試み `409 GATHERING_NOT_IN_SCHEDULING_PHASE` を検査。確定後も候補日Aへの回答が反映され続けることを検査。 | 一致。 |
| TDR-GTH-11 | 候補日A確定後、同じ参加者が確定日・非確定日の両方に新規回答し、両方のタリーに反映され、局面が `SELECTING_SHOP` のまま、参加者ヘッダの局面表示も同じであることを検査。 | 一致。 |
| TDR-GTH-12 | 参加者Aが回答する前は他者の回答状況（tally要素）が存在しないこと・`data-your-response=="UNANSWERED"` を検査。回答後は集計tallyが出現し値が正しいことを検査。 | 一致。 |
| TDR-GTH-13 | 発行済みトークンとは無関係な文字列（`"guessed-" + secrets.token_urlsafe(24)`）で `GET /participant-links/{token}` を直叩きし、`404 LINK_NOT_FOUND`・スキーマ適合・応答本文に実在する会のタイトルが含まれないことを検査。 | 一致。ADR-0037決定1が明記する「発行済みトークンとは異なる任意の文字列を組み立てる」approachそのもの。ブラウザのクリックスルーではない点も `notVerifiedHere` の許容と一致。 |
| TDR-GTH-14 | 発行済みトークンを `seedExpiredParticipantLink` で即座に期限切れにし、参加者がリンクを開くと `gathering-participant-link-error`（`LINK_EXPIRED`）が出て、`gathering-participant-header`・`gathering-schedule-question` が不在であることを検査。 | 部分一致。契約の `invalidLinkOutcome.absent` は3要素（+ `gathering-participant-name-open`）だが、検査対象は2要素のみ。下記「個別論点3」。 |
| TDR-GTH-15 | 1件回答済みのリンクを `seedRateLimitedParticipantLink` でレート制限状態にし、回答を試みると `LINK_RATE_LIMITED` エラーが出ること、**`data-your-response` の値**が試行前後で変わらないことを検査。 | 部分一致。契約の `priorAnswersRetained` は `data-your-response` **と** `gathering-schedule-tally` の両方の保持を要求するが、検査対象は前者のみ。下記「個別論点4」。 |
| TDR-GTH-16 | 3本発行、1本目だけ回答＋名前付与。幹事画面のリンク一覧が発行順（`issuedAt`昇順）であること、各項目の `hasResponded`/`named` の値を検査。 | 一致。 |
| TDR-GTH-17 | 1本発行し再コピー、返るURLが元のURLと同一であること、`unanswered_summary` が不変であること、一覧の状態（未回答・名無し）が変わらないことを検査。 | 一致。 |
| TDR-GTH-18 | 1本発行（無回答）→ 失効前の分母スナップショット取得 → 失効 → `totalIssuedLinks`不変・`revokedLinks`+1・`activeIssuedLinks`-1・`unansweredCount`-1、かつ`unansweredCount == activeIssuedLinks - respondedCount`（別のDOM属性から独立算出した式で再検算）を検査。一覧上は `revoked=True` のまま残ることを検査。 | 完全一致。契約が名指しした回帰（`data-total-issued-links` から直接算出する旧バグの再導入）を、独立属性からの式再検算で構造的に検出できる形にしている。**緩められていない。** |
| TDR-GTH-19 | 発行済みリンクを失効させてから参加者が開くと `LINK_REVOKED` エラーが出て、`gathering-participant-header`・`gathering-schedule-question` が不在であることを検査。 | 部分一致。TDR-GTH-14と同じ理由で `gathering-participant-name-open` の不在は未検査。 |
| TDR-GTH-20 | 回答済みリンクの失効ボタンがdisabledであることを検査。API直叩きで失効を試み `409 PARTICIPANT_LINK_ALREADY_ANSWERED`、分母不変、一覧の状態不変を検査。さらにそのリンクで参加者ビューが引き続き正常に開けることを検査。 | 一致、かつ「そのリンクは引き続き有効なまま一覧に残る」を実際に参加者ビューを開いて実証しており最小要求より厚い。 |

## 個別論点（5観点チェックリストに基づく詳細）

### 論点1（Major）: TDR-GTH-02 の2段構成——`addCandidateDateOpen` の正の効果が未検査

`assert_add_candidate_date_entry_point_is_reachable_without_side_effects` は、クリック前後で
`_read_gathering_phase_from_dom()` と `_read_candidate_dates()` が不変であることだけを検査する
（負の効果＝副作用が無いことの検査）。browser-interface契約の
`addCandidateDateOpen.requiredOutcome`（「Activating it makes an input surface for a new
candidate date reachable」）が要求する**正の効果**——クリックの結果何らかの新しいDOM要素・
フォームが現れること——は、この関数からもテストスイート全体からも一度も検査されていない。

この設計の是非を判断する。契約自身が「Organizer.dc.html shows only the "候補日を足す" entry
point, not its resulting form, so those details are not yet approved design」と明記しており、
結果として現れるフォームに機械観測可能な `data-testid` が存在しない。したがって tester が
「新しいフォームが出現すること」を厳密な `data-testid` 検査で確認する手段は契約上存在しない。
`.feature` のGiven/When/Then自体（候補日が一覧に加わる・局面不変）は、無副作用検査＋API直叩き
による追加＋反映確認、という組み合わせで満たされている——ここは妥当と判断する。

ただし、"何らかのDOM変化が起きたこと" 自体（要素数の増加、`aria-expanded` の切り替わりなど、
特定の test-id に依存しない一般的な観測）を試みることは可能だったはずで、その代替手段も
試みられていない。DSL自身のdocstringは「it cannot drive the resulting, contractually-unspecified
form」と正直に書いており、隠蔽ではない——P-08の精神には沿っている。しかし現状のままでは
`browserActions.addCandidateDate`（`gathering-add-candidate-date-open` の活性化が
`gathering-candidate-date` の出現に**直接**つながるという契約の記述）は、ブラウザ操作としては
一度も実演されていない。**判断**: 現状の2段構成は `.feature` レベルの3行（Given/When/Then）を
満たす限りにおいて許容できるが、browser-interface契約の `addCandidateDateOpen`/`browserActions.
addCandidateDate` という独立したMustを満たしているとは言えない。architectが観測面
（少なくとも「クリック後に新しい入力コントロールが最低1つ出現する」ことを検出できる汎用的な
属性）を追加契約するまで、この項目は「未検証」として記録すべきである。

### 論点2（Minor〜Medium、architect宛の申し送り）: TDR-GTH-08の「近い順」が自己整合性検査止まり

`assert_open_shop_preview_shows_expected_count_and_order` は、DOM上のプレビュー店名の並びが
**同じHTTP応答**の `previewShops` の並びと一致することを検査する。これは「DOMが応答を正しく
描画しているか」の配線検査としては有効だが、「その応答の並びが実際に近い順であるか」という
業務ロジック自体は一切検証していない——`OpenShopPreviewItem` スキーマは距離・座標を含まない
ため（`forbiddenFields` により意図的に非公開）、L4からは独立に「本当に近い順か」を検証する
手段が契約上存在しない。過去の監査（`reviews/audit-tdr-cs-origin-marker-position.md` F1）が
指摘した「自己整合性チェックは配線ミスと正しい実装を区別できない」という同型の限界がここにも
存在する。ただしF1のケースと異なり、ここでは「決め打ち定数と正しい実装が区別できない」という
具体的な偽陽性シナリオまでは特定できておらず、判断を保留する。architectへの申し送り事項として
記録する（このseamの近さの正しさの検証はL1の責務とADR-0037決定3・帰結に明記されているため、
L1側にこの検証が存在するかどうかは本監査の対象外——`src/**`を読まない制約により確認していない）。

### 論点3（Minor）: TDR-GTH-14/19の`invalidLinkOutcome.absent`が3件中2件しか検査されない

`assert_participant_link_error` は `gathering-participant-header`・`gathering-schedule-question`
の不在のみを検査する。契約の `browserEntry.participantAnswer.invalidLinkOutcome.absent` は
これに加えて `gathering-participant-name-open` の不在も要求しており、この1件が両シナリオ
（TDR-GTH-14, TDR-GTH-19）で未検査のまま欠落している。

### 論点4（Major）: TDR-GTH-15の`priorAnswersRetained`が`data-your-response`のみで`gathering-schedule-tally`を検査しない

`prior_answers_snapshot`/`capture_current_your_responses` は `data-your-response` のみを
キャプチャし、`assert_your_responses_unchanged` もこれのみを比較する。契約の
`rateLimitedScheduleResponse.priorAnswersRetained` は「Every previously recorded
data-your-response **and** gathering-schedule-tally value...is unchanged」と明記しており、
`gathering-schedule-tally`（`data-going-count`/`data-maybe-count`/`data-not-going-count`）側の
保持は一度も検査されていない。TDR-GTH-15のGivenでは当該参加者が既に回答済みのため、この
tallyは画面上に存在しているはず（TDR-GTH-12の「回答後にtallyが出現する」ルールにより）——
検査対象として取りうる状態であるにもかかわらず取っていない。これは契約が明示的に列挙した
2つの保持対象のうち1つが丸ごと欠落しているという点で、TDR-GTH-19/14の欠落（論点3）より重いと
判断し、Majorとした。

### 論点5（Major）: `unavailableControls`・`disclosureObservations`が20シナリオ通じて未検査

契約が定める以下のMustについて、`gathering_scheduling_browser.py`・
`gathering_scheduling_steps.py`・`test_gathering_scheduling_acceptance.py`のいずれにも対応する
検査コードが存在しない（`grep`で確認、0件）。

- `unavailableControls.forbiddenTestIds`（`candidate-origin-marker`・`candidate-map`・
  `private-search-origin` が会の画面に一切現れないこと）
- `unavailableControls.allGatheringScreenFormControlsMustDeclarePurpose` /
  `allowedPurposes` / `forbiddenPurposes`（`manual-ordering`・`secondary-condition` の禁止を
  含む、フォームコントロールの目的宣言の網羅性）
- `disclosureObservations.bodyMustNotContain`（`syntheticDisclosureCanaries` 由来の禁止文字列）
- `disclosureObservations.bodyMustNotExposeTestIds`（`private-search-origin`・
  `candidate-origin-marker`・`candidate-map-marker`）
- `disclosureObservations.participantTokenHandling`（トークンがlocalStorage/cookie等に
  永続化されないこと）

このプロジェクトには同種の検査を実装した明確な先例が存在する——
`candidate_search_browser.py` は `ALLOWED_CONTROL_PURPOSES` に基づく網羅的なpurpose検査
（`purpose in ALLOWED_CONTROL_PURPOSES` を全フォームコントロールに対して実行）と
`assert_map_has_no_forbidden_surfaces`（`DISCLOSURE_FORBIDDEN_TEST_IDS`の不在検査）を実装・
使用している。TDR-GTHのbrowser-interface契約は同じ形の`unavailableControls`/
`disclosureObservations`セクションを持つが、対応する検査が一つも書かれていない。特に、
`gathering-scheduling`の開店件数プレビュー（`OpenShopPreviewItem`）は候補検索と同じ非公開
母集団を再利用する新機能であり、この母集団のデータが誤って会の画面に漏出しないことを保証する
のがまさに`disclosureObservations`の役割である——その保護が全く検査されていない状態でマージ
される。CSRFのネガティブテスト（CSRFトークン無しでの拒否）はこのプロジェクトの既存の
TDR-CS側でも慣習的に書かれていないため、その不在は本監査では指摘していない（既存の設計判断
として扱う）が、本項目はそれとは異なり明確な先例が同一リポジトリ内に存在するため、過不足の
「不足」として記録する。

### 論点6（Minor、掃除対象）: 未使用のDSLメソッド

`assert_participant_progress`（`gathering-participant-progress`要素の
`data-total-candidate-dates`/`data-answered-candidate-dates`を検査する）が定義されているが、
`gathering_scheduling_steps.py`からもテストファイルからも一度も呼ばれていない。契約の
`browserControlSurface.participantAnswer.progress`はどのTDR-GTH-XXシナリオにも直接紐付かない
補助的な要素（Answer.dc.htmlの「日程 2/3」表示に対応）であるため、対応するシナリオが無いこと
自体は不自然ではないが、前回監査（`reviews/audit-ring-labels-and-empty-guidance.md`系列）で
同種の「未使用step」が指摘・記録されている先例があり、再発として記録する。実装が壊れても
どのテストも赤くならない。

### レビューチェックリスト（5観点）

1. **過不足**: 過剰な検査（契約より厳しすぎる誤検出リスク）は見当たらない。不足は上記
   論点1・3・4・5・6のとおり複数ある。TDR-GTH-01〜20の20シナリオ全てに対応するテストメソッドは
   存在し、シナリオ→テストの欠落（1対1対応の欠落）自体は無い。
2. **Givenの正当性**: ADR-0037決定1〜5に完全準拠。会・候補日・リンク・回答は例外なく公開API
   境界（`gathering-scheduling-api.yaml`）経由で構築されており、DB直接操作は無い。
   `seedExpiredParticipantLink`/`seedRateLimitedParticipantLink`/
   `GATHERING_OPEN_SHOP_WEEKDAY_MATCH`という3つの許可された例外seamのみが使われている。
   `resetGatheringSchedulingAcceptanceState`/`resetCandidateProposalAcceptanceState`/
   `resetAuthenticationAcceptanceState`が毎テスト前に呼ばれ独立性が保たれている。
3. **Thenの検証対象**: TDR-GTH-18の核心的な式（`activeParticipantLinkCount -
   respondedParticipantCount`）は独立算出による再検算まで行っており模範的。一方、論点3・4・5の
   とおり複数のThen/Mustの検証対象が部分的、または皆無である。
4. **失敗の握りつぶし**: `try/except`によるエラーの隠蔽、無条件`pass`、意味のないtrueアサーション
   は見当たらない（grep確認済み）。全アサーションヘルパー（`assert_present`/`assert_absent`等）は
   既存のTDR-CS用共有インフラをそのまま再利用しており、新規に緩められた挙動は無い。
5. **暗黙の前提**: `candidate_date_id_at`は、送信した`startAt`の文字列とAPI応答が返す
   `startAt`の文字列が**バイト同一**であることを暗黙に仮定している（サーバー側のISO-8601
   正規化——例えば`+00:00`と`Z`表記の差——で容易に崩れうる）。崩れた場合は`KeyError`で
   明確に失敗するため「握りつぶし」ではないが、フォーマット依存の脆さとして記録する。

## 契約↔テスト対応の監査

- **承認済みシナリオのうちstep未実装のもの**: 無し（TDR-GTH-01〜20すべてに対応するテスト
  メソッドが存在する）。
- **シナリオに対応しない孤児step**: 無し（`steps.py`の62メソッドは全てテストファイルから
  呼ばれている。`dsl`層の未使用は論点6の1件のみ）。
- **同義stepの重複**: 見当たらない。
- **契約が定めるがどのシナリオ番号にも紐付かないMust**（`unavailableControls`・
  `disclosureObservations`・`tentativeSelectionAndPreview`の「前の選択がfalseに戻る」性質等）の
  未検査は論点5および以下の追加観察として記録する。

### 追加観察（Minor、判断保留寄り）: 「以前選択していた候補日のtentative-selectedがfalseに戻る」が未検査

契約の`tentativeSelectionAndPreview.trigger.requiredOutcome`は「Exactly one
gathering-candidate-dateのdata-tentative-selectedがtrueになる（**any previously true element
becomes false**）」と明記するが、どのTDR-GTH-XXテストも仮選択を1回しか行っておらず、2つ目の
候補日を選び直して1つ目が`false`に戻ることを確認するテストが無い。特定のシナリオ番号に
紐付く要求ではないため過不足の判断は保留するが、記録しておく。

## 人間の承認判断のためのチェックリスト

- [ ] Blocker: 0件（本監査の判定）
- [ ] Major論点1（TDR-GTH-02の正の効果未検証）を、現状の契約の下で許容するか、architectへ
      観測面追加を差し戻すか
- [ ] Major論点4（TDR-GTH-15のtally保持が未検査）の追加を、本PRのブロッカーとするか次PRへ
      送るか
- [ ] Major論点5（unavailableControls/disclosureObservationsが全く検査されていない）を、
      本PRのブロッカーとするか、developer実装が正しい前提で次PRへ送るか——姉妹契約
      (`candidate-search`)との検査密度の非対称が生まれる点に留意
- [ ] Minor論点3（invalidLinkOutcomeの`gathering-participant-name-open`不在検査の欠落）
- [ ] Minor論点6（`assert_participant_progress`の未使用コードの掃除）
- [ ] 論点2（近い順の自己整合性止まり）はarchitectへの申し送り事項として記録するに留めるか
- [ ] ADR-0037自体はまだ`status: 提案中`——本PRのマージが承認行為になる想定で良いか
      （`meta/adr/0035`方式(i)）

以上。
