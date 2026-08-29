# 監査レポート: デスクトップ地図主役デッキ送り (adr/0031) acceptance 差分レビュー

- 担当: reviewer
- 監査対象: `feat/map-primary-desktop-deck`（HEAD `4d080fb`）の `tests/acceptance/**` 差分
  （`git diff origin/main...HEAD`）
  - `tests/acceptance/dsl/candidate_search_browser.py`（新設: renderModes/デッキ関連の定数・メソッド一式）
  - `tests/acceptance/steps/candidate_search_steps.py`（新設: 対応するstep 8件）
  - `tests/acceptance/test_candidate_search_acceptance.py`（新設: `test_tdr_cs_02_desktop_deck_navigation_windows_candidates_without_changing_them`）
- 照合元: `contracts/candidate-search-browser-interface.yaml`（v1.5.0。`renderModes`、
  `browserControlSurface.proposal.deckNavigation`、`browserActions.pageDeckPrevious`/
  `pageDeckNext`、`browserActions.selectMarker.deckVisibility`）、`contracts/candidate-search.feature`
  （無変更 — `デッキ`/`deck`の語は0件、確認済み。このスライスはGherkinシナリオではなく契約のUI実装詳細
  としてのみ導入されている）、`adr/0031`（承認待ち）
- 独立性: tester のdocstring・コミットメッセージは判断材料にせず、DSL/step のコードと、それが読む
  `src/dining_radar/web/static/dining_radar/web/candidate.js`（実装、監査のため読んだが変更していない）を
  自分で突き合わせて判定した

## 実行結果

今回はコードの静的読解のみで判定した（テスト自体は実行していない）。以下の結論はすべて静的な
コード追跡（DSL↔契約↔`candidate.js`の該当箇所の突合）に基づく。

## 結論

**新規ブロッカーは無い。** 依頼文が名指しした「構造上ぜったいに失敗しない検査」のパターン
（同一出どころの値どうしの比較、恒真assertion）はこの差分には見当たらなかった——これは前2回の
同型欠陥（F1: aria-labelの早期return、origin marker座標の文字列一致）とは異なる結果である。
一方、契約が明記した`unaffected`/`disabledState`の一部が**実行経路上で一度も検証されない**という、
ブロッカーではないが記録すべき指摘が2件ある（下記G1・G2）。地図ピン選択でウィンドウ外のカードを
選ぶ`deckVisibility`検査（依頼文の懸念5）は正しく設計されている——最初から窓の中にあるカードでは
なく、`end`の直後（窓の外）のカードを明示的に選んでいる。

## 対訳表

| # | 契約のMust | 呼び出されるstep | DSLが実際にすること | 判定 |
|---|---|---|---|---|
| renderModes.invariant（排他性） | 幅ごとの2モードは常にどちらか一方だけ成立する | `render_mode_test_ids_are_mutually_exclusive` → `assert_render_mode_test_ids_are_mutually_exclusive` | `LIST_PRIMARY_TEST_IDS`・`MAP_PRIMARY_TEST_IDS`それぞれの存在をDOMから直接読み、「どちらか一方のみ真」「他方の全testidが不在」を確認する。2つの属性を同一ソースから比較していない、独立したDOM存在確認 | 対応。テスト自体を実行しても常に真にならない構造 |
| deckNavigation.description（`mapPrimaryLayout`前提） | このスライスのデッキ検査はmapPrimaryLayout成立が前提 | `map_primary_layout_holds` → `assert_map_primary_layout_holds` | `MAP_PRIMARY_TEST_IDS`全存在・`LIST_PRIMARY_TEST_IDS`全不在を確認 | 対応 |
| unavailableControls.allowedPurposes（`candidate-deck-page-previous/-next`追加） | 送りボタンはそれぞれ専用の`data-candidate-control-purpose`を宣言する | `deck_paging_controls_declare_correct_purposes` → `assert_deck_paging_controls_declare_correct_purposes` | 各ボタンの`data-candidate-control-purpose`属性値を直接読み、期待値と一致させる。`ALLOWED_CONTROL_PURPOSES`集合にも2値を追加済みで、既存の全画面フォームコントロール走査（`assert_no_location_range_or_manual_order_control`）も誤検知しない | 対応 |
| deckNavigation.position.valueShape | 件数カウンタは1始まりの整数、`1<=start<=end<=total` | `deck_position_counter_is_well_formed` → `assert_deck_position_counter_is_well_formed` | 3属性を正規表現`^\d+$`で検証しつつ整数変換、大小関係を確認。`total`はさらに実際のDOM上の`candidate-card`要素数（別途`by_test_id`で数え上げ）と突き合わせる | 対応。`total`はJS内部配列長`orderedCardElements.length`（`deckTotal()`）由来だが、DOM上の実カード数とも一致することを別クエリで確認しており、二重計上・欠落系のバグは捕捉できる |
| deckNavigation.disabledState | 両端で`disabled`（不在ではなく）になる | `deck_paging_controls_disabled_state_matches_window` → `assert_deck_paging_controls_disabled_state_matches_window` | `to_be_disabled()`/`to_be_enabled()`でPlaywrightのネイティブdisabled状態を検査（`data-testid`の存在だけでなく実際のdisabled属性） | **一部未実行（G1参照）** — 「前へ」がstart=1で無効になる側は実行時に実際に踏むが、「次へ」がend=totalで無効になる側はこのスライスのシナリオでは一度も到達しない |
| deckNavigation.orderingInvariant | 送りは並び・`data-candidate-ref`集合を変えない | `organizer_pages_the_deck_forward`/`_backward` → `page_deck_next_and_verify_window_advances`/`_previous_and_verify_window_recedes` | クリック**前後**でDOMから`_card_candidate_refs()`（全カードの`data-candidate-ref`を並び順で取得）等を再取得し、`_assert_display_snapshot`で一致を確認する。同一ソースの言い直しではなく、実際に2回DOMへ問い合わせている | 対応。この検査は前後比較として正しく機能する |
| browserActions.pageDeckNext/Previous.requiredOutcome.visibleWindow | start/endの単調性・境界 | 同上 | `assertGreater(start_after, start_before)`等で単調性を検査。実行前に`assertLess(end_before, total, ...)`のガードがあり、既に全カードが窓内なら明示的なAssertionErrorで停止する（無意味な成功を返さない） | 対応 |
| browserActions.pageDeckNext/Previous.requiredOutcome.publicOperation: none | 送りは公開APIを一切叩かない | 同上 | `_perform_without_candidate_request`が`/candidate-proposals`宛リクエストの発生を監視し0件であることを確認 | 対応 |
| browserActions.pageDeckNext/Previous.requiredOutcome.unaffected（`cardsAndMarkersSet`/`dataCandidateRefValues`/`dataSelectionStateValues`/`appliedFilters`/`pendingFilters`/`conditionSummary`） | 送りはこれら全てを変えない | 同上 | `_assert_display_snapshot`は`card_refs`/`marker_refs`/`card_selection_states`/`marker_selection_states`/`condition_summary`/`applied_filters`の6項目を比較する | **`pendingFilters`が欠落（G2参照）**。契約が明記する6項目中5項目のみ検証 |
| browserActions.selectMarker.deckVisibility | 窓の外のカードをピン経由で選ぶと窓に入る | `selecting_a_marker_outside_the_deck_window_brings_its_card_into_view` → `select_marker_outside_deck_window_and_verify_it_becomes_visible` | 現在の窓の`end`の直後（1-based `end+1`）のカードを明示的に選び（`assertTrue(target_position < start or target_position > end)`で事前に窓外であることを確認済み）、`dispatch_event("click")`後に`new_start<=target_position<=new_end`を検証 | **対応。懸念5は該当なし** — もともと窓の中のカードでは検査していない |

## 指摘

### G1 — `disabledState`は両端のうち一端（`candidate-deck-next`がend=totalで無効になる側）が実行経路上一度も真にならない（Medium）

`assert_deck_paging_controls_disabled_state_matches_window`はif/elseの両分岐を持つ正しいロジックだが、
`test_tdr_cs_02_desktop_deck_navigation_windows_candidates_without_changing_them`内での呼び出しは
以下の1回のみ（デッキ送り前）:

```python
self.steps.deck_paging_controls_disabled_state_matches_window()
self.steps.organizer_pages_the_deck_forward()   # 1ステップだけ次へ
self.steps.organizer_pages_the_deck_backward()  # 1ステップだけ前へ（開始位置に戻る）
self.steps.selecting_a_marker_outside_the_deck_window_brings_its_card_into_view()
```

`page_deck_next_and_verify_window_advances`自身のガード（`assertLess(end_before, total, ...)`）が
「既に全カードが窓内なら失敗させる」ため、開始時点では必然的に`end_before < total`——つまり
`candidate-deck-next`は最初から無効ではない状態が保証されている。送りは1クリックのみで、
`candidate.js`の`pageDeckNext`は`deckWindowStart`を1ずつしか進めない（実装を確認済み、
`deckWindowStart + 1`）ため、この1クリックだけでは通常`end==total`（窓が末尾に到達し「次へ」が
無効になる状態）へは到達しない。`deck_paging_controls_disabled_state_matches_window`はこの後
再度呼ばれることもない。

結果として、この実行系列では「`candidate-deck-next`がdisabledになる」という条件分岐
（`disabledState`の後半、Must本文の"exactly when data-deck-visible-end equals data-deck-total"）が
**一度も`True`側で通らない**。もし実装が末尾でも`candidate-deck-next`を無効化し忘れる欠陥を持って
いても、この一連のテストは検出できない。これは依頼文の懸念3「両端の両方を通っているか」に直接
該当する——答えはNOで、`candidate-deck-previous`側（start=1で無効）のみが実際にdisabled=trueの
状態で検査されている。

是正案: シナリオへ「窓が末尾に到達するまで`organizer_pages_the_deck_forward`相当を繰り返す」ステップ
（または末尾到達後に`deck_paging_controls_disabled_state_matches_window`を再度呼ぶステップ）を足せば
閉じられる。恒真化やタウトロジーではなく、単純な実行経路の抜けであるため、ブロッカーとまでは判断
しない。

### G2 — `pageDeckNext`/`pageDeckPrevious`の`unaffected: pendingFilters`が一度も検証されない（Medium）

契約の`browserActions.pageDeckNext`/`pageDeckPrevious`はいずれも次を要求する:

```yaml
unaffected: [cardsAndMarkersSet, dataCandidateRefValues,
             dataSelectionStateValues, appliedFilters, pendingFilters,
             conditionSummary]
```

しかし`DisplaySnapshot`（`page_deck_next_and_verify_window_advances`等が使う前後比較の実体）は
次の6フィールドしか持たない:

```python
card_refs: list[str]
marker_refs: list[str | None]
card_selection_states: list[str | None]
marker_selection_states: list[str | None]
condition_summary: str
applied_filters: dict[str, object]
```

`pending_filters`フィールドが存在せず、`_assert_display_snapshot`も`self._pending_filters`を一切
比較しない。加えて、`test_tdr_cs_02_desktop_deck_navigation_windows_candidates_without_changing_them`は
一度も`organizer_opens_filter_panel`（絞り込みパネルを開いてpendingをdirtyにする操作）を呼ばない
ため、この実行系列では`pending == applied`のまま推移し、たとえ検査していたとしても差分が出る場面が
そもそも作られていない——つまり「検査していない」ことと「検査する機会が無い」ことの両方が同時に
成立している。

契約が明記した6項目中5項目は実際に前後比較されており恒真ではないが、`pendingFilters`だけは
仕組み自体（`DisplaySnapshot`のフィールド）から欠落しているため、将来デッキ送りがpendingを誤って
変えてしまう欠陥が入っても検出できない。是正には(a) `DisplaySnapshot`へ`pending_filters`フィールドを
追加し比較対象にする、(b) このシナリオでpendingをdirtyにしてから送りボタンを押す手順を足す、の
両方が必要（(a)だけでは上記の理由で機会が無いまま緑になり続ける）。ブロッカーとまでは判断しない
（現状のフィルタ非依存の他のMust群は正しく検証されており、この欠落は契約が明記した1項目に限定
されるため）が、次にこの領域を触る際は要修正として記録する。

### 参考（指摘としては報告しない）: デッキの可視ウィンドウ検査は属性ベースであり、CSSクリップの実描画は独立検証していない

`assert_deck_position_counter_is_well_formed`・`disabledState`・`orderingInvariant`・
`selectMarker.deckVisibility`はいずれも`data-deck-visible-start/-end/-total`属性を根拠とする。
`candidate.js`を読むと、この3属性と実際のCSSクリップ幅（`deckViewportEl.style.maxWidth`）・
スクロールオフセット（`offsetPx`）は同一関数`updateDeckPositionDisplay`が同じ`deckWindowStart`/
`deckWindowSize`から生成しており、カード自体は常に全件DOMに存在する（ウィンドウ外のカードもDOM
からは除去されない、`overflow`によるクリップのみ）。したがって、この属性群が正しくても実際の
CSSオフセット計算が独立に壊れているケース（人間が画面を見れば分かるがPlaywrightの`is_visible()`は
祖先の`overflow:hidden`によるクリップを検出しない）は、この一連の検査では捕捉できない。

**ただし、これは契約`deckNavigation.position`/`selectMarker.deckVisibility`自身の文言が最初から
属性ベースで定義されている**（"visibleStart <= its 1-based displayOrdering position <= visibleEnd"、
属性の値としての比較）ためであり、DSLは契約が求めるMustと正確に一致した検査をしている。実際の
画面上のピクセル位置（rendered-geometry）を検査しないのは、本契約ファイル自身が既に採用している
慣行（`filterPanel.controlGrouping.genreGroup.overflowPlacement`のL5配分、`renderModes.
verificationAllocation`のL5配分——いずれも"rendered-geometry properties this contract does not
measure...measured only by orchestrator per activeContext.md's rendered-geometry rule"）と整合する。
新規の欠落ではなく、既存のL4/L5境界線の一貫した適用と判断し、指摘としては報告しない
（記録のみ、将来この境界線自体の是非が問われた際の参考情報として残す）。

## L4 5観点チェックリスト

| 観点 | 判定 | 根拠 |
|---|---|---|
| 過不足 | ほぼOK（G2で1項目欠落） | `deckNavigation`/`renderModes`/`selectMarker.deckVisibility`の新設Mustのほぼ全てに対応するstep/DSLが1件ずつ存在する。契約が要求しない事項の追加検査は見当たらない。`unaffected.pendingFilters`のみ未検査（G2） |
| Givenの正当性 | OK | 新設stepは既存の`set_candidate_state("NORMAL_WITH_WEIGHTED_SAMPLING", ...)`・`open_candidate_screen`系を再利用するのみで、新しいGiven seamは追加していない |
| Thenの検証対象 | 一部NG（G1・G2） | 大半のThenは契約が指す検証対象（属性値・前後比較・公開APIリクエスト有無）を正しく検査している。G1（disabledStateの片端）・G2（pendingFilters）の2項目は検証対象自体が実行経路上に現れないか、比較コードから欠落している |
| 失敗の握りつぶし | OK | 新規コードにtry/except・空catch・過度に緩い比較・sleep同期は見当たらない。ガード（`assertLess`/`raise AssertionError`）はいずれも「検査不能な前提なら明示的に落とす」正しい設計 |
| 暗黙の前提 | 要確認（G1・G2と同一） | 「1回の送りで末尾に到達する」「デッキ検査ではpendingは常にappliedと等しい」という暗黙の前提のもとでシナリオが組まれており、それぞれG1・G2の形で検証機会の欠落につながっている |

## contract ↔ test 対応・孤児監査

### 対応済み

- `renderModes`（`listPrimaryLayout`/`mapPrimaryLayout`の相互排他性）、`deckNavigation`
  （previousControl/nextControl/position/orderingInvariant、disabledStateは一部）、
  `selectMarker.deckVisibility`、`unavailableControls.allowedPurposes`の2新規値——いずれも
  対応するstep/DSLが存在し、`test_tdr_cs_02_desktop_deck_navigation_windows_candidates_without_changing_them`
  から1回ずつ呼ばれていることを確認した。
- `contracts/candidate-search.feature`に対応する記述が無いことも確認した（`デッキ`/`deck`で0件
  ヒット）——このテストはGherkinシナリオ駆動ではなく契約のUI実装詳細としてのみ導入されており、
  それ自体は契約・ADRの記述（adr/0031は候補提案の外部振る舞いを変えないUI実装詳細と位置づけている）
  と整合する。孤児シナリオではない。

### 孤児または不完全な契約要求

- G1: `deckNavigation.disabledState`のcandidate-deck-next側（end=totalでdisabled）が実行経路上
  未検証。
- G2: `browserActions.pageDeckNext`/`pageDeckPrevious`の`unaffected.pendingFilters`が
  `DisplaySnapshot`から欠落し未検証。

### 重複・死んだ受け入れ補助コード

- 見当たらなかった。新設メソッド（`assert_render_mode_test_ids_are_mutually_exclusive`・
  `assert_map_primary_layout_holds`・`assert_deck_position_counter_is_well_formed`・
  `assert_deck_paging_controls_declare_correct_purposes`・
  `assert_deck_paging_controls_disabled_state_matches_window`・
  `page_deck_next_and_verify_window_advances`・`page_deck_previous_and_verify_window_recedes`・
  `select_marker_outside_deck_window_and_verify_it_becomes_visible`・`_deck_window`・
  `_deck_int_attribute`）はいずれも対応するstep経由で1回ずつ呼び出されており、既存メソッドとの
  同義重複も確認できなかった。

## 修正が必要と判断する項目

1. **G1（Medium）**: `disabledState`の`candidate-deck-next`側境界を実際にdisabled=trueへ到達させる
   ステップ（末尾まで送る、または末尾到達後に再度disabled-state検査を呼ぶ）をシナリオへ追加すること
   を推奨する。
2. **G2（Medium）**: `DisplaySnapshot`へ`pending_filters`フィールドを追加して比較対象にし、かつ
   このシナリオでpendingをdirtyにしてから送りボタンを押す手順を追加すること（両方揃って初めて
   `unaffected.pendingFilters`を実際に検証したことになる）を推奨する。
3. 上記いずれもマージを妨げるブロッカーとは判断しない。依頼文が特に警戒した「構造上ぜったいに
   失敗しない検査」（同一ソース同士の比較、恒真assertion）はこの差分には見当たらなかった。
