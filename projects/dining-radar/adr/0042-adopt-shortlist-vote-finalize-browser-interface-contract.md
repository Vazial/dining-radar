---
id: 0042
scope: project/dining-radar
status: 承認済み
date: 2026-09-04
approved_by: "人間裁定（2026-09-03 チャット: 会スコープ契約第1弾の実機確認で『作りかけ。見て判断
  できるところまで作りこんでほしい』と述べ、店の絞り込み連携・承認投票・確定を1本の契約スライスへ
  統合するよう明示指示した。この指示に基づき、orchestratorは本ラウンド（designerがPickFive.dc.html
  ・Final.dc.htmlを仕上げ判断待ちゼロにした後のbrowser-interface契約）の画面骨格承認を、個別の
  チャット裁定としてではなく、この一連の契約PRのマージ自体を承認行為として束ねる運用とした——
  『見て判断できるところまで作りこんでほしい』という人間の意図（作り込みを深め、まとまった単位で
  最終確認する）を、骨格承認と実装承認の分離ではなく統合として解釈したものである。meta/adr/0064の
  作法に従い、この運用上の解釈自体をここに明記する。"
supersedes: []
superseded_by: null
relates_to: [P-06, P-08, ADR-0009, ADR-0013, ADR-0023, ADR-0034, ADR-0035, ADR-0036,
  ADR-0038, ADR-0039, ADR-0040, ADR-0041]
---

# ADR-0042: 5件選定・投票・確定のbrowser-interface契約を起草する（ADR-0013の順序、骨格承認と実装承認を1回に束ねる）

> **承認者向けサマリ**: designerが会フロー後半の残り2枚——`PickFive.dc.html`（5件選定、
> `ADR-0041`のP1〜P3を反映）・`Final.dc.html`（A③幹事の確定後・B-3参加者の確定後、P4・P5を
> 反映）——を仕上げ、判断待ちがゼロになった。`ADR-0013`の順序（画面が先、契約は追随する）に従い、
> `gathering-scheduling-browser-interface.yaml`をv0.4→v0.5へ拡張し、店の絞り込み連携・承認投票・
> 確定・確定後表示の観測面を起草した。`activeContext.md`が第1弾の完了以来記録してきた「FINALIZED
> 局面の観測面ギャップ」をこれで閉じ、`ADR-0040`未決事項2（`gathering-list-item`の会の名前
> data属性）も解消した。
>
> **この一連のPRのマージ自体が画面骨格の承認行為を兼ねる**——依頼文の明示指示どおりであり、
> `meta/adr/0064`が禁じる「起草後に事後的に『本PRのマージをもって承認』と書く」パターンとは異なる。
> 人間が2026-09-03チャットで「見て判断できるところまで作りこんでほしい」と述べたこと自体が、
> 骨格承認と実装承認を分離せず束ねる運用の根拠であり、これを承認の実体として`approved_by`へ
> 引用する。
>
> **設計判断の要点**: (1) `OpenShopPreviewItem`に`shopId`を追加した（`gathering-scheduling-
> api.yaml`側、architect自己監査）——5件選定のチェックリストが実際に送る`shopId`を特定する手段が
> 起草時点のAPIに無く、この契約の起草によって実装不能な仕様であることが判明したため。(2) 幹事の
> チェック・ラジオ選択はローカルの保留状態とし、送信ボタンでだけ`setShortlistedShops`/
> `finalizeGathering`を呼ぶ（`candidate-search-browser-interface.yaml`のフィルタパネルと同じ
> 保留→適用の流儀）。(3) 参加者の投票チェックは逆に、チェックのたびに即座に`setShopVotes`を呼ぶ
> （Vote.dc.html「選ぶとその場で保存されます」、送信ボタンを持たない）。(4) FINALIZED局面で、
> SCHEDULING/SELECTING_SHOP専用の操作的コントロール（候補日追加・仮選択・この日にする・リンク新規
> 発行・失効・5件差し替え・確定）をすべて不在にし、再コピーだけを残す（P4）。(5) 参加者の確定後
> 画面は、日程・投票の内訳表示を`decision`の一枚要約で完全に置き換える（共存ではなく置き換え、
> `gathering-scheduling-api.yaml`が残していた未決の書き方を決着させた）。(6) FR-028として1件
> 報告する: Organizer.dc.html状態②の「店を絞りなおす」「5件を差し替える」という2つの異なる文言の
> ボタンを、今回のdesigner材料は区別し直していない——同じpurposeの2インスタンスとして扱った。

## 文脈

### 1. 何が起きたか

`ADR-0040`・`ADR-0041`が起草した`gathering-scheduling-api.yaml` v0.5.0（店の絞り込み連携・
承認投票・確定を統合した契約）に対し、designerが画面を描く番になった。designerは
`PickFive.dc.html`（5件選定の2案、P1〜P3裁定を反映）・`Final.dc.html`（A③幹事の確定後・B-3
参加者の確定後、P4・P5裁定を反映）を仕上げ、判断待ちをゼロにした——`Flow.dc.html`（局面を進める
2操作=緑の塗り／局面内の重要操作=緑の輪郭という凡例の更新）・`Organizer.dc.html`（A②投票中の
画面、今回は「承認済み・無変更」として扱われる）とあわせて、会フロー全体の画面骨格が揃った。

`ADR-0013`が確立した順序（画面が先、契約は追随する）に従い、architectは本ADRでこれらを承認済み
設計としてbrowser-interface契約の観測面を起こす。

### 2. 骨格承認と実装承認を1回に束ねる運用

依頼文は「骨格承認はこの一連のPRのマージが承認行為という扱い（人間の『見て判断できるところまで
作りこんでほしい』という指示に基づき、骨格承認と実装承認を1回に束ねる。0064書式で記録すること）」
を明示した。これは`meta/adr/0064`が禁じる「承認の実体を曖昧にしたまま事後的に正当化する」
パターンとは異なる——2026-09-03の人間の発言そのものが、この運用（骨格確認と実装確認を分離せず、
一連の契約PRのマージでまとめて判断する）の根拠として遡って引用できる、明示的な人間の意図表明で
あるためである。本ADRの`approved_by`はこの経緯をそのまま記す。

### 3. `OpenShopPreviewItem.shopId`の欠落発見

`PickFive.dc.html`案A（採用）は、幹事ダッシュボード内の開いている店の一覧にチェックボックスを
置き、チェックした店の集合を`setShortlistedShops`へ送る——板自身が「右の一覧でチェックが入って
いる店の集合が`shortlistedShops`」と契約語彙に明示的に対応づけている。この観測面を契約に起こす
段になり、`previewOpenShopsForCandidateDate`（`ADR-0040`が「5件選定の下見にも再利用する」と
した既存エンドポイント）の`OpenShopPreviewItem`が、起草時点（`ADR-0035`）から一貫して表示専用
フィールドしか持たず、`shopId`を含んでいないことに気づいた——`CandidateDateOpenShopPreview.
previewShops`の説明文自体が「この対応づけ方法は固定しない」と明示的に先送りしていた箇所である。
チェックボックスと実際に送信する`shopId`を結びつける具体的な観測面を書こうとして初めて、この
先送りが実装不能な仕様だったことが判明した。architectはこれを自己監査による修正として
`gathering-scheduling-api.yaml`へ`shopId`を追加した（本ADRの帰結を参照）。

## 決定

### 決定1. 5件選定面は保留チェック＋送信ボタンとする

`organizerDashboard.shortlistSelection`を新設し、`gathering-open-shop-list`
（`gathering-open-shop-list-item`、`data-shop-id`・`data-shortlisted`属性）と
`gathering-shortlist-submit`（「この◯件で投票する」）を定義した。チェックボックス
（`gathering-open-shop-select`）の活性化はローカルの保留状態を切り替えるだけで、公開APIを
呼ばない——`candidate-search-browser-interface.yaml`の`changePendingFilter`（保留→`apply`で
初めて確定）と同じ流儀を踏襲した。下限1件（P2）・絞り込みなし（P3）をそのまま反映する。

### 決定2. 投票開始後は別の面（差し替え可）に切り替える

`organizerDashboard.shortlistedShopVotes`を新設し、`gathering-shortlisted-shop-list`
（`data-approval-count`・`data-responded-count`、D7の店ごと分母）と、確定用の
`gathering-finalize-shop-select`（ラジオ、これもローカル保留）・`gathering-finalize-submit`
（`finalizeGathering`を呼ぶ）を定義した。`Gathering.votingStartedAt`が非nullになると
`shortlistSelection`から`shortlistedShopVotes`へ表示が切り替わり、「5件を差し替える」
（`gathering-shortlist-open`）を押すと`shortlistSelection`が再び開き、現在の
`shortlistedShops`で事前チェックされる（D7）。

### 決定3. FINALIZED局面で操作的コントロールを閉じ、記録だけを残す

`activeContext.md`が記録してきた「FINALIZED局面の観測面ギャップ」を、次の閉じ方で解消する。

- `gathering-confirm-date-select`・`gathering-add-candidate-date-open`・
  `gathering-candidate-date`の仮選択purpose・`gathering-shortlist-open`・
  `gathering-finalize-shop-select`／`-submit`・`gathering-participant-link-copy`・各行の
  `gathering-participant-link-item.revoke`は、いずれもFINALIZED（前3つはSCHEDULING専用のため
  SELECTING_SHOP到達時点で既に不在）になると不在にする。
- `gathering-candidate-date-list`／`gathering-shortlisted-shop-list`／
  `gathering-participant-link-list`／各種サマリ属性は、記録としてそのまま残す（`Final.dc.html`
  の「日程の記録」「票の記録」「発行済みリンク」パネル）。
- `gathering-participant-link-item.recopy`だけは、局面に関わらず一貫して到達可能なままにする
  （P4）。

### 決定4. 参加者の投票は即時送信、確定後は完全な置き換え

`participantAnswer.shopVoteQuestion.selectOption`（`gathering-shop-vote-select`）は、活性化
のたびに参加者の承認集合全体を`setShopVotes`へ即時送信する——`Vote.dc.html`が「選ぶとその場で
保存されます」と明示し、専用の送信ボタンを持たないため、`shortlistSelection`の保留モデルとは
意図的に非対称にした。

`participantAnswer.finalizedView`（`gathering-participant-decision`、`Final.dc.html`B-3）は、
`ParticipantView.decision`が非nullになった時点で、`gathering-schedule-question`・
`gathering-shop-vote-question`・`gathering-participant-progress`のいずれも完全に不在にし、
`decision`の一枚要約（自分の出欠回答・自分が選んだ店、他者の情報は一切含めない、P5）だけを
表示する。`gathering-scheduling-api.yaml`の`ParticipantView.decision`は「これらを`decision`と
並べて表示するかどうかは後続の契約が決める」と未決のまま残していたが、`Final.dc.html`が実際に
どちらを選んだか（完全な置き換え）を示したため、本ADRはこれを決着として反映する。

### 決定5. `OpenShopPreviewItem`へ`shopId`を追加する（自己監査）

文脈3の発見を受け、`gathering-scheduling-api.yaml`の`OpenShopPreviewItem`へ`shopId`
（必須）を追加し、`previewShops`の説明文から「対応づけ方法を固定しない」という先送りの記述を
削除した。この契約はまだ人間未承認のドラフトであり、影響を受ける実装が存在しないため、この時点
での追加は破壊的変更としての懸念を伴わない。

### 決定6. `gathering-list-item`へ会の名前属性を追加する

`ADR-0040`未決事項2（監査指摘: `gathering-list-item`に会の名前を機械観測する属性が無い）を、
`data-gathering-title`属性の追加で解消した。

### 決定7（FR-028）. 「店を絞りなおす」と「5件を差し替える」を区別しない

`Organizer.dc.html`状態②は、`ADR-0036`承認時から変わらず、日程パネル脇に「店を絞りなおす」・
「5件を差し替える」という2つの異なる文言のボタンを描いている。今回のdesigner材料
（`PickFive.dc.html`・`Final.dc.html`）はこの2つの意味上の違いを再定義しておらず、
`Organizer.dc.html`自体も本ラウンドでは「承認済み・無変更」として扱われている。architectは
この2つを同じ`gathering-shortlist-open`purposeの2インスタンス（`gathering-create-open`が
ヘッダーと空状態の2箇所に現れるのと同じcardinalityの流儀）として扱った——これが正しいかは
人間の確認を要する未決事項として申し送る（下記参照）。

## 検討した代替案

- **5件選定のチェックボックスも参加者の投票チェックボックスと同じ即時送信モデルにする**: 却下
  （決定1）。`PickFive.dc.html`は明示的に「3 / 5 件を選びました」という保留カウンタと専用の
  送信ボタンを描いており、チェックのたびに`setShortlistedShops`を呼ぶ設計ではない——D7の
  差し替えも「選び直してから1回押す」操作として描かれている。
- **確定後の参加者画面で、日程回答・投票の内訳を`decision`と並べて残す（共存）**: 却下
  （決定4）。`Final.dc.html`B-3は明確に`decision`と「あなたの記録」だけを描き、既存の
  per-candidate-date/per-shopの内訳UIを再掲していない。
- **「店を絞りなおす」「5件を差し替える」に異なるpurpose・異なる振る舞いを与える**: 却下
  （決定7）。今回の入力材料にはこの2つを区別する根拠が無く、architectの推測で振る舞いを分岐
  させるとFR-028の精神（食い違いは解消せず報告する）に反する。同じpurposeとして扱い、食い違いを
  記録するにとどめた。
- **`OpenShopPreviewItem.shopId`の欠落を、browser-interface契約側だけで（DOM順序による相関
  など）回避する**: 却下（決定5）。`setShortlistedShops`が受け取る`shopIds`はサーバーが検証
  する実在の店舗識別子であり、ブラウザが独自に発明した値では成立しない——APIレスポンスに
  無い値をクライアントが送信できるはずがなく、根本的な情報の欠落はAPI側でしか埋められない。

## 帰結

- `contracts/gathering-scheduling-api.yaml`（更新、`version` 0.5.0→0.5.1、ステータス:
  承認待ち）: `OpenShopPreviewItem`へ`shopId`（必須）を追加し、`previewShops`の説明文を
  更新した（決定5）。
- `contracts/gathering-scheduling-browser-interface.yaml`（更新、`contractVersion` 0.4→0.5、
  ステータス: 承認待ち）: `organizerDashboard.shortlistSelection`・`shortlistedShopVotes`・
  `finalizedSummary`、`participantAnswer.shopVoteQuestion`・`finalizedView`を新設。
  `gathering-list-item`へ`data-gathering-title`を追加（決定6）。SCHEDULING専用コントロール
  （`confirmDate`・`addCandidateDateOpen`・仮選択purpose）とFINALIZED専用の不在ルール
  （`participantLinkCopy`・`participantLinkList.item.revoke`）へpresenceRuleを追記した
  （決定3）。`allowedPurposes`へ6件を追加（`gathering-open-shop-select`・
  `gathering-shortlist-submit`・`gathering-shortlist-open`・`gathering-finalize-shop-select`・
  `gathering-finalize-submit`・`gathering-shop-vote-select`）。`profiles.localAcceptance.
  verifiesScenarios`へTDR-GTH-26〜36を追加した。
- `contracts/gathering-scheduling.feature`・`product-brief.md`は本ADRでは変更しない——業務
  契約・製品文書はADR-0040・ADR-0041が既に確定させている。
- `ARCHITECTURE.md`・`design.md`は変更しない——本ADRは既存スライスの契約拡張であり、モジュール
  境界・依存方向を変えていない。

## 未決事項（次工程・人間への申し送り）

1. **決定7のFR-028報告**: 「店を絞りなおす」「5件を差し替える」を同じ`gathering-shortlist-open`
   purposeとして扱った判断が正しいか、人間の確認を要する。異なる振る舞いが必要と判明した場合は、
   本ADRを新しいADRで補う。
2. **母集団が多い日の5件選定**: `PickFive.dc.html`自身が「母集団が多い日の見え方は描いていない」
   と明示的に認めている——`openShopCount`が`previewShops`の件数（現状10件のキャップ）を超える
   場合、超過分の店はこの選定面から選べない。orchestratorの実測を経た再設計が必要になる可能性が
   ある未決事項として残す。
3. **`ADR-0035`から持ち越し、引き続き未決**: 会データの保持期間・削除方針、署名付きリンクの
   有効期限日数・レート制限の具体値（いずれも根拠の薄い暫定値）。
