---
id: 0063
scope: project/dining-radar
status: 承認済み
date: 2026-09-19
approved_by: "人間裁定（2026-09-19、designerの板 E:/AWS/dsg-out/party2/d7/S4-SpSelect.dc.html・
  S4-PcSelect.dc.htmlを見て決定、orchestrator経由でarchitectへ伝達）。決定は4点。(1) 見出しの
  すぐ下から地図いっぱい: 見出しは会の名前と決まった日時の1行（PC）、スマホは名前+削除ボタンの行と
  日時の行の2行。局面の札（「店を選び中」）は画面から落とす。地図は見出しの下から画面の下端
  （スマホは下部ナビの上）まで。店の一覧は地図の上に浮かせる（PCは左のパネル、スマホは下から出る
  シート）。画面下の帯（いま選んでいる店と「この店で確定」）はそのまま。(2) 集計と日程はタブ／
  開閉の奥へ: 一覧の上端にタブを置き、「店 N件」「日程」「回答 N/M人」「リンク N本」を切り替える。
  既定は「店」。集計の行（N人が回答・有効なリンクN本・まだN人が未回答）と「日程」の枠（決まった
  候補日と票）はタブの奥へ移す。回答の内訳はタブのラベルに出るので、「まだN人が未回答」という文
  そのものは画面から消える。(3) 選んでいる店を一覧の先頭に貼り付ける: 幹事が選んだ店の行を一覧の
  上端に貼り付け、スクロールしても離れない。残りは票が多い順のまま並べ、番号の丸は票の順位を保つ
  （選んだ店が2位なら「2」のまま）。選んだ行は薄い地色・左の縦線・「選択中」の札で示す。色の役割を
  2つに分ける——緑＝票が多いこと（「いちばん人気」）、スミ色＝幹事が選んでいること。地図のピンも
  同じ規則で、選んだ店のピンだけ大きくする。(4)「この会を削除」は見出しの行に文字のボタンとして
  直に置く（メニューに隠さない）。ハンバーガー（≡）は別の物に使っているので削除には使わない。
  この裁定はUI形状と業務規則のみを定めたものであり、契約上の具体化（どの既存の値で足りるか・
  新しいtestId/purposeが要るか・presenceRuleの書き方・.featureシナリオの要否）はarchitectの
  裁量に委ねられた——本ADRの決定1〜4がその具体化にあたる。"
supersedes: []
superseded_by: null
relates_to:
  [P-01, P-04, P-06, P-08, P-11, ADR-0036, ADR-0038, ADR-0041, ADR-0054,
   ADR-0055, ADR-0056, ADR-0059, ADR-0060, ADR-0061, ADR-0062, TDR-GTH-11,
   TDR-GTH-33, TDR-GTH-67]
---

# ADR-0063: 店を選び中の幹事ダッシュボードを、確定後の地図いっぱいの骨組みへ揃える

> **承認者向けサマリ**: 実機フィードバックの積み残し（activeContext.md「人間の判断が要ること」
> 2026-09-19 時点の1件目、「店を選び中の板が無いので手を付けていない」）に対し、designerが板
> （`party2/d7/S4-SpSelect.dc.html`・`S4-PcSelect.dc.html`）を描き、人間がチャット選択肢UIで
> 4点を裁定した。本ADRはその契約上の具体化を行う。決定は4点。
>
> **(1)** `organizerDashboard.phaseIndicatorAttributes`（局面の札、`gathering-phase-indicator`）
> の`presenceRule`を、SCHEDULING・FINALIZEDでは出現しSELECTING_SHOPでは出現しない、という
> 条件付きへ狭める——この要素はドラフト時（`ADR-0036`）から一貫して「幹事ダッシュボードが描画
> される限り無条件に存在する」だったが、その前提を今回はじめて崩す。`participantAnswer.
> headerAttributes`（参加者側の同じ局面値）は無変更のまま——`TDR-GTH-11`がこの局面遷移を参加者
> 画面だけからでも検証できる、という既存の設計はそのまま成立する。**(2)** 新規
> `organizerDashboard.headingBar`（`gathering-dashboard-title`/`gathering-dashboard-confirmed-
> date`）を、SELECTING_SHOP局面の間だけ持たせる——いずれも新しいAPIフィールドではなく、
> `organizerGatheringList.list.item`の`data-gathering-title`と
> `shortlistedShopVotes.finalizeConfirmDialog.date`の`data-confirmed-candidate-date`という、
> 既に確立済みの値をこの局面のこの画面へはじめて投影したものである。「この会を削除」ボタンを
> 見出し行へ直に置くという要望は、`gathering-delete-open`（既存、無条件に存在）の設置場所という
> geometryにすぎず、`ADR-0062`決定2と同じ理由で契約変更なしで閉じる。**(3)** 新規
> `organizerDashboard.shopSelectionPanel`（4件のタブ、`gathering-shop-select-tab-shop`
> 〈既定〉/`-schedule`/`-answers`/`-links`）を、SELECTING_SHOP局面の間だけ持たせる——`ADR-0062`
> 決定4が確定後の画面に確立した「入口の状態だけが可視性を左右し、対象要素自身のpresenceRuleは
> 変えない」という設計をそのままこの局面へ広げ、`shopSelectionEntry`/`shortlistedShopVotes.
> list`・`candidateDateList`・`responseTable`・`participantLinkList`という4つの既存の面を
> 束ねる。**(4)** `shortlistedShopVotes.list`の`orderingInvariant`（票の多い順、無変更）と、
> 同じ`item.detailFields.map.marker`の`requirement`へ、それぞれ非拘束の注記を加える——選択中の
> 行をCSSで画面上端に貼り付けてもDOM順（＝票の順位）は変わらないこと、地図のピンの大きさ・色は
> 既存の`data-current-leader`（`ADR-0055`決定6、いちばん人気）と`data-finalize-selected`
> （幹事が選んでいる）という独立した2つの属性から導出でき、新しい属性は増やさないことを明記する。
>
> 払うもの: 見出し・タブ・浮かせた一覧・スティッキーな選択行・ピンの色とサイズの具体的な見た目
> （配色・アニメーション・スクロール）はいずれも実装選択のまま固定しない——この契約の一貫した
> 流儀（`ADR-0059`決定5・`ADR-0060`決定5・`ADR-0062`決定2と同じ）。

## 文脈

### 0. 検証の申告（meta/adr/0039）

本ADRが前提とする既存契約の記述は、`gathering-scheduling-browser-interface.yaml`
（contractVersion 0.24.2、`ADR-0060`〜`ADR-0062`まで反映済み）・`gathering-scheduling-api.yaml`
（v0.18.0）・`gathering-scheduling.feature`（TDR-GTH-01〜66）を実際に読んで確認した——
`organizerDashboard.phaseIndicatorAttributes`が「幹事ダッシュボードが描画される限り無条件に存在
する」と明記していたこと（ドラフト時、`ADR-0036`。以後`ADR-0038`決定10・`ADR-0041`P6は値集合を
確認しただけで、この存在規則自体は一度も変えていない）、`organizerDashboard`に会の名前・決まった
日時を常設で示す要素が一つも無かったこと（`organizerGatheringList.list.item`の
`data-gathering-title`/`data-confirmed-candidate-date`はダッシュボードではなく一覧画面の要素で
あること、`shortlistedShopVotes.finalizeConfirmDialog.date`の`data-confirmed-candidate-date`は
確認ダイアログを開いたときだけ存在する一時的な要素であること）、`gathering-delete-open`が既に
無条件・二段階確認つきで存在し、設置場所（geometry）を契約が一度も固定していないこと、
`respondedSummary`/`unansweredSummary`/`candidateDateList`/`responseTable`/
`participantLinkList`がいずれも3局面を通じて無条件に存在し続けると明記されていること、
`shortlistedShopVotes.list`の`orderingInvariant`が`wantToGoCount + okToGoCount`降順で無変更
であること、`item.detailFields.map.marker`が`data-shop-id`のみを持ち位置以外の見た目を一切
固定していないこと、`finalizedSummary.answersOpen`/`linksOpen`（追補22）が「対象要素自身の
presenceRuleは変えず、入口の状態だけが可視性を左右する」という設計をFINALIZED局面に対して
既に確立していたことを、それぞれ実際の記述として確認した。designerの板
（`E:\AWS\dsg-out\party2\d7\S4-SpSelect.dc.html`・`S4-PcSelect.dc.html`）とその描画画像
（`S4-SpSelect.png`・`S4-PcSelect.png`）、`activeContext.md`「人間の判断が要ること」節の該当
記述も実際に読んだ。確認していないのは、これらの決定を実装したコードの挙動そのもの——architect
は実装コードを読まない・書かない。

### 1. 何が起きたか

実機フィードバック第2便・束D（投票・確定）を扱った`ADR-0062`は、確定後（FINALIZED）の幹事
ダッシュボードを「地図いっぱい、決まった店と集まる場所だけ」の骨組みへ作り直したが、店を選び中
（SELECTING_SHOP）の同じダッシュボードには対応する板が無く、`activeContext.md`は「店を選び中の
板が無いので手を付けていない」と積み残しを記録していた。designerが板`party2/d7`を描き、人間が
2026-09-19にチャット選択肢UIで4点を裁定した（approved_by参照）——要は、確定後の画面が既に持つ
骨組み（見出し・地図いっぱい・浮かせた一覧・タブの奥への集計）を、店を選び中の画面にも同じ形で
揃えるという裁定である。

### 2. 「ADR-0054決定1」「ADR-0060」という当初の手がかりの当否（依頼文の検証）

依頼文は「ADR-0054決定1（局面の札）やADR-0060（最有力の印の置き場所）など、この決定が上書きする
既存の決定があれば明示的に指す」と手がかりを示していたが、`ADR-0054`決定1を実際に読むと、その
内容は「上部の居場所2つ（『ランチ候補をさがす』『ランチ会』）を会の画面群にも常設する」という、
共有ナビゲーションについての決定であり、局面の札（`gathering-phase-indicator`）には一度も
言及していない——本ADRが実際に狭めるのは`ADR-0036`（ドラフト時）が定めた
`phaseIndicatorAttributes`の無条件存在規則である（文脈0節）。`ADR-0054`決定1自体は本ADRで一切
変更しない。`ADR-0060`についても、その決定7・8および2026-09-19追補が扱うのは候補**日**
（`gathering-candidate-date`・`responseTable.leaderSummary`）の最有力印であり、本ADR決定4が
扱う店の`data-current-leader`（`ADR-0055`決定6が起源）とは別の値・別の画面要素である——`ADR-0060`
自体も本ADRで変更しない。もっとも、`ADR-0060`の2026-09-19追補（`leaderSummary`のpresenceRuleを
SCHEDULING局面だけへ狭めた技術判断）は、本ADR決定1が採る手法（既存の値の無条件presenceRuleを
局面条件つきへ狭める、new業務判断ではなく運用範囲の明確化）の直接の先例であり、その意味でのみ
本ADRと関係する。両ADRとも、本ADR自身が変更する対象ではないことをここに明記する。

## 決定

### 決定1. 局面の札は店を選び中の局面でだけ画面から落とす

`organizerDashboard.phaseIndicatorAttributes.requirement`を書き換え、`gathering-phase-
indicator`の`presenceRule`を「phaseがSCHEDULINGまたはFINALIZEDの間は出現し、SELECTING_SHOPの
間は出現しない」という条件付きへ狭める——ドラフト時（`ADR-0036`）から本ADRまで一貫していた
「幹事ダッシュボードが描画される限り無条件に存在する」という前提を、この1局面に限って崩す
（人間裁定「局面の札（『店を選び中』）は画面から落とす」）。`participantAnswer.
headerAttributes`（参加者側の同じ局面値、`gathering-participant-header`の`data-gathering-
phase`）はこの決定の対象外で無変更のまま——`TDR-GTH-11`（開催日確定後も局面は「店を選び中」の
まま変わらないこと）を参加者画面だけからでも検証できるという、ドラフト時からの既存の設計意図
（文脈0節・本ファイル冒頭コメント）はそのまま成立し続ける。`TDR-GTH-33`（幹事が日と店を確定する）
のような、局面遷移を業務言語で述べるシナリオの本文はいずれも特定の画面要素を名指ししておらず、
書き換えを要しない——ただし、これらのシナリオを幹事側から検証してきた既存のL4実装が
`gathering-phase-indicator`を直接読んでいた場合は、SELECTING_SHOP局面の間だけ`participantAnswer.
header`かAPIレスポンス自身へ読み替える実装対応が要ることを、次工程への申し送りとして記録する
（下記「未決事項」）。

### 決定2. 見出しに会の名前と決まった日時を新設し、「この会を削除」は契約変更なしで見出しへ置く

新規`organizerDashboard.headingBar`（`gathering-dashboard-title`/`gathering-dashboard-
confirmed-date`）を、SELECTING_SHOP局面の間だけ（`shopSelectionEntry`と同じ条件で）持たせる。
`gathering-dashboard-title`の`data-gathering-title`は`organizerGatheringList.list.item`が
既に使う同名属性・同じ値（`Gathering.title`）をこのダッシュボードへはじめて投影したものであり、
新しいAPIフィールドを要しない。`gathering-dashboard-confirmed-date`の`data-confirmed-candidate-
date`は`shortlistedShopVotes.finalizeConfirmDialog.date`・`finalizedSummary.decisionBanner`
が既に使う同名属性・同じ値（確定済み候補日の`startAt`）を、確認ダイアログを開かなくても・確定
しなくても常設で示す値としてはじめて持たせたものである——SELECTING_SHOP局面に達している時点で
`confirmCandidateDate`は必ず成功済みのため、この値は常に非nullである。

「この会を削除」ボタン（`gathering-delete-open`）を見出し行に文字のボタンとして直に置き、
ハンバーガー（`crossFileSharedNavigation`、`ADR-0059`）には入れないという要望は、この要素の
既存の`presenceRule`（無条件）・`requiredOutcome`（確認ダイアログを開く）のいずれも設置場所
そのものを固定していないため、**契約変更なしで閉じる**——`ADR-0062`決定2が「決める」ボタンの
押しやすい位置を同じ理由で契約変更なしに閉じたのと同じ扱いである。

### 決定3. 集計と日程をタブの奥へ移す

新規`organizerDashboard.shopSelectionPanel`（4件のタブ、`gathering-shop-select-tab-shop`
〈既定選択〉/`-schedule`/`-answers`/`-links`）を、SELECTING_SHOP局面の間だけ持たせる。4つの
タブはそれぞれ次を開閉する——`shopTab`は`shopSelectionEntry`/`shortlistedShopVotes.list`
（どちらが該当するかは店が1件でも入っているかによる、両要素とも既存のpresenceRuleのまま）、
`scheduleTab`は`candidateDateList`、`answersTab`は`responseTable`、`linksTab`は
`participantLinkList`。**いずれの対象要素の`presenceRule`も変えない**——`ADR-0062`決定4が
FINALIZED局面の`answersOpen`/`linksOpen`に対して確立した「対象は常にDOM上に存在し続け、入口の
状態だけが可視性を左右する」という設計を、この局面のこの4面へ広げただけである。`respondedSummary`/
`unansweredSummary`（集計の行）自体も無変更のまま——人間の言葉「回答の内訳はタブのラベルに出る
ので、『まだN人が未回答』という文そのものは画面から消える」は、この2要素が既に持つ値
（`data-responded-count`/`data-active-issued-links`）から導出する非拘束の可視文言の話であり、
新しい属性を追加する理由にはならない（`ADR-0060`決定9と同じ非拘束の扱い）。この契約はPCとスマホ
の提示を分けない——`ADR-0062`決定4のFINALIZED局面向けタブ／開閉行の分岐（板G1/G2で提示形態が
分かれた）とは異なり、板S4は1本のタブ列をPC・スマホ共通で描いており、本決定もそれに合わせて
renderModesを持ち込まない。

### 決定4. 選択中の行の貼り付きと、地図ピンの2つの独立した視覚規則を明文化する

`shortlistedShopVotes.list.orderingInvariant`（票の多い順、無変更）へ、選択中の項目
（`data-finalize-selected="true"`）を実装がCSSで画面上端へ視覚的に貼り付けても、このDOM順
（＝票の順位）は変わらないという非拘束の注記を加える——番号の丸のような、リスト位置から導出する
表示はこのDOM順のまま保たれる。`item.detailFields.map.marker`の`requirement`へ、このマーカーの
大きさ・色が、同じ`data-shop-id`で相関する項目自身の`data-current-leader`（`ADR-0055`決定6、
いちばん人気＝緑）と`data-finalize-selected`（幹事が選んでいる＝スミ色・大きさ）という、既に
存在する独立した2つの属性から導出できるという注記を加える——新しい属性は増やさない。この契約は
2つの信号を1つの視覚状態へ混同することだけを禁じ（票の最多店と幹事の選択店は一致しないことが
ある）、具体的な色・サイズ倍率・表現手段（アイコンかサイズかその両方か）は実装選択のまま固定
しない。

## 検討した代替案

- **決定1で、局面の札をSELECTING_SHOP以外の局面（SCHEDULING・FINALIZED）でも落とす**: 却下。
  人間の裁定は「店を選び中の幹事画面」という1局面の板だけを対象にしており、他の2局面の板を
  人間が同時に確認した事実はない——スコープを板が示した範囲に限定した。
- **決定1で、`gathering-phase-indicator`自体を廃止し、代わりにheadingBarへ局面値を複製する**:
  却下。人間の言葉は「局面の札は画面から落とす」であり、値そのものの必要性を否定していない
  （参加者側は今も必要とする）。廃止ではなく、この1局面での不在として表現する方が、将来
  SCHEDULING/FINALIZEDでこの要素を読む既存のテスト・実装との互換性を保つ。
- **決定2で、`gathering-dashboard-title`/`-confirmed-date`をSELECTING_SHOP以外の局面にも
  広げる**: 却下。板S4が対象にしたのはこの局面の画面であり、他の2局面（特にFINALIZEDは既に
  `decisionBanner`という別の見出し相当を持つ）を同時に裁定した事実はない——次にSCHEDULING局面の
  板を扱う回にarchitectが人間へ確認すべき対象として残す（下記「未決事項」）。
- **決定2で、「この会を削除」の設置場所（見出し行）を新しいgeometry属性として契約に明記する**:
  却下。`ADR-0062`決定2が同種の要望（「決める」ボタンの位置）を契約変更なしで閉じた前例と
  同じ理由——この契約は個別要素の画面上の位置を固定する設計を採っていない。
- **決定3で、PCとスマホで異なる提示形態（タブ／開閉行）を`ADR-0062`決定4と同じように分岐させる**:
  却下。板S4はPC・スマホの両方に対して同じ1本のタブ列を描いており、板G1/G2のような提示の分岐を
  人間が裁定した事実はない——この契約が元々持たないrenderModesの概念を、根拠なく持ち込む理由が
  無い。
- **決定3で、`respondedSummary`/`unansweredSummary`自身の`presenceRule`もタブの状態に連動させる
  （非選択時は絶対にDOMから消す）**: 却下。`ADR-0062`決定4の`answersOpen`/`linksOpen`が
  `responseTable`/`participantLinkList`自体の`presenceRule`を変えなかったのと同じ判断——
  「存在」と「可視」を分け、対象要素自体は常に存在し続けるという、この契約が確立済みの区別を
  踏襲する。
- **決定4で、地図ピンの色・大きさを判定するための新しい合成属性（例:
  `data-marker-visual-state`）を新設する**: 却下。両方の信号（`data-current-leader`・
  `data-finalize-selected`）は既に別々の場所（項目自身／その`finalizeSelect`子要素）に存在し、
  `data-shop-id`によるマーカーとの相関も既に確立済みである——合成属性を新設することは、
  `ADR-0059`決定6・`ADR-0060`決定7が確立した「複製は将来のドリフトの温床」という判断に反する。
- **決定4で、選択中の項目をDOM順そのものの先頭へ実際に並べ替える（orderingInvariantを変える）**:
  却下（人間裁定）。人間の言葉「残りは票が多い順のまま並べ、番号の丸は票の順位を保つ」は、
  DOM順（＝票の順位）そのものは変わらないことを明示的に要求している——視覚的な貼り付き（CSS）
  だけがこの要望を満たす。

## 帰結

- `contracts/gathering-scheduling-browser-interface.yaml`（改訂、現行contractVersion 0.24.2 ->
  0.25.0）: 決定1（`phaseIndicatorAttributes`の`presenceRule`狭め）、決定2（新規
  `organizerDashboard.headingBar`、`allowedPurposes`/`verifiesScenarios`への追加なし——
  headingBar自身はいずれの操作的コントロールも持たない）、決定3（新規
  `organizerDashboard.shopSelectionPanel`、`allowedPurposes`へ4件追加）、決定4
  （`shortlistedShopVotes.list.orderingInvariant`・`item.detailFields.map.marker.
  requirement`への非拘束の注記追加）を反映する。**具体的なYAML編集は本ADRと同じ提出物
  （`projects/dining-radar/.spec/selecting-layout.spec`のdiff指定）を参照。**
- `contracts/gathering-scheduling.feature`: 新規TDR-GTH-67（決定2、headingBarの新しい内容を
  検証する）を追加する。決定1・3・4はいずれも既存の値の存在規則・可視性・非拘束の視覚表現だけを
  扱い、業務言語で書く新しい事実を生まないため、対応する新規シナリオは無い（`ADR-0062`決定2、
  追補21・22が同種の判断で新規シナリオを伴わなかったのと同じ扱い）。**具体的な差分は同diff
  指定を参照。**
- `contracts/gathering-scheduling-api.yaml`: 変更しない——決定1〜4のいずれも、
  `gathering-scheduling-api.yaml`が既に返している値（`Gathering.phase`/`title`/
  `confirmedCandidateDateId`が指す`startAt`、`ShortlistedShop`の`wantToGoCount`/`okToGoCount`/
  `respondedParticipantCount`等）だけで構築・検証できる新しいDOM表現であり、新しいAPIフィールド・
  新しいエラーコードを要求しない。
- `contracts/test-support-api.yaml`: 変更しない——決定1〜4のいずれも、既存の
  `setShortlistedShops`・`setShopVotes`・`confirmCandidateDate`等が既に公開している境界だけで
  構築・検証できる新しいGiven状態を要求しない（`ADR-0060`帰結・`ADR-0061`帰結・`ADR-0062`帰結と
  同じ理由）。
- `product-brief.md`・`ARCHITECTURE.md`・`design.md`: 変更しない——本ADRは会スコープの契約内部の
  画面構成・観測面の変更であり、製品境界・モジュール境界を変えない。

## 未決事項（次工程・人間への申し送り）

1. **決定1の実装上の帰結**: SELECTING_SHOP局面を幹事側から検証してきた既存のL4実装が
   `gathering-phase-indicator`を直接読んでいた場合、この局面の間だけ`participantAnswer.
   header`かAPIレスポンス自身へ読み替える対応が要る。この契約自体は`participantAnswer.
   headerAttributes`という代替の観測面を既に持っており、新しい観測面を要しない——実装対応の
   要否と範囲はdeveloper/testerの実装時の確認事項として申し送る。
2. **SCHEDULING局面の見出し**（決定2で新設したheadingBar相当の値をSCHEDULING局面にも広げるか）
   は、本ADRの範囲外——板S4はSELECTING_SHOP局面だけを対象にしており、次にSCHEDULING局面の板を
   扱う回にarchitectが人間へ確認することを推奨する。
3. **見出し・タブ・浮かせた一覧・スティッキーな選択行・ピンの色とサイズの具体的な実測**
   （44px下限、タブのキーボード到達性、CSSスティッキーの挙動、色のコントラスト等）は、
   `ADR-0059`決定5・`ADR-0060`決定5・`ADR-0062`未決事項2と同じくorchestratorの領分——実装が
   固まった段階で確認する。本ADR自身は、決定3の4件のタブに最初からtestId/purposeを与えている
   ため、追補21・22のような事後登録は不要なはずである。
