# 監査レポート: TDR-CS「幹事がランチ候補を見て別の切り口で比べ直す」（TDR-CS-00〜08）

- 作成: reviewer
- 監査対象（working tree、未コミット差分）:
  - `tests/acceptance/test_candidate_search_acceptance.py`（新規、無変更）
  - `tests/acceptance/steps/candidate_search_steps.py`（新規、無変更）
  - `tests/acceptance/dsl/candidate_search_browser.py`（新規、**本レポート改訂で再監査**）
  - `tests/acceptance/dsl/js_browser_mechanics.py`（新規、**本レポート改訂で再監査**）
  - `tests/acceptance/dsl/browser_mechanics.py`（新規。`authentication_browser.py`から汎用のHTTP/HTMLパース機構を抽出しただけで、TDR-AUTH固有の業務ロジックは変更されていない）
  - `tests/acceptance/dsl/authentication_browser.py`（変更。同上の抽出に伴う委譲のみ。無変更）
  - `tests/acceptance/dsl/openapi_schema.py`（変更。`nullable: true`のJSON Schema変換と`$ref`解決の修正。無変更）
- 突き合わせた契約: `contracts/candidate-search.feature`（TDR-CS-00〜08）、`contracts/candidate-search-browser-interface.yaml`、`contracts/candidate-search-api.yaml`、`contracts/test-support-api.yaml`
- 注意: 本レポートはtesterの意図説明・コード中のコメント・docstring・コミットメッセージを判断材料にせず、コードの動作のみから作成した（`meta/agents.md` §3、`PRINCIPLES.md` P-01/P-07）。実装コード（`src/dining_radar/**`）は読んでいない
- **改訂版**: 本レポートは前回提出版（`assert_no_duplicate_shops`・`assert_no_secondary_conditions_or_manual_sort`・`request_unsupported_lens_directly`の変更前に対する監査）を差し替える。差し替え理由は`candidate_search_browser.py`・`js_browser_mechanics.py`の2ファイルが変更されたためで、変更後のコードを独立に読み直して全項目を再判定した。前回指摘した3点の決着状況は4節に記録した
- 前回監査からの継続事項: 本プロジェクトの`reviews/`ディレクトリは本レポートが初出であり、TDR-AUTHについても本リポジトリ内に独立監査の記録は見当たらない。TDR-AUTHの業務ロジック自体は本スライスの差分に含まれないため引き続き監査対象外とする

---

## 0. 承認者向けサマリ（人間はまずここだけ読む）

**結論**: 前回指摘した3点（TDR-CS-07・TDR-CS-01の重複店舗検証・TDR-CS-01/04の補助条件不在検証）はいずれも**解消を確認した**。新たな差し戻しレベルの不一致は検出されなかった。

**平易版対訳表**（1シナリオ1行、業務の言葉のみ）

| シナリオ | テストが実際にやること | 一致 |
|---|---|---|
| TDR-CS-00 サインインしていない訪問者には候補提案を見せない | サインインせずに画面を開き、サインインフォームだけが出て候補面・地図・再提案・補助条件が一切出ないこと、非公開情報が漏れていないことを確かめる | ✅（無変更） |
| TDR-CS-01 サインイン後に初期のランチ候補と位置関係をすぐ比較する | サインインし、候補が出せる状態にしてから画面を開く。初期候補・地図・出典・切り口の理由が最初から出ており、補助条件やコンセプト選択を求められず、店舗の実質的な重複（`data-provider-page-href`基準）がなく、非公開情報が漏れていないことを確かめる | ✅（2点とも解消。4節参照） |
| TDR-CS-02 選んだコンセプトの店舗を地図とカードで比較する | 候補が出ている状態でカード⇔マーカーの相互強調、地図の表示範囲・出典、カードの必須8項目、禁止された地図要素の不在を確かめる | ✅（無変更） |
| TDR-CS-03 次のページを足さずポップアップで別の切り口を選んで再提案する | 再提案ポップアップを開き、選択肢が3つ以下・現在の切り口を含まないことを確認、切り口を選んで送信し、新しい候補で画面が完全に置き換わり、新規候補が既出候補より前に並び、既出候補が除外されないことを確かめる | ✅（無変更） |
| TDR-CS-04 補助条件なしで切り口による比較を保つ | 画面上のあらゆるフォーム系コントロールが許可された目的のいずれかを宣言していること（＝補助条件・並び替え用コントロールが存在しないこと）、コンセプト選択は再提案からしかできないことを確かめる | ✅（解消。4節参照） |
| TDR-CS-05 条件に合うランチ候補がない | 「候補なし」状態にしてから画面を開き、専用の空表示が出て候補カード・地図・エラー表示のいずれも出ないこと、APIが200＋`proposal: null`であることを確かめる | ✅（無変更） |
| TDR-CS-06 候補情報を取得できない | 「取得不能」状態にしてから画面を開き、安全な案内文が出て候補カード・地図が出ないこと、非公開情報が漏れていないこと、APIが503＋規定コードであることを確かめる | ✅（無変更） |
| TDR-CS-07 対応していない再提案の切り口を選んだ | 再提案ポップアップを開いて実際に提示されている切り口を1つクリックし送信するが、送信直前にPlaywrightのネットワークインターセプトで送信本文だけを`AMENITY_REFERENCE`へ差し替える。応答が400＋規定コード・非空メッセージ・非公開情報の非漏洩であることに加え、**画面上に`candidate-proposal-problem`とその案内文が実際に表示されること**を確かめる | ✅（解消。4節参照） |
| TDR-CS-08 短時間に提案を繰り返し依頼した | 「レート制限中」状態にしてから画面を開き、安全な案内文が出て候補カード・地図が出ないこと、非公開情報が漏れていないこと、APIが429＋`Retry-After`ヘッダーであることを確かめる | ✅（無変更） |

**要確認の注記**（非ブロッキング。詳細は4節）:
1. TDR-CS-07の新実装は、実際にクリック可能な（除外対象ではない）切り口を1つ選んでUIから送信させつつ、送信直前にネットワークレベルで本文だけを`AMENITY_REFERENCE`へ差し替えている。この「UI操作で送信は行うが送信内容だけをすり替える」という手法が、シナリオの「幹事が現在提示されていない切り口を選んでいる」という業務文の忠実な翻訳かどうかは、`data-reproposal-kind`の選択操作自体は実在の切り口に対して行われている以上、額面通りの「選ぶ」動作ではない。ただし契約`requestUnavailableEnumLens`が「UIの選択肢を要さない決定的観測」と明記した専用seamの実行モデルとしては妥当な実装であり、応答は実サーバから返る本物であることを確認した
2. TDR-CS-01/04の新しいフォームコントロール走査（`FORM_CONTROL_SELECTOR`）は、契約`forbiddenFormControlCategories`の11カテゴリをHTMLタグ名とARIAロールの組み合わせで機械的に再現しているが、`[role='button']`（ARIAロールのみで実装されたボタン相当ウィジェット）は走査対象に含まれていない。ネイティブ`<button>`タグは含まれる
3. `js_browser_mechanics.py`の`csrf_token`関数は、今回の`request_unsupported_lens_directly`書き換えに伴い呼び出し元がなくなり、未使用のまま残っている（`build_captured_response`は`capture_candidate_proposal_response`から引き続き使われている）

---
以下は監査の証跡。承認者は原則サマリだけで判断できる。疑わしい行があれば該当の詳細に潜る。

## 1. 対訳表（詳細）

TDR-CS-00・02・03・05・06・08は前回監査から対象コードに変更がないため、前回の対訳表をそのまま維持する（1-A節）。TDR-CS-01・04・07は変更されたメソッドに関わる行を再監査した（1-B節）。

### 1-A. 変更なしのシナリオ（前回監査を維持）

`git diff`および目視比較により、これらのシナリオが依存する`assert_visitor_guided_to_sign_in_without_candidate_surface`・`assert_initial_proposal_screen`・`assert_initial_concept_has_rationale`・`assert_provider_credit`・`assert_cards_and_map_show_current_concept`・`assert_required_card_fields_match_current_proposal`・`assert_map_attribution_and_fit`・`assert_map_has_no_forbidden_surfaces`・`select_first_card_and_verify_marker_highlighted`・`select_first_marker_and_verify_card_highlighted`・`open_reproposal_popup`・`assert_reproposal_options_bounded_and_exclude_current`・`select_and_submit_first_offered_lens`・`assert_display_replaced_by_reproposal`・`assert_repeat_priority_orders_new_before_repeated`・`assert_repeated_candidate_not_excluded`・`assert_no_results_shown`・`assert_no_results_from_captured_api`・`assert_screen_has_no_private_disclosures`・`assert_safe_unavailable_guidance`・`assert_captured_problem_matches_schema`、および`js_browser_mechanics.py`の`is_candidate_proposal_response`・`CapturedApiResponse`・`build_captured_response`・`capture_candidate_proposal_response`・`by_test_id`・`wait_for_at_least_one`・`assert_present`・`assert_absent`・`assert_all_present`・`assert_all_absent`・`require`は、前回監査時点から1バイトも変わっていないことを確認した。したがってTDR-CS-00・02・03・05・06・08の対訳表・判定（いずれも✅、差し戻しレベルの不一致なし）は前回提出時のまま有効である。詳細な行単位の対訳は前回版と同一のため、ここでは結果のみを再掲する。

| シナリオ | 前回の判定 | 本改訂での再確認 |
|---|---|---|
| TDR-CS-00 | ✅ 不一致なし | 対象コード無変更。再確認結果も✅ |
| TDR-CS-02 | ✅ 不一致なし | 対象コード無変更。再確認結果も✅ |
| TDR-CS-03 | ✅ 不一致なし | 対象コード無変更。再確認結果も✅ |
| TDR-CS-05 | ✅ 不一致なし | 対象コード無変更。再確認結果も✅ |
| TDR-CS-06 | ✅ 不一致なし | 対象コード無変更。再確認結果も✅ |
| TDR-CS-08 | ✅ 不一致なし | 対象コード無変更。再確認結果も✅ |

### 1-B. 変更されたシナリオの再監査

#### TDR-CS-01: サインイン後に初期のランチ候補と位置関係をすぐ比較する

| # | シナリオ文 | steps → dsl | 変更後のコードが実際に行うこと | 一致 |
|---|---|---|---|---|
| 01-4 | Then 初期表示で幹事に補助条件またはコンセプトの選択を求めない | `initial_display_requests_no_secondary_input` → `assert_no_secondary_conditions_or_manual_sort` | `[candidate-secondary-conditions, candidate-manual-ordering]`の不在を確認した上で、画面上の`select, input（type=hiddenを除く）, textarea, button`要素、および`[role=checkbox/radio/range/combobox/listbox/slider/spinbutton]`要素を**全件**列挙し、各要素の`data-candidate-control-purpose`属性が`{candidate-card-selection, candidate-map-marker-selection, reproposal-open, reproposal-selection, reproposal-submit, reproposal-cancel, auth-sign-out, auth-password-change-open}`（契約の`allowedPurposes`と同一の8値）のいずれかであることを確認する。属性が無い（`None`）要素や許可リスト外の値を持つ要素があれば失敗する | ✅（前回の「属性を既に宣言している要素だけを見る」という部分一致は解消。契約の`allCandidateScreenFormControlsMustDeclarePurpose: true`をほぼ機械的に再現している。ただし`[role='button']`は走査対象に含まれない——0節・4節参照） |
| 01-6 | And 初期の候補に同じ店舗は重複して示されない | `initial_candidates_have_no_duplicate_shop` → `assert_no_duplicate_shops` | 各カードの`data-provider-page-href`属性（契約`cardDataAttributes.repeatComparisonHref`、返却値`providerPageUrl`と一致することが別途02-6で検証済みの属性）を集め、(1)カードが1件以上存在すること、(2)全カードがこの属性を持つこと、(3)その値の一覧に重複がないことを確認する | ✅（前回の「opaqueな`candidateRef`の一意性」から、契約が定める店舗識別用の実URL属性に基づく判定へ変更され、業務上の「同じ店舗」概念に沿った検証になった） |
| その他（01-1〜01-3, 01-5, 01-7, 01-8） | — | 対象コード無変更 | ✅（前回判定を維持） |

#### TDR-CS-04: 補助条件なしで切り口による比較を保つ

| # | シナリオ文 | steps → dsl | 変更後のコードが実際に行うこと | 一致 |
|---|---|---|---|---|
| 04-3 | Then 幹事は検索範囲の希望またはジャンルを入力・選択しない | `initial_display_requests_no_secondary_input` → `assert_no_secondary_conditions_or_manual_sort` | 01-4と同一 | ✅（解消） |
| 04-5 | And 幹事は並び順を手動で指定できない | 同上の呼び出し（`candidate-manual-ordering`の不在＋全フォームコントロールが許可目的のいずれかを宣言していることの確認に`manual-ordering`という許可目的が含まれていないことも内包） | 同上 | ✅（解消） |
| その他（04-1, 04-2, 04-4） | — | 対象コード無変更 | ✅（前回判定を維持） |

#### TDR-CS-07: 対応していない再提案の切り口を選んだ

| # | シナリオ文 | steps → dsl | 変更後のコードが実際に行うこと | 一致 |
|---|---|---|---|---|
| 07-1/07-2 | Given 幹事が現在提示されていない切り口を選んでいる／When 幹事が再提案を依頼する | `organizer_requests_an_unsupported_lens_directly("AMENITY_REFERENCE")` → `request_unsupported_lens_directly` | 再提案ポップアップを開き（`candidate-reproposal-dialog`が現れることを内部的に確認済み）、実際に提示されている選択肢の先頭（`AMENITY_REFERENCE`以外の、現に提示されている切り口）をクリックし、送信ボタンをクリックする。ただし送信ボタンのクリックより前に、次に発生する`POST /candidate-proposals`リクエストを1回だけPlaywrightのネットワークルートで横取りするよう登録しておき、実際にリクエストが発火した瞬間にその送信本文だけを`{"reproposalKind": "AMENITY_REFERENCE"}`に書き換えてからサーバへ転送する。レスポンスはこの横取り済みリクエストに対する実サーバの応答であり、ページの実際のfetch呼び出しがこれを受け取るため、アプリのクライアントJSがこの応答を通常通り処理する | ⚠️ 要確認（0節1参照。「選ぶ」という語の額面通りの動作ではなく、UI操作は実在の切り口に対して行い送信本文だけを差し替える手法。ただし契約`requestUnavailableEnumLens`が定める専用seamの意図——UIに存在しない選択肢を決定的に発生させる——には合致する） |
| 07-3 | Then その切り口では提案できないことが示される | `unsupported_lens_is_rejected` → `assert_direct_problem_matches_schema` | 捕捉した応答について`status`が400、`ProblemResponse`スキーマ適合、`code`一致、`message`非空、canary非混入を確認する。**それに加えて**、画面上の`candidate-proposal-problem`要素が存在し`data-problem-code`属性が期待コードと一致すること、`candidate-proposal-problem-guidance`要素のテキストが非空であることを確認する | ✅（前回の「API応答のみで画面表示を検証しない」という不一致は解消。契約`requiredOutcome.present`が要求するDOM出現が実際に検証されるようになった） |
| 07-4 | And 非公開の検索地点や探索条件の詳細は示されない | 07-3と同じ呼び出しに内包（`_assert_no_disclosures()`が末尾で呼ばれる） | HTML全文にcanary文字列が含まれないこと、`[private-search-origin, candidate-provider-internals, candidate-origin-marker, candidate-route, candidate-current-location]`が画面上に存在しないことを確認する（API応答本文のcanary非混入は`_assert_problem_response`側で別途確認） | ✅（前回はAPI応答のみだったが、DOM側の非漏洩確認が追加された） |

## 2. レビューチェックリスト（`meta/verification.md` L4詳細(3)）

| 観点 | 前回 | 今回 | 指摘 |
|---|---|---|---|
| ① 過不足 | 一部NG（TDR-CS-07） | **OK** | TDR-CS-07のThenが画面表示を検証するようになり、過小検証は解消した。それ以外の32個のThen節は引き続き文が指示する検証のみを行っている |
| ② Givenの正当性 | OK | OK | TDR-CS-07の新しいGiven実装（UI操作＋ネットワークレベルの本文差し替え）は業務APIの実装をなぞるものではなく、契約が明示する専用seam（`requestUnavailableEnumLens`）の意図を実現する手段として妥当と判断した。それ以外は前回同様、Given専用seamまたは公開境界のみを使用している |
| ③ Thenの検証対象 | 一部NG（TDR-CS-07） | **OK** | TDR-CS-07が画面上のDOM状態（業務上の観測可能な結果）を検証するようになった。TDR-CS-01の重複店舗検証も、opaqueなUI識別子ではなく契約が定める店舗識別属性（`data-provider-page-href`）を対象にするようになり、業務上の「同じ店舗」概念により忠実になった |
| ④ 失敗の握りつぶし | OK | OK | 新規追加された`capture_candidate_proposal_response_with_overridden_body`・`_is_candidate_proposal_path`にも`try`/`except`・`sleep`・緩い比較は見当たらない。ルートハンドラ（`route.continue_`）は横取りしたリクエストを必ず転送しており、握りつぶし・打ち切りは無い |
| ⑤ 暗黙の前提 | 一部要確認（TDR-CS-01/04） | **ほぼ解消（残1件）** | `FORM_CONTROL_SELECTOR`が契約の`forbiddenFormControlCategories`11種を网羅的に再現しているが、`[role='button']`（ARIAロールのみのボタン相当ウィジェット）が対象から漏れている——契約は`button`をネイティブ`<button>`タグに限定する趣旨なのか、ARIAロールも含む趣旨なのか契約文面だけでは判定できないため、これを暗黙の前提として4節に記録した |

## 3. 契約↔テスト対応の監査

- **step未実装の承認済みシナリオ**: なし。`python manage.py test tests.acceptance`を再実機実行し、`Ran 15 tests ... OK`（skip 0、fail 0、error 0）を確認した
- **シナリオに対応しない孤児step**: なし（前回と同様、`candidate_search_steps.py`の全メソッドが呼ばれている構造に変更はない）
- **同義stepの重複疑い**: なし（前回と同様の判断。Cucumber方式のグローバルstep解決を持たない構成であるため構造的に発生しない）
- **未使用コードの検出（新規）**: `js_browser_mechanics.py`の`csrf_token`関数が、`candidate_search_browser.py`から呼び出されなくなり未使用になっている（コメント内の参照のみ残存）。テストの正しさには影響しないが、死んだコードとして記録する
- **govlint(L0)確認**: `python meta/tools/govlint.py`を再実行し、`govlint: エラーなし`を確認した（dining-radar該当分なし）
- **L4実機実行**: `python manage.py test tests.acceptance`を実行し、`Ran 15 tests in 230.796s` / `OK`（TDR-AUTH 6件・TDR-CS 9件、skip 0・fail 0・error 0、`test_tdr_cs_07`を含め全件pass）を確認した。orchestratorの申告（L0〜L4全緑、L4 15件skipゼロ）と一致することを独立に確認した

## 4. 前回指摘3点の決着状況

1. **TDR-CS-07（差し戻し候補）→ 解消**。`request_unsupported_lens_directly`は、実際にクリック可能な選択肢に対してUI操作（開く・選ぶ・送信）を行いつつ、Playwrightのネットワークルート機能で送信直前に本文だけを`AMENITY_REFERENCE`へ差し替える方式に変更された。これにより応答はアプリの実際のfetch呼び出しが受け取り、クライアントJSの通常の応答処理経路を通ってDOMが更新される。`assert_direct_problem_matches_schema`が画面上の`candidate-proposal-problem`・`candidate-proposal-problem-guidance`の出現とその内容を新たに検証しており、契約`requiredOutcome.present`とシナリオの「示される」の両方を満たす。**残る軽微な要確認事項**: この手法は「幹事が切り口を選ぶ」という語を額面通りに再現しているのではなく、UI操作と送信内容を意図的に分離した専用の観測手段である。契約が意図した実行モデルとしては妥当と判断したが、この解釈自体の妥当性は人間が最終確認することを推奨する（0節1参照）
2. **TDR-CS-01の重複店舗検証 → 解消**。`assert_no_duplicate_shops`は`candidateRef`（opaqueなUI識別子）ではなく`data-provider-page-href`（契約が定める店舗識別用の実URL属性）の一意性を検証するようになった。業務上の「同じ店舗」概念に沿った検証になっており、以前指摘した「常に真になり得る検証」という懸念は解消した
3. **TDR-CS-01/04の補助条件不在検証 → ほぼ解消**。`assert_no_secondary_conditions_or_manual_sort`は、`data-candidate-control-purpose`を既に宣言している要素だけでなく、契約が列挙する11カテゴリに相当するHTML要素・ARIAロールを持つ要素を全件列挙し、各要素が許可された8つの目的のいずれかを宣言していることを検証するようになった。契約の`allCandidateScreenFormControlsMustDeclarePurpose: true`をほぼ機械的に再現している。**残る軽微な指摘**: `[role='button']`（ARIAロールのみで実装されたボタン相当ウィジェット）は走査対象に含まれておらず、契約の`button`カテゴリがネイティブ`<button>`タグに限定される趣旨か、ARIAロールも含む趣旨か契約文面だけでは判定できない。ブロッキングとは判断しないが、次にこの語彙を扱う際に確認することを推奨する

## 5. 検証の申告（`meta/adr/0039`）

- **L0（govlint）**: 実機実行。`python meta/tools/govlint.py` → エラー0件（dining-radar関連のREPORTなし）
- **L4（受け入れシナリオ実行）**: 実機実行。`python manage.py test tests.acceptance` → `Ran 15 tests in 230.796s`、`OK`（TDR-AUTH 6件・TDR-CS 9件、skip 0・fail 0・error 0）。orchestratorの事前申告（L0〜L4全緑、L1単体107件・branch coverage 95%・mutation 162/162=100%・L2 7件・L3 67件・L4 15件skipゼロ）と一致することを独立に確認した
- **波及確認**: `js_browser_mechanics.py`の共有プリミティブのうち、TDR-CS-00/02/03/05/06/08が依存する関数（`is_candidate_proposal_response`・`CapturedApiResponse`・`build_captured_response`・`capture_candidate_proposal_response`・`by_test_id`・`wait_for_at_least_one`・`assert_present`・`assert_absent`・`assert_all_present`・`assert_all_absent`・`require`）が前回監査時点から1バイトも変わっていないことを目視で確認した。変更は`capture_candidate_proposal_response_with_overridden_body`・`_is_candidate_proposal_path`の追加と`Route`のimport追加のみであり、これらはTDR-CS-07の`request_unsupported_lens_directly`からのみ呼ばれる。したがってTDR-CS-00/02/03/05/06/08への波及はないと判断した（L4の実機再実行結果もこれを裏付ける）
- **L1〜L3**: 実行していない。developerの領分であり、activeContext.md／orchestrator申告に基づく。reviewerの職務範囲はL4のstep/DSL監査であるため、L1〜L3を独自に再実行してその数値を検証してはいない——「検証していない」ことをここに明記する
- **govlintの契約承認チェック**: 本スライスは契約ファイル自体を変更していない（working tree上でも無変更）ため、govlintのADR-0043検査の対象外である

## 6. 結論

- [x] 承認材料が揃った（人間の突き合わせ待ち）
- [ ] testerへの差し戻し（不一致あり）
- [ ] シナリオ側/契約側の欠陥疑い → 矛盾分析レポートを提出済み

前回提出版で指摘した3点（TDR-CS-07の差し戻し候補、TDR-CS-01の重複店舗検証、TDR-CS-01/04の補助条件不在検証）はいずれも解消を確認した。TDR-CS-00〜08の9シナリオすべてで、対訳表・チェックリストともに差し戻しレベルの不一致は検出されなかった。残るのは2件の非ブロッキングな要確認事項（TDR-CS-07の「UI操作と送信内容の分離」という手法の解釈、`FORM_CONTROL_SELECTOR`が`[role='button']`を含まない点）のみであり、いずれも人間の最終確認を推奨するが承認を妨げるものではないと判断する。L0・L4は実機実行で緑を独立に再確認済み(5節)。TDR-CS-00/02/03/05/06/08が依存する共有プリミティブへの波及がないことも確認済み。
