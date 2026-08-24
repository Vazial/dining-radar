# activeContext.md — Dining Radar

> P-11: This file represents only the current state. Durable decisions belong in ADRs; approved artifacts belong in git.

## Current state

### プロジェクト名

The project is named `dining-radar`. It was renamed from `toyama-dining-radar` on 2026-08-20 (ADR-0026) because the old name carried a real prefecture name into a public repository, which is exactly what this product's own `product-brief.md` §4 and ADR-0002 forbid. The Python package was already `dining_radar` and did not change, so no import, settings module, static path, or CSS class moved. The scenario-ID prefix `TDR` stayed as well — it appears 738 times, including in approved contracts — and `meta/scenario-id-prefixes.md` instead dropped the place name from its description, leaving `TDR` an opaque token. The git branch `project/toyama-dining-radar` and its ruleset keep the old name on purpose (ADR-0026 decision 4). **Renaming this project did not remove the region from the public repository**: `toyama-weekend-radar` and `connpass-session-radar` still carry it, and ADR-0026's consequences section lists every remaining place.

The rename was built once against the pre-#106 `main`, held when it turned out to collide with the then-unpushed `docs/tdr-cs-origin-and-walking-time`, and redone on top of that branch's merge — the cheaper-to-reproduce change goes last (FR-020).

### 画面の機能について確定した人間裁定（2026-08-23）

ワイヤフレーム（`https://claude.ai/code/artifact/278c94d2-116e-4bcd-87df-b552607541c7`。designer が
`design/explorations/` の3枚を土台に `/design` で作成。元データは未コミット）をもとに、人間が4件を裁定した。

1. **ジャンル行**: 「ほか N件…」の展開ボタンを**行の左端に固定**する。1行の横スクロールは維持し、
   高さは変えない。折り返しは採らない（2026-08-14 の見送りを維持）。**契約確認が要る**——
   `genrePresentation` はジャンルの順序を定めているが**位置を定めていない**ので、追補の要否を見ること
2. **候補の取得に失敗したとき**: 直前まで表示していた候補を**残す**。エラーは上に出す。古い候補を
   新しい提案と誤読しうる点は承知のうえで、比べていた材料を失わないほうを採る
3. **件数の予告**: **適用ボタンにだけ出す**（「この条件で探す（8件）」）。常時表示は引き続き置かない。
   契約は既に件数を `candidate-filter-apply` の `data-match-count` 属性に持っているので、それを
   文字として見せる形になる
4. **PC版は今回の合意の対象に含めない**。幹事はスマホ中心（2026-08-22 裁定）なので、まずスマホを固める。
   PC版のワイヤフレームは参考として存在するが、合意対象外

**まだ決めていないこと**（designer が破線で残し、裁定を仰いでいない残り）: 429（レート制限）と503
（取得不能）を画面で区別するか／0件のとき契約どおり地図ごと消えるのを受け入れるか／「絞り込みを見直す」
を押せるものにするか。エラー時の画面状態は `product-brief.md` §8 で未決のままである。

### 契約が、この画面の中心を「禁止」している（2026-08-23 確認）

`ADR-0025` は基点と徒歩時間の表示を承認済みだが、**マージ済みの契約はまだ旧世界のままである**。実測:

- `contracts/candidate-search-browser-interface.yaml:310` — `forbiddenTestIds` に `candidate-origin-marker`
- 同 `:795` — `bodyMustNotExposeTestIds` に `candidate-origin-marker`
- `contracts/candidate-search.feature:84` — 「非公開の検索地点、経路、現在地、**徒歩時間**は示されない」
- `candidate-walking-radius-ring` は現行契約に存在しない。API に `walkingTimeMinutes` も無い
- `CandidateFilters` に `walkingTimeMaxMinutes` が無い（徒歩の上限）

つまり基点マーカー・同心リング・カードの徒歩時間・徒歩の上限は、**現時点では契約が明示的に禁じている**。
契約改訂はこの画面が成立する前提そのものであり、あとで足す追補ではない。L4 の都合で契約だけ先に
マージできないため、契約・実装・テストを同一スライスで動かす。

**解決した（2026-08-24、developer）。** architect が `81bc06f` で契約改訂をこのブランチへコミットし、
上記の禁止はすべて反転済み（`candidate-origin-marker` は許可側、`walkingTimeMinutes`・
`walkingTimeMaxMinutes`・`walkingTimeBand` は契約に存在する）。developer がその改訂契約を満たす実装を
同ブランチへ積んだ。要点:

- `src/dining_radar/recommendation/pipeline.py` の `_distance()` は**度単位からメートル単位**に変わった
  （既存の等長方位図法的近似はそのまま、`METERS_PER_DEGREE_LATITUDE=111,320` を掛けるだけ——単位変更は
  距離に依存する既存の順序付け・重み付け計算をすべて不変に保つ、スケール不変な設計だったため無傷）。
  新設 `walking_time_minutes()`（`WALKING_METERS_PER_MINUTE=80`——不動産の「徒歩1分=80m」表示規約、
  切り上げ）と `walking_time_band()`（`WALKING_TIME_MAX_PRESET_MINUTES=(10,15,20,30)`、実データ由来ではない
  実装上の恣意的な値）を追加。`walkingTimeMaxMinutes` はハード絞り込み（`filter_candidates`・
  `apply_izakaya_bar_fallback` の両方に、居酒屋バーのフォールバック再試行でも緩めないよう配線済み）。
  `Proposal`/`ProposalResult` に `search_origin: Origin` を追加。`CandidateFilters`・`PopulationAttribute`
  それぞれに新フィールドを追加。プリセット `(10,15,20,30)` は `candidate.js` 側の
  `WALKING_TIME_MAX_PRESETS_MINUTES` と手作業で同期させている実装責任（契約が構造的に強制できないと
  明記している点、契約ノート2節参照）。
- `web/serializers.py`・`web/views.py`・`suggestions/service.py`・`suggestions/acceptance_state.py` を
  配線。`acceptance_state.py` に `WALKING_TIME_LIMIT_EXCLUDES`（TDR-CS-15、しきい値12分固定の合成値）と
  `RATE_LIMITED_AFTER_INITIAL_SUCCESS`（TDR-CS-16、1回目だけ成功しその後429を返す、モード選択のたび
  キャッシュカウンタをリセットする自前の2段階状態——`set_mode` を2回呼ぶ手法は使っていない）を追加。
- `candidate.js`・`home.html`: 検索基点マーカーと徒歩圏の同心リング（プリセットごとに1本）、カードの
  徒歩のめやす欄（`約N分`、rawValueAttribute なし）、徒歩の上限フィルタ（単一選択・独立グループ）、
  ジャンル行の「ほか N件…」を横スクロールコンテナの外側・先頭に固定するDOM再構成、429時に直前の候補・
  地図・適用済み条件を保持したまま問題バナーを追加表示する挙動（`applyPendingFilters` は成功時のみ
  `currentFilters` をコミットするよう変更）、適用ボタンの文言を「この条件で探す（対象N件）」に変更
  （「〜件表示されます」型の文言を使わない）。
- 検証: L1（ruff・334 unit tests・カバレッジ97%）/ L2（構造12件）/ L3（境界171件 + Django check ×2）は
  すべて緑。mutation testing はこの Windows 環境で `WinError 206`（コマンドライン長超過、2026-08-14 の
  記録済み既知の環境限界——本スライスで悪化させたのではなく、既に壊れていたものに新規テストを足しても
  症状は変わらない）によりフル実行不能。個別ファイルへスコープを絞った部分実行では新規追加ロジックに
  生き残ったミュータントは無かった（`pipeline.py` 単体で 80.0%→84.2%、新規の `_distance()`・
  `walking_time_band` の生存ミュータントを追加テストで潰した後）。CI（Ubuntu）が実測する。
  L4（`tests/acceptance/test_candidate_search_acceptance.py`、tester の担当外のstep定義は未変更のまま）を
  手動実行すると 14件中11件成功・3件失敗——失敗3件はすべて `candidate-origin-marker` の**旧契約の禁止**を
  まだ主張している既存のstep定義によるもので、新契約はこれを許可側へ反転しているため、実装が新契約を
  正しく満たしていることの状況証拠になる。既存stepの改訂は tester の領分のため未着手のまま残した。

### `mapObservations.searchOriginMarker.positionAttributes` の実装と地図resizeの不具合修正（2026-08-24、developer）

architect が `contractVersion 1.3.1` で `mapObservations.searchOriginMarker` に `positionAttributes`
（`data-origin-latitude`/`data-origin-longitude`）を新設した（FR-022(1)。基点マーカーの位置を
`response.searchOrigin` の値と突き合わせて検証する手段が契約に無かった穴を塞ぐ追記、人間の再承認は
不要と architect が判断した記録）。`candidate.js` の `initializeMap` で `candidate-origin-marker` の
`data-testid` を設定している直後に、`String(searchOrigin.latitude)`/`String(searchOrigin.longitude)` を
2属性へ設定した——契約の `presenceRule` が要求する「正確な文字列一致」を、`fieldRow` の
`rawValueAttribute`（`data-raw-value` に `String(value)` を入れる）と同じ様式で満たす。

あわせて `activeContext.md` Next work 5 に記録されていた既知の不具合（画面サイズが変わると地図がずれる）
を修正した。**実測して分かった訂正がある**——元の記述は「resizeハンドラが一切無い」としていたが、
vendored `leaflet.js`（1.9.4）を読むと `trackResize: true` がデフォルトで有効で、`candidate.js` は
これを上書きしていないため、**素朴なブラウザ `window` resize（`page.set_viewport_size()` が発火させる
もの相当）はこの修正の前から既に自己修復していた**（3通りの独立した実験で確認：スタッシュした無修正の
コードでも、Playwright の `set_viewport_size` を挟んだ前後でタイルの被覆・マーカー位置が完全に一致した）。
**実際に空いていた穴**は、`window` resize を伴わないコンテナだけの寸法変化——`candidate-map` の高さが
`home.html` で `dvh`/`vh` 単位のため、スマホでスクロール中にブラウザのツールバーが出入りするとコンテナが
CSSだけで寸法変化し、多くのモバイルブラウザではこれが `window` の `resize` を発火させない。これは
「幹事はスマホ中心」（人間裁定2026-08-22）に直結する経路である。修正は `candidate.js` の `initializeMap`
の末尾で `ResizeObserver` をコンテナへ直接 `observe` し、発火のたびに `map.invalidateSize()` を呼ぶ
（`initializeMap` の再実行時は先に `disconnect()` してから張り直す）。

再発防止テストは `tests/ui_invariants/test_render_invariants.py` に
`test_map_tiles_still_cover_the_container_after_it_resizes_without_a_window_resize` として追加した
（ADR-0020 決定4の4つのゲート不変条件には含めていない——同ファイルの `test_long_regular_holiday_...` と
同じ「プレゼンテーション回帰」の型に倣った）。判断の理由: (1) `page.set_viewport_size()` ベースのテストは
Leaflet自身の `trackResize` で既に緑になってしまうため、この変更を入れる前後を判別できない（実測で確認
済み）。(2) 実際に穴があった経路（`window` resizeを伴わないコンテナ単独の寸法変化）を再現するには、
コンテナ要素へ直接インラインstyleで寸法を強制する必要があった——`candidate-map-wrapper` が
`display:flex; flex-direction:column` なので、`height`だけを`!important`で強制してもフレックスの
主軸shrinkに押し戻される点が実装時のハマりどころで、`flex: 0 0 <height>px !important` も併せて設定する
ことで解消した。(3) このテストは fix を無効化して実際に赤くなることを確認した（コンテナの新しい下辺まで
タイルが届かず `assertGreaterEqual` が失敗）うえで、fix を戻して緑に戻ることも確認済み——このプロジェクト
の他の回帰テスト（keyboard-activation defect等）と同じ「revert-and-rerun」の実証パターンに倣った。

検証（developer が独立に再実行）: L1（ruff・ruff format・334 unit tests・カバレッジ97%——`coverage
report --fail-under=90` 通過。mutationは今回のスライスで Python ソースを一切変更していないため
再実行不要、2026-08-14 に確立した先例のとおり）/ L2（構造12件+9 subtests）/ L3（境界171件+23 subtests、
Django check ×2）/ L5（`tests/ui_invariants` 12件+3 subtests、新規テストを含めすべて緑）が緑。L4
（`manage.py test tests.acceptance`）も developer の担当外だが健全性確認として実行し、22件すべて緑
だった（tester が別途 `5bea6c8` で origin/walking-time の step を既に翻訳済みのため、上記の
「14件中3件失敗」はこの時点で解消している）。

### 独立監査F1（基点マーカー位置検証のトートロジー）を解消した（2026-08-24、developer）

独立監査（`reviews/audit-tdr-cs-origin-marker-position.md`、branch `test/origin-marker-position`
——このブランチ自体には未マージで、`git show a22bb2b:...`で内容を読んだ。下の「気づいたこと」参照）が
Blocker 1件（F1）を報告した。基点マーカーの数値一致検証は「マーカーの位置が応答の`searchOrigin`に
由来し、独立に知られた定数ではないこと」を証明すると契約が主張していたが、`acceptance_state.py`の
`_ORIGIN = Origin(latitude=0.0, longitude=0.0)`が全14箇所・全モードで共有されていたため、応答を正しく
読む実装と`0`/`0`を決め打ちする実装が常に同じ結果になり、実際には証明できていなかった。architect が
`ffd6937`で`test-support-api.yaml`（`1.4.0`）に`CandidateProposalAcceptanceState.searchOrigin`
（任意・nullable・緯度経度）を新設済み——省略時は従来の合成定数、指定時は応答の`searchOrigin`がその値と
完全一致することを要求する。本スライスはその実装側を担当した。

**基点を動かしたときに候補との相対関係が壊れないようにした方法**: `acceptance_state.py`の全ての
`_..._source()`関数が返す合成候補群は、`_ORIGIN=(0.0, 0.0)`からの絶対緯度経度としてハードコードされて
おり（例: `latitude=0.0010 + index*0.0002`）、徒歩時間・徒歩の上限フィルタ・重み付け選択・
`SHOWN_POOL_PRIORITY`の集合判定はすべて`pipeline._distance(origin, candidate)`——`origin`と`candidate`の
絶対座標の差——に依存する。新設`_origin_shifted()`は、`active_search_origin()`が既定値と異なる基点を
返すとき、候補群の全メンバーを「基点自身が動いた分と全く同じデルタ」で平行移動してから返す。これにより
`candidate.longitude`と`origin.longitude`は既定では両方とも`0.0`で、平行移動後は両方とも同じ
`origin.longitude`になる（同じ値どうしの浮動小数点減算は常に厳密にゼロなので、経度方向の距離寄与は
基点をどこへ動かしても厳密にゼロのまま）。緯度方向も同様に厳密なデルタ保存を確認済みで、
`WALKING_TIME_LIMIT_EXCLUDES`の12分境界（950m/12分・800m/10分・1100m/14分、マージン40〜150m）が
基点を合成的に大きく動かしても崩れないことを単体テストで直接検証した
（`test_walking_time_limit_boundary_is_unchanged_by_a_pinned_origin`）。`NO_RESULTS`（パイプラインを
経由しない固定応答）も`active_search_origin()`を読むよう配線し、モードによらず一貫して基点を報告する。
`set_mode`/`reset_mode`/`views.candidate_proposal_state`（PUT）に`searchOrigin`の受け渡しとスキーマ検証
（`additionalProperties: false`・緯度±90・経度±180・bool値の拒否）を配線し、省略・明示的な`null`の両方が
既定の合成定数へフォールバックすることを確認した。

検証（すべて developer が実行）: L1（ruff・ruff format・352 unit tests——18件新規・カバレッジ97%、
`coverage report --fail-under=90`通過）/ mutation（`acceptance_state.py`・`test_support/views.py`へ
スコープを絞った`--gremlin-targets`実行、139/139 zapped=100%、Windows既知のWinError 206を回避する
2026-08-14確立の先例どおり）/ L2（構造12件+9 subtests）/ L3（境界181件+23 subtests、Django check ×2）/
L5（`tests/ui_invariants` 12件+3 subtests、本スライスはレンダリングコードを変更していないため不変のまま
緑）が緑。加えて、健全性確認として`manage.py test tests`（L4含むフルスイート）を実行し386件すべて緑
だった（担当外のstep定義側はtesterが並行して進めている）。

**気づいたこと**: 依頼で指定された監査レポート`reviews/audit-tdr-cs-origin-marker-position.md`は、この
ブランチ（`docs/record-tdr-cs-slice-state`）の作業ツリーには存在しない。コミット`a22bb2b`として
`test/origin-marker-position`ブランチにのみ存在し、architect の契約改訂コミット`ffd6937`（本ブランチ上、
親は`a078684`で`a22bb2b`を経由していない）はその内容を参照してはいるが、ファイル自体を本ブランチへは
持ち込んでいない。`git show a22bb2b:projects/dining-radar/reviews/audit-tdr-cs-origin-marker-position.md`
で内容を読み、実装はそこに書かれた指摘とADR-0027追記2の記述に基づいて行った。契約自体に矛盾は見つから
なかった——`test-support-api.yaml`の新設スキーマは省略時/指定時の挙動を明記しており、実装で判断に迷う
点はなかった。監査レポートをこのブランチへ持ち込むかどうか（ブランチ間のコーディネーションの問題であり
契約の矛盾ではない）は、developer の権限外として報告のみ行う。

### `design.md` が2世代古い（2026-08-23 確認）

`design.md` は designer が起動時に読む文書（役割定義の5番目）だが、中身は **`ADR-0023` が廃止した
切り口（コンセプト）モデル**のままである——「切り口は現在4種類」「別の切り口で再提案」「最大3つの
次の切り口をモーダルで表示」。さらに57行目は「地図には…**検索基点・経路・現在地・徒歩時間を出さない**」と
書いており `ADR-0025` と正面から食い違う。最後にファイルが動いたのは 2026-08-21 の改名コミットだけで、
**中身は `ADR-0023` 以降一度も更新されていない**。

2026-08-23 の designer は指示どおり読んだうえで「使えなかった」と報告し、契約とADRを正として作業した。
**次の designer が同じ判断をする保証はない。** architect による更新が要る。

### 進行中: ADR-0025（検索基点と徒歩時間の開示）— 人間の承認待ち

ブランチ `docs/tdr-cs-origin-and-walking-time` に、承認待ちの決定と契約改訂がある。実装コードは
一切変更していない。

人間裁定 2026-08-20 chat（『別にソースから現在位置を推測できなければいいから、環境変数で指定すれば
よく、アプリ利用者にはバレてもいい』）を受けて、`ADR-0008` 決定4 の Must のうち **browser への
非開示だけ**を撤回する。公開URL・ログ・trace・Git への非開示と、タイル提供者へ基点を渡さない
`Referrer-Policy`（`ADR-0008` 決定5）は維持する。`ADR-0004` がこれを却下した理由「生活圏の露出と
外部通信を増やす」のうち、前者は露出先を特定していなかった——画面を開けるのは招待制認証を通った幹事
だけで、全員が基点の界隈にいる。後者は徒歩**経路**には当たるが、基点マーカー・同心リング・徒歩時間
には当たらない。決定9として、リング半径から設定探索範囲が間接的に推測されうることも許容した
（値そのものの露出は引き続き禁止）。

契約4本の改訂は architect がドラフト済みだが、**このPRには含めず実装スライスへ回した**。L4は稼働中の
実装の応答を契約スキーマと突き合わせるため、契約だけ先に進めると `'searchOrigin' is a required
property` で提案を取得する全シナリオが落ちる（実測: 11 error）。改訂シナリオは画面挙動そのものを
検証しているので、必須項目を任意に緩めても解消しない。既存シナリオに実装待ちの印を付けると、いま
守れている検査まで止まる。この製品で「契約だけ先にマージする」が成立しないことは `ADR-0024` の実績
（契約・実装・テストが同一コミット `6dd0fb1`）とも一致する。ドラフトはブランチ
`docs/tdr-cs-contract-draft-rebased` に退避し（旧 `docs/tdr-cs-contract-draft-adr-0025` は改名前のパスを
指すため使わない）、内容は
`adr-0025-candidate-search-contract-notes.md` が持つ。改訂の要点は `populationAttributes` の同一性境界で、
生の徒歩分を載せると匿名の母集団行と表示中の候補が値の一致で結びつくため、`walkingTimeBand` を
「ブラウザが提示している上限候補のうち、この候補がなお該当する最小値」と定義した。禁止属性の列は
`walkingTimeBand` だけを明示的な例外として書き直し、座標・基点・設定探索範囲・正確な距離・経路・
現在地は禁止のまま残した。徒歩時間の算出方式（直線距離か道のり基準か）には踏み込んでいない——
`ADR-0025` 決定2 が実装スライスへ送った判断であり、契約はどちらでも満たせる形にしてある。製品側では
**直線距離からの概算**を採ることが人間の選択で決着している。実装で必ず踏むのは
`src/dining_radar/recommendation/pipeline.py` の `_distance()` が**度単位**を返すことで、docstring が
その理由（正確な距離をブラウザに返さないので測地線の精度は要らない）を明記している。`ADR-0025` で
この前提が崩れたため、徒歩時間を表示するにはメートル換算が要る。`src/dining_radar/**` は mutation
testing の対象なのでテストも要る。

`design/explorations/` に店を絞る画面のラフ3枚を置いた。**承認済み設計ではない**。これらは designer の
パイプラインを通っておらず orchestrator が直接描いたもので、`meta/adr/0018`・`0020`・`0021` の
design integrator の定義に沿っていない。現状のまま「設計骨格」の承認材料として提出してはならない。

未決だった3つのうち、**すべて解決している**。**(1)** ラフ3枚の由来問題——`design/explorations/` に
**探索資料のまま置く**（人間が選択、決着済み）。README に由来を記録済みで、承認材料に昇格させない。
残っていた「画面作業そのものを designer 経由でやり直す」件は、2026-08-23 に designer が `/design` で
`design/wireframes/` を作成し完了した（下記参照）。**(2)** `ADR-0003` 決定2 が `design-preview` に
「検索基点」「数値距離」を置くことを禁じており、`ADR-0025` で両方が製品の表示物になったことで生じていた
条文の衝突は、**`ADR-0028`（2026-08-24、architect）が解消した**——`design-preview` 受け皿そのものを
廃止したため、禁止条文が適用対象を失った。`ADR-0003` 決定1・2 は `ADR-0028` に置き換わり（superseded）、
決定3（契約との照合境界）・決定4（runtime別のデザイン作成経路）は、その中身がすでに全プロジェクト共通の
designer 役割契約（`meta/adr/0050`）へ移っているため引き継がれない。**(3)** スマホの C 画面は案2
（地図を畳む）と案3（余地バーを地図に重ねる）が未選択だった——**これは 2026-08-23 に決着した（下記）。**

**(3) の前提は確定した（人間裁定 2026-08-22）**——**幹事はスマホ中心でこの作業をする**。したがって
スマホの C 画面は「一応動く」で済ませられず、案2か案3かは本番の判断である。2026-08-11 に人間承認済みの
モバイル優先の配置とも、L5 が 375×812 で走ることとも整合する。なお探索の過程で orchestrator が描いた
「会の進みかた」の図は幹事＝PC・参加者＝スマホとしており**この裁定と食い違う**。図は探索資料であって
承認済み設計ではないため、正はこの裁定である。

**(3) に方向が出た（人間の意向 2026-08-23）。ただしこれは画面構成の指定ではなく、情報量の指針である。**

2026-08-23、`meta/adr/0050` のマージ後に designer を起動し、案2と案3を同じ3場面で並べた比較を作った
（Artifact: `https://claude.ai/code/artifact/ec54ae74-eec4-451c-b16d-3c7c833dcb81`。元データは未コミット）。
それを見た人間が示した意向は、**地図を見ている場面では「位置関係」と「いま選んでいる店舗」以外の情報は
削ってよい**、というものである。人間自身が「厳格に守る必要はない。わざわざ別画面・コンポーネントにする、
とかは不要」と述べている。

そこから読み取れる具体は次の3つだが、**いずれも「こう作れ」ではなく「ここまで削ってよい」の意味**である:

- 最初は店舗のリストでよい。タップしたら地図を見る
- 地図はいま選んでいる店舗を中心に置き、その店舗の情報を添える。**他の店舗の情報は出さなくてよい**
  （地図側に横スワイプのカードデッキは要らない）
- 他の店舗を見たいときは、地図上のピンをタップして切り替える

**構成の決定は designer に残っている。** 別画面にするのか、同じ画面の中で地図を開くのか、コンポーネントを
分けるのかは指定されていない。案2の「地図を1行のバーに畳む」形のままでも、開いたときに他店舗の情報を
落とせば意向は満たせる。**この記述を構成の要件として読まないこと**——初回の記録がそう読んでおり、
人間の訂正を受けて書き直した。

designer に渡すときは「地図側の情報量をここまで削ってよい」という制約として渡し、構成は designer が
決める。渡す際に確認が要る点: 下記の「案2を選ぶと契約の追補が要る」が、採る構成によっては同じ論点に
なる——`candidate-search-browser-interface.yaml` が初期表示に `candidate-map` の存在を要求しているため、
初期表示をリスト主体にする形はいずれもこの条文に触れる。

designer が比較の作図から報告した事実（**すべて作図上の値で未実測**。`meta/adr/0059` 決定5）:

- 案2の「4件同時に見える」は成立しない。契約が要求するカード項目を全部描くと**3件と4件目の頭**まで。
  探索ラフのカードは項目が省かれていたので過大だった
- 案3の「位置関係が常に見える」は、条件を触っている最中には効かない（パネルが地図をほぼ覆う）

designer が報告した契約とのズレ（architect と共有すること）:

- **案2を選ぶ場合、契約の追補が要る。** `candidate-search-browser-interface.yaml` の
  `authenticatedInitialOutcome.present` と `initialProposal.success.present` が初期表示に `candidate-map` の
  存在を要求している。地図を畳む・別画面にする形が、これをDOM上どう満たすのか（存在させて隠すのか、
  条文を緩めるのか）は未決。加えて `candidate.js` に resize ハンドラが無く `invalidateSize()` を呼ばない
  という既知の未修正課題が、**畳んだ地図を開く操作で必ず踏まれる**
- パネル内の「+N件」バッジは契約に無い要素。`populationAttributes` から計算できるが、契約は件数を
  `candidate-filter-apply` の `data-match-count` にしか置いていない。採るなら契約追加が要る
- 常時の件数表示は出していない（人間が一度断っているため）。**探索ラフ3枚はこれを常時出しており**、
  designer はラフを正として引き写さなかった

画面作業そのものは引き続き**designer を起動して行う**（`meta/adr/0050`。マージ済み `3c73e11`）。
orchestrator は自分で描かない。次に designer を起動するときは、**セッションを開き直してから**行うこと
——2026-08-23 の起動では旧定義・旧道具立てで走り、designer が `/design` を起動できなかった
（`meta/adr/0059`・`meta/friction-log.md` FR-003）。上記の Artifact は designer が書いた `.dc.html` を
orchestrator が発行したもので、これは一度きりの処置であり正規の経路ではない（`meta/adr/0059` 決定3）。

プロジェクト名から実在の地名 "toyama" を外す改名は**完了している**（2026-08-20、`adr/0026`）。
Pythonパッケージ `dining_radar` とシナリオIDプレフィックス `TDR` は据え置き、ブランチ
`project/toyama-dining-radar` と ruleset `protect project/toyama-dining-radar` も意図して旧名のまま残す。

Claude took this project over from Codex on 2026-08-04, with no open pull request and a green project branch, so no unmerged Codex artifact was inherited. The project branch was promoted to `main` through merged PR #86; work now runs on ordinary feature branches based on `main`.

`TDR-AUTH` (authentication) and `TDR-CS` (candidate search) are both implemented. `TDR-AUTH` and the first `TDR-CS` are durable on `main`; the filter model described below lives on this feature branch and is not yet merged.

An authenticated organizer opens the screen and immediately sees one proposal — up to five candidate cards and a Leaflet/OpenStreetMap map — without being asked for secondary conditions. Selecting a card highlights its marker and the reverse. The concept-lens model is gone (ADR-0023): there is no `ConceptKind`, no re-proposal modal, and no lens to choose. What replaced it is an always-visible filter panel (genre, izakaya/bar inclusion, non-smoking, card payment, budget tier) plus a fixed nearest-first sort and a "search again" control. Filters separate `applied` from `pending`: changing a control edits only `pending` and issues no request; apply commits it as one `POST /candidate-proposals`; revert restores `applied` without any public operation. Filtering is soft — a candidate whose value is unknown is kept and ranked after the confirmed matches, never removed — and it applies to the whole fetched population, not to the already-capped five. Selection from the filtered population is randomized from a nearest-first pool, so repeated searches do not return the same five shops.

The implementation is four modules. `recommendation` is pure Python with no framework or provider dependency: it deduplicates by provider page URL, applies the candidate filters to the full normalized population, keeps unknown soft-filter values, and selects up to five candidates. `integrations/hotpepper` is the HTTPS-only adapter with env-based configuration, query-key redaction, and provider-shape normalization. `suggestions` mediates the fresh search and the pipeline, applies per-organizer rate limiting, and owns the acceptance-only state seam; it is also the only path by which `web` may reach the provider adapter, which a structural test enforces. `web` serves `POST /candidate-proposals`, a serializer matching the API schema exactly, and the authenticated screen, whose candidate surface is rendered client-side by vanilla JavaScript with no bundler.

The current feature branch contains the chat-approved filter-model UI/UX refinement after `955e10d`: the map-led candidate surface has a bottom-overlapping, horizontally swipable card deck; mobile removes the double outer card chrome; and filter controls separate applied conditions from pending changes. The human approved the subsequent mobile-first placement mock on 2026-08-11, and the production Django screen now reflects it: a 52px header, one-line condition toolbar, horizontally scrolling single-row filter categories, a viewport-filling map, near-full-width compact cards, and an explicit selected-candidate counter. The filter labels reflect the soft-filter model: confirmed card-payment unavailability is excluded while information unavailable remains, and budget controls explicitly say they use dinner-budget tiers.

The current screen refines that agreed control surface without changing its contract or request behavior: at PC widths the expanded filter controls are a three-column floating panel anchored to the condition toolbar; on mobile they are an overlay over the map. The desktop deck keeps its right-edge fade but exposes a thin, styled native horizontal scrollbar so a normal mouse can scroll the candidates. Its card internals retain the earlier compact, pale-green fact and description hierarchy; the repeat-search control shows a text label on PC and stays icon-first on mobile, mobile filter rails add a right-edge fade, and selected chips carry a visible check. The `cardPaymentAvailable=false` caution reads `クレジットカード非対応（支払い方法は要確認）`, stating only the confirmed card limitation. Regular-holiday text wraps naturally rather than ellipsizing and takes its own full-width footer row; the provider link follows on its own 44px target row. The common short value stays compact, while longer provider text remains fully visible and may increase the card height. Orchestrator measured the synthetic screen at 1920×1080: document height equaled the viewport; the deck was `overflow-x: auto`, 1374px wide with 2028px of content, showed the thin native scrollbar, and horizontal input changed `scrollLeft` from 0 to 654; the description background was `rgb(243, 246, 242)`. The candidate article was 384×289.7px; regular-holiday text was 306×35px, exact and unclipped in two lines, and the provider link was a separate 44px row. At 375×812, document height equaled the viewport, the card was 343×242.5px, regular-holiday text was 275×35px with its exact value in two lines, and the provider link remained 44px. Neither viewport had page overflow; the mobile scrollbar remained hidden, and browser warnings and errors were both zero.

The orchestrator completed L5/control-surface checks using the human-owned `.env.local` and real data at 375×812 and 1440×900. At 375×812, the collapsed screen measured exactly one viewport with no page-level overflow, a 343×about-206px card, three equal-width decision facts, and 44px minimum app-authored controls; the only smaller links are the agreed inline OSM/provider credits. The unchanged expanded panel measured about 185px, with three 52px category rows whose overflow remains inside their horizontal rails; changing a filter adds a 44px-high apply action and disables re-search until applied or reverted. Card↔pin synchronization and the 1/5 counter worked in both directions. At 1440×900 the screen also remained exactly one viewport, with the full 1214px map/deck surface and about 350×249px cards. Browser logs contained no warning or error. No privacy-sensitive text or external scripts were introduced, and the OSM attribution remained readable. Earlier real-data checks also found and corrected Leaflet stacking over the deck and attribution occlusion.

The same feature branch now contains the human-agreed deployment preparation for a zero-cost first release: Render Free Web in Singapore, Neon Free PostgreSQL, one Gunicorn worker, WhiteNoise same-origin static delivery, a DB-only readiness probe, and an idempotent first-organizer bootstrap from write-only runtime secrets. `render.yaml`, `build.sh`, `DEPLOYMENT.md`, and proposed ADR-0021 define the topology and operator flow; no Render/Neon resource or public origin has been created yet. Render refuses to start without `DATABASE_URL`, trusts the forwarded HTTPS signal only when Render identifies the runtime, and appends only Render's supplied hostname. Production collection processed 136 static files successfully after removing Leaflet's stale unvendored source-map reference.

~~The isolated `design-preview` retains the approved mobile-first placement mock as a synthetic, network-free reference. Its composition has been translated into the production Django screen; it is no longer an unapproved draft.~~ **Retired (2026-08-24, ADR-0028).** `design-preview` is no longer used — `ci-dining-radar.yml` has never exercised it, and it predates `meta/adr/0050`'s retirement of the external-design-AI economy it was built for. Screen design review now flows through `design/wireframes/` (designer's `/design` output). architect has no git access; a human still needs to delete `projects/dining-radar/design-preview/` and the `dining-radar-design-preview` entry in `.claude/launch.json` (both listed in ADR-0028).

The lens abstraction died by attrition and then by analysis. Three `ConceptKind` values were retired one at a time after live review, each because the lens produced no comparison the organizer could not already see (ADR-0016, ADR-0019). ADR-0023 then retired the concept itself: every surviving lens decomposed into a filter or a sort, so the abstraction was only wrapping those two operations in prose and hiding the controls. Repeat demotion went with it — `previouslyShownProviderPageUrls` and `build_concepts` no longer exist, and randomized pool selection now does the job that demotion was doing.

Candidate cards show name, genre, description, regular holiday, a coarse total-seat reference (少なめ/標準/多め), a coarse non-smoking reference, a coarse dinner-budget reference explicitly labeled as a dinner figure, a caution on shops that do not accept credit cards, and the provider page link (ADR-0019). Access was dropped because the map already shows the same location; business hours were dropped as the largest contributor to mobile card height (ADR-0017), and the provider page remains the authoritative source for hours. The card-payment caution never asserts cash-only, because only credit-card acceptance is retrievable.

So that the browser can show "how many candidates would this match" before the organizer commits a pending change, the response carries `populationAttributes` (ADR-0022): an anonymous attribute table — genre, non-smoking status, card acceptance, budget tier, and whether the genre is default-excluded — with no shop name, URL, coordinate, or identifier. `candidate.js` counts against it locally rather than issuing a provider request per toggle, so its predicate must mirror the server's exactly, izakaya/bar fallback included.

Every machine gate is green on this branch, re-run independently by orchestrator rather than accepted from the roles' self-reports: L0 govlint; ruff and format; L1 (290 passed, 97% branch coverage, and the prior 99.61% mutation result against an 80% gate reused because no Python product source changed); L2 (12 passed); L3 (158 passed plus both Django checks); L4 (20/20 acceptance tests, no skips); and the ADR-0020 L5 render-invariant gate (11 passed plus 3 subtests). `TDR-CS-00` through `TDR-CS-13` execute against the real client-rendered screen through Playwright per ADR-0009; `TDR-AUTH-01` through `TDR-AUTH-05` and `TDR-AUTH-07` keep the plain-HTTP DSL (ADR-0009 decision 4). `reviews/audit-tdr-cs.md` and `reviews/audit-tdr-cs-filter-model.md` hold the independent reviewer's translation tables for `TDR-CS`.

**Only orchestrator can measure rendered geometry** — developer and the role agents have no browser access. Four defects so far were invisible to L1–L4 and surfaced only through real-device measurement: marker attributes never applied, a scenario green without asserting its DOM outcome, template comment text rendering as page content, and a coarse budget tier rendering "情報なし" for every live candidate. Any claim about rendered size or appearance that orchestrator has not measured must be labeled 未実測.

## Live provider measurements (2026-08-10, human's own key and private origin)

These come from direct calls against the configured origin with `lunch=1`, `count=100`, and the configured range, plus the provider's budget master. They are measurements, not assumptions.

- `results_available` = 64, `results_returned` = 64. **The whole population fits in one request; nothing is truncated.** Widening `range` to its maximum yields 94 with the lunch filter, still under the 100 cap.
- `card`: 48 accept, 16 do not — 64/64 populated, no unknowns.
- `non_smoking`: 37 全面禁煙, 14 一部禁煙, 13 禁煙なし — 64/64 populated, no unknowns.
- `budget.name`: 64/64 populated. `budget.average` is 59/64 and mixes free-form prose (`通常平均：3000円 / 宴会平均：3500円`), so `normalize.py` reads `name`, not `average`.
- Genre distribution: 居酒屋 24, 和食 9, カフェ・スイーツ 7, 創作 7, ラーメン 4, イタリアン・フレンチ 4, 洋食 3, 焼肉・ホルモン 2, ダイニングバー・バル 2, other 2. Default genre exclusion leaves 38.
- Provider-side `non_smoking=1` returns 51, exactly 全面禁煙 + 一部禁煙; `card=1` returns 48, exactly the local count. Provider-side and local filtering agree exactly at the current population size.
- The budget master has **17** codes (B009 〜500円 through B014 30001円〜) and the `budget` request parameter accepts **at most 2**. The three coarse tiers cannot be expressed provider-side: the low tier needs 4 codes and the high tier 11.

## Confirmed policies

- Do not commit real life-area names, coordinates, configured ranges, API keys, secrets, provider request URLs/responses, shop IDs, images, shop data, real-data migrations, fixtures, or database dumps. Use only synthetic test/design data.
- Do not cache or persist provider responses. This product does not use durable provider IDs or HMAC-derived lookup data. Reopening that policy requires a new human decision, provider-terms review, and ADR (ADR-0018 examines both and remains `提案中`).
- Send the API key only from the server to the provider; never expose a key-bearing URL, provider internals, or the private origin to a browser, public URL, log, error, or trace.
- Use Leaflet with OpenStreetMap standard tiles only for small authenticated interactive use, with attribution and without tile prefetch, bulk download, or offline cache. The map must not expose the private search origin.
- Leaflet itself (JS, CSS, marker icons) is vendored under `static/` and served same-origin (ADR-0010). The authenticated screen loads no third-party script.
- Candidate-search endpoints depend on an authenticated organizer. ADR-0006 and the authentication contracts define that boundary; this slice implements it locally without choosing a deployment provider.
- Controls on the authenticated candidate screen must appear in the server-rendered HTML, not be inserted by client JavaScript, wherever TDR-AUTH's plain-HTTP DSL observes them (`authentication-browser-interface.yaml` v0.2 `renderModel`).
- Never assert what the provider data cannot confirm. Excluding izakaya/bar genres records uncertainty about lunch service, not its absence; the card-payment caution never claims cash-only.

`manage.py` loads `projects/dining-radar/.env.local` when it exists, using a stdlib-only parser and `os.environ.setdefault`, so a real process environment always wins and a missing file is a no-op. That path is developer convenience only — deployment runs through `wsgi.py` and never depends on it.

ADR-0014 establishes a client-side JavaScript unit-verification layer for `candidate.js`. It is not yet implemented. The ADR is explicit that none of the defects found in that layer so far would reliably have been caught by it — its value is forward-looking regression capture.

ADR-0020's three layers are implemented. `tests/ui_invariants/test_render_invariants.py` (a new directory, outside `tests/acceptance/steps`/`dsl`, maintained by developer per the ADR) machine-checks decision 4's four gate invariants — narrow-width map reachability, keyboard reachability/activation, internal-enum non-exposure, and 44px minimum control size — as independent DOM/geometry assertions against the real screen (`StaticLiveServerTestCase` + `sync_playwright`, reused from the L4 harness; `CandidateSearchBrowserDsl` is reused only for its Given-seam setup and navigation, never for assertions). All nine test methods (12 assertions across three subtests) are green. Building the keyboard-activation check surfaced a real defect the ADR's own premise predicted: map markers were Tab-reachable (Leaflet's `keyboard: true` gives the marker icon `tabindex="0"`) but pressing Enter/Space did not select them, because Leaflet only translates that keypress into a `click` for a marker with a bound popup, which this screen's markers never have (confirmed by reading the vendored `leaflet.js`). `candidate.js` now attaches an explicit keydown handler to each marker, mirroring the candidate card's own existing one; reverting the fix and re-running the new test reproduces the original failure, confirming the test is a genuine regression catcher. `tools/render_observation.py` (decision 1, non-gate) signs in, loads a synthetic proposal, and screenshots the authenticated screen at three viewports (390×844, 730×900, 1440×900) to `.render-observations/` (gitignored, never committed); it performs no comparison. Using it surfaced one methodology lesson, not a product defect: reusing one already-loaded page across `set_viewport_size()` calls renders a stale Leaflet map (two markers appeared to vanish at narrow widths), because `candidate.js` never calls `invalidateSize()` on resize; the tool now loads a fresh page per viewport instead, and confirmed all candidates render correctly at every width once it does. That same absence — no resize handler re-fits the map — remains a real, unfixed latent gap for a user who resizes their window or rotates their device after the map has already rendered; it is not covered by any of decision 4's four invariants (which check the map container's own position/controls' own sizes, not whether Leaflet's internal view is still correct after a resize) and is left for a future slice to pick up. Orchestrator wired the new gate into `ci-dining-radar.yml` as its own `l5-ui-invariants` job with `needs: l4-acceptance` (ADR-0020 decision 6 left the placement to orchestrator; a separate job rather than a step inside `l4-acceptance` keeps "satisfies the approved scenarios" and "still holds the frozen render invariants" distinguishable, and `meta/verification.md` 3.3's ordering falls out of the dependency). Orchestrator re-ran every tier independently rather than accepting the role's self-report: L0 govlint, ruff, 196 unit tests at 96% branch coverage, 7 structural, both `manage.py check` profiles, 19 L4 acceptance tests, and the 9 new invariant tests, plus an independent revert-and-rerun of the `candidate.js` fix confirming exactly one test reddens and the other eight stay green. Mutation testing was not re-run and does not need to be: `pytest-gremlins` targets only `src/dining_radar/**.py`, and no Python source changed in this slice. The gate's own first CI run then failed where every local run had passed (FR-013): decision 4(e)'s 44px check measured *every* element carrying `data-candidate-control-purpose`, including the two controls inside the closed account-menu `<details>`, and `bounding_box()` on non-rendered `<details>` content is unspecified — the same Chromium build (151.0.7922.34) returned a real 161×44 box on one Windows run, a zero box on another, and consistently zero on Ubuntu. `is_visible()` returns a deterministic `False` there on both platforms, so the check now measures only currently-disclosed controls and asserts a non-zero measured count per phase, deferring (never excluding) the account-menu controls to the phase that opens the menu; orchestrator independently confirmed the deferral is real by shrinking that panel's CSS below 44px and watching `auth-password-change-open` redden at 25.59px. No threshold was lowered and no assertion was removed.

## Deployment platform terms and measurements (2026-08-12, orchestrator)

Reconfirmed from the providers' own current documentation, as `DEPLOYMENT.md` requires before any resource is created.

- **Render free web**: health checks are sent **directly to the service port, not through the edge**, so they carry no `X-Forwarded-Proto`; the `Host` header is the service's `onrender.com` subdomain (or a verified custom domain). A check counts as successful on **`2xx` or `3xx` within five seconds**. A free service spins down after **15 minutes** without inbound traffic and takes about a minute to wake; a workspace gets **750 free instance hours** per calendar month; the filesystem is ephemeral and there is no SSH.
- **Neon free**: **100 CU-hours and 0.5 GB per project**, scale-to-zero after **5 minutes** idle and always on for free, 10 branches, 6-hour instant-restore window. The plan is permanent, not a trial. Render's own free Postgres was **not** chosen because it expires 30 days after creation.
- **Hot Pepper**: the required text credit is `Powered by <a href="http://webservice.recruit.co.jp/">ホットペッパーグルメ Webサービス</a>` and must appear on every page or application using the API. `serializers.PROVIDER_CREDIT` matches this exactly and `candidate.js` renders it, so the requirement is met on the successful-proposal screen. Use by a site that takes money from restaurants is prohibited; affiliate revenue is not.

**Correction (2026-08-14).** The 2026-08-12 entry above originally said the provider states no caching rule and that this product's no-cache policy was purely its own choice. That was wrong. Orchestrator read the API reference and the ご利用案内, found no clause, and recorded the negative — without reading the 利用規約 itself (`regulation.html`), and, more to the point, **without reading `adr/0018`, this project's own ADR on exactly this question, which had quoted the clause verbatim including the 24-hour figure since 2026-08-09**. Orchestrator cited ADR-0018 by name repeatedly across that same period while never opening it. The lesson is not "check more web pages" but: before asserting that an external rule does not exist, read the repository's own record of that rule first — a negative finding about provider terms is exactly the kind of claim this project already keeps a document for. The 利用規約 does carry a caching clause — when the ご利用案内 sets no more specific rule, **a cache must be refreshed or deleted within 24 hours** (`個別に定める規定がない場合はキャッシュの更新頻度を24時間以内と定めます`). It also forbids copying retrieved information into a third-party database; browser-local `sessionStorage` on this origin is not one. So the no-cache policy is now backed by a real provider term as well as by this product's own choice, and any browser-held provider-derived value needs a bound at or under 24 hours.

**Verified locally against the production settings module** (`RENDER` set, `DJANGO_DEBUG` unset, a throwaway SQLite standing in for Neon): `collectstatic` copies 136 files and post-processes 398 with no missing manifest entry; the login page renders 200 with `request.is_secure()` true through `X-Forwarded-Proto`; a CSRF-enforced login POST carrying a browser-like `Origin`/`Referer` returns 302 to `/`, so **no `CSRF_TRUSTED_ORIGINS` entry is needed** behind Render's proxy; the authenticated screen then returns 200 under `CompressedManifestStaticFilesStorage`, meaning every static reference resolves; `sessionid` is Secure+HttpOnly+SameSite=Lax and `csrftoken` is Secure+SameSite=Lax. `check --deploy` reports `security.W005` and `security.W021` (HSTS subdomains and preload), both deliberately off. This is a local stand-in, not the public origin.

That local reading of `check --deploy` was incomplete in a way worth recording: the real build also emits **`security.W009`**, and the local probe could not have predicted it, because the probe supplied its own 50-character secret while Render's `generateValue: true` supplies a 256-bit random value base64-encoded to **44 characters**. Django's check fires on `len < 50 or unique < 5 or startswith("django-insecure-")`; only the length arm trips. The value is shorter because base64 packs about 6 bits per character against the roughly 5.64 of Django's own alphabet — 256 bits of entropy against the ~282 of Django's default `get_random_secret_key()`. It is a length heuristic misreading density, and replacing it would create a path where a human sees and pastes the signing key, which is worse than the warning. Left as is.

**A measured defect found this way and since fixed**: under the production settings module with `RENDER` set, `GET /healthz` without `X-Forwarded-Proto` used to return **301**, because `SECURE_SSL_REDIRECT` is on and `SECURE_REDIRECT_EXEMPT` was empty. Combined with the two facts above — Render probes the port directly and accepts `3xx` — the readiness probe was **reported healthy without ever running its `SELECT 1`**, so a suspended or broken Neon compute would not have been detected, contradicting ADR-0021 decision 5 and `DEPLOYMENT.md` §3.6. `SECURE_REDIRECT_EXEMPT = [r"^healthz$"]` now exempts that one path. Re-measured independently: plain-HTTP `/healthz` returns 200 `ok`, while `/`, the login path, `/healthz/`, `/healthzz`, and `/x/healthz` all still return 301 — the exemption matches the exact path only, never as a prefix or substring. An unrecognized `Host` still returns 400, which is correct because Render probes with the service's own `onrender.com` hostname.

## Public origin L5 (2026-08-14, orchestrator, against the live service)

The service is deployed and reachable over HTTPS on a Route 53 subdomain (ADR-0021 addendum). Measured from outside with `curl`, following no redirects:

- `/healthz` returns 200 with body `ok`; the first request after a spin-down took 15.2s, consistent with Render's stated wake time.
- `http://…/` returns 301 to HTTPS. An unauthenticated `/` returns 302 to `/accounts/login/?next=/`.
- The login page returns 200 and contains **no `href` at all** — no public signup and no email-reset affordance, which is what `TDR-AUTH-03` requires.
- Security headers on a real response: `strict-transport-security: max-age=31536000` (no `includeSubDomains`, no preload, as designed), `x-content-type-options: nosniff`, `x-frame-options: DENY`, `referrer-policy: strict-origin-when-cross-origin`, `cross-origin-opener-policy: same-origin`.
- `csrftoken` is `Secure` + `SameSite=Lax`. `sessionid` needs a signed-in session and was not exercised, since orchestrator holds no credentials.
- No API key, coordinate, provider URL, or range appears in the served HTML or in any response header. A 404 returns 179 bytes and names no framework, traceback, or setting.

The authenticated screen was checked by the human, since orchestrator holds no credentials: candidate cards and the map render, and both required credits appear — `Powered by ホットペッパーグルメ Webサービス` and `© OpenStreetMap contributors`. The only external requests observed were OSM tile fetches from `*.tile.openstreetmap.org`, which is the intended boundary: ADR-0010 vendors Leaflet itself same-origin, while the tiles are necessarily fetched from OSM, and `product-brief.md` §3 already accepts that the viewed map extent reaches the tile provider. `Referrer-Policy: strict-origin-when-cross-origin` (measured on a live response) keeps that disclosure to the origin alone, with no path or query — which is precisely why ADR-0021 chose it over `same-origin`. A `chrome-extension://` script also appeared; that scheme cannot be loaded by a page, so it is a locally installed browser extension injecting itself, not something the application serves. Note that a tile URL's `z/x/y` triple is itself a location disclosure and must not be pasted into an issue, pull request, or commit message.

**The `/healthz` exemption works in production, and is now measured rather than inferred.** Enabling gunicorn's access log briefly showed the health check arriving as `"GET /healthz HTTP/1.1" 200 2` from a private RFC1918 address with user agent `Render/1.0`, every few seconds. The 200 rules out `SECURE_SSL_REDIRECT`; the 2-byte body is `ok`, so the view itself answered and its `SELECT 1` ran; and the private source address confirms first-hand what had until then been only Render's documented claim, that the check bypasses the edge.

Getting there exposed a defect in the verification itself. The check written into `DEPLOYMENT.md` on 2026-08-12 — "plain-HTTP `/healthz` must return 200" — is unperformable from the public internet, because Render's edge terminates plain HTTP and answers 301 before gunicorn sees the request (that 301 carries none of Django's headers and no `x-render-origin-server`; the 200 carries both). Orchestrator then proposed watching Neon's compute as a substitute; the human tried it, found it decided nothing, and said so. They were right: the graph's time resolution is coarse and user traffic, verification traffic, and health checks all land on the same line, so the 5-minute and 15-minute idle thresholds cannot be told apart. `DEPLOYMENT.md` §3-3 now prescribes the access log and explicitly warns off the Neon method. The lesson is the one this whole fix was about — a check that looks green while verifying nothing is worse than no check, and that applies to the verification procedure as much as to the probe.

## Live-feedback refinement in flight (ADR-0024, 2026-08-14)

The human used the deployed service against real data and raised two complaints: shops repeating across two or three reloads, and a filter surface that was hard to use — the izakaya/bar toggle sitting under 「こだわり」 rather than with genres, and the population looking smaller than it is. Four changes answer three of them (the fourth, always-showing the match count, and wrapping the chip rails, were offered and declined).

Genres are now ordered by how many candidates carry them, counted browser-side from `populationAttributes`, with the old string-length/collation rule kept only as a tie-break. The old order ignored size entirely: measured against the recorded real-data distribution it hid カフェ・スイーツ, the second-largest genre, behind the overflow chip, leaving 13 of 36 candidates (36%) unreachable without expanding; count order brings that to 25%. The izakaya/bar toggle moved into the genre row, at its head — placing it at the tail first pushed it entirely off-screen at 390px, measured, which made the change a regression in the very discoverability it was meant to fix. Selection dropped the fixed nearest-20 pool for distance-weighted sampling over the whole filtered population, since the old pool meant the farther candidates could never appear at all and randomness only rotated a fixed club (measured expected overlap between consecutive draws: 1.25 of 5, now 0.82). And the browser now remembers which candidates it has already shown, in `sessionStorage`, so a repeat is postponed until the rest of the population has had a turn.

That memory is bounded at 20 hours per entry, pruned on every read, and never leaves the tab. The bound exists because Hot Pepper's terms require a cache to be refreshed or deleted within 24 hours; 20 leaves margin. `product-brief.md` §7's echo-back caveat is amended to match, which is a human re-approval point — the policy it protects (no history, no blacklist, no usage-driven recommendation) is unchanged, and ADR-0018 already established that storing shop identifiers is not itself forbidden, only unnecessary.

Verification, all re-run by orchestrator: L0 govlint, ruff and format, L1–L3 (289 tests plus 30 subtests, 97% branch coverage), L4 (20 acceptance tests including the new `TDR-CS-14`), and the L5 render-invariant gate (10 plus 3 subtests). **Mutation is unmeasured on this branch** — see the defect below. Reviewer's independent audit of the L4 diff is in `reviews/audit-tdr-cs-14.md`; it caught a tautological reappearance assertion and a half-implemented expiry check, both since fixed, and orchestrator confirmed the repaired assertion reddens against a real injected defect (`select_with_shown_priority`'s exhausted branch returning nothing) rather than only against a synthetic response.

**Open, deliberately carried rather than resolved.** `TDR-CS-11` clears `shownCandidateMemory` directly to isolate seed reproducibility; reviewer judged the necessity real but noted the contract never names that as an authorized seam, unlike the expiry case.

~~At 390px the genre rail holds 464px of content in 328px, so the toggle and the overflow chip cannot both be visible~~ **解決した（2026-08-23 人間裁定、2026-08-24 PR #156 でマージ）**——「ほか N件…」を行の左端に固定し、横スクロールする領域から分離した。折り返しは採らなかった（2026-08-14 の見送りを維持）。契約は `controlGrouping.genreGroup.overflowPlacement` でDOM順序と入れ物の分離を機械観測する。**「スクロールしても視覚的に動かない」ところまでは検査していない**——そこまで保証するには `adr/0020` が L5 に置いた幾何測定の新設が要り、それは別の判断である。

**A verification defect found while running this slice.** `tools/check_mutation_score.py` reads `coverage/gremlins/gremlins.json` without checking that it is fresh, so a failed mutation run leaves the previous run's score in place and the gate reports green over stale data. This surfaced because `pytest --gremlins` can no longer run on this Windows machine at all: the suite grew from 246 to 289 tests and the subprocess gremlins spawns now exceeds the command-line length limit (`WinError 206`). CI is unaffected — it runs on Ubuntu, and its `run:` block stops on the failing pytest before the score check — so the exposure is exactly the local path, which is also the path that produces "verified locally" claims. Orchestrator read a stale 99.61% this way before catching it. Fixing the freshness check belongs to developer, not orchestrator: it is the tooling that grades orchestrator's own work, which is the same reasoning that locked `meta/tools/**` under `meta/adr/0046` after FR-022.

## Next work

1. Obtain a human go-ahead for the external Render/Neon account mutations and secret entry, then follow `DEPLOYMENT.md` and perform the public HTTPS/privacy/login L5 checks. Every machine gate on this branch is green, so this is what release now waits on. A change to the no-history/no-durable-identifier product policy requires a new human decision before work starts.
2. Reconfirm the assumed Hot Pepper raw JSON field names against current official documentation. (The provider credit, free-plan, and health-check terms were reconfirmed on 2026-08-12 and are recorded under "Deployment platform terms" above.)
3. Refresh or retire the `project/toyama-dining-radar` branch (the branch and its ruleset keep the old name; the 2026-08-20 rename deliberately left them alone). It is no longer the leading edge: `main` is well ahead of it and 0 behind, so the branch only lags. Decide whether to fast-forward it or drop it in favour of slicing directly off `main`, which is what recent slices have actually done.
4. ~~Consider whether ADR-0003's stated design-preview stack (React, TypeScript, Tailwind, shadcn/ui) should match the receiver's actual dependencies (React, TypeScript, `lucide-react` only, with hand-written CSS), by installing the missing packages or amending the ADR. Designer worked around the gap by requiring visually self-contained artifacts; the divergence itself is unresolved.~~ **Moot (2026-08-24, ADR-0028)** — `design-preview` itself is retired, so its dependency mismatch no longer needs reconciling. Pending action item: a human deletes `projects/dining-radar/design-preview/` and the `dining-radar-design-preview` entry in `.claude/launch.json` (ADR-0028 decision 2).
~~5. The candidate map never calls Leaflet's `invalidateSize()`/re-fits when its container is resized after the initial render (no resize handler in `candidate.js`).~~ **解決した（2026-08-24、developer）**——see below. The original framing was partly imprecise: Leaflet's own default `trackResize: true` (confirmed by reading the vendored `leaflet.js`) already re-fits on a plain browser-`window` resize, so a straightforward `page.set_viewport_size()`-style resize was already handled before this fix. The real remaining gap was a container-size change with **no accompanying `window` resize event** — reachable on a phone because `candidate-map`'s height is `dvh`/`vh`-sized, so a mobile browser's toolbar collapsing/reappearing while scrolling resizes the container purely through CSS. `candidate.js` now attaches a `ResizeObserver` directly to the map container (disconnected/reattached on every `initializeMap` re-render) that calls `invalidateSize()` on any container-size change regardless of cause.
6. `meta/tools/govlint.py`'s `SCENARIO_ID` pattern cannot match `TDR-CS-01` or `TDR-AUTH-01`, so all 19 TDR scenario IDs have never been checked by L0. Fixing it needs a human unlock commit for `meta/tools/**` (`meta/adr/0046`).

## Open questions

- Email delivery and SSO remain deferred; accounts stay invite-only and local. The custom-domain question is closed — a Route 53 subdomain fronts the service, recorded in ADR-0021's 2026-08-14 addendum.
- Whether the "approved screen drives the test-infrastructure control-surface contract" pattern (ADR-0011, ADR-0013) should be generalized into a meta ADR beside `meta/adr/0023`, since other UI projects can hit the same friction. Architect raised this; drafting a meta ADR belongs to orchestrator (`meta/adr/0047`).
- One L4 run failed intermittently and was never explained. Developer's hypothesis (concurrent file edits during the run) was never confirmed. It has not recurred.
- Whether ADR-0020's harness should be generalized to the meta layer (a shared `meta/verification.md` revision and/or a reusable harness for other UI projects). ADR-0020 decision 10 deliberately scopes itself to this project as the human's chosen proving ground, and defers the generalization judgment to orchestrator once enough evidence accumulates (`meta/adr/0047`). The first evidence is in: the gate caught a real keyboard-activation defect on the slice that introduced it. Note that a meta-layer move would also have to answer how the same invariants reach `reservation-frontend`, whose stack (Playwright/TypeScript) differs from this project's (Playwright/Python), and that `meta/tools/**` is locked by `meta/adr/0046` so a shared harness there needs a human unlock.

## Approval state

`product-brief.md` is human-approved (2026-07-31 chat); its no-history/no-durable-identifier amendment was approved in chat on 2026-08-03, and its dinner-budget revision became durable through merged PR #88. The candidate-search interaction revision, ADR-0005, API v0.4, and the Codex-authored design receiver became durable through merged PR #66. ADR-0006 and the authentication contracts became durable through merged PR #67 under ADR-0035 approval mode (i), and the verified authentication implementation through merged PR #71. ADR-0008, the candidate-search contract amendment, the browser interface, and the amended acceptance-only test-support contract became durable through merged PR #76. `TDR-CS` itself, ADR-0009, ADR-0010, ADR-0011, and `candidate-search-browser-interface.yaml` v0.2 became durable through merged PR #82. ADR-0012, ADR-0013, `candidate-search-browser-interface.yaml` v0.3, and `authentication-browser-interface.yaml` v0.2 became durable through merged PR #84, together with the candidate-card refinement. ADR-0014 and the `.env.local` loader became durable through merged PR #87. ADR-0015, ADR-0016, ADR-0017, ADR-0019, API v0.9.0, browser interface v0.7, test-support v0.7.0, and the amended `candidate-search.feature` became durable through merged PR #88. The filter model's four contracts (`candidate-search-api.yaml` v1.0.2, the browser interface, `test-support-api.yaml` v1.0.2, and the amended `candidate-search.feature`), ADR-0021, ADR-0022, and the ADR-0020/FR-013 renumbering became durable through merged PR #90, together with the implementation, the deployment preparation, and the `/healthz` readiness fix.

ADR-0023, the amended `product-brief.md`, and the ADR-0021/ADR-0022 approval records became durable through merged PR #91 and PR #92. ADR-0023 chose ADR-0035 mode (ii) and withheld its own approval until the human re-approved the already-approved statements it contradicts — chiefly `product-brief.md`'s "初期のコンセプト生成と順位付けは、説明可能な決定的ルールで行う" and the concept model the brief was built on. Those statements were still unamended when PR #90 merged the implementation, so an approved document contradicted the shipped product for a real interval. The brief now describes the filter model and states plainly that randomized selection loosens the original deterministic-only promise, and bounds what was loosened: filtering and ordering stay deterministic, and only the draw from the pool is random.

Closing those records took two follow-up pull requests rather than one, both avoidable. `record-update-needs-second-pr` has now occurred seven times repository-wide; FR-008 named the fifth as the point to prefer a mechanism over a convention, and FR-016 and FR-017 are the sixth and seventh. FR-017's proposed check — govlint failing an ADR whose body declares "approved by merging this PR" while its frontmatter still says `提案中` — remains unimplemented because `meta/tools/**` is locked by `meta/adr/0046` and unlocking needs a human commit.

Human resolution on 2026-08-01 approved L4 browser verification for `TDR-AUTH-01` through `TDR-AUTH-05` and `TDR-AUTH-07`, L3 verification for `TDR-AUTH-06`, and deferral of HTTPS transport verification to deployment.

PR #88 merged without the independent reviewer audit that `meta/agents.md` §4 step 7 calls for on `tests/acceptance/**` changes. Orchestrator raised this twice before the merge and received no instruction to run it; the human merged, which under `meta/adr/0035` mode (i) is the approval act. Recorded here so the gap is visible rather than inferred.

**同じことが PR #156 でも起きた（2026-08-24）。** `tests/acceptance/**` を変更しているが reviewer の独立監査を実施していない。orchestrator はPR本文に「未実施。承認前に必要なら実施します」と明記し、人間はそのままマージした——`meta/adr/0035` 方式(i) では**マージが承認行為**なので、これは規程違反ではなく人間の判断である。**2回目なので形として記録する**: 監査を回すかどうかが毎回 orchestrator の申告と人間の裁量に委ねられており、機械的な関所は無い（PRテンプレのチェック欄は自己申告）。

**Convention for this file (FR-008):** do not describe the approval status of an in-flight pull request here. The pull request, the ADR frontmatter, and git already own that fact, and duplicating it guarantees this file becomes false the moment the merge happens (P-04). Describe what exists; let the approval record live where the approval act is.
