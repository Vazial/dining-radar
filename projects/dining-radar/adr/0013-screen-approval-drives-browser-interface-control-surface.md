---
id: 0013
scope: project/dining-radar
status: 承認済み
date: 2026-08-06
approved_by: "本PRのマージをもって承認（ADR-0035 方式(i)、人間裁定 2026-08-06 chat: 実機レビューの3指摘（管理者案内の縮小、パスワード変更/サインアウトの整理、別の選び方ボタンの配置）はいずれも修正OK。方針表明: 『全て修正OKだし、画面的に自然にするために契約の変更が必要になるならOK、のスタンスです』『画面が承認されたら契約も変更する、でいいのでは？』『少なくとも画面が契約に引っ張られるべきではない（モックの時点でそこまで詰められていないのがむしろ問題か？）』）"
supersedes: []
superseded_by: null
relates_to: [P-01, P-02, P-06, P-07, P-08, P-10, TDR-AUTH-02, TDR-AUTH-04, TDR-CS-01]
---

# ADR-0013: 承認済み画面レビューがbrowser-interface契約のcontrol surfaceを駆動してよいという方針を確立し、アカウントメニュー用purposeを1つ追加する

> **承認者向けサマリ**: 人間が認証済み画面の上部を実機レビューし、3点の修正指示を出した——(1)個別
> アカウント案内はツールチップ等に縮小してよい、(2)パスワード変更とサインアウトはメニュー等に
> 整理してよい、(3)「別の選び方」ボタンのレイアウトを直してよい。人間はこれに続けて方針を表明した:
> 「画面が承認されたら契約も変更する」「画面が契約に引っ張られるべきではない」。本ADRはこの方針を
> 記録し、`candidate-search-browser-interface.yaml`のcontrol-surface許可リスト（`allowedPurposes`）
> へ新しいpurpose `auth-account-menu-toggle` を1件追加する（developerがパスワード変更・サインアウト
> をメニュー等へ統合する場合の受け皿。統合するかどうか・どの見た目にするかは指定しない）。あわせて
> `authentication-browser-interface.yaml`へ、TDR-AUTHがプレーンHTTP DSL（サーバ描画HTMLのみを見る）
> で検証される旨を明示する`renderModel`を追加する——メニュー化によって対象コントロールがクライアント
> JSでしか出現しなくなると、この既存の検証方式が壊れるため。(1)と(3)は契約変更を要しないと判定した。
> `allowedPurposes`の列挙という設計自体は妥当と判断し、破棄しない。friction-logへの記録・
> ARCHITECTURE.md/design.mdの更新は、いずれも不要と判定した。

## 文脈

### 1. 何が起きたか

2026-08-06、developerが候補カード洗練（ADR-0012）を実装した状態で、人間が実機（認証済み画面）を
レビューし、スクリーンショットを添えて3点を指摘した。

1. 「管理者から案内された～・・・は不要な表示だし、せめてツールチップとかにすべき」——
   `auth-individual-account-guidance`の可視表示が画面上部で目立ちすぎている。
2. 「パスワード変更とサインアウトが無造作に詰められている」——「メニューバーとかハンバーガー
   メニューとかいろいろあるはずなのに」と、整理された見た目の選択肢があるはずだと指摘。
3. 「別の切り口で再提案」ボタンが「レイアウトも気にせずに左詰めで地図と接近する形で配置されている」。

### 2. 人間の方針表明

人間はこれに続けて、個別の指摘の可否とは別に、一般的な方針を明示した。

> 全て修正OKだし、画面的に自然にするために契約の変更が必要になるならOK、のスタンスです
> 画面が承認されたら契約も変更する、でいいのでは？
> 少なくとも画面が契約に引っ張られるべきではない（モックの時点でそこまで詰められていないのがむしろ問題か？）

この方針表明は、個別の3点の指摘そのものより射程が広い——**画面が必要とする形に、契約（少なくとも
このプロジェクトのbrowser-interface契約）が追随してよい**、という一般原則を宣言している。

### 3. 契約上の事実（orchestratorが確認・供給）

`candidate-search-browser-interface.yaml`の`unavailableControls`は、`forbiddenFormControlCategories`
に`button`を含め、`allCandidateScreenFormControlsMustDeclarePurpose: true`により**候補提案画面上の
全フォームコントロールがpurposeを宣言し、そのpurposeが`allowedPurposes`の列挙に含まれること**を
要求する。改訂前の列挙は8個——`candidate-card-selection`・`candidate-map-marker-selection`・
`reproposal-open`・`reproposal-selection`・`reproposal-submit`・`reproposal-cancel`・
`auth-sign-out`・`auth-password-change-open`——であり、**「メニューを開閉する」に該当するpurposeが
無い**。したがって指摘2をメニュー・ハンバーガー等の開閉トグルで解決すると、そのトグル自体がこの
列挙に反する。

一方、`authentication-browser-interface.yaml`の`individualAccountGuidance`は`present`（DOM存在）と
`data-auth-account-use: individual-only`・`data-auth-credential-sharing: not-requested`の2属性
だけを要求し、「deliberately does not prescribe visible wording, layout, or a new public
operation」と明記している。指摘1（ツールチップ化・視覚的縮小）はこの要求と衝突しない——要素が
DOMに残り属性が付いている限り、契約改訂は要らない。

指摘3（レイアウト）は`candidate-reproposal-open`という既存test idの配置の話であり、既存の
purpose・test id・observationのいずれも変更しない。

L4は`meta/agents.md`のreviewer指摘を受けてtesterが実装した検査であり、画面上の全フォーム
コントロールのpurposeを`allowedPurposes`と突き合わせている。契約改訂を実装より後のPRに回すと、
そのPRのL4は赤いまま着地する。

## 決定

### 1. 方針: browser-interface契約のcontrol surfaceは、承認済み画面の方向性に追随して改訂してよい

dining-radarにおいて、`*-browser-interface.yaml`（test infrastructure専用、公開APIでは
ないacceptance観測SSoT）の**control-surface許可リスト**（`allowedPurposes`のような、UIが持って
よい操作の列挙）は、**人間が承認・指示した画面の方向性と衝突する場合、契約側を改訂して画面に
追随する**。これは`meta/permissions.md`が禁じる「AIによる契約ファイルの直接変更」の例外ではない
——**この改訂自体が人間の再承認点であり、承認の実体は本PRのマージである**（meta/adr/0043相当の
考え方をこのyamlファイルにも適用する。コメントによる承認記録は各yamlファイルのStatusコメントが
担う。方式はADR-0011が既に踏んでいる）。

**適用範囲を明確にする**: 本方針が適用されるのは、**test infrastructure層の観測・control-surface
契約**（`*-browser-interface.yaml`、`test-support-api.yaml`）に限る。**業務契約**（`*.feature`・
`*-api.yaml`）は対象外であり、これらの変更は従来どおり——人間が業務の言葉で内容を承認する通常の
契約変更プロセス（permissions.md §1・§2）を経る。画面の見た目・整理の仕方（メニュー化、
ツールチップ化、レイアウト）は業務behaviorを変えないため、業務契約に触れる必要がそもそも無い
（今回、`candidate-search.feature`・`authentication.feature`・両APIファイルはいずれも変更不要と
判定した——3指摘は全て可視表現・整理方法の変更であり、シナリオが約束する振る舞いを変えない）。

### 2. 決定の順序と成果物の着地は区別する

- **決定の順序（画面が先）**: 人間は画面を実機で見て指摘・裁定を下した。その裁定が契約の許可
  リストと衝突すると分かった時点で、architectが契約側の改訂を起こす。契約が先に変わって画面が
  それに従うのではない。
- **成果物の着地（同一PR）**: L4はCIで`allowedPurposes`を検査するため、契約改訂が実装より後の
  PRに着地すると、実装PRのL4が赤いまま残る。したがって**本ADRが認可する契約改訂は、developerが
  3指摘を実装するのと同一のPRに同梱する**。これは`meta/adr/0022`の断面①（契約合意）→断面②
  （実装合意）という通常順序の**逆転ではない**——契約の"内容"についての人間裁定はこのADRのマージで
  既に成立しており（断面①に相当）、実装PRはその契約のもとで動く（断面②）。両者が同一PRに同梱
  されるのは、検証機構（L4がCIで契約を参照する）の都合であり、承認の順序が乱れるわけではない。

### 3. 前例（ADR-0011）との関係

`projects/dining-radar/adr/0011`は同型の先例である——承認済み画面設計（総席数の`38席`
表示）とbrowser-interface契約（可視値の厳密等価）が衝突し、契約側を改訂して解いた。ADR-0011は
**この1回の衝突を解く判断**として書かれており、一般方針を宣言してはいない。本ADRは、人間が今回
明示的に一般方針として述べた（「画面が承認されたら契約も変更する、でいいのでは？」）ことを受けて、
**ADR-0011が実質的に確立していた運用をdining-radarの標準方針として明文化する**。今後、
同種の衝突が生じた場合、architectは個別にADRで裁定を仰ぐのではなく、本ADRが定める方針
（test infrastructure層のcontrol surfaceは画面に追随する、業務契約は対象外、着地は同一PR）に
まず照らし、方針の範囲内で収まるかを判定してよい。範囲外（業務契約に触れる、または新しい業務
capabilityを許可リストに追加するように見える場合）は、引き続き人間へエスカレーションする。

### 4. `meta/adr/0023`（consumer-driven契約）との関係

`meta/adr/0023`は**クロスプロジェクト**の軸で「UIの設計がバックエンド契約の形を駆動してよい」
consumer-driven契約を定めた。本ADRが扱うのは**同一プロジェクト内**、しかも**業務契約ではなく
test infrastructure層の観測契約**という別の軸であり、0023を適用対象として引用することはできない
（0023の決定文・帰結の図はいずれも2プロジェクト間の越境を前提にしている）。ただし**根底にある
考え方は同型**である——「消費者（この場合は画面そのもの、あるいはUIを最終承認する人間）の必要が、
契約の形を駆動してよい」という原則を、0023はクロスプロジェクトの業務契約について、本ADRは
プロジェクト内のtest infrastructure観測契約について、それぞれ別の軸で明文化している。**本ADRは
0023を拡張・上書きするものではなく、直交する別の適用である。**

### 5. `allowedPurposes`の設計自体の再検討（結論: 破棄しない。1件追加で足りる）

`allowedPurposes`は、危険な操作（`forbiddenPurposes`: `secondary-condition`・`filter`・
`sort`・`manual-ordering`。ADR-0005決定4・TDR-CS-04が禁じる補助条件・並べ替え）を締め出す
**positiveな許可リスト**である。この設計は、新しい正当なUI要素（今回のメニュートグルのような）を
足すたびに契約改訂を要するという性質を**本質的に持つ**——許可リストである以上、列挙されていない
操作は自動的に拒否される。

この性質を**denylist方式**（`forbiddenPurposes`だけを禁止し、それ以外は自由）に変更する代替案も
検討したが、**不採用**とする。理由: `forbiddenPurposes`の4項目（補助条件・フィルタ・並べ替え・
手動順序）を禁じるという保証こそがADR-0005決定4の中核であり、positiveな許可リストは「禁止したい
概念を漏れなく列挙できるか」という不確実性を持たないのに対し、denylistは「まだ列挙していない
危険な新規操作」を将来のcontrol追加のたびに見逃すリスクを持つ。今回の3指摘のような正当なUI整理
のために、この安全側の設計を緩める理由はない。

したがって、**purposeを1つ追加する**（`auth-account-menu-toggle`）にとどめ、許可リストという
設計自体は維持する。この追加コストは、`allowedPurposes`が意図通り機能している証拠でもある——
`design/reconciliation/candidate-card-refinement.md` N-7は2026-08-06付でこの正確なシナリオ
（アカウント操作をメニュー化する場合に契約改訂が要る）を**実装着手前に**言い当てていた。

### 6. `candidate-search-browser-interface.yaml`の変更

`unavailableControls.allowedPurposes`へ`auth-account-menu-toggle`を追加する。この新しいpurposeは:

- **純粋な開閉（disclosure）コントロールである**。それ自体は`publicOperation`を持たず、新しい
  業務capabilityを許可しない。既にpurposeを宣言している既存コントロール（`auth-sign-out`・
  `auth-password-change-open`）を、単一の入口の背後にまとめて見せたり隠したりするだけの役割に限る。
- **developerに実装方式を強制しない**。この購入をトグル型メニュー（ハンバーガー等）に使うか、
  常時見えるメニューバー（トグル不要、この新purposeを使わない）に使うか、あるいはCSSの余白調整
  だけで指摘2を解決し新しいコントロールを一切足さないか——いずれもdeveloperの選択に委ねる。
  **「アカウント操作をメニュー等にまとめられること」を可能にするのが本ADRの目的であり、特定の
  UI形状を義務付けるものではない。**
- **既存のTDR-CS・TDR-AUTHいずれのシナリオも、このコントロールの開閉状態を直接検査しない**ため、
  `browserActions`への新規エントリは追加しない。`allCandidateScreenFormControlsMustDeclarePurpose`
  ゲートがこの新しいpurposeを許可するだけで、実装・検証は足りる。

`contractVersion`を`0.2`から`0.3`へ上げ、ファイル冒頭のStatusコメントに本改訂を記録する。

### 7. `authentication-browser-interface.yaml`の変更（実行モデルの明示。FR-004の教訓の適用）

TDR-AUTHはプレーンHTTP DSL（ADR-0009決定4）で検証されており、クライアント側JavaScriptを実行せず
サーバ応答のHTMLだけを見る。指摘2をメニュー等の開閉コントロールで解決する場合、`auth-sign-out`・
`auth-password-change-open`が**クライアントJSでDOMに挿入されて初めて出現する**実装だと、この
既存の検証方式が壊れる（サーバ応答のHTMLにその時点で存在しないため、プレーンHTTP DSLからは
「無い」ものとして観測される）。

`FR-004`（browser-interface契約が実行モデルを明示せず、TDR-CSのL4が17件中8件failした事例）の
教訓——「browser-interface契約のcontrol surfaceが`publicOperation`を伴わない状態変化を含む場合、
architectは起草時点でその実行モデル前提を契約本文に明示する」——をここで先取り適用する。
`browserControlSurface.authenticated`へ`renderModel`を追加し、この契約が要求する`present`な
コントロールは**サーバ描画のHTMLマークアップに存在しなければならない**（HTML`hidden`属性や
CSSクラスによる視覚的な非表示は許容するが、クライアントJSによるDOM挿入だけでの出現は不可）こと
を明示する。

`contractVersion`を`0.1`から`0.2`へ上げ、ファイル冒頭のコメントに本改訂を記録する。

### 8. 指摘1（個別アカウント案内）・指摘3（レイアウト）は契約変更不要と判定する

- **指摘1**: `authentication-browser-interface.yaml`の`individualAccountGuidance`は既に
  「visible wording, layout, or a new public operation」を規定しないと明記しており、
  ツールチップ化・視覚的縮小はこの要求の範囲内で実現できる。developerがもし操作可能な
  （`button`カテゴリの）開閉トリガーを使う実装を選ぶ場合は、そのトリガーは新しいpurposeを
  要する——本ADRはその新規purposeを先回りして追加しない（P-02: 必要になっていない分は
  書かない）。CSSまたはネイティブの`title`属性等、操作コントロールを伴わない実現方法であれば
  契約変更は不要である。この場合分けをdeveloperへの実装上の注意として記録するにとどめ、対応が
  必要になった場合は改めてエスカレーションする。
- **指摘3**: `candidate-reproposal-open`の配置（レイアウト）はCSSの問題であり、control surface
  のpurpose・test id・observationのいずれも変更しない。

## 検討した代替案

- **案A: `allowedPurposes`をdenylist方式に変更する** / 不採用: 決定5参照。ADR-0005決定4が禁じる
  4種の操作を許可リストが積極的に締め出す設計を緩めると、将来の新規コントロール追加時に危険な
  操作を見逃すリスクが増える。
- **案B: 本ADRを起票せず、developerの実装PRの中でarchitectが同時に契約を直す（先例ADR-0011方式
  そのまま、方針の明文化はしない）** / 不採用: 人間が今回「画面が承認されたら契約も変更する」
  という**一般方針**を明示的に述べた。この表明を個別ADRの帰結に埋もれさせず、名前のある方針
  として残すことは、今後同種の衝突が起きるたびに人間へ個別裁定を仰ぐコストを下げる（P-02の
  精神——スライスごとに必要な分だけ確定するが、確定した方針は再利用できる形で残す）。
- **案C: `meta/adr/0023`を拡張し、この方針をメタ層で一般化する** / 不採用（architectの権限外の
  判断）: メタADRの起草は`meta/adr/0047`によりorchestratorの領分である。本ADRはプロジェクト
  scopeにとどめ、メタ層への一般化が必要かどうかはorchestratorへの提案として報告するにとどめる
  （本ADR内では決定しない）。
- **案D: 指摘1にも先回りして開閉トグル用のpurposeを追加する** / 不採用: 決定8参照。P-02
  （必要な分だけ確定する）に従い、CSSだけで実現できる可能性がある変更に先回りしてcontrol
  surfaceを広げない。

## 帰結

- `candidate-search-browser-interface.yaml`: `allowedPurposes`へ`auth-account-menu-toggle`を
  追加、`accountMenuToggleNotes`でその意味論を明記、`contractVersion`を`0.3`へ、Statusコメント
  を更新。この改訂は人間の再承認点であり、承認の実体は本PRのマージである。
- `authentication-browser-interface.yaml`: `browserControlSurface.authenticated`へ
  `renderModel`を追加（プレーンHTTP DSLの実行モデル制約の明示）、`contractVersion`を`0.2`へ、
  冒頭コメントを更新。承認の実体は同じく本PRのマージである。
- `candidate-search.feature`・`candidate-search-api.yaml`・`authentication.feature`・
  `authentication-api.md`はいずれも変更不要（決定1・決定8）。
- developerは、指摘2（アカウント操作の整理）を解決する際、`auth-account-menu-toggle`を使うか
  どうか、どう見せるかを自由に選べる。開閉コントロールを使う場合、対象コントロール一式
  （トグル自体を含む）はサーバ描画HTMLに存在させること（決定7の`renderModel`）。指摘1・指摘3は
  CSS・可視表現の変更で足りると判定したが、指摘1で操作可能なトリガーを選ぶ場合は新規purposeが
  要ることを認識しておくこと。
- **friction-logへの記録は行わない。** 決定5・本節で述べた通り、`allowedPurposes`という許可
  リスト設計は`design/reconciliation/candidate-card-refinement.md` N-7（2026-08-06、本ADRより
  前）が実装着手前に正確に予見しており、契約起草時に見落とした既存の衝突する成果物も無い
  （ADR-0011=FR-005の状況とは異なる。あちらは既に承認済みだった画面設計と突き合わせ文書を
  architectが確認しなかった見落としだったが、今回は指摘2の解決方式（メニュー化）自体が本ADRで
  初めて承認された新しい方向性であり、契約起草時に確認すべき既存の衝突する成果物はそもそも
  無かった）。今回契約改訂が必要になったのは、許可リストが意図通り「新しい操作の追加には人間の
  承認点を通す」というゲートとして機能した結果であり、AIの迷い・誤り・見逃しではない
  （`meta/permissions.md`「人間判断の記録ルール」：人間判断の発生そのものはfrictionではない。
  この整理は`meta/adr/0047`が示した「自己採点でない限り、人間の承認点で止まる判断材料の提出は
  frictionではない」という区別と同じ性質のものである）。
- **`ARCHITECTURE.md`・`design.md`は更新不要と判定する。** 本ADRはモジュール境界・データ
  フロー・業務レベルの設計骨格を変更しない——test infrastructure層の観測契約（control surface
  のpurpose許可リストと、既存の実行モデル前提の明示）にとどまる決定である。`ARCHITECTURE.md`の
  検証境界の節は既にTDR-AUTHがプレーンHTTP・TDR-CSがJS実行可能なブラウザ自動化である旨を記述
  しており、本ADRの`renderModel`追加はこの既存記述を補強するだけで矛盾も追加情報も生まない
  （ADR-0011・ADR-0012が同種の判断を下した先例に倣う）。
- **orchestratorへの提案（architectはメタADRを起草しない。meta/adr/0047）**: 本ADRが確立した
  方針——test infrastructure層の観測契約は、人間が承認した画面の方向性に追随して改訂してよく、
  業務契約とは別処理とする——は、`meta/adr/0011`に続く2件目の同型事例である。他のUIを持つ
  プロジェクト（reservation-frontend等）でも同種の衝突が将来起こりうるため、この方針をメタ層
  （例えば`meta/adr/0023`の隣に置く新規メタADR、または`meta/verification.md` L4詳細への追記）
  で一般化する価値があるかどうかは、orchestratorの判断に委ねる。本ADRはこの提案を記録するに
  とどめ、メタADRを起草しない。
