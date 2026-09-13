# 独立監査: 会に入れた店が残り1件のときのトグル非活性化（TDR-CS-22ほか、ADR-0057）

- **監査対象**: `git diff 129e3ae..93ee919 -- projects/dining-radar/tests/acceptance`
  （`test/last-shortlisted-shop-toggle`のHEAD、commit `93ee919`）。対象ファイル: 6本——
  `dsl/candidate_search_browser.py`・`dsl/gathering_scheduling_browser.py`・
  `steps/candidate_search_steps.py`・`steps/gathering_scheduling_steps.py`・
  `test_candidate_search_acceptance.py`・`test_gathering_scheduling_acceptance.py`。
  `129e3ae..93ee919`の全差分（`--stat`で確認）はこの6ファイルに限られ、`src/**`への漏れは無い
  （`src/**`は読んでいない）。
- **起点の確認**: 指示どおり`git fetch origin && git checkout -b review/last-shortlisted-shop-toggle
  origin/test/last-shortlisted-shop-toggle`を実行し、`git log --oneline -1` = `93ee919`、
  `candidate-search.feature`の`TDR-CS-22`出現を確認（2件: シナリオ本文1＋見出しコメント1）した
  うえで作業を継続した。
- **依拠した契約**: `candidate-search-browser-interface.yaml`（1.11.0、`gatheringMode.cardToggle.
  disabledState`/`disabledReason`/`lastShopNotice`）・`candidate-search-api.yaml`（`Candidate.
  isShortlisted`/`shownProviderPageUrls`の非決定性に関する記述）・`candidate-search.feature`
  （TDR-CS-20〜22）・`gathering-scheduling.feature`（TDR-GTH-44）・`test-support-api.yaml`
  （`GATHERING_OPEN_SHOP_WEEKDAY_MATCH`・TDR-CS-22の一覧登録）・`gathering-scheduling-api.yaml`
  （`version: 0.15.0`、`minItems: 1`）・`adr/0057-disable-and-explain-the-last-shortlisted-shops-
  toggle.md`。
- **独立性の担保**: 本worktree内でBash（相対パスなし・絶対パスのみ）・Read・Grepだけを使い
  コード本体を読み下した。シナリオ文（`.feature`）はコードを読み終えたあとに突き合わせた。
  docstring・コメントは「コードが実際に何をしているか」の技術的記述として引用する場合に限り
  採用し、testerの意図の弁明としては採用していない——後述のMajor所見は、むしろdocstringの
  「guaranteed」という自己申告そのものが契約の記述と矛盾することを、契約とコードベース自身の
  別ファイルの記述から独立に指摘したものである。

## 結論（先頭サマリ）

**Blocker: 0件。Major: 1件。Minor: 3件。**

TDR-CS-20・TDR-GTH-44のGiven書き換え（ADR-0057決定6が指示した「外す対象がその1件だけに
ならないよう、すでに別の1件を会に入れている前提へ改める」）は、いずれも実装済みの是正
（`toggle_off_the_first_shortlisted_candidate_card`の位置ベースlocator再解決バグの修正）に
正しく相乗りしており、`minItems: 1`（P2）に一度も抵触しない構成になっている。TDR-CS-21の
`disabledReason=limit-reached`拡張、TDR-CS-22の新規4アサーション（非活性・理由属性・
`lastShopNotice`の存在/不在をカード単位で検査）は、属性名・値ともに契約1.11.0の文言
（`data-gathering-toggle-disabled-reason`、`limit-reached`/`last-shop`、
`candidate-card-gathering-last-shop-notice`）と1文字違わず一致し、文言（可視テキスト）の
検査には踏み込んでいない——契約が明記する「内容だけ固定、文言は固定しない」の流儀を
正しく尊重している。

その上で、**TDR-CS-22の新設Given（`given_a_gathering_with_exactly_one_shortlisted_shop`）が、
このコードベース自身がかつて実際に踏んだのと同型の非決定性の罠にかかっている**（Major、
下記）ことを報告する。これは検査の甘さではなく、Givenの構成が「毎回同じ状態を作れるか」という
決定性の観点で穴を持つという指摘であり、実際に発火した場合は静かに誤って合格するのではなく
`to_have_count(1)`のタイムアウトとして大きな声で失敗する。

## 対訳表

| ID | シナリオ文の要旨 | 実際にコードが行うこと | 観測される契約面 | 一致判定 |
|---|---|---|---|---|
| TDR-CS-20（Given書き換え） | 会モードで店を会に入れると地図のピンにもその状態が示される。Given: 「すでに別の1件を会に入れている」 | `test_tdr_cs_20_...`は`organizer_adds_a_candidate_to_the_gathering()`（画面内カードを直接クリック、`toggle_first_candidate_into_gathering`）でGivenの1件をブラウザ操作のみで作り、`toggle_a_not_yet_shortlisted_card_and_return_ref`で2件目をカード単位のrefを保持して追加、`toggle_off_card_by_candidate_ref`でrefを指定して外す。各遷移直後に`gathering_mode_band_shows`で1→2→1を検査 | `gatheringMode.cardToggle`/`mapMarker`（1.11.0で変更なし） | 一致。GivenがAPI直叩きではなくブラウザの同一セッション内操作のみで組み立てられており、後述Majorの「別セッションの独立抽選」問題を構造的に回避している |
| TDR-GTH-44（Given書き換え） | 幹事は店を1件ずつ会に入れたり外したりできる。Given: 「すでに別の1件を会に入れている」 | `open_shop_ids_for_the_confirmed_date()[0]`（`/candidate-proposals`への単発API呼び出しの先頭要素）を`organizer_shortlists_shops_via_api`で先に会に入れておき、画面を開いたあと`toggle_one_not_yet_shortlisted_candidate_card_and_return_ref`/`toggle_off_candidate_card_by_ref`で別の1件を足して外す。各遷移で`gathering_mode_band_shows`（サーバー側`shortlistedShopCount`由来）を1→2→1で検査 | `SetShortlistedShopsRequest`の`minItems: 1`（無変更）、`gatheringMode.cardToggle` | 一致（ただし下記「GTH-44は当初疑ったが無害と判定」参照）。Thenが依存するのは常にband（サーバー真値）と「新たに足した/外したその1件」のみで、Givenで先に入れた特定の1件がこの後の画面描画に実際に**現れるかどうか**には一切依存しない構成になっている |
| TDR-CS-21（拡張、シナリオ文は無変更） | 会モードで5件に達すると、帯からその理由が分かる | 既存の帯検査に加え、`organizer_searches_again_on_shop_selection_entry`→`unselected_candidate_toggle_is_disabled`→`unselected_candidate_toggle_disabled_reason_is_limit_reached`を追加。`.first`の未選択トグルに`disabledReason="limit-reached"`、ページ全体に`lastShopNotice`が0件であることを検査 | `gatheringMode.cardToggle.disabledReason`（ADR-0057決定2、値`limit-reached`） | 一致するが**Minor3**（下記）——`.feature`のGherkin本文（Given/When/Then）は「帯」の話のみで、カード単位の`disabledReason`には一切触れていない。契約Mustの検査自体は正しいが、シナリオIDとテキストの対応が薄くなっている |
| TDR-CS-22（新規） | 会に入れた店がちょうど1件のとき、その店のトグルは押せず理由が添えられる。もう1件入れると両方押せる見た目に戻り理由も消える | Given: `given_a_gathering_with_exactly_one_shortlisted_shop`（`/candidate-proposals`への単発API呼び出しで得た`candidates[0]`を`PUT .../shortlisted-shops`で確定）。1つ目のThen: `assert_only_shortlisted_toggle_is_disabled_with_last_shop_reason`（`shortlisted="true"`トグルがちょうど1件・`disabled`・`disabledReason="last-shop"`・自カードに`lastShopNotice`1件、他の全カードは`enabled`・`disabledReason`不在・`lastShopNotice`0件を個別に検査）。2つ目のThen: `assert_both_shortlisted_toggles_enabled_and_no_last_shop_notice`（2件とも`enabled`・`disabledReason`不在、ページ全体で`lastShopNotice`0件） | `gatheringMode.cardToggle.disabledState`ケース(2)・`disabledReason`・`lastShopNotice`（いずれも1.11.0新設） | **前半（Then2本）は一致・厚い。Givenの決定性にMajor（下記）** |

## 個別論点

### Major 1: TDR-CS-22のGivenが、独立した2回の`proposeCandidates`抽選の一致を無保証で仮定している

`given_a_gathering_with_exactly_one_shortlisted_shop`
（`dsl/candidate_search_browser.py:643`）は次の手順を踏む。

1. `given_a_selecting_shop_gathering`で会を作成・確定（既定では`candidate_date_iso`未指定＝
   「+3日後」で曜日は実行日依存）。
2. `_gathering_api("POST", "/candidate-proposals", {"gatheringId": gathering_id})`という
   **ブラウザを経由しない生API呼び出し**を1回行い、その`candidates[0]["shopId"]`を選ぶ。
3. `PUT /gatherings/{id}/shortlisted-shops`でその1件を確定させる。

その後、テスト本体（`test_tdr_cs_22_...`、`test_candidate_search_acceptance.py:475`）は
`organizer_opens_this_screen_in_gathering_mode(gathering_id)`でブラウザから**別の、独立した**
`proposeCandidates`呼び出しを発生させ（`open_gathering_mode_from_dashboard`内の
`capture_candidate_proposal_response`、`dsl/candidate_search_browser.py:688`）、その結果に対して
`assert_only_shortlisted_toggle_is_disabled_with_last_shop_reason`が
`expect(shortlisted_toggles).to_have_count(1)`を要求する——つまり**手順2で選んだ店が、手順4の
独立した抽選でも画面に描画されること**を前提にしている。

このGivenのdocstring（`dsl/candidate_search_browser.py:650`以降）は「そのshopIdはこのgathering
自身のproposeCandidates応答から読むので、この画面自身が描画する候補の1つであることが
guaranteed（保証済み）」と述べているが、これは**契約自身が明記して否定している性質**である。
`candidate-search-api.yaml`は次のとおり明記する（同ファイル605〜640行付近）:

> Up to 5 candidates, distance-weighted-randomly sampled with not-yet-shown priority...
> The response carries no random seed; **production sampling is non-deterministic between
> requests**（強調引用者）

`GATHERING_OPEN_SHOP_WEEKDAY_MATCH`の母集団は曜日ごとに「月5/火5/水4/**木6/金6/土6**/日5」
（`OPEN_SHOP_COUNT_BY_WEEKDAY`、`dsl/candidate_search_browser.py:364`）であり、表示上限5件を
超える木・金・土（7曜日中3日）では、手順2の抽選と手順4の抽選は**互いにshownProviderPageUrls
を共有しない、それぞれ独立な「初回」抽選**になる（`shownProviderPageUrls`はサーバーが保持
するのではなく**リクエスト側が渡す**フィールドであり、手順2は生APIコール、手順4はブラウザの
別セッションなので、互いのshown履歴を知らない）。したがって6件母集団から5件を無作為抽出する
独立試行が2回行われるだけであり、手順2で選ばれた1件が手順4の抽選でも選ばれる保証は無い
（一様重みだとして概算1/6の確率で漏れる。既定Given（曜日未指定）が木・金・土に着地する確率は
7日中3日なので、通算で概算1回あたり約7%、`+3日`固定のためGTH-44のように毎回同じ曜日に着地する
ケースほどではないにせよ、無視できない頻度で発火しうる）。

**この懸念は推測ではなく、このコードベース自身が過去に実際に踏んだ同型のバグの記録と一致する**。
`dsl/gathering_scheduling_browser.py:1749`の
`fetch_confirmed_date_open_shop_ids_with_a_spare`は、まさに「別の抽選で選んだ店が、この確定日の
表示上限つき抽選に生き残っているか」という**同種の仮定**を持っていた退役済み手法
（`fetch_a_shop_id_not_open_on`）について、自らのdocstringで次のように証言している:

> whether that probed shop actually survived Thursday's own unseeded 6-into-5 display-cap draw
> was incidental, not guaranteed, and **reproduced empirically failing**

この退役済み手法は「shown-pool-priorityで2回目の呼び出しに1回目のshownProviderPageUrlsを
引き継がせ、決定的にスペアを保証する」という技法（同ファイル1764行以降）に置き換えられた——
ただしこの技法が保証するのは**同一の呼び出し列（生API呼び出し同士）の中でのみ**であり、
CS-22のGivenが必要とする「生APIの抽選 → 後から開くブラウザの独立抽選」という**別セッション
間の一致**は、この技法をもってしても保証できない（ブラウザ自身のJS側shown履歴は生APIコールの
履歴を知らないため）。

**実害の範囲**: TDR-GTH-44（同じラウンドで書き換えられた、表面上よく似た构成）は、この懸念に
**当てはまらない**と判定した——Thenが依存するのは常に帯の`shortlistedShopCount`（サーバー真値、
描画される候補集合とは無関係に正しい）と「Whenで新たに足した／外したその1件」のみであり、
Givenで先に入れた1件が実際に画面へ描画されるかどうかにTDR-GTH-44のいかなるアサーションも
依存していない（トレース済み、上記対訳表参照）。TDR-CS-20も同様に無関係——Givenの1件をAPI
直叩きではなくブラウザの同一セッション内操作だけで組み立てているため、この懸念が原理的に
発生しない。**この懸念が実際に成立するのはTDR-CS-22の1つ目のThenに限られる**——
`expect(shortlisted_toggles).to_have_count(1)`（`dsl/candidate_search_browser.py:891`）が、
Givenで確定させた特定の店が「まさにこの独立抽選でも描画される」ことに直接依存しているため。

**失敗の性質**: 発火した場合は`to_have_count(1)`のタイムアウトとして**大きな声で失敗する**
（誤って合格する方向のリスクではない）。ただし発生頻度が(a)前回監査のカレンダー往復上限問題
（実質的に到達不能な理論上の縁）より明らかに高く、(b)このコードベース自身が「実際に
reproduced empirically failing」と記録した既知の罠と同型であるため、Blockerではないが
Majorと判定する——CIが実装の実際の退行と無関係に間欠的に赤くなり、原因調査コストを生む。

**推奨される是正**（人間・testerへの申し送り、reviewerはstep/DSLを書かない）:
`given_a_gathering_with_exactly_one_shortlisted_shop`の呼び出し側で`candidate_date_iso`に
表示上限5件以下の曜日（例: `next_weekday_iso(2)`、水曜・4件、`OPEN_SHOP_COUNT_BY_WEEKDAY[2] ==
4`）を明示的に指定する——母集団が表示上限以下なら「全員が必ず描画される」ため独立抽選間の
不一致が原理的に発生しなくなる。この方法はTDR-CS-19/21が逆方向（あえて6件母集団を選んで
上限超過を作為的に作る）で既に確立している「曜日を明示指定して決定性を得る」という同じ手筋の
応用であり、新しいseamは不要（`candidate_date_iso`引数は既に存在する）。

### Minor 1: `assert_only_shortlisted_toggle_is_disabled_with_last_shop_reason`が`wait_for_at_least_one`直後に`.count()`を呼ぶ（FR-039寄りの注意点）

`dsl/candidate_search_browser.py:869`以降、`cards = wait_for_at_least_one(self.page, CARD)`
（「**先頭**要素がattachedになるまで待つ」だけの意味論、`js_browser_mechanics.py:106`のdocstring
自身が明記）に続けて`card_count = cards.count()`を即座に呼んでいる。カードが1件ずつ段階的に
描画される実装であれば、この`.count()`は本来の最終件数より少ない値を読みうる——ただし直後の
`assertGreaterEqual(card_count, 2, ...)`が失敗すれば大きな声で失敗し、仮に閾値をぎりぎり満たす
中途半端な件数で通過した場合は、まだ描画されていない他のカードに対する「非活性でない」
「`lastShopNotice`が無い」という否定側チェックがスキップされたまま通過しうる——これは
FR-038が警戒する「Givenが薄く、実装欠陥が通り得る」形の一種になりうる。

ただしこの`wait_for_at_least_one`→即`.count()`という組み合わせ自体は本diff固有ではなく、
同ファイル786・2384・3000・3005・3018行など複数箇所で既に使われている確立済みの慣行であり、
候補一覧が単一のAPI応答から一括で（段階的にではなく）描画される実装を暗黙の前提としている
（前回監査でも同種の暗黙の前提が指摘されているが、Blocker/Major扱いにはなっていない）。
新規性・実害の両面でMajorに満たないと判断しMinorとするが、TDR-CS-22はこのパターンを
**新しいシナリオの主要Thenの入口**として使っている点で、既存箇所より露出は高い。

### Minor 2: TDR-CS-22周りの2つの新設Then（`assert_only_shortlisted_toggle_is_disabled_with_last_shop_reason`／`assert_both_shortlisted_toggles_enabled_and_no_last_shop_notice`）とTDR-CS-20周りの`toggle_a_not_yet_shortlisted_card_and_return_ref`／`toggle_off_card_by_candidate_ref`が、`gathering_scheduling_browser.py`の`toggle_one_not_yet_shortlisted_candidate_card_and_return_ref`／`toggle_off_candidate_card_by_ref`とほぼ同一のロジックを独立に複製している

両ファイルのdocstringが互いに「mirrors ... identical」と明記しており意図的な複製（この2ファイル
の既存方針、クロスインポートしない）であるため欠陥ではないが、今後どちらか一方だけを直しても
もう一方に波及しない保守コストは実在する。指摘のみ、対応不要。

### Minor 3: TDR-CS-21の`.feature`本文が、拡張後にテストが検査する`disabledReason`に一切言及していない

`candidate-search.feature`のTDR-CS-21（337〜341行）はGiven/When/Thenのいずれも「帯
（`gatheringMode.band`）」の話のみで、カード単位の`data-gathering-toggle-disabled-reason`には
一言も触れていない。しかし`test_tdr_cs_21_band_shows_the_limit_reached_reason_at_five`
（`test_candidate_search_acceptance.py:445`）は、この拡張により`unselected_candidate_toggle_
disabled_reason_is_limit_reached`という**カード単位**の新規アサーションを実行するようになった。
検査内容自体は契約1.11.0の`disabledReason`Mustに正しく合致しており誤りではないが、シナリオID
とGherkin本文だけを見て「このシナリオが何を検査しているか」を追跡する監査・トレーサビリティ
（`profiles.localAcceptance.verifiesScenarios`的な発想）の観点では、本文と実装検査内容の対応が
薄くなっている。TDR-CS-22が同種の新設Mustのために新しいシナリオID・新しいGherkin本文を得たのと
非対称——`limit-reached`側だけがGherkin非改訂のまま実装に飲み込まれた形になっている。是正
（TDR-CS-21のAnd行に「そのカードの理由を機械的に読める」旨を1行足す、あるいは新規シナリオIDを
起こす）はarchitect/architectレベルの契約改訂判断であり、reviewerとしては指摘に留める。

## レビューチェックリスト（5観点）

1. **過不足**: TDR-CS-20/21/22・TDR-GTH-44の対象シナリオすべてに1:1で対応する`def test_tdr_*`
   メソッドが存在し、欠落・孤児は見当たらない（下記対応監査参照）。過剰に厳格で誤検出リスクの
   ある検査（文言固定など）も見当たらない。ただしMinor3のとおり、TDR-CS-21の検査範囲が
   Gherkin本文の宣言範囲を超えて拡張されている。
2. **Givenの正当性**: TDR-CS-20/GTH-44はいずれもadr/0037決定1（公開境界経由）を守り、
   `minItems: 1`に一度も抵触しない構成になっている——採点は良好。TDR-CS-22のGivenは
   **Major1のとおり、決定性の観点で穴がある**（公開境界を経由している点自体は正しいが、
   その境界呼び出しのタイミング・セッション分離が「常に同じ結果を作れるか」を壊している）。
3. **Thenの検証対象**: TDR-CS-22の2本のThenは、対象カードの正の検査（disabled/reason/notice）
   と非対象カード全件の負の検査（enabled/reason不在/notice不在）を両方行っており、「全カード
   非活性化」「notice全カード漏出」「reason属性の後残り（stale）」「noticeの消し忘れ」の
   いずれの欠陥注入シナリオに対しても検知できる構成になっている（Major1のGivenが正しく1件を
   描画できた前提のもとでは）。TDR-GTH-44/CS-20の除去検証も、DOM属性の反転確認だけでなく
   サーバー真値（band）の増減まで確認しており「除去が静かに失敗する」ケースを検知できる。
4. **失敗の握りつぶし**: 本diffに`try/except`によるエラー隠蔽・無条件`pass`の新規追加は無い
   （diffを機械的に走査して確認済み）。
5. **暗黙の前提**: Major1で詳述した「2回の独立したproposeCandidates抽選が同じ店を含む」という
   暗黙の前提が最大の指摘。ほかに`_read_gathering_mode_band`の即時読み取り（`expect(...).
   to_have_attribute`等の直前の待機が同一レンダーコミットでband側も更新済みという前提に
   乗っている）は、本diff固有ではなく既存の確立済み慣行であり、個別に安全側の並び（要素ごとの
   `to_be_enabled()`待機→同じ要素の属性読み取り）になっていることを確認したため、新規の懸念
   としては計上しない。

## 契約↔テスト対応の監査

- **承認済みシナリオのうちstep未実装のもの**: 無し。`candidate-search.feature`のTDR-CS-22は
  `test_tdr_cs_22_last_shortlisted_shop_toggle_is_disabled_with_a_reason`として実装済み。
  `gathering-scheduling.feature`のTDR-GTH-44は書き換え後も同じテストメソッド名のまま実装済み。
- **シナリオに対応しない孤児step**: 無し。旧`toggle_off_the_first_shortlisted_candidate_card`
  （`gathering_scheduling_browser.py`）・旧ステップ`organizer_toggles_off_the_first_
  shortlisted_candidate`はいずれも本diffで削除され、呼び出し元も存在しないことを
  `grep`で確認済み（残存する言及はdocstring内の後方参照コメントのみ）。
- **同義stepの重複**: `organizer_removes_the_shop_from_the_gathering`（位置ベース、TDR-CS-17用）
  と`organizer_toggles_off_the_shop_by_ref`（ref指定、TDR-CS-20用）は同じ`candidate_search_
  steps.py`に共存するが、対象シナリオのGiven形状が異なる（前者は空の状態から1件だけ操作、
  後者は2件ある状態から特定の1件を操作）ため真の重複ではない。
- **属性名・enum値の直接照合**: `data-gathering-toggle-disabled-reason`・
  `limit-reached`/`last-shop`・`candidate-card-gathering-last-shop-notice`は、契約
  （`candidate-search-browser-interface.yaml`1276〜1348行）とテストコードの定数
  （`GATHERING_TOGGLE_DISABLED_REASON_ATTR`ほか、`candidate_search_browser.py:345`以降）とで
  文字列レベルで完全一致することを確認した。
- **`profiles.localAcceptance.verifiesScenarios`・`test-support-api.yaml`の一覧登録**:
  いずれもTDR-CS-22を登録済み（`candidate-search-browser-interface.yaml:391`、
  `test-support-api.yaml`複数箇所、2026-09-13追補10）であることを確認した。

## 統合後に欠陥注入すべきassertionの一覧

1. **`assert_only_shortlisted_toggle_is_disabled_with_last_shop_reason`**（TDR-CS-22）:
   実装側に「5件到達時と同じ理由（limit-reached）を残り1件のケースにも誤って出す」欠陥、
   および「lastShopNoticeを全カードに出す」欠陥をそれぞれ注入し、他カードに対する負の検査
   （`disabledReason`不在・`lastShopNotice`0件）が確実に失敗することを確認する。
2. **`assert_both_shortlisted_toggles_enabled_and_no_last_shop_notice`**（TDR-CS-22）:
   「2件目を入れても最初の1件のdisabledReason/lastShopNoticeが消えない」退行（stale属性）を
   注入し、`assertIsNone`と`to_have_count(0)`がそれぞれ確実に失敗することを確認する。
3. **`assert_unselected_candidate_toggle_disabled_reason_is_limit_reached`**（TDR-CS-21拡張）:
   `disabledReason`の値を`last-shop`と`limit-reached`で取り違える欠陥を注入し、
   `to_have_attribute`が確実に失敗することを確認する。
4. **Major1自体の実測**: `given_a_gathering_with_exactly_one_shortlisted_shop`の
   `candidate_date_iso`を明示的に木・金・土曜へ固定した状態でTDR-CS-22を複数回リピート実行し、
   `to_have_count(1)`が実際に間欠的にタイムアウトすることを実測で確認することを推奨する
   （既存コードに変更を加えず、テスト実行時のパラメータ操作のみで再現できるはず）。

## 人間の承認判断のためのチェックリスト

- [ ] Major1（TDR-CS-22のGivenが2回の独立抽選の一致を無保証で仮定している）を、本PRの
      ブロッカーとして扱い`candidate_date_iso`を表示上限以下の曜日へ固定させるか、次PRへ
      送るか（reviewerとしては、発火頻度と既知の同型バグの前例を踏まえ、マージ前の是正を推奨）
- [ ] Minor1（`wait_for_at_least_one`直後の`.count()`）・Minor2（DSL間の意図的複製）は
      次回のこの画面群を触るラウンドへ送ってよいか
- [ ] Minor3（TDR-CS-21のGherkin本文が拡張後の検査内容を反映していない）を、architectへの
      次回契約改訂の申し送り事項とするか、それとも許容する運用差分として明示的に受け入れるか
- [ ] 「統合後に欠陥注入すべきassertion」4件を、統合後の欠陥注入フェーズで実際に実行するか
- [ ] `candidate-search-browser-interface.yaml`（1.11.0）・`candidate-search.feature`・
      `gathering-scheduling.feature`・`test-support-api.yaml`はいずれも本ラウンドの記述時点で
      承認済みのADR-0057に基づく——本PRのマージが実装承認を兼ねる従来運用のままでよいか

以上。
