# 監査レポート: モバイル・スワイプ送り (adr/0033) acceptance 差分レビュー

- 担当: reviewer
- 監査対象: `feat/mobile-map-primary-swipe`（HEAD `a22cc6a`、作業ツリー `E:/AWS/run2`）の
  `tests/acceptance/**` 差分（`git diff origin/main...HEAD`）
  - `tests/acceptance/dsl/candidate_search_browser.py`（renderModes定数の全面書き換え＋
    タッチスワイプ関連メソッド新設）
  - `tests/acceptance/steps/candidate_search_steps.py`（新設: step 8件）
  - `tests/acceptance/test_candidate_search_acceptance.py`（新設:
    `test_tdr_cs_02_mobile_deck_navigation_swipes_candidates_without_changing_them`）
- 照合元: `contracts/candidate-search-browser-interface.yaml`（v1.6.0。`renderModes`、
  `deckNavigation.swipeSurface`/`position`、`browserActions.pageDeckSwipeForward`/
  `pageDeckSwipeBackward`、`selectMarker.deckVisibility`の一般化）、`candidate-search.feature`
  （無変更 — `スワイプ`/`swipe`0件、確認済み）、`adr/0033`（承認済み）、`meta/adr/0065`
  （欠陥注入の規程。本レポートは静的読解のみで判定し、実際の欠陥注入は行っていない——
  前回の`audit-desktop-deck-navigation.md`と同じ限界）
- 参考（developer管轄、監査対象ではない）: `tests/ui_invariants/test_render_invariants.py`、
  `tests/test_static_assets.py` — L5側がadr/0032決定6（narrow-widthの期待値を
  `mapPrimaryTouchLayout`へ差し替え）を正しく反映していることを確認する目的でのみ参照した
- 独立性: testerのdocstring・コミットメッセージは判断材料にせず、DSL/stepのコードを自分で
  追跡して判定した。実行はしていない（静的読解のみ）

## 結論

**新規ブロッカーは無い。** v1.6.0が新設・変更したMustは、対訳表のとおりstep/DSLと1対1で
対応しており、契約が要求しない事項の追加検査も見当たらない。依頼文が特に警戒した3点——
(1) `boundaryOvershoot`の検査の空振り、(2) スワイプ方向の実験的発見が失敗したときに検査が
素通りする、(3) `listPrimaryLayout`退役に伴うPC側検査の弱体化——は、いずれも該当しなかった。
「構造上ぜったいに失敗しない検査」も見当たらない。前回のG2（`unaffected.pendingFilters`未検査）は
**タッチ側では解消済み**（新設の6項目すべてが実際に前後比較される）。一方、軽微な指摘が1件ある
（H1: 死んだstep 2件）。

## 対訳表

| # | 契約のMust (v1.6.0) | 呼び出されるstep | DSLが実際にすること | 判定 |
|---|---|---|---|---|
| `renderModes`（`listPrimaryLayout`退役・`mapPrimaryTouchLayout`新設、決定1） | いま名前を持つ2モードは`mapPrimaryLayout`（ボタン）と`mapPrimaryTouchLayout`（スワイプ面）のみで、互いに排他 | `render_mode_test_ids_are_mutually_exclusive` → `assert_render_mode_test_ids_are_mutually_exclusive` | `MAP_PRIMARY_LAYOUT_TEST_IDS`（`[DECK_PREVIOUS, DECK_NEXT]`）と`MAP_PRIMARY_TOUCH_LAYOUT_TEST_IDS`（`[DECK_SWIPE_SURFACE]`）それぞれのDOM存在を独立に読み、排他性を検証。旧`LIST_PRIMARY_TEST_IDS`/`MAP_OPEN`/`MAP_SHEET_CLOSE`はコード中に一切残っていない（`grep`で0件確認済み）——退役を機械的にも反映 | 対応 |
| `deckNavigation.description`（両モードいずれでも成立）＋`swipeSurface.presenceRule`（`mapPrimaryTouchLayout`専有で存在・`mapPrimaryLayout`では不在） | このスライスのタッチ側デッキ検査は`mapPrimaryTouchLayout`成立が前提 | `map_primary_touch_layout_holds` → `assert_map_primary_touch_layout_holds` | `DECK_SWIPE_SURFACE`と`DECK_POSITION`の存在、`MAP_PRIMARY_LAYOUT_TEST_IDS`（ボタン側）の不在を確認 | 対応 |
| `deckNavigation.position.presenceRule`（決定2: `candidate-deck-position`はどちらのモードにも共通） | 件数カウンタはどちらのモードでもテスト対象 | `assert_map_primary_layout_holds`/`assert_map_primary_touch_layout_holds`双方が`DECK_POSITION`を明示的に別枠で`present`側へ追加（`MAP_PRIMARY_*_TEST_IDS`配列自体からは意図的に除外） | 対応。契約の決定2（「共通要素は排他性配列のメンバーではない」）をコード側の配列構造にも正確に反映している |
| `browserActions.pageDeckSwipeForward/Backward.gesture`（方向を固定しない） | 実装が選んだ「forward」方向を、契約が固定しない前提で扱う | `_forward_swipe_direction` | 初期状態（`start==1 かつ total>1`）でのみ動作を許可し、そうでなければ`AssertionError`で明示的に停止（黙って推測しない）。leftward/rightwardの順に試し、`after_start > start`で前進を検知したら確定。前進しなかった場合は「窓が完全不変」であることを明示的に検証してから次の方向を試す——「境界での正しい無反応」と「操作が届いていない」を区別する設計になっている。**両方向とも前進しなかった場合は`AssertionError`で明示的に失敗させ、無言で素通りしない** | 対応。依頼文の懸念3に直接応える設計 |
| `browserActions.pageDeckSwipeForward.requiredOutcome.visibleWindow` | 前方向のスワイプで窓が単調に前進 | `organizer_swipes_the_deck_forward_until_it_reaches_the_end`（内部で`page_deck_swipe_forward_and_verify_window_advances`を反復） | 呼び出し前に`assertLess(end_before, total, ...)`ガード。前後で`_deck_window()`を再取得し`start_after > start_before`等を検証 | 対応 |
| `browserActions.pageDeckSwipeBackward.requiredOutcome.visibleWindow` | 後方向のスワイプで窓が単調に後退 | `organizer_swipes_the_deck_backward_until_it_reaches_the_start` | 同上（backward版）。forward方向が未確定なら`require`で明示的に停止 | 対応 |
| `browserActions.pageDeckSwipeForward.boundaryOvershoot` | 末尾で追加スワイプしても窓は無変化・エラーなし・公開操作なし | `deck_swipe_forward_is_a_no_op_at_the_boundary` → `assert_deck_swipe_forward_is_a_no_op_at_the_boundary` | **正のコントロール必須のガード**: `self._swipe_forward_direction`が同一テスト内で既に確定していなければ`require`で例外を送出し検査自体を拒否する。確定済みの場合のみ、`end_before == total`を確認したうえで同方向のスワイプを送り、窓・`_display_snapshot`・`pendingFilters`が不変であることを検証 | **対応。詳細は指摘なしのG1/G2欄参照** — 空振りしない設計を確認した |
| `browserActions.pageDeckSwipeBackward.boundaryOvershoot` | 先頭で追加スワイプしても窓は無変化 | `deck_swipe_backward_is_a_no_op_at_the_boundary` → `assert_deck_swipe_backward_is_a_no_op_at_the_boundary` | 同上（backward版）。`self._swipe_backward_confirmed`という**別フラグ**で正のコントロールを要求——forward確定だけではbackwardの配線を証明しないという理由が明記されている | 対応 |
| `browserActions.pageDeckSwipeForward/Backward.requiredOutcome.unaffected`（6項目、`pendingFilters`含む） | カード集合・`data-candidate-ref`・選択状態・適用済み条件・pending条件・条件文言のいずれも変えない | 上記4メソッドすべて | `_display_snapshot`/`_assert_display_snapshot`で5項目（`card_refs`/`marker_refs`/`card_selection_states`/`marker_selection_states`/`condition_summary`/`applied_filters`）、加えて`pending_before = dict(...)`→`assertEqual(self._pending_filters, pending_before)`で6項目目を**明示的に**検証 | **対応。前回G2（PC側で欠落）はタッチ側では解消済み** |
| `browserActions.pageDeckSwipeForward/Backward.requiredOutcome.publicOperation: none` | 公開APIを一切叩かない | 上記4メソッド | 全て`_perform_without_candidate_request`でラップ、候補提案リクエストが0件であることを確認 | 対応 |
| `browserActions.pageDeckSwipeForward/Backward.verificationAllocation.L4`（合成ジェスチャの限界を明記） | 合成ジェスチャが人間の指の到達可能性を証明しないことをG1拡張として明記 | `_dispatch_deck_swipe`のdocstring、テストメソッドのdocstring | いずれも「実機で人間の指がこの範囲を実際につまんでスワイプできることまでは証明しない」「G1と同種、ドラッグ操作へ初めて広げた限界」を明記。証明していないことを証明したかのようには書いていない | 対応（依頼文の懸念6に該当なし） |
| `selectMarker.deckVisibility`（決定5: `mapPrimaryLayout`専有から両モード適用へ一般化） | ピン選択でウィンドウ外のカードが窓に入ることを、両モードで検査する | `selecting_a_marker_outside_the_deck_window_brings_its_card_into_view`（デスクトップテストと**共有**、モバイルテストの末尾でも呼ばれる） | 既存メソッドをそのまま再利用。`MOBILE_MAP_PRIMARY_TOUCH_VIEWPORT`下で実行されるため、決定5が要求する「両モードで成立」の一般化を実際に運動させている | 対応。新規コード不要で契約の要求を満たしている |
| `deckNavigation.disabledState`（タッチ側は非該当） | `mapPrimaryTouchLayout`にはネイティブdisabled状態が無い | （該当なし） | タッチ側に`disabledState`相当の検査は存在しない | 対応（契約が要求していないので検査しないのが正しい——過剰検査ではない） |

## 指摘

### H1 — 死んだstep（未使用）が2件（Low）

`steps/candidate_search_steps.py`が新設した`organizer_swipes_the_deck_forward`/
`organizer_swipes_the_deck_backward`（単発スワイプ、`_until_`ループを介さない版）は、
`test_candidate_search_acceptance.py`の新設テストからも既存テストからも一度も呼ばれていない
（`grep`で確認済み。呼ばれているのは`organizer_swipes_the_deck_forward_until_it_reaches_the_end`/
`_backward_until_the_window_reaches_the_start`のみ）。対応するDSLメソッド
（`page_deck_swipe_forward_and_verify_window_advances`/`_backward_and_verify_window_recedes`）
自体は`_until_`ループの内部から間接的に呼ばれているため死んでいないが、**それを直接公開する
このstep 2件だけが孤立している**。

デスクトップ側（`organizer_pages_the_deck_forward`/`_backward`、adr/0031）は単発版が
`test_tdr_cs_02_desktop_deck_navigation_...`から直接呼ばれており対称性が取れているのに対し、
モバイル側は単発版のstepを作った上で使っていない。ブロッカーではない（DSLメソッド自体は
実質的に検査されており、機能欠落ではない）が、次にこの領域を触る際、使うか消すかを判断すべき
未使用コードとして記録する。

## L4 5観点チェックリスト

| 観点 | 判定 | 根拠 |
|---|---|---|
| 過不足 | OK（H1は不足ではなく余剰） | v1.6.0が新設・変更したMustはすべて対応するstep/DSLを持つ。契約が要求しない検査の追加は見当たらない。H1は「使われていないstepが余分にある」であり、Mustの検査漏れではない |
| Givenの正当性 | OK | 新設stepは既存の`lunch_candidates_can_be_proposed_at_a_known_search_origin`・`open_candidate_screen`系を再利用するのみで、新しいGiven seamは追加していない |
| Thenの検証対象 | OK | `boundaryOvershoot`・方向発見・`unaffected`のいずれも、契約が指す検証対象（属性値・前後比較・公開APIリクエスト有無）を正しく検査しており、恒真化や空振りは見当たらなかった |
| 失敗の握りつぶし | OK | try/except・空catch・過度に緩い比較・sleep同期は見当たらない。`require`/`raise AssertionError`のガードは「検査不能な前提なら明示的に落とす」設計で一貫している |
| 暗黙の前提 | 要確認（H1と同一） | 「390px幅でも初期表示で複数ページある（`total>1`）」という前提のもとで方向発見が成立する（満たさなければ`AssertionError`で明示的に落ちるため、暗黙のまま素通りする形にはなっていない）。H1（未使用step）は前提というより余剰コードの記録 |

## contract ↔ test 対応・孤児監査

### 対応済み

- `renderModes`（`mapPrimaryLayout`/`mapPrimaryTouchLayout`の相互排他性、`listPrimaryLayout`の
  完全退役）、`deckNavigation.swipeSurface`/`position`（両モード共通化）、
  `browserActions.pageDeckSwipeForward`/`pageDeckSwipeBackward`（`visibleWindow`・
  `boundaryOvershoot`・`unaffected`6項目・`publicOperation: none`）、`selectMarker.deckVisibility`の
  一般化——いずれも対応するstep/DSLが存在し、新設テストから最低1回呼ばれていることを確認した
- `contracts/candidate-search.feature`に対応する記述が無いことも確認した（`スワイプ`/`swipe`で
  0件ヒット）——adr/0033自身がTDR-CS-02のUI実装詳細と位置づけている記述と整合する

### 孤児または不完全な契約要求

- 見当たらなかった

### 重複・死んだ受け入れ補助コード

- H1: `organizer_swipes_the_deck_forward`/`organizer_swipes_the_deck_backward`（step、2件）が
  未使用

## 前回までの指摘の現況（新規発見ではなく確認のみ）

- F1b（輪ラベルの集合比較）: 本差分は`walkingRadiusRings`に触れていない。無関係、現況変化なし
- G1（合成イベントは指の到達可能性を証明しない）: adr/0033・本差分のdocstringが正しく明記して
  おり、拡大解釈も過小申告も無い
- G2（`pendingFilters`未検査）: **タッチ側の新設4メソッドでは解消済み**。ただし依頼文どおり
  PC側（`page_deck_next_and_verify_window_advances`/`_previous_and_verify_window_recedes`、
  `assert_deck_paging_controls_disabled_state_matches_window`）は本差分でも変更されておらず、
  `pendingFilters`比較は依然として無い——`grep`で確認済み。新規指摘としては報告しない
  （依頼文が既知として明示済み）が、対訳表上は「未解消のまま」であることを記録する
- 可視ラベル要素の`data-testid`欠落: 本差分の対象範囲（スワイプ面）に該当する新規ラベル要素は
  無い。無関係

## 判定

**問題なし（ブロッカー無し）。** 軽微な指摘1件（H1、未使用step 2件、Low）を記録する。
