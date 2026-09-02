# 独立監査: TDR-GTH-21〜25 新規step／TDR-GTH-02書き直し／横断検査v0.4追随

- 監査対象コミット: `e117580`（`origin/test/gathering-entry-steps`）。差分ベースは
  `origin/main`（`d5ca830`、PR #182マージ後）との比較。
- 監査対象ファイル（`git diff d5ca830 e117580 --stat`で確認、この3ファイルのみ）:
  - `tests/acceptance/dsl/gathering_scheduling_browser.py`
  - `tests/acceptance/steps/gathering_scheduling_steps.py`
  - `tests/acceptance/test_gathering_scheduling_acceptance.py`
- 依拠した契約: `contracts/gathering-scheduling.feature`（TDR-GTH-01〜25）、
  `contracts/gathering-scheduling-api.yaml` v0.3.0、
  `contracts/gathering-scheduling-browser-interface.yaml` v0.4、
  `contracts/candidate-search-browser-interface.yaml` v1.7.0（`gatheringEntry`節のみ）、
  `adr/0038`、`adr/0039`。前回監査
  `reviews/audit-gathering-scheduling-steps.md`（対象コミット`44bfef9`、Blocker 0/Major 3/Minor 3）
  の続編として、そこでのMajor#1（TDR-GTH-02の正の効果未検証）の解消状況を中心に確認した。
- 独立性の担保: 対訳表はコード（DSL・steps・testの3ファイル）を先に読み、その後シナリオ文・契約
  Mustと突き合わせた。tester のコミットメッセージ・docstringは「コードが実際に何をしているか」の
  記述として使う場合のみ引用し、意図の弁明としては採用していない。`src/**`は一切読んでいない。

## 結論（先頭サマリ）

**Blocker: 0件。Major: 3件。Minor: 4件。判断保留: 0件。既知の限界（tester報告済み、確認のみ）: 2件。**

前回監査のMajor#1（`addCandidateDateOpen`の正の効果が未検証だった2段構成）は**解消されている**——
TDR-GTH-02は`gathering-add-candidate-date-open`のクリックで
`gathering-add-candidate-date-form`が実際にDOMへ出現することを直接検査したうえで、そのフォームへ
入力し送信し、新しい候補日がDOM上に現れることまでを一気通貫でブラウザ操作として検証するよう
書き直されている。無副作用検査（クリック単体で局面・候補日一覧が変わらないこと）も同じ関数内に
残しており、退行していない。

横断検査（`assert_gathering_screen_has_no_forbidden_surfaces`）は`ADR-0039`の
`operationalControlScope`（登録済みtest id＋ネイティブ`input`/`textarea`タグの二重条件による
限定的免除）を正確に反映しており、`GATHERING_ALLOWED_PURPOSES`・`GATHERING_FORBIDDEN_TEST_IDS`・
`GATHERING_DISCLOSURE_FORBIDDEN_TEST_IDS`・`GATHERING_VALUE_ENTRY_CONTROL_TEST_IDS`・
`GATHERING_FORBIDDEN_PURPOSES`の5つの定数リストは、いずれも契約v0.4の対応する列挙と**1対1で完全一致**
することを直接突き合わせて確認した。この検査は一覧（TDR-GTH-21/22）・作成（TDR-GTH-23）の両新設
namespaceでも呼び出されており、前回監査Major#3で指摘した「一度も呼ばれない」状態からは大きく改善して
いる。

一方で、今回のコード読解で新たに3件のMajor（過不足の「不足」）を見つけた——(1)
`gathering-list-item`が契約上持つべき5属性のうち2つ（`data-responded-count`・
`data-active-issued-links`）が一度も読まれず検査されていない、(2)
`organizerGatheringCreate.submit`の成功経路（および重複拒否分岐）がブラウザ操作として一度も
駆動されていない——これは契約が`TDR-GTH-01`を`notVerifiedHere`から`verifiesScenarios`へ格上げした
という設計意図と噛み合っていない、(3) 横断検査自体が`gathering-add-candidate-date-form`（および
その内部の`gathering-add-candidate-date-input`）が実際にDOM上に存在する状態で一度も呼ばれていない
——ADR-0039の核心である「登録された値入力コントロールの限定免除」が、まさにその存在理由となった
コントロールに対して実地検証されていない。詳細は個別論点1〜3。

## 対訳表（コードから読み取った記述 → シナリオとの突き合わせ）

| ID | 実際にコードが行うこと | シナリオ文・契約との一致 |
|---|---|---|
| TDR-GTH-02（書き直し） | `gathering-add-candidate-date-open`をクリック→クリック直後に`gathering-add-candidate-date-form`がDOMに現れることを検査（正の効果）→クリック前後で局面・候補日一覧が不変であることも同時に検査（負の効果）→フォームへ日時を入力→送信→新規候補日が1件だけ増えたことをid集合差分で検査→局面が「日程を聞き中(SCHEDULING)」のまま→フォームが送信後も開いたまま残ることを検査。 | **一致、かつ前回監査Major#1を解消**。`addCandidateDateOpen.requiredOutcome`（正の到達可能性）・`addCandidateDateForm.presenceRule`（送信後も開いたまま）の両方が実際にブラウザ操作で検証されるようになった。新規候補日の同定を`candidate_date_id_at`（バイト同一性に依存する既存の脆さ）ではなくid集合差分で行っており、前回監査が記録した脆さの再導入も避けている。 |
| TDR-GTH-21 | 幹事が2件の会をAPI経由で作成（Given状態構築、adr/0037決定1準拠）、うち1件をAPI直で確定済み（SELECTING_SHOP）にする。一覧を開き、DOM順（createdAt降順）・`data-gathering-id`・`data-gathering-phase`・`data-confirmed-candidate-date`（確定済みはISO文字列、未確定はNone）が期待どおりであることを検査。横断検査（forbidden surfaces）を実行。未確定の会を一覧から開き、URLに対象`gatheringId`が含まれること・ダッシュボードの局面表示が正しいことを検査。 | **部分一致**。「名前・局面・確定した開催日が示される」のうち局面・確定開催日は検査されているが、**名前は契約自体に対応するdata属性が無く検査不能**（`assert_gathering_list_matches`のdocstringが明記、既知の限界。下記「確認事項1」）。加えて、契約が`gathering-list-item`に定める5属性のうち`data-responded-count`・`data-active-issued-links`の2つは一度も読まれない（下記「個別論点1」）。 |
| TDR-GTH-22 | 会0件の状態で一覧を開き、`gathering-list-empty`の存在・`gathering-list-item`の不在を検査。横断検査を実行。`gathering-list-empty`内の（`empty_state.locator`でスコープを絞った、かつ「その要素は1個だけ」であることを`to_have_count(1)`で検査した）createOpenをクリックし、会をつくる画面（`gathering-create-name-input`の出現）が開くことを検査。 | 一致。「一覧が0件でも`gathering-list`自体がDOMに存在しなければならない」という契約の要求は、`open_organizer_gathering_list()`が`wait_for_at_least_one(GATHERING_LIST)`で待つ形で暗黙に強制されている（合流検証でtester/developerが実際に踏んだ回帰の再発防止として機能する構造）。 |
| TDR-GTH-23 | 会の一覧のヘッダーから会をつくる画面を開き（`.first`で先頭のcreateOpenをクリック——下記「個別論点5」参照）、名前だけ入力し、送信ボタンがネイティブdisabled状態であることを`expect().to_be_disabled()`で検査。別途、その無効化されたUIをバイパスしてAPIへ`candidateDates: []`で直接POSTし、`400 REQUEST_REJECTED`を検査（契約に専用コードが無いため契約上最も具体的な検査、と明記）。`listGatherings`で該当タイトルの会が存在しないことを検査。横断検査を実行。 | 一致。disabledStateをUXの代理検査とし、サーバー境界は別途API直叩きで検証する構成はTDR-GTH-20の先例と同型。 |
| TDR-GTH-24 | 既存候補日と同一日時の会をGiven状態としてAPI経由で構築、ダッシュボードを開き候補日一覧のスナップショットを取得、インラインフォームを開いて同一日時を再度送信、応答が`409 DUPLICATE_CANDIDATE_DATE`であること・候補日一覧がスナップショットと完全一致（順序含む）で不変であること・フォームが開いたままであること・入力欄の値が送信時の値のまま保持されていることを検査。 | 一致。`addCandidateDateForm.submit.requiredOutcome`のDUPLICATE_CANDIDATE_DATE分岐（フォーム開いたまま・入力値保持・候補日追加なし）を厚く検査している。 |
| TDR-GTH-25 | ランチ候補の母集団を用意し、進行中（SCHEDULING）の会を2件作成、ランチ候補画面を開いて`candidate-gathering-entry-badge`の`data-in-progress-gathering-count`が"2"であることを検査、導線をクリックして会の一覧画面（`gathering-list`の出現）が表示されることを検査。 | 一致（Given/When/Thenそのものは満たす）。ただし`getInProgressGatheringCount`のカウント境界（SELECTING_SHOPも計上・FINALIZEDは除外・0件ならバッジ自体が不在）はこのシナリオでは検査されない範囲——.featureのGiven文自体が「進行中の会をいくつか」としか要求していないため、過不足の「不足」とまでは言えない（下記「個別論点7」に記録のみ）。 |

### 確認事項1（task指示のとおり、確認のみ）: 会一覧の「名前」は契約のdata属性が無く検査不能

`organizerGatheringList.list.item.attributes`（`gathering-scheduling-browser-interface.yaml`
v0.4）は`id`/`phase`/`confirmedCandidateDate`/`respondedCount`/`activeIssuedLinks`の5属性のみを
定義し、会の名前（`title`）に対応するdata属性が無い。`.feature`のTDR-GTH-21は「それぞれの会に
ついて、名前・局面・確定した開催日（あれば）が示される」と明記しているにもかかわらず、
`assert_gathering_list_matches`は名前を検査対象から外し、その理由をdocstringで明記している
（"the contract's gathering-list-item attributes ... define no machine-observable name field,
so the .feature's "名前...が示される" clause cannot be verified here"）。これは**tester側の
緩みではなく契約側の欠落**であり、FR-028としてarchitectへ送付済みであることを`activeContext.md`
（2026-09-02付の入口追補実装記録）で確認した。tester の対応（緩めずに欠落を明記した文書化）は
P-08の精神に沿っており、reviewerとしても妥当と判断する——追加の指摘事項としては扱わない。

### 確認事項2（task指示のとおり）: TDR-GTH-01がAPI直のまま残置されている件への見解

`gathering-scheduling-browser-interface.yaml`のヘッダコメント（2026-09-01追補）は「TDR-GTH-01は、
専用の作成画面が無かったために`notVerifiedHere`としていたが、この追補で解消し
`verifiesScenarios`へ移した」と明記し、実際`profiles.localAcceptance.verifiesScenarios`に
`TDR-GTH-01`が含まれ、`notVerifiedHere`からは外れている（残るのはTDR-GTH-13のみ）。
`renderModel`は「verifiesScenariosに挙がるものはJS-capableなブラウザ自動化で検証する」という
実行モデルを明言している。

しかし実際の`test_tdr_gth_01_organizer_creates_a_gathering_with_candidate_dates`は変更されておらず、
`organizer_creates_the_gathering()`経由で`createGathering`をAPI直叩きするだけで、
`organizerGatheringCreate`のUIを一度も経由しない。tester はこれをモジュールdocstringで明確に開示
しており（"TDR-GTH-01's own test still drives createGathering directly ... that is out of this
slice's explicit scope"）、隠蔽ではない。

**reviewerの見解**: この開示自体は誠実だが、単に「TDR-GTH-01がAPI直のまま」という一点にとどまらない
実体がある——**契約が新設した`organizerGatheringCreate.submit`という操作サーフェス全体が、
どのTDR-GTH-XXシナリオによってもブラウザ操作として一度も駆動されていない**（下記「個別論点2」で
定量的に確認）。TDR-GTH-01を将来ブラウザ駆動へ書き直すか、GTH-23とは別に「会をつくる画面から
実際に会を作成できる」ことを検査する新規シナリオ相当のテストを追加しない限り、契約が
`verifiesScenarios`で謳う被覆状態と実際のテストスイートの間に実質的な乖離が残る。次のラウンドで
拾うべき項目として記録する（個別論点2参照、Major）。

## 個別論点

### 論点1（Major）: `gathering-list-item`の5属性中2属性（responded-count/active-issued-links）が一度も検査されない

契約は`organizerGatheringList.list.item.attributes`として
`id`/`phase`/`confirmedCandidateDate`/`respondedCount`/`activeIssuedLinks`の5つを定義し、
`requirement`は"data-responded-count and data-active-issued-links mirror
Gathering.respondedParticipantCount / Gathering.activeParticipantLinkCount exactly"と明記する。
しかし`_read_gathering_list_items`（`gathering_scheduling_browser.py`）は`id`/`phase`/
`confirmedCandidateDate`の3属性しか読まず、`assert_gathering_list_matches`もこの3属性しか比較
しない。`gathering-list-item`を検査するのは全25シナリオ中TDR-GTH-21のみであるため、この2属性は
このスライス全体を通じて一度も機械検証されない。`data-active-issued-links`は
`organizerDashboard.denominatorAttributes`側で厳重に検査されている同名の値（TDR-GTH-18の核心
検査）だが、一覧側の同名属性が独立に正しく投影されているかは別問題であり、代替されない。

### 論点2（Major）: `organizerGatheringCreate.submit`の成功経路が一度も駆動されない

`gathering-create-submit`というtest idは、コード全体を通じて**disabled状態の検査
（`assert_gathering_create_submit_is_disabled`、TDR-GTH-23）でしか触れられていない**——実際に
クリックして成功させる操作は、`GATHERING_ALLOWED_PURPOSES`集合内の文字列としてしか登場しない
（`grep`で確認）。同様に`gathering-create-candidate-date-input`（候補日欄への実際の入力）・
`gathering-create-add-candidate-date-row`（行追加）・`gathering-create-remove-candidate-date-row`
（行削除）・`gathering-create-cancel`もすべて文字列定数としてのみ存在し、Playwrightの
`click()`/`fill()`の対象になったことは一度も無い（`grep`で確認、いずれもDSL内の集合リテラル
としてのみ出現）。

結果として、`organizerGatheringCreate.submit.requiredOutcome`（成功時に`createGathering`が呼ばれ
一覧の先頭に現れること）も、その`DUPLICATE_CANDIDATE_DATE`分岐（入力保持のまま拒否）も、
`browserActions.createGathering`アクションも、一度もブラウザ経由で実演されていない。これは
確認事項2で述べたTDR-GTH-01の契約上の位置づけ（`verifiesScenarios`への格上げ）と正面から
食い違う——契約は「この操作面はブラウザで検証できる」と宣言しているが、実際にそれを検証する
シナリオが1つも無い。

### 論点3（Major）: 横断検査がADR-0039の当事者コントロール（`gathering-add-candidate-date-input`）に対して一度も実地検証されない

`screen_has_no_forbidden_controls_or_disclosures`（＝`assert_gathering_screen_has_no_forbidden_
surfaces`）は、`gathering-add-candidate-date-form`がDOMに存在する状態で一度も呼ばれない。
TDR-GTH-02とTDR-GTH-24はいずれもこのフォームを開くが、どちらも横断検査を呼び出していない
（テストコードの呼び出し列を確認、両テストとも`screen_has_no_forbidden_controls_or_disclosures`
の呼び出しが無い）。この検査を呼ぶ既存のテスト（TDR-GTH-05/08/09/16/21/22/23）は、いずれも
フォームを開かない状態でしか実行されない。

これが重い理由: `ADR-0039`が新設した「登録済みtest id＋ネイティブinput/textareaタグ」という
二重条件の免除ロジック（`is_registered_value_entry_control`）は、`gathering-create-name-input`・
`gathering-create-candidate-date-input`についてはTDR-GTH-23（作成画面が開いたまま横断検査を実行）
で実地にDOM要素へ対して働くことが確認できるが、`gathering-add-candidate-date-input`——
architectのADR-0039起草コメントが名指しした、この設計変更の**直接の原因の1つ**である
コントロール——については、免除ロジックが実際にレンダリングされた要素に対して正しく機能するかが
一度も確かめられない。もし実装がこの要素を誤って`<div contenteditable>`等の非`input`/`textarea`
要素にしていた場合や、`purpose`属性の無い別の禁止カテゴリ要素にこのtest idを誤って再利用した
場合、このテストスイートはそれを検出できない。

### 論点4（Minor）: 値入力免除の判定が`type`属性まで見ていない

`is_registered_value_entry_control`は`tag_name in {"input", "textarea"}`のみを見ており、
`<input>`の`type`属性（text/date/time/datetime-local/number）までは確認しない。契約の
`operationalControlScope`は明示的に「native `input` (of type text/date/time/datetime-local/
number) or `textarea`」と型を限定しているが、テスト側の判定はタグ名のみで型を見ないため、
理論上は`gathering-create-name-input`のようなtest idが誤って`<input type="checkbox">`等へ
付け替えられても、この横断検査は素通りしてしまう。現在の登録リスト4件はいずれも実際には
テキスト/日時系の入力であるため実害は無いが、契約が定める限定条件の一部（型の限定）を
テストコードが構造的に強制していない。

### 論点5（Minor）: `gathering-create-open`の「常設ヘッダー」インスタンスが非空リスト状態で一度も押されない

`open_gathering_create_from_header`（TDR-GTH-23）は`.first`で先頭の`gathering-create-open`を
クリックするが、呼び出し時点の状態は`reset_state()`直後で会が0件——つまり
`gathering-list-empty`内のインスタンスと常設ヘッダーのインスタンスが**両方**存在する状態である。
`.first`がどちらを拾うかはDOM順序（ヘッダーが本文より先、という契約が固定していない前提）に
依存する。TDR-GTH-22は`empty_state.locator(...)`で明示的に空状態側のインスタンスへスコープを
絞っているため、両テストが実際に異なる要素を叩いている可能性は高いが、契約上保証された区別では
ない。両インスタンスの`requiredOutcome`は同一（同じ画面へ遷移）と契約が明記しているため実害は
無く、実装が全く問題なくても検出できないバグは無い——記録のみ。より本質的な指摘は、**会が1件以上
ある状態でのヘッダーの`gathering-create-open`単体**（空状態パネルが存在しない場合の、真に唯一の
インスタンス）が、どのシナリオでも一度もクリックされないことである。

### 論点6（Minor、シナリオに紐付かない追加観察）: 新設操作の一部が丸ごと未検証

以下は`.feature`のどのTDR-GTH-XXシナリオも文面上要求していないため過不足の「不足」とは言えないが、
契約が新設した操作面のうち一度もブラウザ操作として実演されないものとして記録する:
`organizerGatheringCreate.candidateDateRow.addRow`/`removeRow`、`organizerGatheringCreate.cancel`、
`organizerDashboard.candidateDateList.addCandidateDateForm.cancel`（インライン追加フォームの
「やめる」）。次に`tests/acceptance/**`を触る人が拾うべき対象として申し送る。

### 論点7（Minor、シナリオに紐付かない追加観察）: `getInProgressGatheringCount`の境界（SELECTING_SHOP計上・FINALIZED除外・0件時のバッジ不在）が未検証

TDR-GTH-25はSCHEDULING局面の会2件だけを用意しており、`candidate-gathering-entry-badge`の
`presenceRule`（"Present exactly when the count is greater than zero; absent when it is
zero"）のうち0件分岐、および`getInProgressGatheringCount`がSELECTING_SHOPも計上しFINALIZEDを
除外するという定義（`activeContext.md`のdeveloper記録）は、いずれもこのスライスのシナリオでは
検証されない。`.feature`のTDR-GTH-25自体のGivenが「進行中の会をいくつか」としか要求していない
ため、これも過不足の「不足」というよりは契約Mustのうち特定シナリオに紐付かない部分の記録である。

### レビューチェックリスト（5観点）

1. **過不足**: 過剰な検査は見当たらない。不足は論点1・2・3（Major、いずれも実際に存在する契約
   Mustの未検査）および論点4〜7（Minor）のとおり。TDR-GTH-02・21〜25の6シナリオすべてに対応する
   テストメソッドは存在し、シナリオ→テストの1対1対応の欠落は無い。
2. **Givenの正当性**: `given_multiple_scheduling_gatherings`・`confirm_candidate_date_via_api`は
   いずれも公開API境界（`gathering-scheduling-api.yaml`）を経由しており、`adr/0037`決定1に
   引き続き準拠している。DB直接操作・未承認seamの使用は無い。`confirm_candidate_date_via_api`が
   確定操作自体をAPI直で行っている点は、確定操作そのものの正しさをTDR-GTH-10/11が別途検査済み
   であることを踏まえたGiven状態構築として妥当と判断する（docstringが明記、既存の同型パターン
   TDR-GTH-13/20のAPIバイパスと整合）。
3. **Thenの検証対象**: TDR-GTH-24（重複拒否）は候補日一覧の完全一致比較・入力値保持まで検査して
   おり模範的。一方、論点1・2・3のとおり、複数の契約Mustが未検証のまま残る。
4. **失敗の握りつぶし**: `try/except`によるエラー隠蔽、無条件`pass`、意味のないtrueアサーションは
   3ファイルいずれにも見当たらない（`grep`で確認済み）。
5. **暗黙の前提**: `_fill_candidate_date_time_input`は、日時入力欄がネイティブ
   `datetime-local`型（またはその等価な2分割入力）であることを前提にしている——これは同ラウンドで
   developerが実際に踏んだタイムゾーン起因バグ（FR-028、`activeContext.md`に記録済み・修正済み）
   と直接関係する前提であり、既に一度実地で崩れて修正された経緯がある。今回のテストは修正後の
   規約（datetime-localの生の数字をUTCとしてタグ付けする実装）と整合しており、TDR-GTH-24が
   全緑であることを`activeContext.md`で確認したが、この整合はtester側の固定フィクスチャ規約と
   実装側の変換規約という**2つの独立した約束が偶然噛み合っている**構図であり、契約自体はどちらの
   タイムゾーン解釈が正しいかを決めていない（developer申し送り済み、architect/人間の判断待ち）。
   論点5に記載した`.first`のDOM順序依存も同種の暗黙の前提である。

## 契約↔テスト対応の監査

- **承認済みシナリオのうちstep未実装のもの**: 無し（TDR-GTH-02・21〜25すべてに対応するテスト
  メソッドが存在する）。
- **シナリオに対応しない孤児step**: 無し。`gathering_scheduling_steps.py`の全メソッドが
  `test_gathering_scheduling_acceptance.py`から呼ばれていることを機械的に確認した
  （未使用0件）。`gathering_scheduling_browser.py`のDSLメソッドも、`candidate_date_id_at`
  （既存の意図的な直接呼び出しパターン、前回監査で確認済み）を除き全て`steps.py`経由で使用されて
  いることを機械的に確認した（未使用0件）。前回監査Minor#6で指摘した`assert_participant_progress`
  はコードベースから完全に削除されている（`grep`で0件、5fd4a5aで対応済みと符合）。
- **同義stepの重複**: 見当たらない。
- **契約定数リストとテスト定数リストの1対1一致**: `GATHERING_ALLOWED_PURPOSES`（17件）・
  `GATHERING_FORBIDDEN_TEST_IDS`（3件）・`GATHERING_DISCLOSURE_FORBIDDEN_TEST_IDS`（3件）・
  `GATHERING_VALUE_ENTRY_CONTROL_TEST_IDS`（4件）・`GATHERING_FORBIDDEN_PURPOSES`（2件）の
  いずれも、契約`gathering-scheduling-browser-interface.yaml` v0.4の対応する列挙と完全一致する
  ことを直接突き合わせて確認した——ズレは無い。
- **契約が定めるがどのシナリオ番号にも紐付かないMust**: 論点6・7に記載のとおり。

## 人間の承認判断のためのチェックリスト

- [ ] Blocker: 0件（本監査の判定）
- [ ] 前回監査Major#1（TDR-GTH-02の正の効果未検証）は解消されている、との本監査の判定に同意するか
- [ ] Major論点1（`gathering-list-item`の`data-responded-count`/`data-active-issued-links`が
      未検査）を、本PRのブロッカーとするか次PRへ送るか
- [ ] Major論点2（`organizerGatheringCreate.submit`の成功経路が一度もブラウザ駆動されず、
      契約の`verifiesScenarios`宣言と実態が食い違う）——TDR-GTH-01の書き直し、または新規シナリオの
      追加のいずれを次スライスに求めるか
- [ ] Major論点3（横断検査が`gathering-add-candidate-date-form`存在下で一度も走らない）を、
      本PRのブロッカーとするか次PRへ送るか——修正はTDR-GTH-02またはTDR-GTH-24へ1行
      `screen_has_no_forbidden_controls_or_disclosures()`呼び出しを足すだけで解消可能
- [ ] Minor論点4〜7（型属性未確認・ヘッダーインスタンス未検証・addRow/removeRow/cancel系未検証・
      進行中件数の境界未検証）の扱い
- [ ] 確認事項1（会一覧の「名前」検査不能）はFR-028としてarchitect送付済みで対応不要、との
      本監査の確認に同意するか
- [ ] 確認事項2（TDR-GTH-01のAPI直残置）の見解——契約の`verifiesScenarios`宣言との整合をどの
      タイミングで取るか（Major論点2と合わせて判断）

以上。
