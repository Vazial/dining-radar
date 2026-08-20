# friction-log.md

> Append-only record of AI mistakes, uncertainty, and avoidable rework. Human
> decisions by themselves are not friction; record only the AI contribution.

## FR-001: Design was commissioned before the chat Spec was closed

```yaml
id: FR-001
date: 2026-07-31
found_at: AI
slice: TDR-CS
agents: [architect, designer, orchestrator]
cause_category: workflow sequencing
cause_key: design-commissioned-before-contract-agreement
pushed_to: [projects/toyama-dining-radar/activeContext.md]
status: 対応済み
principles: [P-05, P-10]
```

- Situation: External design commissioning and the review-only preview used the
  earlier coordinate-input, primary/alternative, variable-count draft before
  the user closed the candidate-search Spec checkpoint.
- AI contribution: The workflow advanced to design reconciliation without first
  establishing the chat-agreed contract as the authoritative input. That made
  the brief, preview, and reconciliation stale and created avoidable contract
  rework.
- Downward push: The current `activeContext.md` now records that the preview is
  stale and requires reconciliation against the contract before any
  implementation slice. ADR-0003 states that the contract, not the receiver,
  is the SSOT for candidate-search behaviour.
- Result: No broad governance change is proposed from one occurrence. Future
  work follows the existing chat-first checkpoint before commissioning design.

### FR-001 follow-up (2026-07-31)

- The remediation is now represented by `product-brief.md`: it is the explicit
  human-review-pending input before the stale candidate-search contract and
  design artifacts may be replaced.
- The replacement order is recorded in `activeContext.md`: Product Brief
  review, then contract/ADR revision, then design reconciliation. No external
  design commissioning is authorized by this follow-up.

### FR-001 follow-up (2026-07-31, Product Brief approval)

- The Product Brief was approved in chat before the candidate-search contract
  and ADR were rewritten. The replacement contract now remains a separate
  human-review proposal, and the stale design brief/preview remain untouched.
- This completes the documented sequencing remediation for this occurrence;
  future design work still waits for approval of the replacement contract.

## FR-002: 認証受け入れテストに必要な Given seam を契約せず、L4 実装が停止した

```yaml
id: FR-002
date: 2026-08-01
found_at: L4
slice: TDR-AUTH
agents: [architect, developer, tester]
cause_category: L4 test infrastructure contract missing
cause_key: l4-given-seam-contract-missing
pushed_to:
  - projects/toyama-dining-radar/contracts/test-support-api.yaml
  - projects/toyama-dining-radar/ARCHITECTURE.md
status: 対応済み
principles: [P-02, P-03, P-04, P-10]
```

- Situation: The approved authentication scenarios require synthetic account creation, account deactivation, scenario isolation, and a deterministic throttled-sign-in state. The authentication contracts defined only browser-facing behaviour, so developer and tester had no machine-readable agreement for the acceptance-only Given seams required to execute L4.
- AI contribution: The authentication implementation slice was started without projecting those non-public setup and observation boundaries into a test-infrastructure contract. This made the L4 blocker discoverable only after implementation work had begun.
- Downward push: `contracts/test-support-api.yaml` is now the ADR-0008 SSoT for the three minimal acceptance-only seams. `ARCHITECTURE.md` makes the public-boundary versus Given-seam split explicit. The seam is deliberately limited to synthetic authentication state; it neither extends the business API nor changes the approved acceptance scenarios.
- Result: Developer and tester can consume the same original OpenAPI file for the implementation and DSL sides. Exact production throttle values remain outside the contract, while TDR-AUTH-07 becomes deterministic.

## FR-003: Given seamだけを先に補い、browser操作とlocal/deploymentの観測境界を契約しなかった

```yaml
id: FR-003
date: 2026-08-01
found_at: L4
slice: TDR-AUTH
agents: [architect, developer, tester]
cause_category: L4 browser observation contract missing
cause_key: l4-browser-observation-contract-missing
pushed_to:
  - projects/toyama-dining-radar/adr/0007-separate-local-auth-verification-from-deployment-transport.md
  - projects/toyama-dining-radar/contracts/authentication-browser-interface.yaml
  - projects/toyama-dining-radar/contracts/test-support-api.yaml
  - projects/toyama-dining-radar/ARCHITECTURE.md
status: 対応済み
principles: [P-01, P-03, P-04, P-10]
```

- Situation: After the Given seams were specified, the local authentication slice still lacked a shared browser control surface and a way to distinguish local HTTP acceptance execution from the deferred public HTTPS transport. Isolated developer and tester could not determine which UI states, security observations, and verification layer applied to each TDR-AUTH scenario.
- AI contribution: The first remediation treated L4 setup as the only missing interface. It did not also contract the browser operation/observation side or explicitly project the local/deployment split that the human had to resolve.
- Downward push: ADR-0007 records the human resolution. `authentication-browser-interface.yaml` is the acceptance-only SSoT for test IDs, browser outcomes, profile split, and security observations; `test-support-api.yaml` exposes only the effective local acceptance security boundary for L3. The deployment transport remains out of this local slice.
- Result: Browser L4 and configuration L3 can now be implemented independently without source-code knowledge, while an HTTP localhost run cannot be misreported as public HTTPS verification.

### FR-003 follow-up (2026-08-01, tester audit)

- The first browser-interface draft named controls and observations but omitted the isolated runner's entry URL. That still left the tester unable to reach the sign-in/protected surface without inspecting implementation routes.
- `authentication-browser-interface.yaml` now makes `TDR_ACCEPTANCE_BASE_URL` plus `/` the only local acceptance entry, with required unauthenticated/authenticated outcomes. The same entry states where public-sign-up and email-reset controls must be absent. This is a test-harness boundary only; it does not choose a public origin or deployment route.

### FR-003 follow-up (2026-08-01, independent acceptance review)

- The independent reviewer found that several approved outcomes still had no stable machine-readable observation: candidate/map/lens/private-origin absence, persistent-session proof, individual-account guidance, reset-operation absence, first-request deactivation ordering, complete generic/throttled disclosure checks, and the exact candidate-error schema reference.
- `authentication-browser-interface.yaml` now defines only those missing observables: forbidden surface test ids and synthetic disclosure canaries, same-cookie entry reopen, individual-account guidance, absent-operation route probes, the required first post-deactivation request order, unknown-versus-disabled response comparison in both failure states, and `ProblemResponse` schema references. No business scenario, public candidate API shape, or local/deployment split changed.

### FR-003 follow-up (2026-08-01, TDR-AUTH-02 acceptance review remediation)

- The independent reviewer found that the opaque
  `auth-individual-account-guidance` control id alone did not make the
  approved no-credential-sharing outcome observable. Naming a control is not
  an assertion of its meaning.
- `authentication-browser-interface.yaml` now requires a machine-readable
  semantic state on that existing control: `individual-only` account use and
  `not-requested` credential sharing. The assertion uses `data-*` attributes
  so it does not prescribe visible copy, layout, or a new browser operation.
  No business scenario, public API, or authentication policy changed.

## FR-004: browser-interface契約が実行モデル（サーバ描画かクライアントJS描画か）を明示せず、L4が8/9シナリオで観測不能になった

```yaml
id: FR-004
date: 2026-08-04
found_at: L4
slice: TDR-CS
agents: [architect, developer, tester]
cause_category: L4 test infrastructure contract incomplete (execution model)
cause_key: l4-render-model-not-contracted
pushed_to:
  - projects/toyama-dining-radar/adr/0009-adopt-js-capable-browser-automation-for-candidate-search-l4.md
  - projects/toyama-dining-radar/ARCHITECTURE.md
status: 対応済み
principles: [P-02, P-05, P-10]
```

- Situation: `candidate-search-browser-interface.yaml`（PR #76）は control surface の語彙（test id・
  属性・状態遷移）を定義したが、その語彙をどの実行モデル——サーバ応答時点のHTMLか、クライアントJS
  実行後のDOMか——で観測するかを明示しなかった。tester はTDR-AUTHの先例（プレーンHTTP＋HTMLパースで
  足りた）をそのまま踏襲してstep定義を書き、developer は tester と共有コンテキストを持たずに並行して
  候補提案画面全体をクライアントレンダリングで実装した。両者は独立に別々の前提を選び、L4実行で
  17件中8件fail・2件skipという形で食い違いが露見した。
- AI contribution: 契約起草時（architect、PR #76）、ADR-0005（モーダル置換はdocument navigationを
  伴わない）とADR-0008（比較状態はブラウザのJS実行コンテキストだけに存在しサーバへ送らない）は既に、
  少なくとも再提案の置換と再表示降格がクライアント側JavaScriptなしに実現できないことを含意していた。
  それにも関わらず、browser-interface契約はこの実行モデル前提を機械可読な形で固定しなかった。
  tester側もTDR-AUTHの先例をこのスライスの契約に対して再検証しなかった。
- Downward push: ADR-0009が実行モデル（JS実行可能なブラウザ自動化）を確定し、既存契約の語彙が
  そのまま十分であることを確認した。今後、browser-interface契約の control surface が
  `publicOperation` を伴わない状態変化（クライアントJSだけで完結する操作）を含む場合、architectは
  起草時点でその実行モデル前提（サーバ描画で足りるか、JS実行可能なツールを要するか）を契約本文に
  明示する。
- Result: TDR-CS-00〜08 はADR-0009の執行モデルのもとで観測可能になる。承認済み契約の再起草は不要
  だった。

## FR-005: browser-interface契約のnullBehaviorが、既に承認済みだった画面設計の表示整形（総席数の単位付与）を確認せず、可視値の厳密等価を全フィールドに一律要求した

```yaml
id: FR-005
date: 2026-08-05
found_at: L4
slice: TDR-CS
agents: [architect]
cause_category: contract drafted without checking an already-approved conflicting artifact
cause_key: card-field-equality-rule-vs-approved-display-formatting
pushed_to:
  - projects/toyama-dining-radar/contracts/candidate-search-browser-interface.yaml
  - projects/toyama-dining-radar/adr/0011-separate-visible-formatting-from-raw-value-equality-for-total-seats.md
status: 対応済み
principles: [P-02, P-06, P-08, P-10]
```

- Situation: `candidate-search-browser-interface.yaml`（PR #76、2026-08-03起草）の
  `cardDataAttributes.nullBehavior` は、必須の8フィールド全てに一律で「非nullの値は可視値が返却値と
  厳密に等しい」と定めた。しかし承認済みの画面設計（`CandidateSearchPreview.tsx`、PR #66、
  2026-08-01承認）は既に350行目で `totalSeats` を `` `${candidate.totalSeats}席` `` と単位付きで
  描画していた——これはPR #76の起草より前に人間承認済みの成果物だった。加えて、
  `design/reconciliation/candidate-search.md`（2026-08-01、本ADRのさらに前）は round-1の突き合わせで
  既に「APIは `integer | null` であり、表示時にのみ『席』を付けるべきfieldである」と記録しており、
  totalSeatsが表示時だけ単位を持つ特殊フィールドであることは文書化済みだった。architectは契約起草時
  にこの2つの既存成果物を突き合わせず、8フィールド一律の厳密等価ルールを書いた。L4
  （ADR-0009で有効化したJS実行可能なブラウザ自動化）が実画面に対して実行して初めてこの矛盾
  （画面は`38席`、契約は`38`との厳密一致を要求）が発覚した。
- AI contribution: 既に承認済みだった2つの成果物（画面設計、突き合わせ文書）を、新しい契約
  （browser-interface.yaml）のnullBehavior起草時に確認しなかった。developerは承認済み画面設計に
  忠実に実装し、testerは契約に忠実にassertしており、どちらの誤りでもない——見落としは契約起草の
  時点にある。
- Downward push: ADR-0011が人間裁定（可視テキストとは別の機械可読属性 `data-raw-value` で
  厳密等価を検査し、可視値には表示整形を許す。案A採用、案B・Cは却下）を記録する。
  `candidate-search-browser-interface.yaml` の `totalSeats` フィールドが
  `rawValueAttribute: data-raw-value` を宣言し、nullBehaviorがこの例外を明示する。
- Result: 今後、architectは契約が可視値の厳密等価を要求する箇所を起草する際、その表示を担う
  既承認の画面設計（design-preview配下、または実装済み画面）や既存の突き合わせ文書に、単位・整形
  などの表示上の差異が既に記録されていないかを確認する。

## FR-006: activeContextの承認記録を「マージ後に偽になる文面」で書き、マージ直後に2本目のPRが要る状態を作った

```yaml
id: FR-006
date: 2026-08-05
found_at: L5
slice: TDR-CS
agents: [orchestrator]
cause_category: 記録の書き方が承認行為の時点に依存している
cause_key: record-update-needs-second-pr
pushed_to:
  - projects/toyama-dining-radar/activeContext.md
status: 対応済み
principles: [P-04, P-11]
```

- Situation: TDR-CS実装PR（#82）に載せた `activeContext.md` の承認記録を、orchestratorが「**Awaiting approval in the open pull request**」「Next work: 人間承認とマージを得ること」と書いた。ADR-0035 方式(i)では承認行為の実体がそのPRのマージであるため、マージが成立した瞬間にこの2文は事実でなくなり、記録を直すためだけの2本目のPRが必要になった。
- AI contribution: orchestratorが、記録の文面を**書いている時点の状態**（まだ承認されていない）で固定した。方式(i)を採る以上、記録は**マージ前後のどちらでも真である**書き方——「本PRのマージをもって確定する」——にできたし、契約・ADR側では実際にその書き方をしていた（`.feature` のステータス行、ADRの `approved_by`）。activeContextにだけ同じ配慮が及ばなかった。
- Downward push: `activeContext.md` の承認記録を、マージ済みの事実として述べる形に直した。cause_key は reservation-system の FR-015・FR-021 と**意図して揃えた**。対象文書は違う（あちらはADR・契約の承認記録、こちらはactiveContext）が、機構は同一である——「承認行為はマージであり、記録を書けるのはマージ前」という時間差を、文面の書き方で吸収しそこねると2本目のPRが要る。
- Result: リポジトリ全体でこのcause_keyは3回目である。ただし**govlintのcause_key再出現検出はfriction-logファイル単位**であり、プロジェクトを跨いだ再出現を数えられない（ルート `activeContext.md` に既知の穴として記録済み）。したがってこの3回目は機械には見えず、人間が突き合わせない限り「toyama-dining-radarでの1回目」としか映らない。

## FR-007: Django's single-line-only `{# #}` comment syntax was used across multiple lines, and no machine check read rendered output for stray template delimiters

```yaml
id: FR-007
date: 2026-08-06
found_at: L5
slice: TDR-CS
agents: [developer]
cause_category: implementation defect invisible to existing test assertions
cause_key: template-comment-syntax-not-multiline
pushed_to:
  - projects/toyama-dining-radar/tests/test_template_syntax.py
status: 対応済み
principles: [P-01, P-10]
```

- Situation: While implementing ADR-0013's authenticated-header changes, developer wrote three
  explanatory comments in `web/templates/web/home.html` using Django's `{# ... #}` syntax spread
  across multiple lines. Django's template tokenizer matches `{#...#}` with a regex that has no
  `DOTALL` flag, so `.` never matches a newline; a `{#` left unclosed on its own line is therefore
  not recognized as a comment tag at all. The literal `{#`, the intended comment body, and the
  eventual `#}` all rendered as ordinary page text. This inflated the authenticated header from
  78px to 755px and pushed the map from 279px down to 919px (measured by orchestrator on a real
  device at 390×844, after ruling out dev-server template caching as the cause).
- AI contribution: developer used the single-line-only comment form for genuinely multi-line
  explanatory text, instead of `{% comment %}...{% endcomment %}` (which Django does support across
  lines). No existing test caught it: unit/L4 assertions check for the *presence* of specific
  substrings and test ids (`assertContains`, acceptance `present`/`absent` observations), which
  still hold when unrelated extra text also renders, and nothing read rendered output for stray
  template delimiters. Developer's own verification reports across this refinement had repeatedly
  and correctly flagged visual layout/pixel results as "unverified, no browser access from this
  role" -- that caveat is exactly what let a defect of this shape through every layer developer
  could self-check.
- Downward push: `tests/test_template_syntax.py` adds two guards. A source-level check
  (`SingleLineCommentSyntaxSourceTests`) reads every `.html` template's raw text and fails if a
  `{#` is not closed by `#}` on the same line, independent of whether any current view test
  happens to render that template. A rendered-output check (`RenderedTemplateSyntaxLeakTests`,
  defense in depth) fetches the login, authenticated-home, and password-change pages and asserts
  the response body never contains a raw `{#`, `#}`, `{% comment %}`, or `{% endcomment %}`. Both
  were verified to actually catch the original defect shape before being relied on.
- Result: this is the same class of failure FR-004 named -- a defect that is silent until an
  execution model machine verification does not cover is exercised (there, JS execution; here,
  reading rendered bytes for stray delimiters instead of only checking for expected substrings).
  The gap is now closed for this specific defect shape at L1 (source- and rendered-output checks),
  pushed below the layer (L5, real-device review) that first found it, per P-10.

## FR-008: FR-006で「記録の書き方を直す」と押し下げた直後の次スライスで、同じ失敗を繰り返した

```yaml
id: FR-008
date: 2026-08-06
found_at: L5
slice: TDR-CS-refinement
agents: [orchestrator]
cause_category: 記録の書き方が承認行為の時点に依存している
cause_key: record-update-needs-second-pr
pushed_to:
  - projects/toyama-dining-radar/activeContext.md
status: 対応済み
principles: [P-04, P-10, P-11]
```

- Situation: FR-006（PR #83）で、orchestratorは「activeContextの承認記録をマージ後に偽になる文面で書いた」ことを記録し、押し下げ先を「マージ前後のどちらでも真である書き方にする」とした。**その次のスライス（PR #84）で、同じorchestratorが再び「The candidate-card refinement slice is complete and **awaits approval**」「候補カードの洗練スライスが**PR中**」と書き、マージ成立と同時に3箇所が偽になった。**
- AI contribution: FR-006の押し下げが**書き手の注意に依存する規約**だったこと。規約は同じ書き手が同じ文脈で1スライス後に破っており、注意による是正が機能しないことを実測した。cause_keyはリポジトリ全体で**4回目**（reservation-system FR-015・FR-021、当プロジェクトFR-006、本件）。
- Downward push: 規約を「真になる書き方をする」から**「そもそも書かない」**へ変えた。`activeContext.md` に**進行中PRの承認ステータスを書かない**——その事実はPR・ADRのfrontmatter・gitが既に所有しており、複製は必ずドリフトする（P-04）。activeContextは「何が存在するか」を書き、承認記録は承認行為が起きる場所に置く。この規約を activeContext 自身の中に明記した（規約を守る場所と規約を書く場所を一致させ、次の書き手が読まずに済ませられないようにした）。
- Result: 「書き方に気をつける」から「書く対象を減らす」へ移した。ただし**これも機械検証ではない**——govlintはGitHubのPR状態を知らないため、この種の陳腐化を機械的に検出できない。4回目にして初めて「注意では直らない」ことが実測できたので、5回目が起きたら規約ではなく機構（例: activeContextから承認ステータス節そのものを廃し、承認記録をADRのfrontmatterに一本化する）を検討すべきである。

## FR-009: `candidate.js`がクライアント描画の唯一の担い手として3スライス育つ間、既に一般定義済みだったフロントエンドL1（単体テスト・lint）が一度も適用・指摘されなかった

```yaml
id: FR-009
date: 2026-08-06
found_at: L5
slice: TDR-CS
agents: [architect, developer]
cause_category: existing general verification rule not applied when a client-rendering satellite was introduced
cause_key: client-js-l1-not-provisioned
pushed_to:
  - projects/toyama-dining-radar/adr/0014-establish-client-js-unit-verification-layer.md
  - projects/toyama-dining-radar/ARCHITECTURE.md
status: 対応済み
principles: [P-01, P-02, P-05, P-10]
```

- Situation: `meta/verification.md` §4は、フロントエンドのL1手段を「単体テスト、lint」と既に一般的に
  定義していた。`candidate.js`はADR-0009（TDR-CS本体スライス）で候補提案画面の唯一の描画手段として
  生まれ、以後ADR-0012・ADR-0013の2回の洗練スライスを経て543行（13関数の単一IIFE）まで育ったが、
  この間L1に相当する機械検証（単体テスト・lint）は一度も導入されなかった。`reviews/audit-tdr-cs.md`・
  `reviews/audit-pre-live-data.md`を含む複数回の監査でもこの欠落は一度も指摘されず、orchestratorが
  Python側との定量比較（単体テスト0件・mutation対象外・行数543行）を行って初めて可視化された。
- AI contribution: architectはADR-0009起草時、L4（JS実行可能なブラウザ自動化）の欠落だけを問題として
  扱い、`meta/verification.md`が既に一般的に要求していたL1（フロントエンド単体テスト）をこのファイルに
  適用する決定を同時に起こさなかった。developerは以後2回の実装スライス（ADR-0012・ADR-0013）でこの
  ファイルを合計数百行分成長させたが、いずれのスライスの検証申告（`meta/adr/0039`）も、Python側と
  同様の単体テストをJS側に求めなかった。どちらの役割も個別には既存規律に反していない（L1はdeveloperの
  領分だが、契約・検証要件の起草時にその適用漏れを最初に指摘すべき立場はarchitectでもある）が、
  結果として3スライスにわたり誰も指摘しなかった。
- Downward push: `adr/0014`がこのプロジェクトにL1（JS単体検証層）を確立し、`ARCHITECTURE.md`の
  検証境界節に反映した。カバレッジ・mutationの数値基準はPython側と同じ床（branch coverage 90%・
  mutation score 80%）とし、実ブラウザ依存で原理的に検証不能な範囲は名指しで除外できる。
- Result: `candidate.js`のL1ゲート自体（実際のテストスイート・CIジョブの追加）は本FRの時点では
  未着手であり、developerの次の実装スライスに委ねられる——本FRが閉じるのは「この欠落を認識し、
  是正の方針を確定した」という統治面までである（`reservation-frontend`のFR-002〜005が同種の順序
  ——ADR・契約の確定を「対応済み」とし、実装の着地は後続スライスに委ねる——を採っている先例に倣う）。

## FR-010: ADR-0015が`IZAKAYA_BAR_INCLUDED`を追加した際、`reProposalOptions.maxItems: 3`との容量衝突を確認しなかった

```yaml
id: FR-010
date: 2026-08-08
found_at: L5
slice: TDR-CS
agents: [architect]
cause_category: new contract enum member added without checking interaction with an existing fixed-size array constraint
cause_key: concept-kind-addition-vs-reproposal-cap-unchecked
pushed_to:
  - projects/toyama-dining-radar/adr/0016-retire-genre-variety-for-try-again-and-fix-reproposal-capacity.md
  - projects/toyama-dining-radar/contracts/candidate-search-api.yaml
status: 対応済み
principles: [P-02, P-08, P-10]
```

- Situation: ADR-0015（2026-08-07）は実データレビューを受けて`ConceptKind`へ5番目の値
  `IZAKAYA_BAR_INCLUDED`を追加し、「非拘束の見解として…他の4切り口より低い優先順位に置くことを
  推奨する」とした。しかし`candidate-search-api.yaml`の`reProposalOptions`は既に`maxItems: 3`
  という固定容量制約を持っており、`ConceptKind`が5種類、表示中の1つを除いた残りが最大4つになる
  以上、優先順位を最後に置いたことと`maxItems: 3`の組み合わせは、5つ全てがビルド可能な母集団では
  `IZAKAYA_BAR_INCLUDED`が常に切り捨てられることを**単純な計数だけで**含意していた。これは実データを
  必要としない論理的な帰結だったが、ADR-0015はこの容量衝突を一度も検討・言及しなかった。orchestratorが
  2度目の実機レビューで、実際に`IZAKAYA_BAR_INCLUDED`が一度もAPI応答に現れないことを計測して初めて
  発覚した（`adr/0016`文脈節）。
- AI contribution: architect（ADR-0015起草時）は、`ConceptKind`へ新しい値を追加する決定と、
  `reProposalOptions.maxItems: 3`という既存の固定容量制約が同じ契約内に共存することの相互作用を
  確認しなかった。「優先順位はpipeline実装の詳細であり本ADRは拘束しない」という留保はあったが、
  その留保自体が容量超過という契約レベルの帰結を隠す形になった——優先順位をどこに置いても、
  5種類中4つを提示しようとする限り必ず1つが切り捨てられるという事実は、優先順位の値によらず
  常に成立する契約構造上の問題であり、pipeline実装の詳細ではなかった。
- Downward push: `adr/0016`が`GENRE_VARIETY`の削除により`ConceptKind`を4種類へ戻し、表示中の1つを
  除いた残りが常に`maxItems: 3`に収まる構造にした。将来`ConceptKind`に新しい値を追加するarchitectは、
  追加後の総数から表示中の1つを引いた値が`reProposalOptions.maxItems`に収まるかを明示的に確認する
  ことを`adr/0016`決定4に申し送りとして記録した。
- Result: 本件は「新しいenum値の追加」と「既存の固定容量スキーマ制約」という、今後も繰り返しうる
  組み合わせの一般的な見落としパターンである。次に同じ形の追加が起きた場合、この確認を怠らないことが
  再発防止の実体であり、今回は機械的な検査（例えばenum数と`maxItems`の関係を検証するgovlintルール）
  までは導入しない——単一契約ファイル内の2つの数値の関係をチェックする汎用ルールの費用対効果は、
  再発時に判断する（P-05）。

## FR-011: ADR-0015が表示上限を5件に絞った際、それがADR-0008決定2の再表示降格を無効化することを、ADR-0015・ADR-0016いずれの起草時にも確認しなかった

```yaml
id: FR-011
date: 2026-08-08
found_at: L5
slice: TDR-CS
agents: [architect]
cause_category: existing contract constraint changed without checking its interaction with a mechanism defined in a different, unrelated ADR
cause_key: display-cap-silently-disables-repeat-demotion
pushed_to:
  - projects/toyama-dining-radar/adr/0017-move-repeat-demotion-to-server-and-remove-business-hours.md
  - projects/toyama-dining-radar/contracts/candidate-search-api.yaml
status: 対応済み
principles: [P-02, P-08, P-10]
```

- Situation: ADR-0015（2026-08-07）は`CandidateConcept.candidates.maxItems`を100から5へ改め、
  「これは表示上限であり、取得・順位付け対象の上限ではない」と明記した。しかしこの変更以前は、
  応答が最大100件を運びうる一方で表示は一部だけだったため、ブラウザは表示していない候補を手元の
  メモリに保持でき、ADR-0008決定2の「同一画面のメモリだけで既表示候補を判定し降格する」機構は
  6位以下の候補をのちの再提案で繰り上げる余地を持っていた。ADR-0015が応答の実運搬件数を表示件数
  ちょうどの5へ絞った時点で、ブラウザは表示分より多くの候補を一度も受け取らなくなり、
  ADR-0008決定2の降格機構は「5件の中で並べ替える」以上のことができなくなった——これは実データを
  要さない論理的帰結だった。同日に「もう一度探す」を追加したADR-0016も、この機構が「既存の
  再表示降格（ADR-0008決定2）だけに頼る」と明記しながら、その機構が既に機能条件を失っていることを
  確認しなかった。3度目の実機レビュー（`adr/0017`文脈1節）で、「もう一度探す」を2回押しても候補が
  完全に同一・同順序になることが計測されて初めて発覚した。
- AI contribution: architectは、ADR-0015起草時に`candidates.maxItems`を変更する決定と、ADR-0008
  決定2という**別のADRが定めるブラウザ専用アルゴリズム**への影響を確認しなかった。ADR-0016起草時にも、
  「既存の再表示降格に頼る」と書きながら、その機構が実際に機能する前提（表示分より多い候補をブラウザが
  保持していること）をADR-0015が既に崩していたことを再検証しなかった。本件はFR-010（`ConceptKind`
  追加時に`reProposalOptions.maxItems`との衝突を確認しなかった）と同じ**種類**の見落とし——契約の
  一部を変更する際、それに依存する別の機構への影響を確認しない——だが、機構自体は異なる（FR-010は
  同一契約ファイル内のenum数と配列上限の関係、本件は表示上限という容量系フィールドと、別ADRが定める
  ブラウザ専用アルゴリズムの関係）ため、cause_keyは新規に発行する。
- Downward push: `adr/0017`が再表示降格の実施主体をブラウザからサーバへ移し、サーバが取得・
  ランキング済みの母集団全体（5件への切り詰め前）から毎回選び直す構造にした。これにより、表示上限を
  何件に設定しても、母集団に未表示の候補が残る限り降格が機能する——表示上限の値と降格機構の可用性が
  構造的に分離された。
- Result: 「表示上限のような容量系フィールドを変更する際は、それに依存する別の機構（今回は
  再表示降格）が存在しないかを確認する」ことを、以後の同種変更で確認事項として扱う。機械的な検査
  （例えば契約ファイル横断で「表示件数を絞る変更」と「既存の降格・並べ替えアルゴリズムの前提」の
  依存関係を検出するgovlintルール）は導入しない——契約ファイルをまたぐ暗黙の依存関係を汎用検出する
  費用対効果は、再発時に判断する（P-05、FR-010と同じ判断）。

## FR-012: ADR-0019決定8で、architectが自身のセッション内追記をADR-0019自身の根拠として循環的に引用し、予算感の表示を不当に全面却下した

```yaml
id: FR-012
date: 2026-08-09
found_at: AI
slice: TDR-CS-field-refinement
agents: [architect]
cause_category: 契約の除外根拠として、同一ドラフト内で自ら書き足した文をあたかも独立した既存決定であるかのように引用した
cause_key: adr-cites-own-session-edit-as-independent-precedent
pushed_to:
  - projects/toyama-dining-radar/adr/0019-refine-comparison-lenses-and-card-fields-from-field-survey.md
  - projects/toyama-dining-radar/product-brief.md
status: 対応済み
principles: [P-01, P-06, P-08, P-10]
```

- Situation: ADR-0019のドラフト（実データのフィールド調査を受けた切り口・カード項目の再設計）で、
  architectは人間が併記した2つの予算感の扱い方——(a) ランチ1000円以下を見通す推論、(b) 段階に分けて
  予算感をディナー予算と明示して見せる——のうち、(a)は確認できない事実の断定になるため妥当に不採用と
  したが、**(b)も含めて全面不採用**と判定した。その根拠として`product-brief.md` §3・§7が
  「既に持つ明確な除外決定」を挙げたが、その除外記述の一部（「実データのフィールド調査で価格帯情報
  自体は取得できることが確認できたが…ADR-0019。理由はADR-0019決定8を参照」）は、**同じドラフト作業の
  中でarchitect自身が新たに書き足した文であり、ADR-0019自身を根拠にADR-0019の結論を正当化する
  循環になっていた**。
- AI contribution: architectは、`product-brief.md`の既存の除外記述（このセッション以前から実在した
  「価格帯は Hot Pepper の情報がディナー寄りであるため表示しない」という文）と、自分が今回のドラフトで
  同じ節に書き足した文（ADR-0019を参照する新規の一節）を区別せず、両者をまとめて「既に持つ明確な
  除外決定」として引用した。これは根拠の出所を検証せずに引用した誤りであり、P-06（決定は新しい決定で
  置き換える。古い記述を信じる事故を防ぐ）が防ごうとする事故の一種——ただし今回は「古い記述」ではなく
  「自分がたった今書いた記述」を、あたかも独立した先行決定であるかのように扱った点で、通常のP-06違反
  とは異なる新しい形である。
- Downward push: orchestratorがこの循環を検知し、人間へ事実を提示した。人間は「ざっくりの段階表示が
  できるなら入れてほしい」と回答し、決定8を差し戻した。ADR-0019決定8を全面書き換え、`dinnerBudgetTier`
  （ディナー予算をディナー予算と明示した3段階の粗い目安。ランチ価格は推論・断定しない）を採用する
  設計に改めた。`product-brief.md` §3・§7も、この差し戻しを反映して改訂する（人間の再承認点）。
- Result: 今後、architectが契約・ADRの除外根拠として「既存の決定」を引用する際は、その引用元の文が
  **本当に過去の別の作業で確定したものか、それとも今回のドラフト作業自身がその場で書き足したものか**
  を区別すること。同一PR・同一ドラフト内で書いた文を、独立した先行制約として自己引用してはならない。
  機械的な検査（例えば同一PR内の差分行を根拠として引用していないかを検出するgovlintルール）は
  導入しない——単発の推論エラーであり、再発時に費用対効果を判断する（P-05、FR-010・FR-011と同じ判断）。

## FR-013: ADR-0020のゲートが、非表示要素に対する未規定・環境依存のジオメトリ値に合否を乗せており、ローカルだけ緑になった

```yaml
id: FR-013
date: 2026-08-12
found_at: L5
slice: UI-HARNESS
agents: [developer]
cause_category: new verification gate made pass/fail depend on a browser API whose value is unspecified for the state being measured
cause_key: gate-depends-on-unspecified-browser-geometry
pushed_to:
  - projects/toyama-dining-radar/tests/ui_invariants/test_render_invariants.py
status: 対応済み
principles: [P-01, P-04, P-10]
```

- Situation: ADR-0020決定4(e)の44pxゲートは、`[data-candidate-control-purpose]`を持つ**すべての**要素を
  `bounding_box()`で測っていた。この集合には、閉じた`<details class="candidate-account-menu">`の中にある
  `auth-password-change-open`・`auth-sign-out`が含まれる（`renderModel`によりサーバレンダリングHTMLに
  存在するため）。閉じた`<details>`の非レンダリング内容に対する`getBoundingClientRect()`の値は仕様上
  規定されておらず、実測でWindowsは実寸（161×44）を返す実行とゼロを返す実行の両方があり、Ubuntu CIは
  一貫してゼロを返した。結果、developerのローカル検証（3回緑）とorchestratorの独立再実行（緑）を
  すり抜け、**PR #89のCIで初めて赤**になった。`is_visible()`は同じ状態に対し両環境で決定論的に`False`を
  返しており、判定に使える安定した観測面は最初から存在していた。
- AI contribution: developerは、新設するゲートの合否を、測ろうとしている状態（非レンダリング内容）に
  対して値が規定されていないAPIに乗せた。ゲートは「何を正しいと判定するか」を定める機構であり
  （`meta/permissions.md`）、その判定が環境依存であってよいかを設置時に確認しなかった。加えて、
  44px規則が対象とするのは決定4(e)が言う**活性化可能な**操作面であるのに、その時点で開示されていない
  操作面まで測っており、規則の対象範囲をテストが正しく写していなかった。orchestratorも、同一
  Chromiumバージョンでのローカル緑をもって通し、環境差の可能性を事前に潰さなかった。
- Downward push: `_assert_all_declared_controls_meet_44px`は、測定前に`is_visible()`で現に開示されて
  いる操作面だけに絞る。除外ではなく**開示フェーズへの先送り**であり、同メソッドは再提案ダイアログ・
  アカウントメニューを開いた後に同一テスト内で再度呼ばれるため、いずれの操作面もゲートから外れない。
  絞り込みがゲートを空虚にしないよう、各フェーズで実際に測った件数が0でないことを検証する
  （`checked > 0`）。orchestratorは、アカウントメニューのCSSを一時的に44px未満へ縮めて
  `auth-password-change-open height 25.59px < 44px (account menu open ...)`で赤化することを独立に確認し、
  先送り先で確かに測られていることを実証した。閾値の変更・アサーションの削除・恒久的な除外は行っていない。

## FR-014: orchestratorが、CIの全ジョブ結果を見ないままPRを「完了」として人間へ報告した

```yaml
id: FR-014
date: 2026-08-12
found_at: 人間
slice: UI-HARNESS
agents: [orchestrator]
cause_category: completion reported from a partial gate result instead of the full one
cause_key: orchestrator-reports-completion-before-gate-result
pushed_to:
  - projects/toyama-dining-radar/friction-log.md
status: 対応済み
principles: [P-01, P-07, P-10]
```

- Situation: orchestratorはPR #89を作成した直後に`gh pr checks`を一度だけ実行し、L0が`pass`・L1が
  `pending`・L2以降が未表示という**途中経過**を見た状態で、PRの内容と残課題を人間へ報告して締めた。
  その時点で新設したL5ジョブはまだ実行されておらず、実際には落ちていた。人間が「L5エラー出てますよ
  チェックしましたか」と指摘して初めて発覚した。
- AI contribution: `meta/adr/0027`は「緑CI以外の独立した根拠なしにagent成果物を通さない」と定め、
  `meta/adr/0039`決定1はorchestratorに機械検証の実行を義務づけている。orchestratorはローカルで全段を
  独立再実行しており、その根拠自体は満たしていた——しかし**新設したゲートはCI環境で初めて実行される
  ものであり、ローカルの緑はCIの緑を含意しない**。この非対称性が最も強く効く場面（環境が変わる新ゲートの
  初回実行）で、orchestratorは未完了のCIを待たずに報告した。「後で確認しますか」と申し出たことは、
  報告を完了として提示したことの免責にならない。
- Downward push: 新設・変更したCIジョブを含むPRでは、orchestratorは全ジョブが終了状態
  （`pass`/`fail`）になるまで完了報告をしない。本件は規程の新設ではなく既存規律（ADR-0027・0039決定1）の
  適用漏れであるため、新しい機構は足さない（P-05）。同種の再発が観測された場合は、報告前に全ジョブの
  終了を機械的に確認する手順の明文化を検討する。

## FR-015: ADR-0016が「人間がランダム性を却下した」と記録したが、同じ項に引用された人間自身の言葉はシャッフルの採用を提案していた

```yaml
id: FR-015
date: 2026-08-10
found_at: AI
slice: TDR-CS-filter-model
agents: [architect, orchestrator]
cause_category: 人間の裁定として記録した内容が、同じ記録に引用された人間自身の発言と矛盾しており、却下の理由も人間の理由ではなく既存文書の引用だけで構成されていた
cause_key: adr-records-rejection-contradicting-human-quoted-words
pushed_to:
  - projects/toyama-dining-radar/adr/0016-retire-genre-variety-and-add-same-lens-retry.md
  - projects/toyama-dining-radar/adr/0023-replace-concept-lenses-with-filters-sort-and-randomized-pool-selection.md
status: 対応済み
principles: [P-01, P-04, P-06, P-08, P-10]
```

- Situation: 2026-08-10、人間が「もう選び方の意義がないかもしれない」「ある程度ランダム性を持たせる
  ことはできそう？」と述べ、切り口モデルの廃止と無作為性の導入を求めた。ADR-0023のドラフトを作成した
  architectは矛盾分析の中で、これを「ADR-0016で人間自身がほぼ同じ提案を明示的に却下している」と指摘し、
  人間に過去の却下を読み直すよう再確認を推奨した。orchestratorがADR-0016の原文を確認したところ、
  **その指摘は記録の表面だけを読んだものであり、記録自身の内部矛盾を見落としていた**。
- AI contribution: ADR-0016は「orchestratorが提示した2案（(a)縮退時に提示しないだけにする／
  (b)毎回違う店が出るよう決定性を再検討する）をいずれも却下し」と書き、代替案節でも
  「**(b) 毎回違う店が出るよう決定性を再検討する**: 却下（人間裁定）」と記録している。しかし
  **同じ項に引用された人間自身の言葉は「そもそもシャッフルしてればジャンルもばらけるはずだから、
  選び方を廃止してシャッフル機能にするほうがいいかもしれないね／前回出した店舗は出さない
  （優先順位を下げる）の方針でどうかな」であり、シャッフルの採用と切り口モデルの廃止を提案している**。
  人間は無作為性を否定していない。さらに(b)の却下理由として記録されたのは
  「`product-brief.md`・`ADR-0004`・`ADR-0005`・`ADR-0008`・API仕様が確立した『決定的ルールだけで
  選ぶ』という要求と衝突する」——すなわち**既存文書の引用だけであり、人間自身が述べた理由は一つも
  記録されていない**。実際には、人間の2文目（既表示店舗の優先順位を下げる）だけが実装され、1文目
  （シャッフル）は実装されないまま「人間裁定による却下」として記録された。
- Downward push: orchestratorがADR-0016の原文（人間の引用を含む）を読み、architectの指摘を人間へ
  そのまま伝えず、記録の内部矛盾として提示した。ADR-0023は無作為性を導入する方向のまま進め、
  「過去に却下された提案の蒸し返し」という枠組みでは人間に提示しない。
- Result: FR-012（architectが自身のセッション内追記を独立した先行決定として自己引用した）と合わせ、
  **記録が人間の意思に反する権威を作り出す**という同じ結果を持つ2例目である。cause_keyは機構が
  異なるため分けたが、3例目が出たら共通ルールへ統合すること。今後、ADR・friction-logへ「人間裁定に
  よる却下」を記録するときは、(1)人間自身の言葉を引用し、(2)引用した言葉が却下と整合することを
  起草者が確認し、(3)却下理由に人間自身の理由を必ず1つ以上含めること——却下理由が既存文書の引用
  だけで構成されている場合、それは人間の裁定ではなく起草者の推論である。機械的な検査は導入しない
  （P-05、FR-010〜FR-012と同じ判断）。

## FR-016: ADR本文が「マージをもって承認」と宣言しているのにfrontmatterは`提案中`のまま提出され、記録を閉じるだけの2本目のPRが要った。同じcause_keyの5回目である

```yaml
id: FR-016
date: 2026-08-12
found_at: AI
slice: TDR-CS-filter-model
agents: [architect, orchestrator]
cause_category: 承認記録が承認行為の時点に依存しており、1本のPRで閉じられない
cause_key: record-update-needs-second-pr
pushed_to:
  - projects/toyama-dining-radar/adr/0021-adopt-free-render-neon-deployment-topology.md
  - projects/toyama-dining-radar/adr/0022-expose-identity-free-population-filter-attributes.md
  - projects/toyama-dining-radar/product-brief.md
status: 未対応
principles: [P-04, P-10, P-11]
```

- Situation: PR #90 は ADR-0021・0022・0023 の実装を`main`へ載せた。ADR-0021の本文は
  「本ADRはPRのマージをもって承認とする（ADR-0035方式(i)）」と自ら宣言し、ADR-0022も
  「承認記録はPR mergeまで作らない」と書いていた。ところが**両ADRのfrontmatterは
  `status: 提案中` / `approved_by: null` のまま提出された**。マージは起きたのに記録は
  閉じず、`status:`を書き換えるためだけの2本目のPR（本PR）が必要になった。ADR-0019は
  同じ状況で`status: 承認済み` / `approved_by: "本PRのマージをもって承認"`と先に書いて
  1本で閉じており、**その書き方はこのリポジトリに既に存在していた**。ADR-0043はまさに
  「承認記録をPR1本で閉じる」ために作られている。
- AI contribution: ADRの**本文とfrontmatterが食い違ったまま**提出されたこと。govlintが
  読むのはfrontmatterなので、機械は両ADRを「提案中のまま滞留」と報告し続けた——本文を
  読めば「マージ待ち」だと分かるのに、機械にはそれが見えない。起草者は宣言を散文で書いて
  満足し、機械が読む場所へ同じ宣言を書かなかった。
- あわせて記録する、より重い順序違反: **ADR-0023の実装が先に`main`へ載り、それと正面から
  衝突する既承認文書（`product-brief.md`「初期のコンセプト生成と順位付けは、説明可能な
  決定的ルールで行う」ほか）は、その時点で改訂されていなかった。** ADR-0023自身が方式(ii)
  を選び「人間が個別に再承認するまで承認済みにしない」と宣言していたにもかかわらず、実装だけが
  先行した。承認済み文書が実体と食い違う期間が実際に発生している。activeContextが既に
  記録しているとおり「未承認の契約に対する実装を止める機械的な仕組みは無い」。
- cause_keyの出現回数: リポジトリ全体で**5回目**（reservation-system FR-015・FR-021、
  当プロジェクト FR-006・FR-008、本件）。**FR-008はこの5回目を名指しで予告していた**——
  「5回目が起きたら規約ではなく機構（例: activeContextから承認ステータス節そのものを廃し、
  承認記録をADRのfrontmatterに一本化する）を検討すべきである」。予告どおり5回目が起きた。
- Downward push（人間の判断を要する）: 今回の形は機械検査に載る。**ADR本文が「マージをもって
  承認」の意を宣言しているのにfrontmatterが`提案中`のままなら、それはPR提出時点で既に矛盾で
  あり、govlintがERRORで落とせる**（本文の宣言文字列とfrontmatterの`status`の照合）。
  これは「書き手の注意」に依存しない。ただし`meta/tools/**`は`meta/adr/0046`で施錠されており、
  実装には人間の開錠コミットが要る。**この押し下げは提案であって実施ではない**——費用対効果と
  開錠の是非は人間が判断する。実施しない場合、6回目は同じ形で起きると予想する。

## FR-017: FR-016で押し下げ案を書いたその同じPRの中で、唯一開いていたADRに対して同じ手落ちを犯し、3本目のPRを要した

```yaml
id: FR-017
date: 2026-08-12
found_at: AI
slice: TDR-CS-filter-model
agents: [orchestrator]
cause_category: 承認記録が承認行為の時点に依存しており、1本のPRで閉じられない
cause_key: record-update-needs-second-pr
pushed_to:
  - projects/toyama-dining-radar/adr/0023-replace-concept-lenses-with-filters-sort-and-randomized-pool-selection.md
  - projects/toyama-dining-radar/activeContext.md
status: 未対応
principles: [P-04, P-06, P-10, P-11]
```

- Situation: PR #91 で orchestrator は FR-016 を記録し、「ADR-0019は`status: 承認済み` /
  `approved_by: "本PRのマージをもって承認"`と先に書いて1本で閉じており、その書き方はこの
  リポジトリに既に存在していた」と明示した。**その同じPRの中で、唯一まだ開いていた
  ADR-0023 に対して、その書き方を使わなかった。** ADR-0023の保留条件は「product-brief改訂の
  承認」であり、その改訂こそがPR #91の中身だったのだから、`approved_by: "PR #91のマージを
  もって承認"`と先に書けば1本で閉じられた。結果、`status:`を書き換えるためだけの3本目のPR
  （本PR #92）が必要になった。
- あわせて記録する2つ目の手落ち: PR #91 で orchestrator は activeContext へ
  「The brief's amendment **is in flight**」と書いた。**これはFR-008の押し下げ
  「activeContextに進行中PRの承認ステータスを書かない」の直接違反である。** 予告どおり、
  マージ成立と同時にこの一文は偽になった。
- AI contribution: **欠陥を正確に記述する能力と、同じ文書内でそれを回避する能力は別物である。**
  FR-016の本文は、正しい書き方・その所在（ADR-0019）・それが存在する理由（ADR-0043）まで
  正しく特定していた。にもかかわらず、同じ書き手が同じPRの中で、同じ種類の判断を誤った。
  FR-008は「規約は同じ書き手が同じ文脈で1スライス後に破っており、注意による是正が機能しない
  ことを実測した」と書いたが、本件はさらに強い——**1スライス後ですらなく、同じPRの中で破った。**
- cause_keyの出現回数: リポジトリ全体で**7回目**（reservation-system FR-015・FR-021、
  当プロジェクト FR-006・FR-008・FR-016、本件で6・7回目相当。FR-016が5回目、本件が
  6回目にあたる手落ちを2つ含むため、以後は件数ではなく「規約による是正は5回連続で失敗した」
  という事実として扱うこと）。
- Downward push: FR-016が提案した機械検査（ADR本文の宣言文字列とfrontmatterの`status`が
  食い違ったらgovlintがERROR）を、**提案から要請へ格上げする**。本件は「注意深く書けば防げた」
  という反証を自ら潰した——押し下げ案を書いている最中の書き手ですら防げないなら、規約に
  残す意味は無い。実施には`meta/adr/0046`が施錠する`meta/tools/**`の人間による開錠コミットが
  要るため、orchestratorは実装しない（施錠が防いでいる違反そのものになる）。**人間が開錠しない
  という判断もありうる**——その場合、この種の記録の遅れは「起きるもの」として受け入れ、
  friction-logへ数え続けるほうが、守られない規約を増やすより誠実である。

## FR-018: FR-016・FR-017が特定した書き方が目の前にあったのに使わず、同じcause_keyで記録を閉じるだけのPRをまた要した

```yaml
id: FR-018
date: 2026-08-20
found_at: AI
slice: TDR-CS-origin-and-walking-time
agents: [orchestrator]
cause_category: 承認記録が承認行為の時点に依存しており、1本のPRで閉じられない
cause_key: record-update-needs-second-pr
pushed_to:
  - projects/toyama-dining-radar/adr/0025-disclose-search-origin-and-walking-time-to-the-authenticated-screen.md
status: 未対応
principles: [P-04, P-06, P-10]
```

- Situation: orchestrator は ADR-0025 を `status: 提案中` / `approved_by: null` で起草し、PR #106
  として提出した。PRはマージされたが、ADRは「提案中」のまま残り、frontmatterを書き換えるだけの
  2本目のPRが要った。`meta/adr/0006` は「PRで提案するADRは、status を『承認済み』・approved_by を
  『本PRのマージをもって承認』と書いてよい」と明示しており、ADR-0016・ADR-0019・ADR-0023 に実例が
  あり、**FR-016 と FR-017 がまさにこの手落ちを2件連続で記録していた**。回避手段は規約・実例・
  直前の failure log の3方向から利用可能だった。
- AI contribution: FR-017 は「規約による是正は5回連続で失敗した」と結論し、以後は件数ではなく
  その事実として扱えと書いた。**本件はその宣言後の最初の機会で、6回目の失敗になった。** 本件に
  情状酌量の余地は無い——FR-017 が「押し下げ案を書いている最中の書き手ですら防げない」ことを
  示したのに対し、本件の書き手は friction-log を**読んでいなかった**。ADRを起草する前に
  friction-log を読む手順が存在しないことが、規約が届かない経路として実測された。
- cause_keyの出現回数: 規約による是正は**6回連続で失敗した**。
- Downward push: FR-016・FR-017 が提案し要請へ格上げした機械検査（frontmatterの`status`と
  ADR本文の宣言・マージ状態の食い違いをgovlintがERRORにする）を繰り返す。実施には
  `meta/adr/0046` が施錠する `meta/tools/**` の人間による開錠コミットが要るため、orchestratorは
  実装しない。**本件が付け加える情報は1点だけである**——FR-017 は「注意深く書けば防げる」の
  反証を提示したが、本件は**書き手が過去の記録に到達すらしない**経路を示した。したがって
  「ADR起草時にfriction-logを読む」という手順を足しても、その手順自体が同じ経路で忘れられる。
  人間が開錠しない判断もありうるが、その場合この種の記録の遅れは恒久的なものとして扱うべきで
  あり、規約側の文言追加はもう試すべきではない。

