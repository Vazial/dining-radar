---
id: 0009
scope: project/dining-radar
status: 承認済み
date: 2026-08-04
approved_by: "本PRのマージをもって承認（ADR-0035 方式(i)、人間裁定 2026-08-04: TDR-CSのL4はJS実行可能なブラウザ自動化を用いて実画面に対して実行する。却下: (B) 候補面をサーバレンダリングに寄せる／(C) 該当のThen節をL5走破に委ねる）"
supersedes: []
superseded_by: null
relates_to: [P-01, P-02, P-08, P-10, TDR-CS-00, TDR-CS-01, TDR-CS-02, TDR-CS-03, TDR-CS-04, TDR-CS-05, TDR-CS-06, TDR-CS-07, TDR-CS-08]
---

# ADR-0009: TDR-CSのL4はJS実行可能なブラウザ自動化で実画面に対して実行する

> **承認者向けサマリ**: 認証済みの候補提案画面は、サーバーが返す `<div id="candidate-app"></div>` という
> 空のマウント点だけを持ち、候補カード・地図・再提案モーダル・エラー表示はすべてクライアント側
> JavaScriptが生成する。tester のL4ツールはTDR-AUTHの先例に倣いプレーンHTTP＋HTMLパースで書かれており
> JSエンジンを持たないため、TDR-CS-01〜08（8シナリオ）が両者の正しさに関わらず観測不能になり、
> TDR-CS-00は「候補面が何もサーバ描画されないので何もしなくても通る」空虚な緑になっていた。人間は
> JS実行可能なブラウザ自動化（reservation-frontendのPlaywright先例と同型）を採用し、画面をサーバ
> レンダリングへ寄せる案と、該当Then節をL5走破に委ねる案を却下した。既存の
> `candidate-search-browser-interface.yaml`・`test-support-api.yaml` は内容として十分であり、
> 契約の文言変更は不要と判断する。`selectCard`/`selectMarker` に `publicOperation` が無いのは欠落では
> なく、選択のハイライトがブラウザ内だけの状態でありサーバ往復を伴わない（ADR-0008の原則と整合する）
> という意図された設計であることを、本ADRで明文化して以後の再エスカレーションを防ぐ。

## 文脈

### 1. 何が起きたか

orchestratorがTDR-CSのL4を実行した結果、17件中7 pass / 8 fail / 2 skipだった。

- `TDR-CS-01`〜`08` は、実装・step定義の正しさに関わらず観測不能である。認証済み画面のサーバ
  レンダリング結果には空のマウント点しかなく、候補カード・地図・再提案モーダル・エラー表示は実行時に
  client-side JavaScriptが生成するため、JSエンジンを持たないプレーンHTTP＋HTMLパースのツールでは
  これらのDOM状態を一切観測できない。
- 唯一通っている `TDR-CS-00`（未サインイン者に候補面を見せない）は、候補面が何もサーバ描画されない
  ため自動的に通っている。**実装が壊れていても緑になる**空虚な緑である。
- tester は独立に `TDR-CS-02`（カード↔マーカーの相互ハイライト）と `TDR-CS-03`（同一画面内の再表示
  降格順序）の2つのThen節を現行ツールでは実行不能として `skipTest` で明示しエスカレーションした。
  根拠は、`candidate-search-browser-interface.yaml` が他の操作（`initialProposal`・`submitReProposal`・
  `requestUnavailableEnumLens`）には `publicOperation` を宣言しているのに `selectCard`/`selectMarker`
  には宣言していないこと、およびADR-0008が再表示降格をブラウザ内メモリに限定しサーバへ送らないと
  定めていることである。
- developer が出す `data-testid` と tester が期待する `data-testid` は完全に一致している。ズレている
  のは「どこで出るか」（サーバ応答時点か、クライアントのJS実行後か）の一点だけである。
- L0・L1・L2・L3 は緑（単体100件、branch coverage 95%、mutation score 100%、構造6件、境界61件、
  `manage.py check` 両プロファイル）。ボトルネックはL4だけである。

### 2. なぜ契約の語彙のズレではなく執行モデルの欠落なのか

`candidate-search-browser-interface.yaml` は control surface の語彙（test id・属性・状態遷移）を
正しく定義している。tester が「現行契約はTDR-CS-00〜08を翻訳するのに十分」と独立に判定した事実
（`activeContext.md`）もこれを裏付ける。欠けていたのは語彙ではなく、**その語彙をどの実行モデル
（サーバ応答時点で存在するHTMLか、クライアントJS実行後のDOMか）で観測するかという前提**である。
ADR-0005（モーダル置換はdocument navigationを伴わない）とADR-0008（比較状態はブラウザのJS実行
コンテキストだけに存在しサーバへ送らない）は、契約起草時点（PR #76）で既に、少なくとも再提案の
置換と再表示降格はクライアント側JavaScriptなしに実現できないことを含意していた。しかし
`candidate-search-browser-interface.yaml` はこの実行モデル前提を明示せず、tester はTDR-AUTHの先例
（プレーンHTTP＋HTMLパースで足りた）をそのまま踏襲した。developer は tester と共有コンテキストを
持たずに並行作業し、初期表示を含む画面全体をクライアントレンダリングで実装した。両者が独立に
選んだ前提が食い違ったのは、契約がその前提を機械可読に固定していなかったためである。

## 決定

### 1. TDR-CSのL4は、JS実行可能なブラウザ自動化で実画面に対して実行する

TDR-CS-00〜08 の browser L4 は、`contracts/candidate-search-browser-interface.yaml` の control
surface と観測を、**実際にJavaScriptを実行する自動化ツール**（reservation-frontendの先例に倣えば
Playwright等。具体的なライブラリ選定はtester/orchestratorが行う）を用いて、サーバがレンダリングした
HTMLではなく**クライアント側JS実行後の実画面**に対して行う。既存の `contracts/test-support-api.yaml`
のacceptance-only seamと、既存のstep定義規約（分岐禁止・DSL経由・SUTの公開境界のみ操作、
`meta/verification.md` L4詳細）は変更しない。

### 2. 却下した代替案とその理由

- **(B) 候補面をサーバレンダリングに寄せる**: 少なくとも「別の切り口で再提案」の画面全置換
  （ADR-0005決定3、document navigationを伴わない）と、表示済み候補の再表示降格
  （ADR-0008決定2・3、ブラウザのJS実行コンテキストだけに存在しサーバへ送らない）は、承認済みの
  durable decisionが要求する振る舞いそのものがクライアント側の状態であり、サーバレンダリングへ寄せる
  ことは検証ツールの都合でADR-0005・0008を再び開くことを意味する。これはL4ツールの選定という
  検証設計の問題を、確定済みの製品体験の再決定にすり替える。
- **(C) 該当のThen節をL5走破に委ねる**: カード↔マーカーの相互ハイライト（`data-selection-state`）と
  再表示降格順序（`data-repeat-status` とその並び順）は、いずれもDOM属性の機械的な比較で判定できる
  ——意味理解や体験の質の判断を要さない。これは `meta/verification.md` §3.4／`meta/adr/0032` が
  L5走破の正当な用途として定める「意味理解が要る検証」「未知の帰結の1回限りの発見」のどちらにも
  当たらず、走破を安定した回帰ゲートに使うことになる（同ADRが明示的に禁じる用法）。加えて、
  観測不能なのは TDR-CS-02・03 の該当Then節だけでなく `TDR-CS-01`・`04`〜`08` も同様であり、(C)は
  問題の一部（2/9）にしか対応しない。

### 3. 既存契約への影響: 変更不要と判定する

- **`selectCard`/`selectMarker` に `publicOperation` が無いこと**: 欠落ではなく意図された設計である
  と確認する。カード・マーカーの選択ハイライトは、`openReProposal`（モーダルを開く操作）と同様に
  純粋なブラウザ内DOM状態の変更であり、サーバへの往復を伴わない。ADR-0008が定める「比較状態は
  ブラウザのメモリだけに存在する」原則と整合しており、`initialProposal`・`submitReProposal`・
  `requestUnavailableEnumLens` のように実際にHTTPリクエストを発生させる操作にだけ `publicOperation`
  が宣言されているという契約内の一貫したパターンからも裏付けられる。JS実行可能な自動化ツールは
  要素を直接クリックしDOM属性を観測できるため、`publicOperation` の有無に関わらず実行できる。
  本条により、この点についての再エスカレーションは不要と確定する。
- **`TDR-CS-02`・`TDR-CS-03` のThen節の観測可能化に契約追記は不要**: `browserControlSurface`・
  `browserActions` が既に定義する test id・属性（`data-selection-state`・`data-repeat-status`・
  `data-provider-page-href` 等）は、JS実行可能なツールがDOM上で直接観測できる形になっている。
  不足していたのは語彙ではなく実行モデルであり、決定1がそれを解消する。
- **承認済みシナリオ本文（`contracts/candidate-search.feature`）の変更は不要**: シナリオは業務の言葉
  だけで書かれており、レンダリング方式（サーバ／クライアント）のような技術的執行モデルへの言及を
  持たない。本ADRはシナリオの意味を変えない。**なお、将来もし本文の変更が必要と判断される場面が
  生じた場合、それは人間の再承認点である**（`meta/permissions.md` 契約行、AIによる契約ファイルの
  直接変更は禁止）。本ADRの範囲では該当しない。

### 4. 適用範囲

本ADRはTDR-CS（candidate-search）のL4に適用する。TDR-AUTH-01〜05・07は現行のプレーンHTTP＋HTMLパース
ツールで既に緑であり空虚な緑の兆候は報告されていないため、本ADRはTDR-AUTHへ遡及適用しない。将来別の
スライスで同種のクライアントレンダリング画面が現れた場合、その時点で同じ判断を独立に行う（P-02）。

## 検討した代替案

代替案の内容と却下理由は決定2に記載した。

## 帰結

- TDR-CS-00〜08 が実際に機械実行され、`TDR-CS-00` の空虚な緑が解消される。
- tester は既存の `candidate-search-browser-interface.yaml`・`test-support-api.yaml` を書き換えずに
  step定義とDSLをJS実行可能なツール向けに書き直す。新規・変更されたstep定義とDSLの差分は、
  `meta/verification.md` L4詳細(2)の対訳表つき人間承認を要する（既存ルールの適用であり本ADRが
  新設するものではない）。
- CI（`.github/workflows/ci-dining-radar.yml`）へのブラウザバイナリ導入・L4ジョブ追加と、
  Python側の開発依存追加（`pyproject.toml` dev extras）はorchestrator/tester側の実装作業であり、
  本ADRの範囲外（architectは`.github/workflows/**`を編集しない）。reservation-frontendの
  `ci-reservation-frontend.yml` L4ジョブ構成が参照可能な先例である。
- ARCHITECTURE.mdの検証境界（L4）節に、TDR-CSがクライアントレンダリングでありJS実行可能な自動化で
  検証する旨を追記する（本PRに同梱）。
- friction-logに、契約起草時に実行モデル前提を明示していなかった見落としを記録する（本PRに同梱、
  cause_key: `l4-render-model-not-contracted`）。
