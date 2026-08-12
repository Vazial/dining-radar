# TDR-CS フィルターモデル acceptance 差分レビュー

- 担当: reviewer
- 対象: working tree の `tests/acceptance/**` 差分
  - `test_candidate_search_acceptance.py`
  - `steps/candidate_search_steps.py`
  - `dsl/candidate_search_browser.py`
  - `dsl/js_browser_mechanics.py`
- 照合元: `candidate-search.feature`、`candidate-search-api.yaml`、
  `candidate-search-browser-interface.yaml`、`test-support-api.yaml`
  （いずれも今回のフィルターモデル draft）
- 実装コード、tester の説明・コメント・報告は判断材料にしていない。
- 実行結果はこのレビューの証拠にしていない。以下は scenario / step / DSL /
  contract の静的対訳である。

## 結論

**要修正（L4 step 承認不可）**。認可済みでない訪問者への候補カード非表示、既定の
居酒屋・バー除外、カード払い注意の「現金のみと断定しない」制約を、現在の差分は
いずれも十分に検証しない。これらはシナリオまたは browser-interface の必須結果であり、
テストが緑でも仕様充足を意味しない。

## Scenario → step → DSL 対訳

| Scenario | step の実際の呼出し | DSL が観測すること | 判定 |
|---|---|---|---|
| CS-00 未認証 | `visitor_opens…` → `visitor_is_guided…` | サインインフォーム、content/map/filter/search-again 等の不在、canary/test id の不在 | **不足**: cards/card/marker の不在を検証しない |
| CS-01 初期表示 | `organizer_opens…` → 初期表示・重複・秘匿・出典 | `POST` 応答の card 順、重複 URL、DOM の秘匿 canary、固定の provider credit | 一部不足: credit を応答値と照合しない |
| CS-02 比較 | cards/map、相互選択、地図、必須 field、パネル内予算注記 | 応答と card/marker の対応、選択状態、field raw 値、地図属性 | **不足**: 予算注記の「ディナー由来」「1件だけ」を検証しない |
| CS-03 絞り込み変更 | card-payment を dirty にして apply | 新しい POST、`cardPaymentOnly=true`、応答と DOM の置換、ソフトフィルタ一致・群順 | 代表操作のみ。pending の非送信・非破壊は未検証 |
| CS-04 地点/範囲/並べ替えなし | control purpose を列挙 | 既知 test id の不在、列挙した form control の purpose | **不足**: 地点・範囲を指定するボタン等を意味的に否定できない |
| CS-05 0件 | `NO_RESULTS` を seam で設定 | no-results、cards/map/problem 不在、200 の空 candidates、filter open | 概ね対応 |
| CS-06 取得不能 | `PROVIDER_UNAVAILABLE` を seam で設定 | problem/guidance、503 schema/code、秘匿 | 対応 |
| CS-08 rate limit | `RATE_LIMITED` を seam で設定 | problem/guidance、429 schema/code、秘匿 | 対応 |
| CS-09 居酒屋/バー | 初期表示後に include toggle を apply | 初期 request に `includeIzakayaBar` がない/false、toggle の存在、後の候補 URL に新規値が一つある | **不足**: 初期候補の除外も、後の候補が除外対象を含むことも検証しない |
| CS-10 fallback | `IZAKAYA_BAR_ONLY` を seam で設定 | response flag、candidates、fallback notice の存在、no-results 不在 | **不足**: notice の二つの必須開示と、他 filter を緩めない境界を検証しない |
| CS-11 もう一度探す | seed 7 → 19 → 7 として search-again | default filter body、応答 card/marker、異なる seed の差・同一 seed の再現 | 概ね対応。ただし初回 `{}` と後続の展開済み defaults の「同じ」の定義が曖昧 |
| CS-12 カード払い注意 | `NORMAL_WITH_POOL` で比較 | response が false の card に caution 属性、非 false では caution 不在 | **不足**: caution の文言（cash-only 禁止）を検証しない。表示対象も pool 抽選次第 |
| CS-13 情報なし | 匿名属性から、情報なしを含む最大5件の filter 組合せを選択して apply | confirmed non-match の不在、unknown state、confirmed → unknown の DOM 順 | 対応。ただし近い順そのものは API 応答を信頼するだけ |

## 指摘

### R1 — 未認証時に候補カードが漏れても通る（Blocker）

`UNAUTHENTICATED_FORBIDDEN_TEST_IDS` は `candidate-proposal-content` と map を対象にするが、
`candidate-proposal-cards`、個々の `candidate-card`、`candidate-map-marker` を含まない。
そのため content の外にカードまたは marker が誤って描画されても CS-00 は通る。
feature の「店舗カード、地図を見られない」と、認証境界に反する。

修正は、未認証 outcome の不在集合を cards/card/map-marker/provider credit を含む候補面全体へ
拡張し、CS-00 でその集合を直接検証すること。

### R2 — CS-09 が既定除外・include 後の包含を証明していない（Blocker）

`assert_izakaya_bar_inclusion_adds_candidates` は、include 後の候補に初回になかった
`providerPageUrl` が一つあることだけを見る。抽選があるため、同じ非除外ジャンルの別店舗に
替わっただけでも通る。一方、初回候補に default-excluded なジャンルが混入していても
検証しない。

`populationAttributes` の `genre` と `defaultExcluded` を、候補の `genre` と照合して、
初回には default-excluded genre が存在しないこと、include 後には少なくとも一つ存在することを
検証する必要がある。抽選に依存する Given なので、test-support はその観測を必ず可能にする
固定 seed/結果保証も持つ必要がある。

### R3 — CS-12 が「現金のみ」と断定する回帰を通す（Blocker）

card-payment caution は `data-card-payment-available="false"` だけを検証し、可視文言を一切
検証しない。browser-interface は「クレジットカードを利用できないことだけを示し、cash-only
その他の支払方法を主張してはならない」と明記する。`現金のみ` と描画しても現状は通る。

注意文がクレジットカード非対応を表すこと、および `現金のみ` 等の断定を含まないことを検証する。
また `NORMAL_WITH_POOL` は母集団に false/true があるだけで、ランダムな5件に両方が含まれる保証が
ないため、CS-12 用の決定的な表示 Given も必要である。

### R4 — CS-02/CS-10 の必須開示が存在確認に縮退している（High）

予算注記は非空かつ通貨記号・円を含まないことしか見ず、ディナー予算由来であることも、
panel 内に厳密に一つだけであることも確認しない。fallback notice も存在だけで、既定除外を
外したこととランチ営業が未確認であることの双方を確認しない。

それぞれ browser-interface の `budgetTierNoteObservation` と
`izakayaBarFallbackNoticeObservation` の語義を満たす可視テキスト・個数を検証すること。

### R5 — filter panel の公開操作・状態遷移に孤児がある（High）

browser-interface が要求する以下を、いずれの scenario も検証しない。

- control 変更時の cards/markers/condition summary 不変と POST 不在
- `candidate-filter-revert` の pending 復元、panel 維持、POST 不在
- panel を閉じたときの applied/pending/display 不変
- dirty 時の `data-match-count` の正確性、0 件時 apply disabled
- CS-10 の「明示した genres/non-smoking/card/budget を fallback が緩めない」

少なくとも CS-03 と CS-10 に対応する step を追加し、各操作の request 有無と DOM state を
契約どおり観測する必要がある。

### R6 — CS-04 は検索地点・探索範囲の指定を意味的に否定できない（High）

`assert_no_location_range_or_manual_order_control` は known test id と control purpose の許可集合を
見る。許可された purpose を偽って付けた地点/範囲選択ボタン、または目的を宣言しない
非列挙の interactive element を検出できない。現在の browser-interface も地点・範囲 controls の
否定を機械可読な identifier/semantics で持たない。

browser-interface に地点/範囲を指定する control の禁則を観測可能な形で追加し、CS-04 はそれを
直接否定すること。公開 request に location/range parameter が無いことは L3 で別途検証する。

### R7 — `searchAgain` の request 同一性が契約文とずれている（Medium）

初回 request は `{}`、再検索は展開済み defaults を期待している。API contract は「同じ
`filters` object」を再送すると表現する一方、DSL はこの二つを同じ適用条件として扱う。
意味的には同値でも byte/object としては同じではないため、contract と test のどちらを正とするか
曖昧である。

初期 request の既定 filters 正規化を contract に明記するか、再検索も初回の object を再送する
ようにし、DSL の assertion をその定義に合わせること。

### R8 — provider credit と attribution が response/契約への完全照合でない（Medium）

credit は response の `providerCredit` ではなく固定文字列・href と比べ、attribution も required の
完全テキストではなく部分一致である。response が正しい値を返しているのに DOM が別の値を表示する
ケース、または余分な誤表記を検出しない。

capture 済み response の `providerCredit` と DOM を照合し、attribution は contract 指定の完全値で
検証すること。

### R9 — 「近い順」の L4 証跡は response を信頼しているだけ（Medium）

`assert_current_display_ordering` は DOM card order が response `candidates` の順と一致し、unknown
group が末尾であることを検証する。しかし各 group が近い順かは、距離を公開しない API response
だけからは独立に判定できない。CS-03/11/13 の「常に近い順」は L4 では未観測である。

非公開地点・距離を公開しない制約を守ったまま、acceptance-only seam に synthetic な非位置的
順序証跡を与えるか、近い順の意味検証を L1/L3 の専用証跡に明確に分離すること。

## L4 5観点チェックリスト

| 観点 | 判定 | 根拠 |
|---|---|---|
| 過不足 | NG | R1–R6。scenario の必須結果が複数、存在または属性だけに縮退している。 |
| Given の正当性 | NG | `NORMAL_WITH_POOL` は母集団特性だけで、CS-09/12 が必要とする表示上の対象を保証しない。R2/R3。 |
| Then の検証対象 | NG | R1/R2/R3/R4/R9。認可・断定禁止・除外/包含・必須開示・近い順の一部が未観測。 |
| 失敗の握りつぶし | OK | 変更された step は一呼出しのみで、DSL に empty catch、sleep、retry、失敗を成功扱いする分岐は見当たらない。 |
| 暗黙の前提 | NG | R2/R3/R7/R9。ランダム抽選、defaults の同一性、距離順を示す証跡が明文化・固定化されていない。 |

## contract ↔ test 対応・孤児監査

### 対応済み

- test-support の reset/state 選択は Given seam としてのみ使う。
- public `POST /candidate-proposals` の 200/429/503 は、該当 scenario で実ブラウザ応答を schema
  照合する。
- cards/markers の response 対応、card/marker 双方向選択、nullable soft-filter の unknown 表示・
  grouping、0件と障害の区別、秘匿 canary は観測される。
- genre preview/overflow の順序と、overflow toggle が POST しないことは panel を開く CS-02/03/09/13
  で共通に観測される。

### 孤児または不完全な contract 要求

- `unauthenticatedOutcome` と feature CS-00 の cards/card/marker 非表示（R1）
- `cardPaymentCaution.presenceRule` の visible-text 禁則（R3）
- `budgetTierNoteObservation` の dinner 開示・厳密1件（R4）
- `izakayaBarFallbackNoticeObservation` の二つの開示（R4）
- `changePendingFilter`、`revertPendingFilters`、`closeFilterPanel`、apply の match count/disabled（R5）
- fallback が他 filter を緩めない条件（R5）
- location/range 指定禁止の直接証跡（R6）
- `providerCreditObservation` と attribution の完全照合（R8）
- displayOrdering の group 内 nearest-first 証跡（R9）

### 重複・死んだ受け入れ補助コード

今回追加された `dsl/js_browser_mechanics.py` の
`capture_candidate_proposal_response_with_overridden_body` と `_is_candidate_proposal_path`
および `json` / `Route` import は、現行 `tests/acceptance/**` 内から参照されない。retired された
invalid lens 操作用の補助が残ったものに見える。テストの意味を変えず削除するか、R5 の
「POST 不在」検証へ実際に使うかを決めること。既存の未参照補助まで今回の差分責任とは
扱わない。

## 修正後に必要な再監査条件

1. R1–R6 を反映した step/DSL 差分を再提出する。
2. `NORMAL_WITH_POOL` のランダム性に対して、CS-09/12 の Given が表示結果まで決定的になることを
   test-support contract で明記する。
3. 全 TDR-CS scenario の各 Then が、上表の未観測事項を残さず public UI/API の観測へ対応することを
   再確認する。
