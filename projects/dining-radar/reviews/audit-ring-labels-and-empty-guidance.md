# 監査レポート: 輪のラベル可読性・0件案内の押せる操作化 acceptance 差分レビュー

- 担当: reviewer
- 監査対象: PR `docs/ring-labels-contract` → `main`（依頼時点 HEAD `18e0e95`）の `tests/acceptance/**` 差分
  （`git diff origin/main...HEAD`）
  - `tests/acceptance/dsl/candidate_search_browser.py`
  - `tests/acceptance/steps/candidate_search_steps.py`
  - `tests/acceptance/test_candidate_search_acceptance.py`
- 照合元: `contracts/candidate-search.feature`（TDR-CS-02・TDR-CS-05）、
  `contracts/candidate-search-browser-interface.yaml`（v1.3.2 → v1.4.0。
  `mapObservations.walkingRadiusRings.bandAttribute`/`bandLabel`、
  `browserControlSurface.empty.reviseFiltersControl`、
  `unavailableControls.allowedPurposes`への`candidate-no-results-open-filter`追加、
  `browserActions.openFilterPanel.input`の第2入力）、`adr/0030`（新規）
- 独立性: tester のコメント・docstring・コミットメッセージは判断材料にせず、DSL/step のコード自体と、
  それが読む `src/dining_radar/web/static/dining_radar/web/candidate.js`・
  `src/dining_radar/web/templates/web/home.html`（実装コード、監査のため読んだが変更していない）を
  自分で突き合わせて判定した。実装への欠陥注入によるフォールトインジェクション検証は、reviewer が
  実装コードを一切変更してはならないという役割制約（および実行環境のガードレール）により行っていない
  ——下記F1は静的なコード読解のみから導いた

## 実行結果（自分で実行）

- `python manage.py test tests.acceptance.test_candidate_search_acceptance.CandidateSearchAcceptanceTests.test_tdr_cs_02_compare_candidates_on_cards_and_map tests.acceptance.test_candidate_search_acceptance.CandidateSearchAcceptanceTests.test_tdr_cs_05_no_matching_lunch_candidates -v 2`
  → **Ran 2 tests in 20.648s, OK**
- 「緑」であること自体は以下の指摘の正しさの根拠にしていない（このプロジェクトの既往のF1と同種の
  懸念を扱うため）。指摘は静的なコード読解（DSL・step・実装の突き合わせ）のみで導いた

## 結論

**ブロッカー級の指摘が1件ある（F1）。** `assert_walking_radius_rings_have_legible_band_labels`
（`mapObservations.walkingRadiusRings.bandLabel`のMustを検査する新設メソッド）は、契約の文言
（「可視テキスト**または**アクセシブルラベル」）には形式的に合致するが、実装が両方の手段を同じコード
ブロックで無条件に用意しているため、**実際に画面上で読める分数（ADR-0030の人間の指摘そのものが
求めた性質）を検査する分岐が、今回追加された acceptance テストの実行では一度も通らない**。
0件案内の押せる操作化（`browserControlSurface.empty.reviseFiltersControl`）については、指摘に
値する不一致は見つからなかった。

## 対訳表

| # | シナリオ/契約文 | 呼び出されるstep | DSLが実際にすること | 判定 |
|---|---|---|---|---|
| TDR-CS-02 Then（新設） | 徒歩圏の同心リングにはそれぞれ何分の範囲かを示す表示が添えられる | `walking_radius_rings_show_each_bands_minutes` → `assert_walking_radius_rings_have_legible_band_labels` | 各`candidate-walking-radius-ring`について`data-walking-radius-minutes`（bandAttribute）を読み、リング自身または子孫要素のうち「aria-labelがあればそれを最優先」「無ければ`is_visible()`な要素の`text_content()`」の順で先頭桁の整数を取り出し、bandAttributeと一致することを確認する | **形式的には契約の`bandLabel`（visible or accessible）と一致するが、この実装のもとでは実質的に検証していない（F1参照）** |
| TDR-CS-05 Then（新設） | その案内を選ぶと絞り込み条件を変更する画面が開く | `selecting_no_results_guidance_opens_the_filter_panel` → `open_filter_panel_via_no_results_guidance` | `candidate-no-results`配下に`candidate-no-results-revise-filters`が**ちょうど1件**存在し活性化していることを確認したうえで実際に`click()`し（`dispatch_event`ではなく実クリック——occlusion/可視性のPlaywright actionabilityチェックを経由する）、既存の`open_filter_panel`と同一の`_assert_filter_panel_opened`（絞り込みパネル・各コントロールの出現、URL不変、budget tier選択肢の完全一致）を再利用して結果を確認する | 対応。`openFilterPanel.input`の第2入力・`reviseFiltersControl`の要求（「exactly one」「openFilterPanelと同じ結果」）をどちらも直接検査しており、既存の`open_filter_panel`と実装を共有しているため将来のドリフトリスクも低い |
| （関連、無変更） TDR-CS-02 Then「地図上の店舗を選ぶと対応する店舗カードが強調される」 | `selecting_a_marker_highlights_its_card` → `select_first_marker_and_verify_card_highlighted` | 今回のdiffで`.first`+`dispatch_event("click")`へ書き換え。既知のG1（合成イベントは人間の指の到達可能性を証明しない）と同じ性質のギャップの新しい適用箇所であり、新規の指摘ではないと判断した | 記録のみ（既知G1の再適用、新規指摘としては報告しない） |

## 指摘

### F1 — `bandLabel`可読性検査は、この実装のもとでは「画面上で読める」ことを一度も検査していない（Blocker）

`candidate-search-browser-interface.yaml`の`bandLabel`は次のように書く。

> Each ring must also expose a non-empty visible or accessible text label -- on the ring itself or
> an element it owns -- whose leading digits, parsed as an integer, equal that same bandAttribute
> value.

DSL（`_first_legible_leading_minutes`）はこれを次の順で検査する。

```python
for node in candidates:            # candidates = [ring] + ring.locator("*") の全descendant
    aria_label = node.get_attribute("aria-label")
    leading = _leading_minutes(aria_label)
    if leading is not None:
        return leading             # ここで即return
    ...  # is_visible() な要素のtext_contentを見るのはこの後
```

`ring`自身（`candidate-walking-radius-ring`のtest idを持つLeafletのSVG `<path>`要素）が
`candidates`リストの先頭であり、`candidate.js`はこの同じ要素に対して次を**無条件に**実行する
（`layoutWalkingRadiusRings`、抜粋・行872-877付近）。

```javascript
ringEl.setAttribute("data-testid", "candidate-walking-radius-ring");
ringEl.setAttribute("data-walking-radius-minutes", String(ring.minutes));
ringEl.setAttribute("aria-label", labelText);   // labelText = String(ring.minutes) + "分"
```

`bandAttribute`と`aria-label`は同じ関数の同じスコープ内で、同じ変数`ring.minutes`から連続する2行で
設定される——独立した2つの実装経路の突き合わせではなく、実質的に同じ値の言い直しである。この
`aria-label`が存在する限り、`_first_legible_leading_minutes`は最初のノード（`ring`自身）で即座に
一致を見つけて`return`し、**後続の`is_visible()`分岐（実際に画面へ描画されるテキストを見る分岐）へは
到達しない**。

一方、実際に人間の目に見える「読める分数」を描画しているのは、この`ringEl`とは別の
Leafletレイヤーである`L.divIcon`ラベル（`layoutWalkingRadiusRings`内、`label.addTo(map)`で
リングとは別に地図へ追加される兄弟要素）である。`ring.locator("*")`はPlaywrightの`Locator`が持つ
CSSセレクタの子孫検索であり、DOM上で兄弟ノードにあるこの`divIcon`要素には**構造的に到達できない**
（`ring`自身のSVG `<path>`に子ノードは無く、`owned.count()`は常に0）。したがって、この`divIcon`
ラベル——位置の衝突回避・画面外へのクランプ・角度探索まで実装されている、本ADRが名指しした
「読める形で示す」ための本体の実装——は、今回追加された acceptance テストのどの分岐からも
一度も読まれない。

**検証**: `RING_BAND_ATTRIBUTE`（`data-walking-radius-minutes`）読み取りと`aria-label`読み取りの
両方を静的にコードから追跡し、`candidates`ループの`for`文がaria-label一致時に即`return`する制御フロー
であることを確認した。実装（`src/**`）へのフォールトインジェクションによる動的確認は、reviewerの
役割制約上行っていない（上記「独立性」参照）——ここに記す結論は静的なコード読解のみに基づく。

**この検査が実際に証明していること**: `data-walking-radius-minutes`（機械値）と`aria-label`
（同じ関数内で同じ値から生成された文字列）が一致していること。これは「実装が`ring.minutes`を
2回書き写す際に食い違えていないか」という限定的な性質のみを検査しており、契約が本来問うべき
「人間が画面を見て分数を読み取れるか」という性質（ADR-0030が明記する動機——本番実測で
`data-walking-radius-minutes`属性はあったが画面には出ていなかったという事故そのもの）は、
`aria-label`という別の（かつ視覚的には無関係な）チャンネルを経由することで、テストの目には
「合格」として映る。

契約の`bandLabel`文言自体は「visible **or** accessible」という選言なので、`aria-label`だけで
Mustを満たすという解釈自体は契約の文面と矛盾しない（SVGの`<path>`が`role`無しで`aria-label`を
アクセシビリティツリーへ公開するかはブラウザ実装依存で本監査では判定していない）。**しかし
acceptanceテストとしての価値は別問題である**——このADR/PRの目的は「画面上で分数が読めること」の
リグレッションを機械的に検出し続けることのはずだが、実際には`divIcon`ラベルの描画が丸ごと壊れる
（位置計算がすべて画面外にクランプされる、`labelVisual`要素が見つからずテキストが入らない、
レイヤーが地図に追加されない等）変更が将来入っても、`ring`自身の`aria-label`さえ無事なら、この
テストは緑のまま検出できない。ADR-0030が実際に対処しようとした本番の事故（属性はあるが画面に
出ていない）と表面的には同じ形の欠陥を、この acceptance テストは見逃せる構造になっている。

**是正案（人間/architectの判断を要する）**:
1. `_first_legible_leading_minutes`の探索順を変え、`ring`自身（同じ関数内で生成された
   aria-label）よりも先に、実際に画面へ描画される別要素（`divIcon`のラベル）の可視テキストを
   優先的に検査する、または独立した2つの経路（可視テキスト・アクセシブルラベル）の**両方**が
   存在し一致することを求める形に変える。
2. もしくは、`ring`自身の`aria-label`は「belt-and-suspenders」であることを認めたうえで、
   `divIcon`ラベル要素にも契約が参照できる安定した目印（既存の`candidate-walking-radius-ring-label`
   というクラス名はあるが`data-testid`は無い）を与え、DSLがその要素を名指しで直接検査できるようにする。
3. どちらも採らない場合は、少なくとも「この acceptance テストは`aria-label`経路のみを検証しており、
   画面上の可視ラベル描画そのものは検証していない」という限界を、契約または監査記録に明記して
   おくべきである。

### F2（0件案内の押せる操作化） — 指摘なし

`open_filter_panel_via_no_results_guidance`は、`candidate-no-results-revise-filters`が
`candidate-no-results`配下にちょうど1件存在すること・活性化していることを確認したうえで、
（`dispatch_event`ではなく）実際の`click()`でPlaywrightのactionabilityチェック（可視性・
ヒットテストを含む）を経由して操作し、既存の`open_filter_panel`が使う`_assert_filter_panel_opened`
（パネル本体・各コントロール7要素の出現、URL不変、budget tierの並び完全一致）をそのまま再利用して
結果を検証している。実装（`candidate.js`の`renderNoResultsReviseFiltersControl`）も、
`candidate-no-results`セクションの子として無条件にボタンを描画し、クリックで
`filterExpanded = true`にして再描画するのみで、既存の`open_filter_panel`と同じ結果を起こす
実装になっていることを確認した。`data-candidate-control-purpose="candidate-no-results-open-filter"`
も`unavailableControls.allowedPurposes`への追加と一致している。恒真化・可視性検査の骨抜きは
見当たらない。

## L4 5観点チェックリスト

| 観点 | 判定 | 根拠 |
|---|---|---|
| 過不足 | OK | TDR-CS-02・05の新設Thenそれぞれに対応するstep/DSLメソッドが1件ずつ存在し、契約が要求しない事項を追加で検査してはいない |
| Givenの正当性 | OK | 新設stepはいずれも既存Given（公開されたテスト支援API経由の状態）をそのまま使い、新しいGiven seamは追加していない |
| Thenの検証対象 | **一部NG（F1）** | 0件案内の押せる操作化は契約の要求（exactly one・openFilterPanel同一結果）を直接検証している。輪のラベル可読性は、契約文言には合致するが、実装のもとでは「画面上で読める」という本来の検証対象に一度も到達しない構造になっている |
| 失敗の握りつぶし | OK | 新規/変更コードに空catch・過度に緩い比較・sleep同期は見当たらない。`_first_legible_leading_minutes`の`except Exception: visible = False`は「detached/不安定なノードを legible とみなさない」という保守的な扱いであり、失敗の握りつぶしではない |
| 暗黙の前提 | 要確認（F1と同一） | 「`aria-label`が`ring`自身にあれば良い」という契約解釈が、実装側の「同じ関数内で同じ値を2回書くだけ」という実態と組み合わさることで、可視描画の暗黙の前提（描画されているはず）が実際には検査されないまま通ってしまう |

## contract ↔ test 対応・孤児監査

### 対応済み

- `TDR-CS-02`の新規Then（同心リングの分数表示）に対応するstep/DSLが存在する（`walking_radius_rings_show_each_bands_minutes`）。
- `TDR-CS-05`の新規Then（案内を選ぶとパネルが開く）に対応するstep/DSLが存在する（`selecting_no_results_guidance_opens_the_filter_panel`）。
- `test_candidate_search_acceptance.py`で両stepともそれぞれ1回ずつ、対応するシナリオ内で呼ばれている（TDR-CS-02本体・TDR-CS-05本体）ことを確認した。

### 孤児または不完全な契約要求

- 上記F1（`bandLabel`の「visible」側の実質的な未検証）。

### 重複・死んだ受け入れ補助コード

- 見当たらなかった。新規メソッド（`assert_walking_radius_rings_have_legible_band_labels`・
  `_first_legible_leading_minutes`・`open_filter_panel_via_no_results_guidance`・
  `_assert_filter_panel_opened`〔既存`open_filter_panel`から抽出・共有〕）はいずれも対応するstep
  経由で呼び出されており、既存stepとの同義重複も確認できなかった。`_assert_filter_panel_opened`への
  抽出はむしろ`open_filter_panel`と`open_filter_panel_via_no_results_guidance`の間の重複コードを
  減らし、ドリフトリスクを下げる方向の変更である。

## 修正が必要と判断する項目

1. **F1（Blocker）**: `bandLabel`可読性検査が、この実装のもとでは`aria-label`（同じ関数内で
   bandAttributeと同じ値から生成される言い直し）に即座に一致してしまい、実際に画面へ描画される
   `divIcon`ラベルの可視性を一度も検査しない。ADR-0030が対処しようとした本番の事故（属性はあるが
   画面に出ていない）と同じ形の将来のリグレッションを、この acceptance テストは検出できない。
   人間/architect/testerの判断で、探索順の変更・可視ラベル要素への専用目印の付与・限界の明記の
   いずれかを選ぶことを推奨する。
2. 0件案内の押せる操作化（F2）は指摘なし。既存G1（合成イベントでの操作は人間の指の到達可能性を
   証明しない）の新しい適用箇所（マーカー選択の`.first`+`dispatch_event`化）は、既知の未解決事項の
   再適用であり、新規の指摘としては報告しない。

---

## 再監査（未コミット差分、tester による F1修正を受けて）

- 対象: `tests/acceptance/dsl/candidate_search_browser.py`の未コミット差分（`git diff`。
  `assert_walking_radius_rings_have_legible_band_labels`・旧`_first_legible_leading_minutes`を
  `_visible_walking_radius_ring_label_minutes`へ書き換え。新定数`WALKING_RADIUS_RING_LABEL_SELECTOR
  = ".candidate-walking-radius-ring-label-visual"`）
- 独立性: orchestratorが報告した欠陥注入結果（`candidate.js`の`labelVisual.textContent`を空文字にして
  `test_tdr_cs_02`が`read minutes []` vs `[5, 10, 15]`で落ちたという申告）は判断の根拠として採用せず、
  静的なコード読解のみで同じ結論に至れるかを自分で確認した。実装コード（`src/**`）は読んだが
  変更していない
- 実行結果（自分で実行）: `python manage.py test
  tests.acceptance.test_candidate_search_acceptance.CandidateSearchAcceptanceTests.
  test_tdr_cs_02_compare_candidates_on_cards_and_map -v 2` → **1 passed**。緑であること自体は
  以下の判定根拠にしていない

### F1再判定 — 大きく改善したが、部分的に未解消（新規の残存ギャップ、F1bとして記録）

**旧F1（aria-labelの早期return）自体は解消したと判断する。** `candidate_search_browser.py`を
grepし、このメソッド周辺で`aria-label`を読む箇所が完全に無くなっていることを確認した（残る
`aria-label`参照は本メソッドとは無関係な既存の`FORM_CONTROL_SELECTOR`走査、`control.get_attribute
("aria-label")`——フォーム系コントロールの意味推定用の別メソッドであり、輪のラベルとは無関係）。
新しい`_visible_walking_radius_ring_label_minutes`は、輪自身やその子孫ではなく、実際に画面へ
描画される別レイヤー（`WALKING_RADIUS_RING_LABEL_SELECTOR`、`candidate.js`の`L.divIcon`が生成する
`labelVisual`要素）だけを`self.page.locator(...)`でページ全体から探し、`is_visible()`な要素の
`text_content()`のみを収集する。この要素は`candidate.js`側で見ても、リングの`aria-label`とは
別の、実際に人間が見る唯一のテキストノードである（`labelVisual.textContent = labelText`）ため、
**この検査は今度こそ実際に画面上のレンダリングを読んでいる**。フォールトインジェクション
（`labelVisual.textContent = ""`）で落ちるというorchestratorの申告についても、自分でコードを
追跡した限り矛盾はなく、`test_tdr_cs_02`を自分で再実行して緑であることも確認した。

**しかし、比較方法をsorted multiset（集合的な一致）にしたことで、新しい種類の穴が生まれている
（F1b、Medium、要記録）。**

```python
self.assertions.assertEqual(
    sorted(label_minutes),
    sorted(ring_band_minutes),
    ...
)
```

これは「輪の`data-walking-radius-minutes`の値の集合」と「画面上に実際に見えるラベルの先頭桁の値の
集合」が一致することだけを検証し、**どの輪とどのラベルが対応しているか（1対1のペアリング）は
検証していない**。契約`bandLabel`の文言自体は"on the ring itself or an element it owns"と
**個々のリングごと**に書かれており、契約が本来求めているのはリング単位の対応関係だが、この
実装ではラベル要素（`L.divIcon`）がリング（SVGの`<path>`）の兄弟ノードであり、両者を紐付ける
機械可読な属性（例えばラベル側にも`data-walking-radius-minutes`を持たせる等）がDOM上に一切存在
しないため、**tester・reviewerの権限内（`tests/acceptance/**`のみ）では、集合比較より厳密な
1対1対応の検証を組み立てることが構造的にできない**——これはF1のときと同型で、原因はDSLのバグ
ではなく実装側のマークアップ構造にある。

具体的に取り逃す欠陥（依頼文が名指しした「輪3本・ラベル3つだが対応がずれている」ケースそのもの）:
本数・値の集合が一致したまま、どの輪がどのラベルと対になっているかだけが入れ替わる欠陥
（例: 5分の輪に「15分」、15分の輪に「5分」というラベルが付く回転/スワップ）は、`sorted()`比較
では**検出できない**——多重集合として`{5, 10, 15}`のままだからである。重複ケース
（例えば同じ分数の輪が2本ある場合や、一方の輪にラベルが2つ付き他方に0個付く場合）は、要素数が
変わる限りは長さの不一致として捕捉できるが、"値の重複と欠落がちょうど打ち消し合う"組み合わせが
あれば同様にすり抜け得る。

**この欠陥クラスが現実的に起きやすいかどうかを、実装を自分で読んで検討した。** `candidate.js`の
`layoutWalkingRadiusRings`は、単一の`rings.forEach`ループ内で、同じイテレーションの`ring.minutes`
変数から輪の半径（`ring.radiusMeters`）とラベル文言（`labelText = String(ring.minutes) + "分"`）の
両方を生成しており、他のイテレーションの値を参照する経路が無い。したがって**現在のコード構造では、
値そのものを取り違えずに対応関係だけをスワップする欠陥は、通常の実装変更では起こりにくい**——
値が変われば多重集合自体も変わり、この検査で捕捉される。この意味で、F1bは今この瞬間の実装に
対する実害というより、**この検査の証明力そのものの理論的な上限**（多重集合比較は本質的に順序・
対応関係を見ない）として記録する。将来、ラベル配置ロジックが複雑化する（本diff自体が衝突回避の
角度探索・画面外クランプを新設しており、この種のロジックはインデックス操作のバグを呼び込みやすい
類のコードである）と、この隙間が現実の欠陥を隠す可能性は残る。

**判定: F1（旧・aria-labelの早期return）は解消。ただしF1bとして新しい残存ギャップを記録する
（Medium、ブロッカーとまでは判断しない——現在のコード構造では発現しにくく、かつ
`tests/acceptance/**`の範囲内では実装側にラベル要素への識別用属性が追加されない限りこれ以上厳密には
できないため）。** マージを妨げる理由とはしないが、次にこの領域を触る際（ラベル配置ロジックの
リファクタ、輪の本数変更など）は要再確認と明記する。

### Q2への回答 — `is_visible()`が証明できること/できないことの開示は概ね正直、ただしF1bは書かれていない

新しい`_visible_walking_radius_ring_label_minutes`のdocstringは、`is_visible()`が
「zero-size, display:none, or visibility:hiddenな祖先を含めて判定する」ことと、外側の
`assert_walking_radius_rings_have_legible_band_labels`のdocstringが「Playwrightの可視性判定は
画面上の物理的な重なり（occlusion、例えば候補ピンがラベルの上に重なる場合）をモデル化しない」
ことを明記しており、**この2点については正直に開示されている**（証明できないことを証明できないと
書く、という監査の基準を満たす）。

**一方、F1b（多重集合比較が対応関係を見ないこと）はdocstringに書かれていない。** docstringは
「2つのmultisetが一致することを要求する」と手法自体は正確に述べているため、読み手が multiset の
性質から対応関係非検証を自力で導出することは可能だが、この検査の限界として**明示的には**
指摘されていない。occlusionの開示に比べると非対称であり、記録に値する（ブロッカーではない）。

### Q3への回答 — `data-testid`不在について（reviewerの見解、実装は変更していない）

`WALKING_RADIUS_RING_LABEL_SELECTOR`がCSSクラスのみに依存し、このプロジェクトの規約
（`by_test_id`／`data-testid`によるDOM要素の特定）から外れている点について、tester・reviewer
どちらもファイル権限外（`src/**`）のため今回の差分では是正できないという整理は妥当と判断する。

**reviewerの見解として、これは実装に`data-testid`を足すべき、かつ足すだけでは終わらない
（契約改訂を伴い得る）と考える。** 理由:

1. `by_test_id`規約からの逸脱は本差分固有の新しい問題であり、既存コードのCSSクラス依存
   （`.candidate-walking-radius-ring-label-visual`のスタイリング用途）とは別に、**acceptanceの
   識別子としてCSSクラス名を使う**という初めての前例をこのファイルに作っている。CSSクラス名は
   スタイル変更のたびに変わり得る（デザイン改修でリファクタされる可能性がある）識別子であり、
   `data-testid`が本来提供する「見た目が変わっても安定した識別子」という保証を失っている
2. より本質的には、F1bで指摘した「1対1対応の検証ができない」という残存ギャップは、
   `data-testid`を足すだけでは閉じない。ラベル要素に`data-testid="candidate-walking-radius-
   ring-label"`を足しても、それは要素の**発見**を安定させるだけで、**どの輪と対になっているか**
   という相関情報は別途要る。閉じるには、ラベル要素自身にも`data-walking-radius-minutes`
   （リングの`bandAttribute`と同名・同値の属性）を持たせる必要がある——これは`cardDataAttributes`
   の`rawValueAttribute`パターンをラベル側にも複製する形になる
3. これは実装の1行追加で完結する変更に見えるが、**契約`bandAttribute`/`bandLabel`は現状
   「リング要素」だけを主語にして書かれており**、ラベル要素という別のDOM要素にも同じ属性名を
   持たせてよいか、持たせた場合それを契約のどの条文が保証するのか（= 将来の実装がこの属性を
   外しても契約違反として検出されるのか）は、今の契約文言だけでは判定できない。したがって
   **これはtester・reviewerが独断で決めてよい範囲を超え、architectの契約改訂（`bandLabel`に
   「ラベル要素はリングのbandAttributeと同値の相関属性を持つ」という一文を足す）を伴うのが筋だと
   考える**——ADR-0030 決定1が「文言・単位表記・配置は実装の選択のまま残す」としているのと同じ
   様式で、相関用の属性名だけを機械可読な形で契約に足す小さな改訂で足りるはずである
4. 人間/architectがこれを不要と判断する（現状の集合比較で十分と判断する）選択肢もあり得る。
   その場合は、F1bを契約またはこの監査記録に「既知の限界」として明記したうえで進めることを
   推奨する

**結論: 是正を強制はしないが、reviewerとしては`data-testid`単体ではなく、ラベル要素への
相関属性（`bandAttribute`と同名）の追加＋それを裏付ける契約改訂をセットで行うことを推奨する。
マージ前必須のブロッカーとはしない（F1bと同様、現在のコード構造では実害が起きにくいため）。**

### 再監査の結論

- **F1（aria-labelの早期return）: 解消したと判断する。** 新しい検査は実際に画面上へ描画される
  `divIcon`ラベルのテキストを、Playwrightの可視性判定を経由して読んでおり、静的なコード読解でも
  それを確認した。
- **新規: F1b（Medium、記録）。** sorted multiset比較は、値の集合が保たれたままリングとラベルの
  対応関係だけが入れ替わる欠陥を検出できない。現在の実装構造（同一forEachイテレーション内で
  半径とラベル文言を同じ変数から生成）では発現しにくいが、検査の証明力としての理論的な上限として
  記録する。ブロッカーとはしない。
- **新規ブロッカーは無い。** 依頼文が挙げた懸念（対応ずれ、重複）はF1bとして記録し、
  ブロッカーではなくMediumの残存事項と判断した。
