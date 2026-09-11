# 独立監査: 実機フィードバック大改訂（会モード一本化・可視性反転・PC2カラム・カレンダー・会削除）

- 監査対象: `git diff origin/main...origin/integrate/gathering-field-feedback -- projects/dining-radar/tests/acceptance/`
  （コミット `2a3fb92`。`dsl/gathering_scheduling_browser.py`・`dsl/candidate_search_browser.py`・
  `steps/gathering_scheduling_steps.py`・`steps/candidate_search_steps.py`・
  `test_gathering_scheduling_acceptance.py`・`test_candidate_search_acceptance.py`の6ファイル）。
- 依拠した契約: `gathering-scheduling.feature`（TDR-GTH-01〜48）・`candidate-search.feature`
  （TDR-CS-00〜19、07は廃止）・`gathering-scheduling-api.yaml`／`-browser-interface.yaml`・
  `candidate-search-api.yaml`／`-browser-interface.yaml`・`test-support-api.yaml`（いずれも
  `origin/integrate/gathering-field-feedback`の実体、v1.5.5）・`projects/dining-radar/adr/0049`・
  `0050`・`0051`。
- **独立性の担保**: `git show origin/integrate/gathering-field-feedback:<path>`でコード本体のみを
  読み下し、シナリオ文（`.feature`）と突き合わせた。docstring・コメントは「コードが実際に何を
  しているか」の記述として引用する場合に限り採用し、意図の弁明としては採用していない。`src/**`は
  読んでいない。
- **手順上の注記（自己訂正）**: 監査序盤、Readツールで`projects/dining-radar/tests/acceptance/**`を
  直接開いたところ、worktreeのHEADが`1125d7e`（本ラウンドの変更を一切含まない、旧`main`相当）に
  据え置かれたままであることに気づかず、廃止済みの`shortlistSelection`関連コード（`OPEN_SHOP_LIST`
  等）を「現行コードに残る重大な欠陥」と誤認しかけた。`git show origin/integrate/...:<path>`で
  取り直した実体ではこれらは正しく削除されていることを確認済み——以後の全記述は`git show`で
  取得した内容にのみ基づく。

## 結論（先頭サマリ）

**Blocker: 0件（テスト内容そのものに対して）。ただし別枠で「マージ順序の懸念」を1件報告する
（下記参照、対応はorchestrator/人間の領分）。Major: 2件。Minor: 3件。**

この改訂は非常に大きい（DSL 2本で1500行超の差分）が、コードの成熟度は高い。個々のdocstringが
過去の監査Major/Minor番号を名指しして再発防止を明記する慣行が徹底しており（例:
「Reviewer audit Major#1」「reviewer audit Minor#4」）、廃止された観測面
（`shortlistSelection`・`OpenShopPreviewItem`・送りボタン・件数カウンタ・確定後の店ごとの記録）
への依存は**一件も残っていない**——全て正しく退役し、退役の事実自体が定数名・コメントとして
明示されている。可視性の反転（TDR-GTH-12・29）も、新規則（無条件present）を検査する形へ正しく
置き換わっており、旧規則（回答前は不在）を検査する残骸コードは存在しない。`ALLOWED_CONTROL_
PURPOSES`（candidate-search、18件）・`GATHERING_ALLOWED_PURPOSES`（gathering-scheduling、26件）
はいずれも契約の`allowedPurposes`列挙と1:1で一致することを直接突き合わせて確認した。曜日依存・
表示上限・`minItems:1`の3つの偶発的破綻（ADR-0052が名指ししたもの）は、companion gathering・
`shownProviderPageUrls`の2回呼び出し（shown-pool-priority）という決定的な技法へ作り直されており、
もはや偶然に頼っていない。

その上で、**この画面（gatheringMode）に固有の新しい業務規則2点の検証が実質的に弱い**ことを
Majorとして報告する——いずれも「店選びの一本化」という今回の目玉機能そのものの正しさに関わる。

## マージ順序の懸念（Blocker相当、ただしtester起因ではない）

`test-support-api.yaml`は本ブランチ（`origin/integrate/gathering-field-feedback`）ではv1.5.5の
ままである。一方、`origin/contracts/gathering-field-feedback`ブランチには本ブランチに
**含まれていない**2件のADR（`projects/dining-radar/adr/0052`・`0053`、コミット`d81550f`・
`76ae27d`）があり、これらが`test-support-api.yaml`をv1.5.7へ改訂して
`GATHERING_OPEN_SHOP_WEEKDAY_MATCH`の説明文の陳腐化した参照（削除済みの`OpenShopPreviewItem`
スキーマを名指ししたまま）を解消している。

実際に検証したところ、**コード自体は既にADR-0052/0053の是正内容を先取りして実装済み**である
（`fetch_shop_id_closed_only_on`・`fetch_confirmed_date_open_shop_ids_with_a_spare`が
companion gathering・shown-pool-priorityの決定的技法を実装しており、`OpenShopPreviewItem`への
参照はコード中に一切残っていない）。しかし**契約ファイル（test-support-api.yaml）の文面は
まだ古いまま**であり、このブランチ単体でmainへ入ると、契約の説明文が「削除済みのスキーマを
読め」と指示したまま残る（コードと契約の記述が食い違う）状態でマージされることになる。

これはtester/reviewerの検査内容の問題ではなく、**2本の並行ブランチ（contracts系とintegrate系）
の統合順序**の問題であり、architect/orchestrator/人間が判断すべき事項として報告する。対応案:
(a) `contracts/gathering-field-feedback`（ADR-0052/0053まで）を先に、または本ブランチへの
リベース/マージで取り込んでから最終承認する、(b) 別PRとして後追いで反映することを明示的に
合意する、のいずれか。

## 対訳表（本ラウンドで新規・改訂されたシナリオのみ。既存シナリオ本文はADR-0053が別途1本ずつ
棚卸し済み——本監査はその棚卸し結果とコードの整合を独立に確認した上で重複掲載しない）

| ID | シナリオ文の要旨 | 実際にコードが行うこと | 一致判定 |
|---|---|---|---|
| TDR-GTH-08（改訂） | 候補日を仮選択→開いている店の**件数だけ**、店名等は示されない | `tentatively_select_candidate_date`が`open-shop-preview`応答を捕捉し、`assert_open_shop_preview_shows_expected_count`が`openShopCount`一致と`"previewShops"`キー不在を検査、`assert_open_shop_preview_shows_no_shop_details`が`gathering-open-shop-preview-item`要素0件を検査 | 一致。件数のみ・店単位要素ゼロの両方を実測 |
| TDR-GTH-12（全面改訂） | 自分が回答前でも他者の回答が見える。回答後も見え続ける | `test_tdr_gth_12_...`: link_bが未回答のままlink_aの回答（tally going=1）を確認→link_bが回答→tally更新（going=1,maybe=1）を確認 | 一致。回答前提示・回答後継続の両方を実測 |
| TDR-GTH-29（全面改訂） | 店投票版のTDR-GTH-12 | 同型: 未投票のlinkでshop_a=1/0/0/1、shop_b=0/0/0/0を確認→自分が投票→shop_a更新、shop_bは自分固有の未投票のまま0のままであることを確認 | 一致。店単位の独立性（shop_bは自分が答えるまで0のまま）まで検査しており厚い |
| TDR-GTH-34（簡素化） | 確定後は自分の開催日回答1行のみ、店ごとの一覧は示されない | `assert_participant_decision_has_no_shop_breakdown`が退役済みtest-id`gathering-participant-decision-shop-vote`の0件を検査、`_read_participant_decision`はスキーマ上その項目を読まない | 一致 |
| TDR-GTH-44（新規） | 店を1件ずつ会に入れる/外す | `organizer_opens_shop_selection_entry`→`gathering_mode_band_shows(0)`→`select_first_n_candidates_into_gathering(2)`→帯=2→`toggle_off_the_first_shortlisted_candidate`→帯=1。**入れた/外した事実は`refresh_gathering_from_api()`でサーバー実値（`shortlistedShops`）と突き合わせている** | 一致。サーバー真実まで確認しており厚い |
| TDR-GTH-45（新規） | 会に入れられる店は最大5件 | 5件選択→帯=5→`search_again`（shown-pool-priority技法で6件目を確実に描画）→`unselected_candidate_toggle_is_disabled`→**ダッシュボードに戻り`shortlisted_shops_match(selected)`で5件の identity が保たれていることを検査** | 一致。同一性の保存まで実証（下記TDR-CS-19との非対称参照） |
| TDR-GTH-46（新規） | 候補日の一括登録、1件でも重複すれば全体拒否 | 既存候補日+新規日をカレンダーで選択・送信→`409 DUPLICATE_CANDIDATE_DATE`→候補日リスト・カレンダーの選択状態（`data-selected`）ともに変化なしを検査 | 一致。「選択状態も戻らない（全部やめる）」まで検査しており厚い |
| TDR-GTH-47（新規） | 今日・過去日は候補日にできない | カレンダーUIの`disabledState`は契約が固定しない（月範囲不定）ためAPI直叩きで`400 CANDIDATE_DATE_NOT_IN_FUTURE`を検査。TDR-GTH-20/23と同じ「契約上任意のUI制約はAPI強制で検証する」先例に倣う、と明記 | 一致。理由が明記されており妥当 |
| TDR-GTH-48（新規） | 会を削除→候補日/回答/票/参加者名が消え、参加者リンクは開けなくなる | `delete_gathering_via_dashboard`が開く→確認ダイアログ表示中に`assert_gathering_screen_has_no_forbidden_surfaces`を実行→確定クリック→一覧から消滅を確認→参加者が同リンクを開くと`LINK_NOT_FOUND`を検査 | 一致。**削除確認ダイアログという新画面状態でFR-030チェックを実行済み**（後述） |
| TDR-CS-17（新規） | 会モードで店を入れる/外す | `organizer_opens_this_screen_in_gathering_mode`→トグルで帯0→1→2→1。band表示は**クライアント側DOM属性のみで判定**（後述Minor） | 一致するが検証強度に非対称あり |
| TDR-CS-18（新規） | 会モードでは候補がその開催日に開いている店へ絞られる | `assert_gathering_mode_candidates_are_within_open_shop_population`は`gatheringContext.gatheringId`一致と各候補の`shopId`/`isShortlisted`非null**のみ**を検査。実際に「開催日に開いている店に絞られている」ことを他の情報源と突き合わせて検査していない | **Major1（下記）** |
| TDR-CS-19（新規） | 会モードで最大5件、既存5件は変わらない | 5件選択→`search_again`→未選択トグルdisabled・選択済みトグルenabledを検査。**「既存5件がそのまま変わらない」という同一性はcandidate-search側では未検証**（GTH側の双子TDR-GTH-45は検証済み） | **Major2（下記）** |

## 個別論点

### Major 1: TDR-CS-18の「候補は開催日に開いている店へ絞られる」が実質的に未検証

`assert_gathering_mode_candidates_are_within_open_shop_population`（`csb.py`）は
`gatheringContext.gatheringId`が指定した会と一致すること、各候補の`shopId`/`isShortlisted`が
非nullであることだけを検査する。これは**絞り込みが行われていなくても常に真になる**チェックで
あり、シナリオが主張する「示される候補は、その開催日に開いている店に絞られている」という
母集団の狭窄そのものを一切証明しない。

根本原因はGiven状態の選び方にある: このテストは`lunch_candidates_can_be_proposed()`
（`NORMAL_WITH_WEIGHTED_SAMPLING`、ジャンル等でランダムに合成された汎用母集団）を使っており、
これは既知の固定件数を持たない。`test-support-api.yaml`には曜日ごとに開店数が既知
（月5/火5/水4/木6/金6/土6/日5）な`GATHERING_OPEN_SHOP_WEEKDAY_MATCH`モードが既に存在し、
`gathering_scheduling_browser.py`側のTDR-GTH-26/27/31/32/38/39/40・candidate_search_browser.py
側のTDR-CS-19自身もこのモードを使っている——このモードを使えば、`search_again`を繰り返して
shown-pool-priority技法でプールを使い尽くし、**実際に出現するshopIdの集合がその曜日の既知件数
（例: 月なら5件ちょうど）に収束すること**を数え上げることで、絞り込みの実在を定量的に証明できた
はずである。現状の実装はこの検証を行わず、絞り込みが機能していなくても（母集団が絞られず
無関係な店が混入していても）このテストは通過する。

### Major 2: TDR-CS-19の「既に入れている5件はそのまま変わらない」が候補検索側で未検証

シナリオTDR-CS-19のThenは2つある——(1)6件目は入れられない、(2)既に入れている5件は
そのまま変わらない。現在のテストは(1)のみ（`unselected_candidate_toggle_is_disabled`・
`selected_candidate_toggle_is_enabled`という**集合的な**disabled/enabled状態）を検査し、
(2)の**同一性**（5件の中身が入れ替わっていないこと）は検査していない。

対照的に、同じ業務規則の双子であるgathering側のTDR-GTH-45（`test_tdr_gth_45_...`）は、
`organizer_selects_first_n_candidates_into_gathering`が返す実際のshopId集合を保持し、
最後に`organizer_opens_the_dashboard()` → `shortlisted_shops_match(selected)`で
ダッシュボード側の`gathering-shortlisted-shop-item`から読み取った実際の5件と突き合わせて
同一性を証明している。candidate-search側にはこの読み取り経路
（`gathering-shortlisted-shop-item`はgathering-scheduling-browser-interface.yaml側の
test-id）が無い——しかしこのファイル自身が確立した「モジュール境界を跨がず生のtest-idを直接
読む」慣行（`GATHERING_MODE_BAND`等）を使えば、`GET /gatherings/{id}`を直接叩いて
`shortlistedShops`のshopId集合を読み、同一性を検査すること自体は可能だったはずである
（`fetch_confirmed_date_open_shop_ids`等、gathering_scheduling_browser.py側で既に確立された
「直接APIを叩く」パターンと同型）。

### Minor 1: TDR-CS-17/19がgatheringモードの選択結果をクライアント側DOM属性のみで判定している

`gathering_mode_band_shows`はページ自身がレンダリングした`data-gathering-shortlisted-count`
属性を読むだけで、`setShortlistedShops`のサーバー応答やその後の`GET /gatherings/{id}`で
サーバー側の実値と突き合わせていない。同じ操作をgathering側から検査するTDR-GTH-44/45は
`refresh_gathering_from_api()`で必ずサーバー実値を読み直しており、非対称になっている。
クライアントが（実際には送信に失敗していても）楽観的に帯を更新するような回帰があった場合、
TDR-CS-17/19はこれを検知できない。Major2の対応と合わせて、直接API呼び出しを1回追加すれば
解消できる。

### Minor 2: FR-030横断検査が、構造的に同一の画面のデータ違いバリエーションでは再実行されていない

`screen_has_no_forbidden_controls_or_disclosures`（gathering-scheduling側）・
`no_location_range_or_manual_order_control_exists`（candidate-search側）は、本ラウンドが
新設した要素・購入可能purpose（26件・18件、いずれも契約と1:1で一致確認済み）を含め広く
実行されている（gathering側18箇所、候補側3箇所）。個別に確認したところ、次の状態では
**明示的には**再実行されていない:

- 参加者スケジュール質問画面で、他者のtallyが自分の回答前から見える瞬間（TDR-GTH-12自身）
- 参加者店投票画面で、他者のtallyが自分の投票前から見える瞬間（TDR-GTH-29自身）
- gatheringModeの母集団絞り込み状態（TDR-CS-18）・5件到達時のdisabled状態（TDR-CS-19）

ただし調査の結果、これらはいずれも**同じ画面の別データ状態**であり、DOM構造（フォーム
コントロールの集合そのもの）は既にFR-030を実行済みの隣接シナリオ（TDR-GTH-05・09の
scheduleQuestion/shopVoteQuestion画面、TDR-CS-17のgatheringMode画面）と同一である——
tally要素はコントロールではなくデータ表示であり、disabled属性の有無もFORM_CONTROL_
SELECTORのマッチ対象から除外されない。したがって未宣言purposeの流入という実害リスクは
低いと判断し、MajorではなくMinorとして記録する。なお、gathering側の横断検査を意図的に
gatheringMode画面（TDR-GTH-38/44/45）で**実行しない**設計は正しい——
`GATHERING_FORBIDDEN_TEST_IDS`に`candidate-map`・`candidate-origin-marker`が含まれており、
これはgatheringダッシュボード文脈での禁止事項であって、gatheringMode（候補検索画面そのもの）
では正当に存在する要素である。もし誤ってgatheringMode上でgathering側の検査を呼んでいたら、
それ自体が新しい欠陥（正当な要素を誤検出）になっていたところであり、この非実行は退行ではなく
正しい設計判断と評価する。

### Minor 3: 「あとで答える」「結果をのぞく」の機能化テストにFR-030が付いていない

`test_gth_answer_later_and_peek_results_are_functional`は`gathering-participant-answer-later`・
`gathering-participant-peek-results`という2つの新規purpose（`GATHERING_ALLOWED_PURPOSES`に
登録済み、契約と1:1一致確認済み）を実際にクリックする唯一のテストだが、
`screen_has_no_forbidden_controls_or_disclosures()`を呼んでいない。この画面状態
（参加者スケジュール質問、両ボタンが実際に描画された状態）はTDR-GTH-05/09で構造的には
既にカバーされている可能性が高い（Minor2と同じ理由）が、この2つの新規purpose自体を含む
状態で明示的に確認されたことは一度もない。次回このテストを触る際に追加することを推奨する。

## レビューチェックリスト（5観点）

1. **過不足**: 検査が甘くなっている箇所はMajor1・2、Minor1〜3のとおり。逆に契約要求より厳しすぎる
   誤検出リスクのある検査は見当たらない。TDR-GTH-44〜48・TDR-CS-17〜19の全シナリオに対応する
   テストメソッドが存在する（孤児シナリオなし、下記契約↔テスト対応監査参照）。
2. **Givenの正当性**: `adr/0037`決定1（公開API境界経由）を維持しつつ、`adr/0052`が発見した
   3つの偶発的破綻（曜日依存の`identify_a_shop_closed_on_the_confirmed_date`、表示上限との
   衝突、`minItems:1`との衝突）はいずれも決定的な技法（companion gathering diff・
   shown-pool-priority 2回呼び出し・「1件は残す」設計）へ作り直されており、もはや偶然に
   頼っていない。ただしTDR-CS-18のGiven（`NORMAL_WITH_WEIGHTED_SAMPLING`）は、この
   シナリオが検査すべき「絞り込み」を検証可能にする母集団を選んでおらず、Major1の根本原因に
   なっている——Givenの選択自体がThenを検証不能にしている実例。
3. **Thenの検証対象**: 可視性反転（TDR-GTH-12/29）・確定後簡素化（TDR-GTH-34）・件数のみ
   （TDR-GTH-08）はいずれも最小要求以上に厚く検査されている。TDR-CS-18の絞り込み・TDR-CS-19の
   同一性保存はMajor1・2のとおり実質的に未検証。
4. **失敗の握りつぶし**: `try/except`によるエラー隠蔽、無条件`pass`は見当たらない。
   `except Exception: visible = False`（`_visible_walking_radius_ring_label_minutes`、
   本ラウンド範囲外の既存コード）はコメントで「detached/unstableなノードは単に見えないとみなす」
   と明記されており、握りつぶしではなく意図的なフェイルセーフ。
5. **暗黙の前提**: `fetch_shop_id_closed_only_on`は「差分は空でない」ことだけを要求し
   （単一性は要求しない、`adr/0052`の指摘どおり実際は複数件になりうることを踏まえて
   `assertGreaterEqual`へ弱めてある——これは正しい弱化であり、契約が保証しない基数を
   過剰に要求していた旧実装のバグを是正したものである）、`_probe_open_shop_ids_on`は
   呼び出し順序に依存しないよう`_created_candidate_date_isos`等の状態を保存・復元する
   （過去に順序依存のバグを実際に再現したとdocstringに明記）。TDR-CS-18のGiven選択
   （Major1）は「暗黙のうちに検証不能な前提を選んでいる」実例として扱う。

## 契約↔テスト対応の監査

- **承認済みシナリオのうちstep未実装のもの**: 無し。TDR-GTH-01〜48（欠番なし、48シナリオ）・
  TDR-CS-00〜19（07は契約上廃止済み、19シナリオ）のすべてに対応する`test_tdr_*`メソッドが
  存在することを`grep`で確認した。
- **シナリオに対応しない孤児step**: 無し。`test_gth_answer_later_and_peek_results_are_functional`
  はシナリオ番号を持たないが、契約自身がこの2操作を「シナリオを持たない契約Must」と明記して
  おり、TDR-GTH-43のソート検査・TDR-CS-02のデスクトップ/モバイル分割と同じ先例に倣う正当な
  扱いである（孤児ではなく意図的な無番号テスト）。
- **同義stepの重複**: 見当たらない。`replace_shortlisted_shop`（gathering側、APIブースト経由の
  差し替え）と`toggle_first_candidate_into_gathering`/`toggle_off_the_first_shortlisted_
  candidate`（candidate-search側、UIトグル経由の入替）は同じ`setShortlistedShops`を呼ぶが、
  検査対象（サーバー側の票の保存 vs. UIのトグル可視化）が異なり重複ではない。
- **purposeの許可一覧と契約列挙の1:1対応**: `ALLOWED_CONTROL_PURPOSES`（candidate-search、
  18件）・`GATHERING_ALLOWED_PURPOSES`（gathering-scheduling、26件）とも契約本文の
  `allowedPurposes`列挙と実際に突き合わせ、過不足なく一致することを確認した
  （過去の監査で指摘された「一覧と実体のずれ」は本ラウンドには存在しない）。

## 人間の承認判断のためのチェックリスト

- [ ] **マージ順序の懸念**（Blocker相当）: `test-support-api.yaml`をv1.5.7へ改訂する
      `projects/dining-radar/adr/0052`・`0053`（`origin/contracts/gathering-field-feedback`
      ブランチのみに存在）を、本ブランチのマージ前後どちらで取り込むかを決定する
- [ ] Major1（TDR-CS-18の絞り込み検証が実質的に非検証）を本PRのブロッカーとして
      testerへ差し戻すか、次PRへ送るか
- [ ] Major2（TDR-CS-19の同一性保存が候補検索側で未検証）を同様にどう扱うか
- [ ] Minor1〜3は次回のこの画面群を触るラウンドへ送ってよいか、本PRで埋めるか
- [ ] `gathering-scheduling.feature`・`candidate-search.feature`・両`-api.yaml`・
      両`-browser-interface.yaml`はいずれも`status: 承認待ち`のまま——本PRのマージが骨格承認・
      実装承認を兼ねる従来運用のままでよいか

以上。
