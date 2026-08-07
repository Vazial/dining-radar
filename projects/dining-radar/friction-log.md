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
