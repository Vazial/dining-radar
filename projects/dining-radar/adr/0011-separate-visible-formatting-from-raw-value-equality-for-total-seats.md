---
id: 0011
scope: project/toyama-dining-radar
status: 承認済み
date: 2026-08-05
approved_by: "本PRのマージをもって承認（ADR-0035 方式(i)、人間裁定 2026-08-05: 案A（可視テキストとは別に機械可読な属性へ生値を持たせ、そちらで厳密等価を検査する。可視値には単位・表示整形を許す）を採用。却下: (B) 実装を`38`の描画に直す（承認済み画面設計に反する）／(C) 契約を『可視値は返却値を含む』に緩める（誤描画も通り検査が弱まる）"
supersedes: []
superseded_by: null
relates_to: [P-01, P-02, P-06, P-08, P-10, TDR-CS-02, TDR-CS-03, FR-005]
---

# ADR-0011: 総席数は可視表示の整形と機械検証の等価対象を分離する（`data-raw-value`）

> **承認者向けサマリ**: L4（JS実行可能なブラウザ自動化、ADR-0009）で `TDR-CS-02` が1件だけ落ちた。原因は
> 承認済み成果物どうしの食い違いである——承認済みの画面設計（PR #66）は総席数を `38席`
> と単位付きで描画するが、承認済みの `candidate-search-browser-interface.yaml`（PR #76）は
> 「非nullの必須フィールドは可視値が返却値と厳密に等しい」と定めており、`38席` ≠ `38`
> で矛盾する。developerは承認済み画面設計に忠実に実装し、testerは契約に忠実にassertしており、
> どちらの誤りでもない。人間裁定（案A）に従い、**可視値とは別に機械可読な `data-raw-value`
> 属性へ返却値をそのまま持たせ、testerはその属性で厳密等価を検査する**。可視値には単位や
> 表示整形を許す。この変更は `totalSeats` フィールドだけに適用し、他の7つの必須フィールドの
> 等価規則は変更しない。`candidate-search.feature`・`candidate-search-api.yaml` への波及はない。

## 文脈

### 1. 何が起きたか

orchestratorがTDR-CSのL4（ADR-0009が確定したJS実行可能なブラウザ自動化）を実行した結果、
15件中14件pass・skipゼロで、`TDR-CS-02` の1件だけが落ちた。

- **承認済みの画面設計**（`design-preview/src/screens/CandidateSearchPreview.tsx`、PR #66でマージ、
  人間承認済み）の350行目は、総席数を `` `${candidate.totalSeats}席` `` と描画する（**単位付き**）。
- **承認済みの browser-interface 契約**（`candidate-search-browser-interface.yaml`、PR #76でマージ、
  人間承認済み）の `cardDataAttributes.nullBehavior` は、「非nullのAPI値は
  `data-value-state=provided` とし、**その可視値は返却値と等しい**」と定めていた。この文言は
  `requiredFields` の8フィールド全てに一律で掛かる。
- `candidate-search-api.yaml` の `totalSeats` は `type: integer, nullable: true` であり、返却値は
  `38` のような整数である。実装は承認済み画面設計に忠実に `38席` と描画し、testerは承認済み契約に
  忠実に可視値と返却値の厳密等価をassertしたため、この1点だけで食い違った。
- 実際に単位を伴う必須フィールドは `totalSeats` だけであり、他の7フィールド（`name`・`genre`・
  `description`・`businessHours`・`regularHoliday`・`access`・`providerPageLink`）はいずれも
  可視値が返却値のまま（整形なし）であり、矛盾していない。

### 2. なぜどちらのagentの誤りでもないか

- developerは `meta/agents.md` §4手順5（承認済み画面設計に忠実に実装する）に従った。
- testerは承認済み契約に忠実にassertした。
- 矛盾の originは、両者が参照した2つの承認済み成果物（画面設計と契約）が、`totalSeats` の
  表示整形について事前に突き合わされていなかったことにある。

### 3. 見落としの所在（friction-log FR-005）

`design/reconciliation/candidate-search.md` は、round-1の突き合わせ（2026-08-01、本ADRより前）
で既に「APIは `integer | null` であり、表示時にのみ『席』を付けるべきfieldである」と記録していた
——つまり、総席数が表示時にだけ単位を付与される特殊なフィールドであることは、
`candidate-search-browser-interface.yaml`（PR #76、2026-08-03）の起草より前から文書化されていた。
architectは契約起草時にこの既存文書、および既に承認済みだった画面設計（PR #66、2026-08-01承認）を
突き合わせず、8フィールド一律の厳密等価ルールを書いた。これは見落としであり、friction-log
FR-005として記録する。

## 決定

### 1. `totalSeats` に機械可読な生値属性 `data-raw-value` を導入する

`candidate-search-browser-interface.yaml` の
`browserControlSurface.proposal.cardDataAttributes.requiredFields.totalSeats` に
`rawValueAttribute: data-raw-value` を追加する。`nullBehavior` を次の規則に改める。

- `totalSeats` が提供されている（`data-value-state=provided`）とき、そのカード要素は
  `data-raw-value` 属性を持ち、値は返却された整数の正準的な10進文字列（例: `38` → `"38"`）と
  厳密に等しい。**acceptance testはこの属性を厳密等価で検査する**。
- `totalSeats` の可視値は、実装が選んだ表示整形（例: 単位接尾辞 `席` を付けた `38席`）を
  返却値の上に加えてよく、可視値そのものは返却値との厳密等価検査の対象にしない。
- `totalSeats` が提供されていない（`data-value-state=unavailable`）とき、`data-raw-value` 属性は
  存在しない（`data-value-state=unavailable` が状態を既に表現しているため）。
- 他の7つの必須フィールドの等価規則は変更しない——可視値は返却値と厳密に等しいまま。
  `providerPageLink` は元から `href` が機械可読な生値であるため `rawValueAttribute` の対象外である。

`rawValueAttribute` というキー自体は他のフィールドにも将来宣言し得る一般的な仕組みとして書くが、
**現時点で宣言するのは `totalSeats` だけ**であり、他フィールドへの適用は今回のスライスの範囲外
とする（P-02: 必要な分だけ確定する）。

### 2. 却下した代替案

- **(B) 実装を `38` の描画に直す**: 承認済み画面設計（PR #66、人間承認済み）に反する。画面設計の
  再承認なしにdeveloperの実装だけを変えることは、承認点の意味を失わせる。
- **(C) 契約を「可視値は返却値を含む」に緩める**: 検査が弱くなる。`38席分の情報なし` のような
  誤描画も通ってしまい、L4がP-01（正しさの保証を機械検証に置く）の要求する強さを失う。

### 3. 波及範囲の判定

- **`contracts/candidate-search.feature`**: 変更不要。`TDR-CS-02` の本文
  「店舗カードには…総席数…が示される」は業務の言葉だけで書かれており、可視表示の整形方式や
  機械検証の等価対象という技術的執行モデルに言及していない。本ADRはシナリオの意味を変えない。
- **`contracts/candidate-search-api.yaml`**: 変更不要。`totalSeats` は元から
  `type: integer, nullable: true` であり、本ADRはAPIの形状を変えず、ブラウザの表示・観測方法だけを
  変える。
- **`design-preview/src/screens/CandidateSearchPreview.tsx`**: 変更不要（却下案Bの理由のとおり）。
  architectはこのファイルを編集しない。

### 4. 適用範囲

本ADRは `candidate-search-browser-interface.yaml` の `totalSeats` フィールドの観測方法にのみ適用
する。将来、他の必須フィールドが表示整形を必要とする場合、その時点で同じ仕組み
（`rawValueAttribute` の宣言）を独立に適用するかを判断する（P-02、P-05）。

## 検討した代替案

代替案の内容と却下理由は決定2に記載した。人間裁定はこれらを明示的に却下し、案Aを採用した。

## 帰結

- `candidate-search-browser-interface.yaml` の `totalSeats` フィールドと `nullBehavior` が改訂される
  （`contractVersion` を `0.1` から `0.2` に上げ、ファイル冒頭にこの改訂を記録するStatusコメントを
  追加した）。この改訂は人間の再承認点であり、承認の実体は本PRのマージである
  （meta/adr/0043の機械検証は `.feature` のステータス行だけを対象とするため、この
  yamlファイルの承認記録はコメントによる）。
- developerは `totalSeats` を描画するカード要素に `data-raw-value` 属性（返却された整数の文字列）を
  追加する。可視テキスト（`38席`）自体は変更しない。
- testerは `TDR-CS-02` のstep定義・DSLのうち `totalSeats` の等価assertionを、可視テキストの厳密等価
  から `data-raw-value` 属性の厳密等価へ切り替える。他のフィールドのassertionは変更しない。この
  step定義・DSLの差分は `meta/verification.md` L4詳細(2)の対訳表つき人間承認を要する（既存ルールの
  適用であり本ADRが新設するものではない）。
- friction-log FR-005に、契約起草時に既存の設計突き合わせ文書と承認済み画面設計を照合しなかった
  見落としを記録する（本PRに同梱）。
- `ARCHITECTURE.md`・`design.md` は更新不要と判定する。本件はモジュール境界・データフロー・
  設計骨格の変更ではなく、既存のテスト観測契約（control surface）内の1フィールドの観測方法の変更に
  留まるため。
