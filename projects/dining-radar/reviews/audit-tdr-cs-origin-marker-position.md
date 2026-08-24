# TDR-CS-15/16 と基点マーカー位置検証の acceptance 差分レビュー

- 担当: reviewer
- 監査対象:
  1. **本ブランチ**（`docs/record-tdr-cs-slice-state`、依頼時点でのHEAD `a078684`）の
     `tests/acceptance/dsl/candidate_search_browser.py` 差分（`origin/main...HEAD`、1ファイル・
     40行追加/10行削除）——基点マーカー位置検証を「存在確認 → 文字列完全一致 → 数値としての一致
     （誤差1e-9度）」と書き換えた最終形。
  2. **PR #156**（マージ済み、base `4ed65ea`→tip `2397398`）の `tests/acceptance/**` 全差分——
     `TDR-CS-15`・`TDR-CS-16` 新規追加、`TDR-CS-01/02/03/04/10` 改訂。`meta/agents.md` §4 step 7 が
     要求する独立監査が実施されないままマージされた分（`activeContext.md` 記載、2回目の未実施）を、
     本監査で遡って実施する。
- 照合元: `contracts/candidate-search.feature`（TDR-CS-01〜04・10・15・16）、
  `contracts/candidate-search-browser-interface.yaml` v1.3.2（`mapObservations.searchOriginMarker`・
  `walkingRadiusRings`・`unavailableControls.locationRangeControlProhibition.displayOnlyOriginException`・
  `browserActions.applyFilters/searchAgain.rateLimited.priorDisplayRetained`）、
  `contracts/candidate-search-api.yaml`（`Candidate.walkingTimeMinutes`・`CandidateFilters.walkingTimeMaxMinutes`・
  `PopulationAttribute.walkingTimeBand`）、`contracts/test-support-api.yaml`
  （`WALKING_TIME_LIMIT_EXCLUDES`・`RATE_LIMITED_AFTER_INITIAL_SUCCESS`・`searchOrigin`の自己整合性に関する
  2026-08-20の記述）、`adr/0025`・`adr/0027`。
- 独立性: tester の意図説明・コメント・コミットメッセージは判断材料にしていない。DSL/契約本文中の
  コメントは、それ自体を根拠として採用せず、記載された契約箇所・実装（`serializers.py`・
  `acceptance_state.py`・`candidate.js`）を自分で開いて独立に真偽を確認した。実装コード（`src/**`）は
  読んだが一切変更していない。

## 実行結果（自分で実行）

- `python -m pytest tests/acceptance -q -k "tdr_cs_15 or tdr_cs_16 or tdr_cs_01 or tdr_cs_02 or tdr_cs_03 or tdr_cs_04"`
  → **6 passed in 62.89s**
- `python -m pytest tests/acceptance -q`（フルスイート）→ **22 passed in 306.38s**
- 「緑」であることは以下の指摘の正しさを裏付ける証拠としては使っていない（過去にこのプロジェクトで
  「シナリオがDOM結果を確認しないまま緑になっていた」欠陥が実在するため）。対訳とチェックリストは
  静的にコードと契約を突き合わせて作成した。

## 結論

**ブロッカー級の欠落が1件ある（F1）。** 基点マーカーの数値一致検証（本ブランチの主題そのもの）は、
「マーカーの位置が応答の `searchOrigin` に由来し、独立に知られた定数ではないこと」を実際には**証明
できていない**——acceptance の合成フィクスチャが、全モード共通で `searchOrigin = (0.0, 0.0)` という
単一の定数しか返さないため、`candidate.js` が応答を正しく読んでいる実装と、`0`/`0` を決め打ちしている
実装のどちらであってもこの検証は区別なく緑になる。契約本文（presenceRule）と `adr/0027` 自身が明記
する検証目的と、実際にテストが持つ検出力が乖離している——依頼文が名指しした「過去に見つかったのと
同型のトートロジー」に該当する。

他に3件、是正または人間の明示確認を推奨する点がある（F2〜F4、いずれもMedium以下）。TDR-CS-15の
「ソフト絞り込みではない」という契約の主張自体が、母集団操作による振る舞いの違いとして原理的に検証
不可能な性質であることも確認したが、これは契約の設計そのものに内在する限界であり、テストの欠陥では
ないと判断した（F5として記録のみ行う）。

## 対訳表 Part A — 本ブランチ: 基点マーカー位置検証

| # | 契約/シナリオ文 | 呼び出されるstep | DSLが実際にすること | 判定 |
|---|---|---|---|---|
| TDR-CS-01 Then4 | 地図には検索基点のマーカーが示される | `search_origin_marker_is_shown` | `_current_proposal()`で応答を取得・schema照合したうえで、`candidate-origin-marker`の存在を確認し、その`data-origin-latitude`/`data-origin-longitude`属性を`float()`で解析、応答`searchOrigin.latitude`/`longitude`と絶対誤差1e-9度以内で`assertAlmostEqual`比較する | **形式的には契約の`presenceRule`（数値比較・許容誤差1e-9度）と一致（F1参照——検証力そのものは別問題）** |
| TDR-CS-04 Then2 | 検索基点は地図上のマーカーとして示されるが、幹事はその位置を変更できない | `search_origin_marker_is_display_only` | `candidate-origin-marker`・`candidate-walking-radius-ring`の全ノードに対し、`dispatch_event("click")`（ポインタ相当）と、`tabindex`があれば`focus()+press("Enter"/"Space")`（キーボード相当）をそれぞれ行い、直前後で`_display_snapshot()`（カード/マーカーref列・条件サマリ・適用済みフィルタ）が不変であることを確認 | 契約`verificationAllocation.L4`の文言（「pointer, and Enter/Space while focused if focusable」で全ての利用可能な活性化を駆動し、何も変わらないことを示す）と一致。ただし技法の変更点はF2で個別に検討 |

## 対訳表 Part B — PR #156: TDR-CS-15・16 新規、TDR-CS-01/02/03/04/10 改訂

| # | シナリオ文 | 呼び出されるstep | DSLが実際にすること | 判定 |
|---|---|---|---|---|
| TDR-CS-15 Given2 | 提案できる候補に、これから指定する徒歩の上限を超える店舗が含まれている | `population_includes_a_candidate_beyond_the_upcoming_walking_time_max` | 初回応答の`walkingTimeMinutes`集合が2値以上であることを確認（`WALKING_TIME_LIMIT_EXCLUDES`の固定境界値12に依存せず、応答から独立に検証） | 対応 |
| TDR-CS-15 When | 幹事が徒歩の上限を指定して探し直す | `organizer_selects_a_walking_time_max_filter`→`organizer_applies_changed_filters` | パネルの実際の`data-walking-time-max-value`選択肢を読み、初回応答の最小分未満〜最大分未満の範囲で母集団を分割する最小のプリセット値を選び、pending filterへ反映（変更のみで公開リクエストが発火しないことを`_change_pending_filters`内部が確認）、その後適用してリクエストを発火 | 対応。プリセット値をハードコードせず契約通り「UI実装が決める閉じた集合」を実行時に読む設計は妥当 |
| TDR-CS-15 Then1 | 指定した上限を超える徒歩のめやす時間の店舗は候補から除かれる | `candidates_over_the_walking_time_max_are_excluded` | `_applied_filters`の実値（実際に送信したHTTPリクエストボディから復元）を基準に、初回応答の中で上限超の`candidateRef`集合を求め、適用後の実応答の`candidateRef`集合との積が空集合であることを確認 | 対応。フィルタ値は実送信リクエストボディ由来で自己申告ではない |
| TDR-CS-15 Then2 | 上限以内の徒歩のめやす時間の店舗は候補に残る | `candidates_at_or_under_the_walking_time_max_remain` | 上限以内の`candidateRef`集合が、適用後の実応答の`candidateRef`集合と完全一致することを確認 | 対応 |
| TDR-CS-15 Then3 | 徒歩のめやす時間が確認できないという理由で候補が残ることはない | `no_candidate_remains_due_to_unknown_walking_time` | 表示中の全カードの`data-value-state`が`provided`であること、応答の全候補の`walkingTimeMinutes`が非nullであることを確認 | **原理的に反証不可能な性質（F5）**——schemaが`walkingTimeMinutes`を非null必須にしているため、「情報なしで残る」ケースは母集団操作では作れない。テストは「情報なしのケースがそもそも存在しない」ことを構造的に示すにとどまり、"soft filterなら情報なしが除外されずランキング後方に残る"という対比を実際に駆動して見せてはいない |
| TDR-CS-15 Then4 | 変更しただけでは探し直さず、適用して初めて候補が入れ替わる | （明示stepなし、`organizer_selects_a_walking_time_max_filter`内部） | `_change_pending_filters`→`_perform_without_candidate_request`が、pending変更の操作中に`POST /candidate-proposals`が一切発火しないことを毎回検証（既存パターンの再利用） | 対応（暗黙だが実質的に検証されている） |
| TDR-CS-16 Given | 幹事に絞り込み条件に基づく候補が示されている | `organizer_has_filtered_candidates`（applyFilters経路）／画面初回オープン（searchAgain経路） | `RATE_LIMITED_AFTER_INITIAL_SUCCESS`モード（初回だけ成功・以降429固定、モード選択毎にカウンタリセット）で最初の1回を成功させ、カード/マーカーの対応を確定させる | 対応 |
| TDR-CS-16 When（applyFilters分岐） | 絞り込み条件を変更する…で候補情報を取得できない | `organizer_attempts_to_apply_changed_filters` | カード払いフィルタを有効化した状態で`apply_filters_expecting_failure()`——直前スナップショットを取得後、`FILTER_APPLY`をクリックし429/`PROPOSAL_RATE_LIMITED`を確認 | 対応。**applyFilters経路を独立に駆動している** |
| TDR-CS-16 When（searchAgain分岐） | 絞り込み条件を変更する、またはもう一度探す…で候補情報を取得できない | `organizer_attempts_to_search_again` | `search_again_expecting_failure()`——直前スナップショットを取得後、`SEARCH_AGAIN`をクリックし429/`PROPOSAL_RATE_LIMITED`を確認 | 対応。**searchAgain経路を独立に駆動している**（依頼文の懸念点は解消と判断） |
| TDR-CS-16 Then1 | 直前まで表示していた候補と地図はそのまま残る | `prior_candidates_and_map_remain` | 失敗直前に取得した`_prior_snapshot`（カード/マーカーref列・条件サマリ・適用済みフィルタ）と現在のDOMを突き合わせ、`candidate-proposal-cards`/`candidate-map`が両方present であることを確認 | **一部不足（F3）**——契約`priorDisplayRetained`は「unchanged card<->marker **data-selection-state correspondence**」も明記するが、スナップショットはref列のみを比較し`data-selection-state`属性値自体は比較していない |
| TDR-CS-16 Then2 | 取得できなかったことが案内される | `fetch_failure_is_announced` | `candidate-proposal-problem`の存在、`candidate-proposal-problem-guidance`のテキストが空でないことを確認 | 対応 |
| TDR-CS-01改訂 Then | 地図には検索基点のマーカーが示される／探索範囲そのものの値は示されない | `search_origin_marker_is_shown`・`search_range_value_is_not_shown` | 後者は`探索範囲`・`検索範囲`・`半径`の3語のみをページ全文から検索（`LOCATION_RANGE_FORBIDDEN_TOKENS`より意図的に狭い——基点マーカー自身が正当に持つ「検索基点」ラベルを誤検出しないため） | 対応。ただしTDR-CS-01からは旧`_assert_no_disclosures()`（`candidate-route`/`candidate-current-location`/`candidate-provider-internals`/`private-search-origin`の不在確認）が外れた。TDR-CS-02が同一の初期画面状態に対し`walking_route_and_current_location_are_not_shown`で同じ集合を検証するため、スイート全体でのカバレッジ後退はないと判断（TDR-CS-01単体では確認しなくなった） |
| TDR-CS-02改訂 Then | 地図には検索基点マーカーと徒歩圏の同心リングが示される／徒歩のめやす時間は推定であることが分かる形で示される | `map_shows_search_origin_marker_and_walking_radius_rings`・`walking_time_is_shown_as_an_estimate` | 前者はマーカー存在＋リング1件以上を確認。後者は各カードの`data-value-state=provided`、可視テキストが`str(walkingTimeMinutes)`を含みかつ完全一致ではなく、`約|およそ|推定|めやす|見込み|くらい|程度`のいずれかを含むことを確認 | 対応。`candidate.js`の実装（`"約" + minutes + "分"`）を独立に読み、正規表現が実際のレンダリング文言を捉えていることを確認した（恒真ではない） |
| TDR-CS-04改訂 Then | 検索基点は地図上のマーカーとして示されるが幹事はその位置を変更できない | `search_origin_marker_is_display_only` | Part Aの表を参照 | 対応（本体はF2参照）。この scenario の Given (`lunch_candidates_can_be_proposed`) では `candidate-walking-radius-ring` が0件のことがあり得るため、その場合リング側の display-only チェックは0回反復で空振りする（F4） |

## 指摘

### F1 — 基点マーカーの数値一致検証は、証明したいこと（応答由来／独立した定数でないこと）を実際には証明していない（Blocker）

`candidate-search-browser-interface.yaml`の`searchOriginMarker.presenceRule`（v1.3.2）は次のように書く。

> ...**that the marker's position derives from `searchOrigin` and not from an independently known
> constant** -- is numeric identity, not string identity.

`adr/0027`もDSLのdocstringも同じ主張を繰り返す（DSL、抜粋）。

```python
"""...this is what proves the marker's position derives from the response, not a fixture-baked value
(FR-022, 3rd recurrence)."""
```

しかし acceptance のテスト支援フィクスチャ（`src/dining_radar/suggestions/acceptance_state.py`）を独立に
読むと、次のとおりである。

```python
_ORIGIN = Origin(latitude=0.0, longitude=0.0)
...
def ...():
    return _CANDIDATES, _ORIGIN
def ...():
    return _IZAKAYA_BAR_ONLY_CANDIDATES, _ORIGIN
... (WALKING_TIME_LIMIT_EXCLUDES・RATE_LIMITED_AFTER_INITIAL_SUCCESSを含む全10モードが同じ`_ORIGIN`を返す)
```

`web/serializers.py`の`serialize_search_origin`はこの値を無変換でそのまま応答へ載せる
(`{"latitude": origin.latitude, "longitude": origin.longitude}`)。**したがって acceptance
テストが発行するどの `POST /candidate-proposals` も、`response.searchOrigin` は常に
`{"latitude": 0.0, "longitude": 0.0}` である。** テストは`candidate.js`側の実装から独立に、
この固定値をどこにも持っていない——毎回応答から読んでいる。

この状態では、`assertAlmostEqual(float(marker属性), origin.latitude, delta=1e-9)`は、
`candidate.js`が実際に`response.searchOrigin.latitude/longitude`を読んで属性へ設定する正しい実装
であっても、**`originMarkerEl.setAttribute("data-origin-latitude", "0")`のように応答を一切読まず
定数を決め打ちする実装であっても、どちらも同じ`0.0 == 0.0`として緑になる**。緯度・経度が入れ替わって
いても、応答が使われず定数が置かれていても、この acceptance スイートの範囲では検出できない。

`test-support-api.yaml`自身（2026-08-20起草、architect）は、この設計判断を次のように**自ら擁護
している**（実際に検証しているのはより弱い主張だと明記している）。

> `searchOrigin`の値そのものをこのGiven APIで選択可能にする必要はないと判断した——L4は「地図上の
> 検索基点マーカーが、その回のレスポンスの`searchOrigin`と一致するか」という**自己整合性だけ**を
> 検証すれば足り（TDR-CS-01・02）、**独立に既知の定数と突き合わせる必要が無いため**。

この文は「自己整合性だけで足りる」という**弱い**主張であり、`browser-interface.yaml`の
presenceRule・`adr/0027`が掲げる「独立に知られた定数ではないことを証明する」という**強い**主張とは
食い違う。`searchOrigin`が実際に定数である以上、「自己整合性」は「常に同じ値と一致する」ことに
縮退し、両者は区別できない——強い主張の方が、この契約群の中で満たされていない。

**この欠陥はtester作成のDSLコード自体のバグではない**（DSLは契約が定義した属性・比較規則を正しく
実装しており、契約の`presenceRule`が今書いてある通りに実装すればこうなる）。**フィクスチャ
（`acceptance_state.py`の`_ORIGIN`が全モード共通の定数であること）と、それを許容する
`test-support-api.yaml`の設計判断側に原因がある**——tester・reviewerの担当外のファイルだが、
本ブランチが数値比較へ書き換えた目的（応答由来性の証明）を acceptance テストが達成できているか、
という監査の核心的な問いには「できていない」と答えるほかない。

是正案（人間/architectの判断を要する。いずれか、または contract の主張を弱めて「自己整合性のみ」
と明記し直す）:
1. `test-support-api.yaml`のいずれかのGiven mode（少なくとも位置検証に使うTDR-CS-01/02が使う
   `NORMAL_WITH_WEIGHTED_SAMPLING`系）の`_ORIGIN`を、非ゼロで縦横入れ替えても区別できる値
   （例: `latitude=35.123456, longitude=139.654321`）へ変更する。
2. もしくは`searchOrigin`をGiven APIで選択可能にし、テストが複数の異なる値で検証できるようにする。
3. どちらも採らない場合は、`presenceRule`・`adr/0027`の文言を「自己整合性のみを検証する」という
   実際に検証できている範囲まで弱め、「独立に知られた定数ではないことを証明する」という誤った
   強い主張を契約から削除する。

### F2 — display-only 証明の技法変更（`click()` → `dispatch_event("click")`）は妥当だが、証明の性質が変わっている点は明記すべき（Low、要確認）

依頼文が懸念した「候補カードが地図に重なるため`click()`から`dispatch_event`へ変えたことで証明が
弱まっていないか」を独立に検討した。

`candidate-search-browser-interface.yaml`の`verificationAllocation.L4`は「pointer, and Enter/Space
while focused if focusable」で「every available activation」を駆動せよと書くのみで、pointer活性化を
実ヒットテスト付きのクリックで行うかどうかまでは指定していない。Playwrightの`Locator.click()`は
要素中心座標への実ブラウザレベルのヒットテスト（"receives pointer events"チェック）を経由するが、
`dispatch_event("click")`は要素自身へ直接合成`click`イベントを発火し、ヒットテストを経由しない。

- **正当性**: 承認済み配置（候補デッキが地図に重なる）のもとでは、実際のユーザーの指がこのマーカーへ
  到達すること自体が不可能であり、`click()`はPlaywrightの actionability チェックで失敗する（依頼文の
  説明の通り、独立に確認できる幾何関係）。マーカー自身に束縛されたクリックハンドラが状態変化を起こす
  かどうかという、この Must が実際に問うている性質は、合成イベントでも同じコード経路（DOM要素への
  `click`リスナー）を通るため、原則として検証できる。
- **残るリスク（記録のみ、修正不要と判断）**: `dispatch_event`が発火するイベントは`isTrusted: false`
  である。もし`candidate.js`またはLeafletが`event.isTrusted`で分岐する実装を持っていれば、この技法は
  その分岐を素通りする。`candidate.js`・vendored `leaflet.js`を読んだ限り、そのような分岐は見当たら
  ない（そもそも稀な実装パターンである）ため、現実的なリスクとしては小さいと判断する。
- 加えて、この技法変更は「現在の画面配置で実際にユーザーがこのマーカーへポインタで到達できるか」という
  別の性質（ヒットテストの結果）を、以前の`click()`よりも検証しなくなっている。これは「マーカー自身の
  ハンドラが no-op である」という Must の対象そのものではないため指摘としては軽微だが、対訳表・
  レビューの記録として明記しておく。

**判定: 契約の文言・実装の両方から見て妥当な技法変更であり、指摘としては記録に留める（要修正ではない）。**

### F3 — TDR-CS-16 の `priorDisplayRetained` 検証が、`data-selection-state` の対応関係そのものは比較していない（Medium）

`browser-interface.yaml`の`priorDisplayRetained`は次を明記する（強調は引用者）。

> Every candidate-card and candidate-map-marker present immediately before this request remains
> present afterward, with unchanged data-candidate-ref values, **unchanged card<->marker
> data-selection-state correspondence**, and unchanged applied filters and condition summary.

`assert_prior_candidates_and_map_remain`が使う`_display_snapshot`/`_assert_display_snapshot`は
`_card_candidate_refs()`・`_marker_candidate_refs()`（いずれも`data-candidate-ref`の順序付きリスト
のみ）・条件サマリ文字列・適用済みフィルタ辞書を比較するが、カード・マーカーそれぞれの
`data-selection-state`属性の値そのものは比較していない。DOMが本当に一切再描画されず「そのまま残る」
実装であれば選択状態も自動的に不変のはずだが、契約が明示的に列挙した性質（選択状態の対応関係）を
このスナップショットは直接は見ていない——「取得失敗時に選択状態だけリセットして再描画する」という
仮の欠陥はこの検証をすり抜けうる。

`_display_snapshot`はTDR-CS-16以外の既存Then（`revertPendingFilters`等）でも共有される既存ヘルパーで
あり、本差分固有の新設欠陥ではないが、TDR-CS-16の契約文が明示的に`data-selection-state`
correspondenceを名指ししている以上、この検証ギャップは記録に値する。

### F4 — TDR-CS-04の`assert_origin_marker_and_rings_are_display_only`は、リング側が0件のGivenでは空振りする（Low、契約上は許容）

`candidate-walking-radius-ring`は契約上`cardinality: zero-or-more-elements-sharing-this-test-id`
であり、TDR-CS-04が使うGiven（`lunch_candidates_can_be_proposed`）でリングが実際に描画される保証は
ない。`assert_origin_marker_and_rings_are_display_only`のループは`nodes.count()`が0であれば単に
0回反復して終わるため、その実行でリング側のdisplay-only性質は何も検証されない。契約上は「0件以上」
なので違反ではないが、リングのdisplay-only性は本差分の範囲では他のどのシナリオでも明示的に
駆動されていない（`grep`で確認: `WALKING_RADIUS_RING`は`map_shows_search_origin_marker_and_walking_radius_rings`
の存在確認と、この display-only チェックの2箇所でしか参照されない）。マーカー本体は必ず検証されるため
ブロッカーではないが、リングの display-only 性質そのものは「たまたまリングが描画されたときにだけ」
検証される構造である点は記録しておく。

### F5 — TDR-CS-15「ソフト絞り込みではない」という契約の主張は、母集団操作による振る舞いの対比としては原理的に検証不可能（記録のみ、テストの欠陥ではない）

`candidate-search-api.yaml`は`Candidate.walkingTimeMinutes`を非null必須と定義しており、
「情報が確認できない」状態がそもそも生成できない。ソフト絞り込み（禁煙・カード払い・予算感）との違いを
テストが実際に見せられるのは「情報なしの候補が絞り込みで除外されず後方に残る」という**対比**の場面
だが、対比対象（情報なしの候補）がこのAPIの型で構造的に作れない以上、この対比自体をacceptanceレベルで
駆動することはできない。`no_candidate_remains_due_to_unknown_walking_time`は「情報なしのケースが
そもそも存在しない」ことを構造的に確認するにとどまり（カードの`data-value-state=provided`・応答の
非null）、これは契約が意図した「ソフト絞り込みとの振る舞いの違いを示す」証明ではなく、「対比する
相手が存在しないので比較しようがない」ことの確認である。**DSLのdocstring自身がこの限界を正直に
書いている**（「there is no 'unknown, kept anyway' path for this hard filter to begin with; this
proves that structurally」）ため、隠された誤りではなく、契約の設計自体に内在する原理的な限界と判断
する。指摘としては記録に留め、修正を求めない。

## L4 5観点チェックリスト

| 観点 | 判定 | 根拠 |
|---|---|---|
| 過不足 | 概ねOK、一部要確認 | TDR-CS-15・16の全Thenに対応するstep/DSLが存在する。TDR-CS-01からの`_assert_no_disclosures()`除去はTDR-CS-02が同一画面状態で肩代わりしており、スイート全体では過不足なし |
| Givenの正当性 | 概ねOK、F1の根本原因 | `WALKING_TIME_LIMIT_EXCLUDES`・`RATE_LIMITED_AFTER_INITIAL_SUCCESS`はいずれも公開境界（`test-support-api.yaml`宣言済みseam）経由。ただし`searchOrigin`を全モード共通の定数(0,0)にとどめた設計判断（F1）が、本ブランチが追加した検証の検出力を実質的に無効化している |
| Thenの検証対象 | **一部NG（F1）** | F1が本監査で最も重い指摘。マーカー位置の数値一致は「応答由来／独立定数でないこと」を証明する目的で書かれているが、フィクスチャの制約により実際にはその性質を検出できない。F3（selection-state対応）も部分的な検証対象の不足 |
| 失敗の握りつぶし | OK | 変更/新規のstepはすべて1DSL呼出しのみ。`require()`はNoneを例外に変換し、`capture_candidate_proposal_response`は実ネットワーク応答を待つ。空catch・過度に緩い比較・sleep同期は見当たらない |
| 暗黙の前提 | 一部要確認 | `enable_walking_time_max_filter_that_excludes_some_candidates`のプリセット選択ロジックは応答から動的に導出しており、暗黙の固定値依存はない。F1は「暗黙の前提」というより「契約の主張と実際の検証力の乖離」に近いが、根はフィクスチャの暗黙の制約（全モード共通の定数原点）にある |

## contract ↔ test 対応・孤児監査

### 対応済み

- `TDR-CS-15`の4つのThenすべてに対応するstep/DSLメソッドが存在する（Then4は`_change_pending_filters`
  内部で暗黙に検証）。
- `TDR-CS-16`の2つのThenは、`applyFilters`・`searchAgain`の両方の失敗経路それぞれで独立に駆動され
  ている（依頼文の懸念点は解消と判断）。
- `TDR-CS-01/02/03/04/10`の改訂は、feature ファイルの新規Then文言（検索基点マーカー・徒歩圏リング・
  徒歩のめやす時間・徒歩の上限の列挙追加）に対応するstepがすべて存在する。TDR-CS-03・10は既存の
  「いずれか」形式のGherkin（列挙のうち1つを例示すれば足りる書き方）を踏襲しており、walking-time-max
  固有の「変更→探し直し」「フォールバックで自動的に緩められない」の実質的な検証はTDR-CS-15自身が担う。

### 孤児または不完全な契約要求

- 上記F1（`searchOriginMarker.presenceRule`の「独立に知られた定数ではないこと」の証明部分）。
- 上記F3（`priorDisplayRetained`の`data-selection-state` correspondence部分）。

### 重複・死んだ受け入れ補助コード

見当たらなかった。本監査で確認した新規/変更メソッド（`assert_search_origin_marker_is_shown`・
`enable_walking_time_max_filter_that_excludes_some_candidates`・`apply_filters_expecting_failure`・
`search_again_expecting_failure`・`assert_origin_marker_and_rings_are_display_only`・
`assert_prior_candidates_and_map_remain`・`assert_fetch_failure_is_announced`ほか）はいずれも1回以上、
対応するstep経由で呼び出されており、既存stepとの同義重複も確認できなかった（ステップ名の呼び出し回数を
機械的に数えて確認済み）。旧ステップ名（`screen_has_no_private_disclosures`・
`steps.map_has_no_forbidden_surfaces`）への参照は残っていない。

## 修正が必要と判断する項目

1. **F1（Blocker）**: `searchOriginMarker.presenceRule`／`adr/0027`が掲げる「独立に知られた定数では
   ないこと」を acceptance レベルで実際に証明できるよう、フィクスチャ側（`test-support-api.yaml`の
   `searchOrigin`設計）を是正するか、契約の主張を実際に検証できている範囲（自己整合性のみ）まで
   明示的に弱めるか、人間/architectの判断を仰ぐことを推奨する。tester・reviewerのファイル
   （`tests/acceptance/**`）だけでは閉じない。
2. F3・F4は Medium/Low の記録であり、必須の差し戻し理由とはしない。人間が許容範囲と判断すれば
   そのまま進めてよい。
3. F2・F5は指摘としては記録のみで、修正を求めない。
