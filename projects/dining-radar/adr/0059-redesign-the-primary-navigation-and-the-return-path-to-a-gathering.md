---
id: 0059
scope: project/dining-radar
status: 承認済み
date: 2026-09-16
approved_by: "人間裁定（2026-09-15〜16 チャット選択肢UI、実機フィードバック第2便・束A『上部ナビと
  会への戻り道』）。(1) 上部ナビ: 2026-09-15、選択肢2（行き先をタブで並べる）を却下し、続く再提示
  『1か3』のうち『案1（≡にしまう）ベース、メニューは右上』を選択、さらに案1-1（≡だけ・右から出る）
  を選択——出し方の選択肢だった『右の縦の欄（常設・畳める）』は『帯だと違和感』として却下。
  2026-09-16、最終形として確定: スマホ（mapPrimaryTouchLayout側）=画面下の固定ナビ『さがす／
  ランチ会 N／アカウント』（いま開いている側に『いまここ』の印。押しても同じ画面を読み直さない。
  『アカウント』は下からシートでパスワード変更・ログアウト）。PC（twoColumnLayout側）=見出し左・
  右上に≡、進行中のランチ会があるときだけ≡の横に『ランチ会 N』チップ（会の画面の中では出さない）。
  ≡を押すと行き先2つ（絵付き・いまここ）とアカウントがボタンの下に落ちる。板:
  E:/AWS/dsg-out/party2/a-nav-r5/（E2=PC、E3=スマホ）。この過程で退けられた案: 行き先をタブで
  並べる／見出し＋反対側ボタン／『メニュー』文字ボタン／見出しを押して切り替え／右の縦の欄
  （常設・畳める）／最初だけ開いておく／下に戻る帯を貼り付け／ナビが会にもどる1本になる。
  (2) 会への戻り道: 2026-09-16、案2『入れた瞬間だけ小窓』を確定（他の未採用案は板の検討過程で
  淘汰済み）。店を入れた瞬間に下へ『◯◯を入れました・N / 5・会にもどる』の小窓が数秒出て消える。
  0件のうちは出ない。5件そろった小窓は自分では消えない。消えたあとの戻り道はスマホ=下のナビ
  『ランチ会』（店選び中は『いまここ』がランチ会に付き、押すとこの会へ）、PC=チップ（店選び中は
  この会へ）。上には緑の1行『◯/◯（◯）に開いている店・入れた店 N / 5』を残す（戻り道ではない）。
  板: E:/AWS/dsg-out/party2/a-back/Back2-*。これにより『戻り道は帯1本』（adr/0054決定4・
  adr/0056決定7、returnToGatheringFromBand）を覆す。両裁定とも確定・再交渉不可（束A完了、
  activeContext.md 2026-09-16記録）。人間はUI形状の裁定のみを下し、契約上の具体化（purposeの
  新設か既存の拡張か、testIdの置き場所、browserActionの入力の付け替え等）はarchitectの裁量に
  委ねられた——本ADRの決定2〜7がその具体化にあたる。"
supersedes: []
superseded_by: null
relates_to:
  [P-02, P-06, P-08, P-11, ADR-0013, ADR-0033, ADR-0038, ADR-0049, ADR-0054,
   ADR-0056, ADR-0057, ADR-0058, TDR-CS-17, TDR-CS-19, TDR-CS-20, TDR-CS-21]
---

# ADR-0059: 上部ナビゲーションを描き直し、会への戻り道を「入れた瞬間の小窓」へ差し替える

> **承認者向けサマリ**: 実機フィードバック第2便・束A（2026-09-14 activeContext記録の指摘1・2・3・
> 17）を受け、designerが板（`party2/a-nav-r5`・`party2/a-back`）を描き直し、人間が2026-09-15〜16
> にチャット選択肢UIで確定させた。決定は7点。
>
> **(1)** モバイル（`mapPrimaryTouchLayout`）に、画面下の固定ナビ（新設
> `candidate-primary-nav-bar`、常設・3項目: `candidate-primary-nav-search`・
> `candidate-primary-nav-gathering`・`candidate-primary-nav-account`）を新設する——現在地の印
> （`data-primary-nav-current`）と、アカウント項目からの下シート開閉（既存purpose
> `auth-account-menu-toggle`を再利用）を持つ。**(2)** デスクトップ（`twoColumnLayout`）に、新設
> `candidate-primary-nav-menu-toggle`（≡、常設）と、それが開く`candidate-primary-nav-menu-panel`
> （行き先2つ＋既存のサインアウト・パスワード変更）を新設する。既存の`candidate-gathering-entry`
> （チップ）は、進行中の会がある（`data-in-progress-gathering-count`>0）ときだけ、かつ
> `gathering-scheduling-browser-interface.yaml`の3画面（一覧・作成・詳細）の外でだけ、≡の隣に出る
> よう性格を改める——**これは`ADR-0054`決定1（モバイル幅でも文字を消さない・会の画面群でも常設）
> をPCの0件時・会の画面群の中の2点でだけ覆す**（モバイルは新設の下部ナビが同じ役目を無条件で
> 引き継ぐため後退ではない）。**(3)** ≡の新しいpurposeは、既存の`auth-account-menu-toggle`
> （`ADR-0013`、アカウント操作限定の開閉）を広げず、新設する——disclosureの範囲が広がる（行き先2つ
> を含む）ため、`ADR-0013`決定5が明記した「既存コントロールをまとめて見せ隠しするだけの役割に限る」
> という既存purposeの狭い定義を保つ。**(4)** 会モードでは、チップ・下部ナビ・≡メニューいずれの
> 「ランチ会」項目も、押すと「この会」（幹事ダッシュボード）へ遷移するよう行き先を切り替える——新設
> `browserActions.returnToGatheringFromEntry`が、既存`openGatheringEntry`（会モードでないときは
> 一覧へ）と入力を共有し、`gatheringContext`の有無で排他的に発火する。**(5)** 会への戻り道を、店を
> 入れた瞬間だけ現れる小窓（新設`candidate-gathering-shortlist-toast`、数秒で消える。ちょうど5件
> そろった瞬間に現れた場合は自分では消えない）へ差し替える——**`ADR-0054`決定4・`ADR-0056`決定7が
> 定めた「帯自体が戻る動線を兼ねる」を覆し**、`candidate-gathering-mode-band`は状態表示専用（緑の
> 1行）へ格下げする。既存`browserActions.returnToGatheringFromBand`は廃止し、新設
> `returnToGatheringFromToast`が小窓の「会にもどる」を引き受ける。**(6)**
> `gathering-scheduling-browser-interface.yaml`自身は新しいtestId・purposeを一切増やさない——
> 共有ナビの規範sourceは`candidate-search-browser-interface.yaml`のまま（`ADR-0054`決定1と同じ
> 流儀）。この結果、会をつくる画面・会の一覧・会の詳細から**初めて**サインアウト・パスワード変更に
> 到達できるようになる。**(7)** 見出し「ランチ候補」→「ランチ候補をさがす」の文言変更は、この見出し
> が契約上のtestIdを持たないため契約変更を要しない。
>
> 払うもの: 下部ナビ・≡メニューの視覚実装（アイコン・開閉アニメーション・小窓の自動消滅までの
> 秒数）はいずれも実装選択のまま固定しない。デスクトップ≡メニュー内の「ランチ会」項目にバッジ件数
> を表示するかどうかは未決のまま残す。

## 文脈

### 0. 検証の申告（meta/adr/0039）

本ADRが前提とする既存契約の記述は、`candidate-search-browser-interface.yaml`
（contractVersion 1.11.0）・`gathering-scheduling-browser-interface.yaml`
（contractVersion 0.20.0）・`authentication-browser-interface.yaml`（contractVersion 0.2）・
`candidate-search.feature`を実際に読んで確認した。`gathering-scheduling-browser-interface.yaml`に
`auth-sign-out`/`auth-password-change-open`/`auth-account-menu-toggle`のいずれの参照も無いこと
（会の画面群からはこれまでサインアウト・パスワード変更に到達できなかったこと）を`grep`で確認した。
designerの板（`E:\AWS\dsg-out\party2\a-nav-r5\`のE2・E3、`party2\a-back\`のBack2-*）と、
`activeContext.md`の2026-09-14〜16の実機フィードバック記録・裁定の控えを実際に読んだ。確認して
いないのは、これらの決定を実装したコードの挙動そのもの——architectは実装コードを読まない・書か
ない。

### 1. 何が起きたか

2026-09-14、実機フィードバック第2便で人間から4点の指摘があった——(指摘1)「ランチ候補をさがす」を
押しても同じ画面が読み込まれるだけで、いまいる場所の印なのか押すボタンなのか分からない。会モード
中に押すと会の店選びから抜けてしまう。(指摘2) 行き先の行とアカウントの行が段で揃っていない。見出し
「ランチ候補」も上の行と重複。(指摘3)「ランチ会」もボタンとして分かりにくい。(指摘17) 店を選んで
から会に戻る導線が分かりにくい——現状は上部の帯（`candidate-gathering-mode-band`）が唯一の戻り道
だが、PCでは貼り付かず、店を選んでいる最中に画面を降りると見失う。

designerが2つの板を描き、人間が2026-09-15〜16にチャット選択肢UIで段階的に絞り込んで確定させた
（approved_by参照）。

### 2. 契約とのズレ（人間の裁定はUI形状のみ。具体化はarchitectの裁量）

designerの報告・orchestratorの整理で、次の5点が契約上のズレとして挙がった。本ADRはこの5点すべて
について具体的な決定を下す（未決に残したものは無い）。

1. `ADR-0054`決定1「文字を常に出す」がPCの0件時・会の画面で覆るかどうか → **決定2で覆す**。
2. `candidate-gathering-entry`の件数バッジの置き場所（チップ・下部ナビのどちらに置くか） →
   **決定1・2で両方に置く**（同じ`data-in-progress-gathering-count`を、mobileBarGatheringと
   entry(チップ)双方が読む）。
3. ≡が行き先とアカウントの両方を開くため、`auth-account-menu-toggle`の役目を広げるか新設するか →
   **決定3で新設**する。
4. 下部ナビを`mapPrimaryTouchLayout`だけの要素として登録するか（`adr/0033`先例） →
   **決定1で登録する**。
5. `candidate-gathering-mode-band`を「上の緑の1行」と「小窓」に分けるときの識別子・属性の置き場所、
   `returnToGatheringFromBand`の入力の付け替え、会モードでの`candidate-gathering-entry`の行き先
   変更 → **決定4・5でそれぞれ具体化する**（詳細は決定本文）。

## 決定

### 決定1. モバイルに画面下の固定ナビを新設する

`renderModes.mapPrimaryTouchLayout`（`adr/0033`）専有の新規testId
`candidate-primary-nav-bar`（常設、`mapPrimaryTouchLayout`が成立する間は無条件に存在——`adr/0033`
がこのモードをリストプライマリの後継として作った先例と同じ「レンダーモード専有」の登記方法を踏襲
する）を新設する。3つの子要素を常に3つとも伴う。

- `candidate-primary-nav-search`（さがす）: 現在地印`data-primary-nav-current`を持つ平叙な
  リンク/ナビ要素（`candidate-gathering-entry`と同じ様式、purpose宣言不要）。現在地のとき押しても
  同じ画面を読み直さない（no-op）。会モード中に押すと、通常モードの候補提案画面へ遷移する——
  「押すと会の店選びから抜ける」という指摘1後半の挙動は、これにより**意図した効果**として明文化
  される（バグではない）。
- `candidate-primary-nav-gathering`（ランチ会 N）: 現在地印と、既存の`data-in-progress-gathering-
  count`バッジ（`entry.badge`の値をそのまま共有）を持つ。会モード中／会の画面群にいるときは現在地
  印が立つ。押下の行き先は決定4が定める。
- `candidate-primary-nav-account`（アカウント）: `<button>`。既存purpose`auth-account-menu-toggle`
  を宣言し、下からのシートで`auth-sign-out`・`auth-password-change-open`を開く。

この下部ナビは、候補検索画面だけでなく`gathering-scheduling-browser-interface.yaml`の3画面
（`organizerGatheringList`・`organizerGatheringCreate`・`organizerDashboard`）でも無条件に常設
される——`ADR-0054`決定1が最初に確立した「会に入ると出られない、を作らない」という関心を、モバイル
幅では後退させず引き継ぐ（決定2参照）。

### 決定2. デスクトップに見出し・≡・チップの3点を新設/改める。`ADR-0054`決定1をPCの0件時・会の画面群
の中の2点で覆す

`renderModes.twoColumnLayout`専有の新規testId`candidate-primary-nav-menu-toggle`（常設、≡）を
新設する。活性化すると`candidate-primary-nav-menu-panel`が開き、2つの行き先
（`candidate-primary-nav-menu-search`・`candidate-primary-nav-menu-gathering`、いずれも現在地印
付き）と既存の`auth-sign-out`・`auth-password-change-open`がボタンの下に並ぶ。この≡・パネルも、
候補検索画面と`gathering-scheduling-browser-interface.yaml`の3画面すべてで無条件に常設される。

既存の`candidate-gathering-entry`（チップ）は、**進行中の会があるとき（`data-in-progress-
gathering-count`>0）だけ、かつ会の画面群（`organizerGatheringList`・`organizerGatheringCreate`・
`organizerDashboard`）の中ではないときだけ**、≡の隣に出るよう性格を改める。

**これは`ADR-0054`決定1（「モバイル幅でも文字を消さない」「会の画面群にも常設」）の一部を覆す**——
覆すのはPCにおける次の2点に限る。

- 元の決定: `candidate-gathering-entry`はビューポート非依存に常に文字ラベルを見せ、会の画面群でも
  無条件に常設される。
- 覆す理由: PCでは、≡自体が常設の「会に入ると出られない」の保証を引き継ぐ（決定1のモバイル下部
  ナビと対になる存在）。0件時・会の画面群の中でチップまで表示すると、行き先が二重（≡の中のランチ
  会項目とチップ）になり、人間裁定（2026-09-16確定形）が明示的に「会の画面の中では出さない」と
  定めた見た目と一致しない。モバイル側は決定1の下部ナビが同じ保証を無条件で引き継ぐため、
  `ADR-0054`決定1の根底にある懸念（「会に入ると出られない」という一度きりの事故）自体は後退しない。

### 決定3. ≡の新しいpurposeは、既存`auth-account-menu-toggle`を広げず新設する

`unavailableControls.allowedPurposes`へ新規purpose`candidate-primary-nav-menu-toggle`を追加する。
既存の`auth-account-menu-toggle`（`ADR-0013`）は変更しない——同ADR決定5が「既にpurposeを宣言して
いる既存コントロール（`auth-sign-out`・`auth-password-change-open`）を、単一の入口の背後にまとめて
見せたり隠したりするだけの役割に限る」と明記した狭い定義を守る。今回の≡は行き先2つも開くため、
disclosureの範囲がこの定義を超える。既存purposeはモバイルの`candidate-primary-nav-account`
（アカウントのみを開く、決定1）で引き続き使う——その用途は`ADR-0013`の原義とちょうど一致する。

### 決定4. 会モードでのナビの行き先を「この会」へ切り替える

`browserActions.openGatheringEntry`の`input`を
`[candidate-gathering-entry, candidate-primary-nav-gathering, candidate-primary-nav-menu-
gathering]`へ広げ、`precondition`に「`gatheringContext`がnullである」を加える（会モードでない
ときだけ、一覧へ遷移するという既存の挙動を維持する）。新設`browserActions.
returnToGatheringFromEntry`が同じ3入力を共有し、逆の`precondition`（`gatheringContext`が非null）
を持つ——会モード中にこれらを押すと、その会の幹事ダッシュボードへ遷移する。2つのactionは同じ3入力
に対して排他的かつ網羅的であり、どちらか一方が必ず発火する。

### 決定5. 会への戻り道を「入れた瞬間の小窓」へ差し替え、帯を状態表示専用へ格下げする

`gatheringMode.band`（`candidate-gathering-mode-band`）から`navigation`の役目（`ADR-0054`決定4:
帯自体が戻る動線を兼ねる）を外し、`formControl: false`の状態表示専用（「◯/◯（◯）に開いている店・
入れた店 N / 5」の緑の1行）に格下げする。既存`browserActions.returnToGatheringFromBand`は廃止する。

新設`gatheringMode.shortlistToast`（testId`candidate-gathering-shortlist-toast`）が戻り道の主役に
なる——`toggleCardGatheringShortlist`が店を**追加**する方向（`false`→`true`）に成功した直後だけ
現れ、実装が選ぶ短い遅延ののち自動的に消える。ただし現れた瞬間の`shortlistedShopCount`が
`maxShortlistedShops`と等しい（ちょうど5件そろった）場合は、自分では消えない。内側の
`candidate-gathering-shortlist-toast-return`（平叙なリンク/ナビ要素、purpose宣言不要）が新設
`browserActions.returnToGatheringFromToast`の入力であり、幹事ダッシュボードへ遷移する。

小窓が消えたあとの戻り道は、決定4が定めるナビ（モバイル下部ナビの「ランチ会」項目・PCのチップ）が
引き継ぐ——これは、`ADR-0054`決定4・`ADR-0056`決定7が定めた「独立した戻るボタンは置かない、帯
自体が兼ねる」という設計を覆すものである。

- 元の決定（`ADR-0054`決定4）: 「候補検索画面（会モード）から会へ戻る動線は、店数を示す帯自体が
  兼ねる。独立した『戻る』ボタンは置かない」。
- 覆す理由: 実機で「上部の帯が唯一の戻り道、PCでは貼り付かない」（指摘17）ことが分かった。人間は
  板を見て、店を入れた瞬間だけ現れて消える小窓の方が、常設の帯より戻り道として分かりやすいと判断
  した（2026-09-16確定）。帯自体は「入れた店の件数が読めること自体が合図になる」という`ADR-0054`
  決定4の設計思想（独立した「確定して戻る」操作を置かない、店は押した瞬間に保存される）はそのまま
  維持し、戻り道としての役目だけを小窓とナビへ移す。

### 決定6. `gathering-scheduling-browser-interface.yaml`自身はtestId/allowedPurposesを増やさない

決定1・2が新設する要素は、いずれも`candidate-search-browser-interface.yaml`だけが規範sourceで
あり続ける——`ADR-0054`決定1が確立した「常設ナビはcandidate-search側の契約が唯一の規範source、
gathering-scheduling側はtestIdを持たない」という流儀をそのまま踏襲する。`gathering-scheduling-
browser-interface.yaml`には、これらの要素がこの3画面でも常設されることを説明する注記
（`crossFileSharedNavigation`）だけを追加する。

この結果として、**`organizerGatheringList`・`organizerGatheringCreate`・`organizerDashboard`から
初めてサインアウト・パスワード変更に到達できるようになる**——`grep`で確認したとおり、この3画面には
これまで`auth-sign-out`/`auth-password-change-open`への参照が一切無く、アカウント操作は候補検索
画面からしか行えなかった。本ADRはこの既存の穴を、新しいナビの副次効果として埋める。

### 決定7. 見出し文言の変更は契約変更を要しない

見出し「ランチ候補」を「ランチ候補をさがす」に変える人間裁定（2026-09-16確定形）は、この見出し自体
が契約上のtestIdを持たない（`grep`で確認済み）ため、契約変更を要しない——実装のみで完結する。

## 検討した代替案

人間が板の検討過程で退けた案（`activeContext.md`裁定の控え記録）は次のとおり——いずれも契約設計上
の検討ではなく、UI形状の選択として人間が退けたものである。

- **行き先をタブで並べる**: 却下（2026-09-15）。
- **見出し＋反対側ボタン**: 却下。
- **「メニュー」という文字ボタン**: 却下。
- **見出しを押して切り替える**: 却下。
- **右の縦の欄（常設・畳める）**: 却下（「帯だと違和感」）。
- **最初だけ開いておく**: 却下。
- **下に戻る帯を貼り付ける**: 却下。
- **ナビが会にもどる1本になる**: 却下。

契約設計上、architectが検討した代替案は次のとおり。

- **`auth-account-menu-toggle`を広げて≡にも使う**: 不採用（決定3）。`ADR-0013`決定5が明記した
  狭い定義（既存コントロールをまとめて見せ隠しするだけ）を、人間の再承認なしに実質的に広げること
  になる——本ADR自体が人間の再承認点であることを踏まえても、既存purposeの意味を静かに変えるより、
  新設して両者の境界を契約に明記する方が、後から見て何が起きたかを辿りやすい。
- **`candidate-gathering-mode-band`のtestId自体を改名する**: 不採用（決定5）。帯という要素・見た目
  （緑の1行）はそのまま残る——変わるのは役目（戻り道→状態表示専用）だけであり、既存のTDR-CS-21
  （帯から5件到達の理由が分かる）が引き続き同じtestIdを指せることを優先した。
- **`returnToGatheringFromBand`を`returnToGatheringFromEntry`と統合し1つのactionにする**:
  不採用（決定4・5）。トースト（小窓）とナビ（チップ/下部ナビ）は別の要素・別のpresenceRuleを持ち、
  一方が無くても他方は独立して機能する（小窓が自動で消えたあとも、ナビは常に有効）。1つのaction名に
  まとめると、どちらの入力からの発火かをrequiredOutcomeの記述だけでは区別できなくなる。
- **`gathering-scheduling-browser-interface.yaml`自身にもこれらのtestId/allowedPurposesを複製
  する**: 不採用（決定6）。`ADR-0054`決定1が既に「規範sourceは1箇所」という流儀を確立しており、
  複製は将来のドリフト（2つの契約が同じ要素について異なる記述を持つ）の温床になる。

## 帰結

- `contracts/candidate-search-browser-interface.yaml`（改訂、現行1.11.0）: `authenticatedInitial
  Outcome.present`から`candidate-gathering-entry`を外す。`renderModes.twoColumnLayout.testIds`へ
  `candidate-primary-nav-menu-toggle`、`renderModes.mapPrimaryTouchLayout.testIds`へ
  `candidate-primary-nav-bar`を追加。`gatheringEntry`節へ`menuToggle`・`menuPanel`・
  `menuDestinationSearch`・`menuDestinationGathering`・`mobileBar`・`mobileBarSearch`・
  `mobileBarGathering`・`mobileBarAccount`を新設し、`entry`（チップ）の`requirement`を書き換える。
  `gatheringMode.band`から`navigation`を外し`shortlistToast`（と`returnControl`）を新設する。
  `unavailableControls.allowedPurposes`へ`candidate-primary-nav-menu-toggle`を追加。
  `browserActions.openGatheringEntry`を拡張し、`returnToGatheringFromBand`を`returnToGathering
  FromEntry`・`returnToGatheringFromToast`へ置き換える。`profiles.localAcceptance.
  verifiesScenarios`へTDR-CS-23を追加。**具体的なYAML編集は次工程で行う**
  （本ADRと同じ提出物のspec-bundle-a参照）。
- `contracts/gathering-scheduling-browser-interface.yaml`（改訂、現行0.20.0）: 自身のtestId/
  allowedPurposesは増やさない。`unavailableControls`へ`crossFileSharedNavigation`注記を新設し、
  この3画面での常設と、サインアウト・パスワード変更へ初めて到達できるようになる旨を明記する。
  **具体的なYAML編集は次工程で行う。**
- `contracts/authentication-browser-interface.yaml`（改訂、現行0.2）: `renderModel`の例示
  パラグラフへ、新設`candidate-primary-nav-menu-toggle`も同じ実行モデル制約（サーバ描画HTML必須）
  の対象であることを明記する。TDR-AUTH自体の検証範囲・シナリオは無変更。
- `contracts/candidate-search.feature`: TDR-CS-17へ「会にもどる案内がしばらく示される」旨のAndを
  1行追記する。新規TDR-CS-23（5件そろうと案内は自分では消えない）を追加する。ナビの構造自体
  （現在地印・行き先の組み立て）は、既存の`candidate-gathering-entry`/`openGatheringEntry`と同様、
  対応する業務シナリオを持たない——UI構造の決定であり業務規則の追加ではないため
  （`ADR-0054`決定4が同じ理由で対応シナリオを追加しなかった先例に倣う）。
- `contracts/gathering-scheduling.feature`: 変更しない——会への戻り道は候補検索側の契約だけで
  完結するナビゲーションの話であり、この契約が観測する業務規則（会の作成・日程・投票・確定）を
  変えない。
- `ARCHITECTURE.md`・`design.md`: 変更しない——本ADRは新しいモジュール境界を生まない。既存の
  「browser-interface契約はtest infrastructure層であり業務契約ではない」という区分もそのまま
  である。

## 未決事項（次工程・人間への申し送り）

1. 下部ナビ・≡メニューの視覚実装（アイコン・開閉アニメーション・配色）は実装選択のまま契約は固定
   しない。
2. 小窓（`shortlistToast`）が自動的に消えるまでの具体的な秒数は契約が固定しない（既存の
   `walkingTimeEstimateWording`等と同じ、内容のみを縛りgeometryやtimingは縛らない流儀を踏襲）。
3. デスクトップ≡メニュー内の`menuDestinationGathering`にバッジ件数（`data-in-progress-gathering-
   count`）を表示するかどうかは、本ADRではMustにしていない——次工程でdesignerの板が必要になった
   時点で人間に確認する。
4. `gathering-scheduling-browser-interface.yaml`の3画面から初めてサインアウト・パスワード変更へ
   到達できるようになることについて、TDR-AUTH自体のシナリオをこれらの画面まで拡張するかどうかは
   本ADRの範囲外——TDR-AUTHは引き続き候補検索画面の`'/'`エントリだけを検証する。
5. 下部ナビ・≡メニューの実測（タップ対象44px下限等）は、案Bのマス寸法と同様、実装が固まった段階
   でorchestratorが確認する（`ADR-0054`未決事項2と同じ扱い）。
