---
id: 0049
scope: project/dining-radar
status: 承認済み
date: 2026-09-09
approved_by: "人間裁定（2026-09-08 チャット選択肢UI、9枚のスクリーンショットを見た実機フィードバック、
  8件。人間の言葉『すべて確定・再交渉不可』）。裁定1: 『7枚目: 選び方が微妙。というか1枚目の画面の
  存在価値がなくなってない？（重複しているように思える）』——会の中の『開いている店から選ぶ』画面
  （P1、adr/0041）を廃止し、ランチ候補画面のカードに『この会に入れる』を置く。裁定2: 『日程を聞いて
  いる段階の店は件数だけ』——『この日に開いている店 37件』の一覧は出さない（多すぎて判断材料に
  ならない）。裁定5: 『候補日はカレンダーで複数選択』——ブラウザ標準の日付入力をやめる。『きれいな
  UIのライブラリなんてたくさん落ちてるので使いましょう』。時間は12:00–13:00を既定にし、選べるのは
  明日以降のみ（今日と過去は選べない）。裁定6: 『PCのランチ候補画面を2カラムに戻す』——『微妙。右に
  地図で一覧左とかじゃなかったっけ』。2026-08-28に採った『地図全面＋下部インセットの横デッキ』
  （adr/0031決定7・8）と、地図を主役にするためのカード圧縮（adr/0031決定9相当）を差し替える。
  裁定7: 『スマホのカードは1枚ずつきっちり止まる』——スワイプが途中で止まって見切れる症状を直す。
  裁定8: 『会への入口の文言を分かる形に』——『会』を『ランチ会』へ言い換える。あわせて同日の
  designer判断（差し戻し可）として、余白とボタンの小ささの是正、参加者の投票画面への店のページ
  リンクの必須化、幹事の投票中画面での最有力候補の強調を記録する。designerが判断せず残した
  R3（『この会に入れる』の外し方と5件到達後の見せ方）・R4（カレンダー選択の送信方法）はarchitectが
  本ADRで決定する。"
supersedes: []
superseded_by: null
relates_to:
  [P-02, P-04, P-06, P-08, ADR-0013, ADR-0018, ADR-0020, ADR-0023, ADR-0025,
   ADR-0031, ADR-0032, ADR-0033, ADR-0034, ADR-0035, ADR-0038, ADR-0040,
   ADR-0041, ADR-0042, TDR-GTH-08, TDR-GTH-44, TDR-GTH-45, TDR-GTH-46,
   TDR-GTH-47, TDR-CS-17, TDR-CS-18, TDR-CS-19]
---

# ADR-0049: 店選びをランチ候補画面へ一本化し、候補日のカレンダー複数選択とPCの2カラム表示を導入する

> **承認者向けサマリ**: 人間が本番の会フローを通しで触り、9枚のスクリーンショットとともに8件の
> 裁定を下した（2026-09-08、選択肢UIで確定・再交渉不可として提示）。本ADRはそのうち画面構成と
> データモデルに関わる5件（裁定1・2・5・6・7、および裁定8の文言変更）と、それに伴い無効になった
> 既存の決定（P1〔ADR-0041〕・2026-08-30追加裁定の店プレビュー一覧・ADR-0031決定7〜9）を扱う。
> 参加者の可視性規則の反転・確定後の記録の簡素化・会の削除は、性質の異なる決定（すでに決着した
> 約束を覆すもの）としてADR-0050が扱う。
>
> **設計判断の要点**: (1) 店選びを`candidate-search`（ランチ候補画面）へ一本化することで、
> `candidate-search`と`gathering-scheduling`という2つのスライスの契約が初めて1画面で交わる。
> 読み取り・絞り込み・表示（母集団のうち「決まった日に開いている店」を出す・カードに「この会に
> 入れる」の状態を出す）は`candidate-search-api.yaml`が持ち、書き込み（会の持ち物である
> `shortlistedShops`を変える）は既存の`gathering-scheduling-api.yaml`の`setShortlistedShops`を
> そのまま再利用する——店を選ぶ操作を2つの契約に分けて重複させない。(2) この一本化にともない、
> `gathering-scheduling-api.yaml`の`OpenShopPreviewItem`・`CandidateDateOpenShopPreview.
> previewShops`（店の一覧を返す仕組み）は使い道を失う。**削除する**——非推奨のまま残さない
> （理由は本文4節）。(3) 日程を聞いている段階の店プレビューも、一覧ではなく件数だけに縮める
> （`openShopCount`は残し、店の一覧は返さない）。(4)候補日はカレンダーで複数選択し、1回の送信で
> まとめて登録する新しい操作（`addCandidateDates`、複数形）を設け、単数形の`addCandidateDate`を
> 置き換える。時間の既定値（12:00–13:00）は契約に新しいフィールドを持たせない——会の「終わりの
> 時刻」を持つという設計判断ではなく、UI側の入力補助にとどめる。今日と過去の日付は拒否する。
> (5) PCの2カラム表示は、2026-08-28の「地図全面＋下部デッキ」（ADR-0031決定7・8）とそのための
> カード圧縮（ADR-0031決定9相当）を置き換える——送りボタン・件数カウンタ（ページング）はPCでは
> 不要になる（5件が一覧に収まるため）。モバイルの地図主体・スワイプ送りは変えない。**業務言語で
> 表現できる部分（`.feature`ファイル）・product-brief.mdは本ADRと同一の作業で改訂済みである。
> 技術契約（`-api.yaml`・`-browser-interface.yaml`）への反映は次工程で行う（下記帰結参照）。**

## 文脈

### 0. 検証の申告（meta/adr/0039）

本ADRが前提とする既存契約の記述は、`gathering-scheduling-api.yaml`（v0.9.0）・
`gathering-scheduling-browser-interface.yaml`（contractVersion 0.9.0）・`candidate-search-api.yaml`
（v1.2.0）・`candidate-search-browser-interface.yaml`（contractVersion 1.7.0）・
`gathering-scheduling.feature`（TDR-GTH-01〜43）・`candidate-search.feature`（TDR-CS-00〜16）を
実際に読んで確認した。designerの板（`E:\AWS\dsg-out\party\Deck.dc.html`・`DeckPhone.dc.html`・
`Calendar.dc.html`・`Organizer.dc.html`・`Handoff.dc.html`・`Decisions.dc.html`）も実際に読んだ。
**確認していないのは、これらの契約変更を実装したコードの挙動そのもの**——architectは実装コードを
読まない（`.claude/agents/architect.md`の禁止事項）。

### 1. 何が起きたか

本番デプロイ済みの会フロー（第1〜4弾、ADR-0035〜0048）を人間が通しで触り、9枚のスクリーンショット
とともに所見を述べた。designerが板を起こし、2026-09-08のチャット（選択肢UI）で8件が決着した
（`Decisions.dc.html`参照）。このうち画面構成・データモデルに関わる5件を本ADRが扱う。

### 2. なぜ一本化するか（裁定1の背景）

人間の言葉は「1枚目の画面の存在価値がなくなってない？（重複しているように思える）」である。
ADR-0041のP1は「投票にかける5件は幹事ダッシュボードの中の一覧からチェックで選ぶ（既存の候補画面
には触れない）」ことを、既存の絞り込み・地図・凍結ゲートに触れずに済むという理由で選んでいた
——しかし、この選択の結果、店を選ぶ体験が2つの画面（ランチ候補画面と会ダッシュボード内の簡易な
一覧）に分裂し、後者は前者が持つ絞り込み・徒歩圏の輪・地図を持たない劣化版になっていた。人間は
実機でこの重複に気づき、劣化版を捨てて既存の充実した画面へ一本化することを選んだ。

## 決定

### 決定1（裁定1）. 店選びをランチ候補画面へ一本化し、会モードを新設する

`gathering-scheduling-api.yaml`の`organizerDashboard`内の店選び（`shortlistSelection`、
PickFive.dc.html系の流れ）を廃止し、`candidate-search`（ランチ候補画面）に**会モード**を新設する。

**会モードの成立条件**: `candidate-search-api.yaml`の`proposeCandidates`（`POST
/candidate-proposals`）が新規の任意リクエストフィールド`gatheringId`を受け取る。これが有効な
gatheringId（呼び出し元organizerが持つ会で、局面が`SELECTING_SHOP`）を指すとき、会モードが成立
する。局面が`SCHEDULING`（まだ開催日が決まっていない）を指す場合は`GATHERING_NOT_IN_SELECTING_
SHOP_PHASE`で拒否し、`FINALIZED`を指す場合は`GATHERING_FINALIZED`で拒否する（いずれも
`gathering-scheduling-api.yaml`の同名コードをそのまま再利用する——本ファイルに新しいコードは
増やさない）。存在しない、または呼び出し元が持たないgatheringIdは`GATHERING_NOT_FOUND`で拒否する。

**母集団の絞り込み**（裁定1・「会モードでは、決まった日に開いている店で母集団を絞る」）:
会モードが成立するとき、候補の母集団は既存の絞り込み（ジャンル・居酒屋バー・禁煙・カード払い・
予算感・徒歩の上限）に加えて、「その会の確定済み開催日に開いている店」だけへ絞られる。判定方式は
`gathering-scheduling-api.yaml`が確立した曜日ベースの`regularHoliday`緩い照合（ADR-0035決定6）を
サーバー内部で再利用する——これは同一プロセス内の関数呼び出しであり、ネットワーク越しの契約結合
ではない。**この絞り込みは幹事が外せない**——他の絞り込みと違い、絞り込みパネルのトグルではなく、
会モードである限り常に適用される固定条件として画面に示す（Deck.dc.html C-1板の「いまの条件」の
1行目、「8/27 (水) に開いている店」）。

**カードの状態**: 会モードが成立するとき、`CandidateProposalResponse.candidates`の各要素
（`Candidate`）へ次の2フィールドを追加する。
- `shopId`（文字列、会モード時のみ非null）: `gathering-scheduling-api.yaml`の
  `OpenShopPreviewItem.shopId`・`ShortlistedShop.shopId`と同じ、opaqueな店舗識別子。この値を
  そのまま`setShortlistedShops`（後述）へ渡す。
- `isShortlisted`（真偽値、会モード時のみ非null）: この店が、その会の現在の`shortlistedShops`に
  含まれているかどうか。

**会の文脈**: `CandidateProposalResponse`へ、会モード時のみ非nullの`gatheringContext`
（新設オブジェクト）を追加する——`{gatheringId, title, confirmedCandidateDate,
shortlistedShopCount, maxShortlistedShops}`。`maxShortlistedShops`は常に5固定値だが、契約として
明示することで「入れた店 3 / 5」という帯の右辺の出どころを機械的に定義する。

**「この会に入れる」の書き込み**: 新しいエンドポイントは作らない。トグルは既存の
`gathering-scheduling-api.yaml`の`setShortlistedShops`（`PUT
/gatherings/{gatheringId}/shortlisted-shops`、完全置換）をそのまま呼ぶ——ブラウザは現在の
`shortlistedShops`（`Gathering`から、または直近の`gatheringContext`の情報と合わせてクライアント側
で保持する集合）に、押した店の`shopId`を足すか除いた配列を送る。この設計は「書き込みは会の持ち物を
変える操作なので会の契約が持つ」という原則をそのまま守り、2つの契約に同じ書き込みロジックを重複
させない。

**旧`shortlistSelection`の廃止**: `gathering-scheduling-browser-interface.yaml`の
`organizerDashboard.shortlistSelection`（`gathering-open-shop-list`・`-item`・
`gathering-open-shop-select`・`gathering-shortlist-submit`・付随する`gathering-open-shop-map`・
`-marker`・detailFields一式）は全廃する。`gathering-scheduling-api.yaml`の`setShortlistedShops`
操作自体（PUT、完全置換の意味論）はそのまま維持する——変わるのは「どの画面から、どの手順で」
呼ぶかだけである。`organizerDashboard.shortlistedShopVotes`（投票タリー画面、Organizer.dc.html
状態②の「お店の候補」パネル）は維持する——店を選ぶ操作ではなく票を読む・確定する操作であり、
一本化の対象ではない（下記決定5参照）。`gathering-shortlist-open`（「店を絞りなおす」「5件を
差し替える」）の`requiredOutcome`は、旧`shortlistSelection`を再び開くのではなく、ランチ候補画面
（会モード）へ遷移するよう改める——D7（差し替え時に残った店の票を引き継ぐ）の意味論はAPI側
（`setShortlistedShops`）で変わらず成立する。

新規シナリオTDR-GTH-44（幹事は店を1件ずつ会に入れたり外したりできる）・TDR-CS-17（同、この画面
から見た記述）・TDR-CS-18（会モードでは候補が開催日に開いている店へ絞られる）を追加した（下記
帰結参照）。

### 決定2（裁定2）. 日程を聞いている段階の店プレビューを件数だけにする

2026-08-30の追加裁定が導入した「候補日を仮に選ぶと、その日に開いている店のプレビュー一覧が出る」
（`gathering-scheduling-browser-interface.yaml`の`tentativeSelectionAndPreview.preview`、
`gathering-open-shop-preview-item`）を**無効にする**。`gathering-scheduling-api.yaml`の
`CandidateDateOpenShopPreview`から`previewShops`（`OpenShopPreviewItem`の配列）を削除し、
`candidateDateId`・`openShopCount`だけを残す。`previewOpenShopsForCandidateDate`
（`GET /gatherings/{gatheringId}/candidate-dates/{candidateDateId}/open-shop-preview`）操作
自体は残す——件数だけを返す軽い問い合わせとして引き続き使う。

**`OpenShopPreviewItem`スキーマ自体を削除する**（非推奨のまま残さない）。理由は、この一本化の後、
店の一覧を表示する役目を負う画面が製品からもう1つも無くなるためである——決定1により5件選定の
一覧表示はランチ候補画面（`candidate-search-api.yaml`の`Candidate`）へ完全に移り、
`OpenShopPreviewItem`を参照する契約要素は無くなる。使われない可能性のあるスキーマを「後方
互換のため」残すことは、この契約が発行済みの公開APIではなく（`DRAFT`のまま、人間の承認前）、
かつ実装が未着手のままP-04（ルール化できるものを文章で書かない、契約は要らなくなったら消す）の
精神にも沿う。

`gathering-scheduling.feature`のTDR-GTH-08を、店の一覧を求める記述から件数だけを求める記述へ
書き換えた（下記帰結参照）。

### 決定3（裁定5）. 候補日はカレンダーで複数選択し、時間は12:00–13:00を既定、明日以降のみ選べる

`gathering-scheduling-api.yaml`に新しい操作`POST /gatherings/{gatheringId}/candidate-dates:batch`
（`operationId: addCandidateDates`、複数形）を新設し、既存の単数形`addCandidateDate`
（`POST /gatherings/{gatheringId}/candidate-dates`）を**置き換える**（削除する。理由は下記
「R4の解決」参照）。`createGathering`のリクエストボディが最初から複数の`candidateDates`を
受け取る設計だったこと（ADR-0035決定1）に、この操作を合わせる。

**リクエスト形状**: `AddCandidateDatesRequest{candidateDates: CandidateDateInput[], minItems: 1}`
——`CreateGatheringRequest.candidateDates`と同じ形状を再利用する。

**全部やるか全部やめるか（R4の解決その1）**: バッチ内のいずれか1件でも既存の候補日、または
バッチ内の他の要素と`startAt`が重複する場合、**バッチ全体を`DUPLICATE_CANDIDATE_DATE`で拒否**
する——1件だけを飛ばして残りを登録する部分成功は行わない。理由は、`createGathering`が既に
同じ全部拒否の方針を持っており（同一リクエスト内の重複を全体拒否）、部分成功はカレンダーで
選んだ日の一部だけが登録され残りが登録されないという、幹事にとって説明の要る中間状態を生む
ためである。

**明日以降のみ（R4の解決その2、新規制約）**: `candidateDates`の各`startAt`について、その日付
部分（時刻を除く）がサーバーの現在日付以降でない場合——すなわち今日または過去の日付である
場合——バッチ全体を新しいエラーコード`CANDIDATE_DATE_NOT_IN_FUTURE`で拒否する。この検査は
`createGathering`・`addCandidateDates`の両方に適用する（カレンダーは会をつくる画面
（E-2）でも候補日を足す画面（A①）でも同じ入力面を使うため、Calendar.dc.htmlの記述どおり）。
日付の境界（「今日」の判定基準タイムゾーン）は実装判断とし、契約では固定しない——既存の他の
時刻境界（レート制限の具体値、有効期限の長さ）と同じ非拘束の扱いに揃える。

**終わりの時刻は持たない（R4の解決その3）**: `CandidateDateInput`／`CandidateDate`スキーマは
変更しない——`startAt`（開始時刻）だけを持ち、終わりの時刻（例: 13:00）を表すフィールドは
追加しない。「12:00–13:00」という既定値は、カレンダーUIが時刻入力欄にあらかじめ入れておく
値（begin=12:00）と、UI側だけが表示する終わりの目安（+1時間、UI定数）であり、サーバーへは
送らず、会のレコードにも保持しない。**理由**: この製品のどの機能も終わりの時刻を消費しない
（会の確定・投票・分母計算・並び替えのいずれも開始時刻だけで足りる）。使われない値をスキーマへ
追加することは、将来「終わりの時刻を編集する」「終わりの時刻で並べる」といった機能が実際に
要求されるまで見送る（P-02、P-05の精神——要るようになってから足す）。この判断はCalendar.dc.html
自身が「会が終わりの時刻を持っているかは契約で確かめられなかった」と申し送っていた問いに対する
architectの決着である。

**カレンダーライブラリの選定**: 契約の範囲外とする（人間の指示どおり、architectは特定の
ライブラリを選ばない）。契約が要求するのは、この操作が受け付けるリクエスト形状（配列・時刻を
含むISO-8601 date-time・重複拒否・過去日拒否）だけであり、選択UIの実装手段（複数選択カレンダー
ライブラリの選定）はdeveloperの裁量に委ねる。

`gathering-scheduling.feature`へ新規シナリオTDR-GTH-46（バッチ登録・重複時の全体拒否）・
TDR-GTH-47（今日以前の日付拒否）を追加した（下記帰結参照）。

### 決定4（裁定6）. PCのランチ候補画面を2カラム（左に一覧・右に地図）へ戻す

`candidate-search-browser-interface.yaml`の`renderModes.mapPrimaryLayout`（2026-08-28、
ADR-0031決定7・8が導入した「地図全面＋下部インセットの横デッキ」、送りボタン
`candidate-deck-previous`/`-next`・件数カウンタ`candidate-deck-position`のページング窓）を
**無効にする**。人間の言葉は「微妙。右に地図で一覧左とかじゃなかったっけ」——2026-08-26時点の
決定1（案1、1列を絞る＋地図sticky）に近い形へ戻すが、カードの中身は今回大きく組み直したもの
であり、当時と同一の形には戻らない。

**新しいrenderMode**: `renderModes.twoColumnLayout`を新設し、`mapPrimaryLayout`を置き換える
（`mapPrimaryTouchLayout`、モバイルのスワイプ送りは変更しない——PC幅とモバイル幅で骨格が
分かれること自体は意図した結果である、DeckPhone.dc.htmlの明記どおり）。`twoColumnLayout`は
専有のtest idを持たない——最大5件のカードをすべて一覧として表示するため、送りボタンも
スワイプサーフェスも要らない。したがって`deckNavigation.previousControl`/`nextControl`/
`position`（`candidate-deck-previous`/`-next`/`-position`）・`unavailableControls.
allowedPurposes`の`candidate-deck-page-previous`/`candidate-deck-page-next`はいずれもPC幅では
不在になる——`candidate-deck-position`はモバイル幅（`mapPrimaryTouchLayout`）でのみ引き続き
必要（DeckPhone.dc.htmlの「2 / 5」表示）。

**カードの圧縮を戻す**（ADR-0031決定9相当の解除）: 地図を主役にするために圧縮していたカードの
密度（紹介文1行・factsを横1列・26pxのリンク行）を戻す——地図を主役にする理由自体が2カラムでは
成立しないため。これにより「26pxのリンク行がADR-0020決定4の44px検査に抵触しうる」という当時の
懸念も消える（Deck.dc.html板の指摘どおり）。

**D-fix 1・D-fix 2の前提消滅**（2026-09-01、ADR-0038付随のdesigner判断）: D-fix 1（PCカードの
高さを揃える）・D-fix 2（件数ピルの位置をページャー形式にする）は、いずれも地図主体デッキが
前提だった——2カラムでは、高さを揃える必要も、送りボタンの間にピルを置く場所そのものも無くなる。
この2点は「無効」ではなく「前提が変わった」ものとして扱う——契約は元々D-fix 1・2の位置・寸法を
拘束していなかった（D-fix 1の`candidate-card-payment-caution`presenceRuleだけが契約に残る
Mustであり、この規則自体は2カラムでも変わらず適用される）。

### 決定5（裁定7）. モバイルのカードは1枚ずつきっちり止まる

`candidate-search-browser-interface.yaml`の`deckNavigation.swipeSurface`
（`candidate-deck-swipe-surface`、`mapPrimaryTouchLayout`専有）に、指を離した位置に依存せず
常に1枚のカードが画面中央で完全に止まることを要求する記述を追加する——designerが提案した
実装手段（`scroll-snap-type: x mandatory`・各カードに`scroll-snap-align: center`）は
architectが契約として固定しない（実装手段の選択はdeveloperの裁量。この点はカレンダー
ライブラリの選定と同じ扱い）。契約が固定するのは結果——**指を離した位置によらず、常に
ちょうど1枚のカードが完全に見える状態で止まる**——である。この性質の検証は、寸法・幾何が
絡む性質であるため、既存の方針（ADR-0020）どおりL5（レンダリング幾何スナップショット）の
管轄とし、L4（機能的な受け入れ）へは新しいMustを追加しない——`candidate-deck-position`の
`data-deck-visible-start`/`-end`が引き続き「1枚だけが見えている」ことを間接的に示す
（`visibleStart == visibleEnd`が常に真になる、という新しい制約をこの属性の記述へ加える）。

### 決定6（裁定8）. 会への入口の文言を「ランチ会」へ変える——契約変更は不要

`candidate-search-browser-interface.yaml`の`candidate-gathering-entry`・
`gathering-scheduling-browser-interface.yaml`の`gathering-list`関連要素は、いずれも可視文言
（ボタンのラベル・見出しの語）を契約のMustとして固定していない——`candidate-gathering-entry`の
`requirement`は要素の実装形（`<a>`等）と活性化時の振る舞いだけを定め、`gathering-list-empty`の
案内文言も同様に固定していない。したがって「会」から「ランチ会」への言い換えは、**この契約への
変更を一切要求しない**——コピーの変更のみで完結する（Handoff.dc.html板自身も「コピーはすべて
下書き、確定は実装／L5に残す」と明記している）。本決定はこの事実の確認として記録する。

### 決定7. Handoff案C（地図の上に帯）は不採用のまま——ADR-0020決定4(a)は無変更

Handoff.dc.htmlの3案（A・B・C）から人間が選んだのは、2026-09-01と同じ**案B**（枠付きボタン＋
進行中件数バッジ）であり、文言だけが「会」から「ランチ会」へ変わった（決定6）。**案C（地図の上に
帯を出す）は選ばれていない**。designer自身が案Cについて「凍結ゲートに触れる恐れがある——
ADR-0020決定4(a)（狭幅で地図が到達可能であること）の実装根拠が`candidate-map`の
`position: fixed; top: 0`に置かれており、地図の上に帯を置くとこの根拠が崩れる」と警告していた
（Handoff.dc.html板）。**案Bのままであるため、この懸念は現実化しない**——ADR-0020決定4(a)・
凍結ゲートの実装根拠は無変更のまま成立する。本決定は「変更が不要である」ことの確認として記録する。

### 決定8（R3の解決）. 「この会に入れる」は幹事が外し方を持ち、5件到達時は未選択のボタンを非活性にする

designerがR3として残した2点を、architectが以下のとおり決定する。

**外し方**: Deck.dc.html板が描いたとおり——カード側の「この会に入れました」を**もう一度押すと
外れる**。これは決定1が定める`setShortlistedShops`の完全置換の意味論と自然に合致する（現在の
配列からその`shopId`を除いた配列を送るだけであり、専用の削除エンドポイントを増やさない）。
designerが懸念した「1回のクリックで会の中身が減る事故」は、確認ダイアログを挟むほどの重さでは
ないと判断する——理由は、外した後もいつでも同じボタンを押し直せば戻せる（削除ではなく
トグルであり、会そのものの削除〔決定はADR-0050が扱う〕とは可逆性が異なる）ためである。

**5件到達後の見せ方**: 未選択（`isShortlisted: false`）のカードの「この会に入れる」ボタンは、
`gatheringContext.shortlistedShopCount`が`maxShortlistedShops`（5）以上のとき**非活性
（disabled）にする**——ボタンごと消す、薄く残すだけで押せる状態にする、の2案は採らない。
理由は、この契約が既に確立している「境界条件では非活性にする、要素を消さない」という一貫した
流儀（`deckNavigation.disabledState`・`gathering-schedule-response-select`等、多数の前例）に
揃えるためである。既に選択済み（`isShortlisted: true`）のカードのボタンは、5件到達後も
外す操作として引き続き活性のままにする——5件目を外して別の店を選び直す動線を塞がないため。

`gathering-scheduling.feature`へ新規シナリオTDR-GTH-45を、`candidate-search.feature`へ新規
シナリオTDR-CS-19を追加した——いずれも「会に入れられる店は最大5件である」ことを検査する、この
画面から見た同じ業務規則である（下記帰結参照）。

## 検討した代替案

- **`OpenShopPreviewItem`を削除せず、非推奨として残す**: 却下（決定2）。この契約はまだ
  `DRAFT`（人間の承認前）であり、公開済みAPIの後方互換を守る理由がない。使われなくなった
  スキーマを残すことは、次にこの契約を読む者への負担を増やすだけである。
- **候補日の複数選択を、既存の単数形`addCandidateDate`をN回呼ぶクライアント側ループとして
  実装する（新しいエンドポイントを増やさない）**: 却下（決定3）。重複判定・過去日判定を
  「全部やるか全部やめるか」で行うには、サーバー側が一括で見る必要がある——N回の個別呼び出しでは、
  一部が成功し一部が失敗する中間状態を避けられない。
- **会モードの母集団絞り込み（決まった日に開いている店）を、`candidate-search-api.yaml`側でも
  独立した曜日照合ロジックとして再実装する**: 却下（決定1）。同じ判定を2箇所に持つと、
  将来どちらか一方だけが変更されて食い違う再発を招く（`ADR-0043`が是正したのと同種の問題）。
  サーバー内部の共有関数として一本化する。
- **PCの2カラムでも「5件」の一覧を送りボタンでページングする（決定4のdeckNavigationを
  维持する）**: 却下。5件は1画面の一覧に収まる分量であり、ページングは不要な操作を1つ増やす
  だけである——モバイルのスワイプは画面が狭いために必要だが、PCの2カラムにその制約はない。
- **モバイルの「1枚ずつ止まる」動作の実現手段（scroll-snap等）を契約のMustにする**: 却下
  （決定5）。実装手段はdeveloperの裁量とし、契約は結果（1枚だけが見える）だけを固定する——
  カレンダーライブラリの選定と同じ非拘束の扱いに揃える。
- **「この会に入れる」を外すときに確認ダイアログを挟む**: 却下（決定8）。トグルは可逆であり、
  会そのものの削除（ADR-0050が扱う、不可逆）と同じ重さの確認を要求する理由がない。

## 帰結

- `contracts/candidate-search-api.yaml`（改訂、次のversion、ステータス: 承認待ち）:
  `CandidateProposalRequest`へ`gatheringId`（任意）を追加。`Candidate`へ`shopId`・
  `isShortlisted`（いずれも会モード時のみ非null）を追加。`CandidateProposalResponse`へ
  `gatheringContext`（会モード時のみ非null）を追加。新エラーコード`GATHERING_NOT_FOUND`・
  `GATHERING_NOT_IN_SELECTING_SHOP_PHASE`・`GATHERING_FINALIZED`を`ProblemResponse.code`へ
  追加（`gathering-scheduling-api.yaml`と同名のコードを再利用し、意味を割らない）。
  **具体的なYAML編集は次工程で行う**（ファイルの分量を理由に、1ファイルずつ・段階を分けて進める
  という今回の依頼の作法どおり）。
- `contracts/candidate-search-browser-interface.yaml`（改訂）: `gatheringMode`という新設節に、
  会モードの帯（`candidate-gathering-mode-band`等、名称は次工程で確定）・カードの
  「この会に入れる」トグル（新規purpose、`allowedPurposes`へ追加）・disabledState（決定8）の
  観測面を追加する。`renderModes.mapPrimaryLayout`を`twoColumnLayout`へ置き換え、
  `unavailableControls.allowedPurposes`から`candidate-deck-page-previous`・
  `candidate-deck-page-next`を削除する。`deckNavigation.swipeSurface`へ「1枚だけが見える」
  制約を追記する。**具体的なYAML編集は次工程で行う。**
- `contracts/gathering-scheduling-api.yaml`（改訂）: `CandidateDateOpenShopPreview`から
  `previewShops`を削除。`OpenShopPreviewItem`スキーマを削除。`addCandidateDate`を
  `addCandidateDates`（複数形、バッチ）へ置き換え、新エラーコード
  `CANDIDATE_DATE_NOT_IN_FUTURE`を追加。**具体的なYAML編集は次工程で行う。**
- `contracts/gathering-scheduling-browser-interface.yaml`（改訂）: `organizerDashboard.
  shortlistSelection`節を全廃。`gathering-shortlist-open`のrequiredOutcomeを
  ランチ候補画面への遷移へ改める。`gathering-add-candidate-date-*`関連の要素をカレンダー入力
  （複数選択）に合わせて改める。**具体的なYAML編集は次工程で行う。**
- `contracts/gathering-scheduling.feature`（改訂、**本ADRと同一の作業で完了済み**）: TDR-GTH-08
  を件数だけを求める記述へ書き換えた。新規シナリオTDR-GTH-44（トグルでの追加・除外）・
  TDR-GTH-45（5件上限）・TDR-GTH-46（候補日のバッチ登録・重複時の全体拒否）・TDR-GTH-47
  （今日以前の日付拒否）を追加した。TDR-GTH-26は業務としての意味（開いている店から5件を選び、
  投票が始まる）が変わらないため本文を変更していない。
- `contracts/candidate-search.feature`（改訂、**本ADRと同一の作業で完了済み**）: 会モードでの
  絞り込み（TDR-CS-18）・「この会に入れる」のトグル（TDR-CS-17）・5件上限（TDR-CS-19）を検査
  する新規シナリオを追加した。既存シナリオ（TDR-CS-00〜16）は本文を変更していない。
- `product-brief.md`（改訂、**本ADRと同一の作業で完了済み**）: §1・§2「幹事ダッシュボード」
  「候補を絞る」・§3・§5・§6・§8を、決定1〜8（会モードの新設、店選びの一本化、カレンダー入力、
  PCの2カラム表示、モバイルのカード送り）に合わせて改訂した。
- `ARCHITECTURE.md`・`design.md`: 店選びの一本化により、候補探索（`candidate-search`）と
  会・日程調整（`gathering-scheduling`）の境界が変わる（初めて1画面で交わる）——次工程の
  YAML改訂と同じタイミングで反映する。

## 未決事項（次工程・人間への申し送り）

1. **本ADRが確定させた仕様のうち、`-api.yaml`・`-browser-interface.yaml`への反映は次工程で
   行う**——`.feature`ファイル・`product-brief.md`は本ADRと同一の作業で改訂済みである。
   `gathering-scheduling-api.yaml`・`gathering-scheduling-browser-interface.yaml`・
   `candidate-search-api.yaml`・`candidate-search-browser-interface.yaml`（合計6,500行超）への
   実際の編集は、1ファイルずつ・段階を分けて行う（今回の依頼の作法どおり）。
2. **`gatheringId`の開示がADR-0018（durable provider ID採用の保留）に触れるかどうか**:
   `gathering-scheduling-api.yaml`は既に`shopId`という「opaqueな店舗識別子」を認証済み幹事へ
   露出している（`OpenShopPreviewItem.shopId`等、ADR-0038・0042）。本ADRの決定1は、同じ
   識別子の概念を`candidate-search-api.yaml`にも会モード限定で持ち込む——新しい開示境界を
   越えるものではないと判断したが、ADR-0018が「provider ID採用は利用規約の再確認後」と
   保留していることとの関係は、人間が明示的に確認していない。次にADR-0018を扱う者は本決定を
   参照材料にできる。
3. **PC 2カラムの列幅・カードの密度・地図の比率は未実測**——`meta/adr/0059`決定5どおり、
   designerの板の寸法はすべて作図上の値である。実測はorchestratorの領分。
4. **モバイルの「1枚ずつ止まる」が実際に実現できているかの確認**——contract上は結果だけを
   固定し実装手段を指定していないため、実機での確認が要る（L5、orchestrator）。
