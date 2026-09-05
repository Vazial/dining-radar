---
id: 0046
scope: project/dining-radar
status: 提案中
date: 2026-09-05
approved_by: null
supersedes: []
superseded_by: null
relates_to:
  [P-04, P-06, P-08, ADR-0013, ADR-0025, ADR-0034, ADR-0039, ADR-0044,
   ADR-0045, TDR-GTH-38, TDR-GTH-39, TDR-GTH-41]
---

# ADR-0046: 三段階投票・地図・店の情報の観測面を閉じ、定休日と未回答店の食い違いを記録する

> **承認者向けサマリ**: `ADR-0044`/`ADR-0045`はAPI契約（`gathering-scheduling-api.yaml`
> v0.7.0）を確定させたが、ブラウザ契約（`gathering-scheduling-browser-interface.yaml`）は
> designerの画面（`PickFive.dc.html`／`Vote.dc.html`／`Organizer.dc.html`／`Final.dc.html`）が
> 描き終わるまで、三段階投票・地図・店の情報の観測面を意図的に「stale」のまま残していた
> （`ADR-0013`の順序）。本ADRは、その観測面をブラウザ契約へ実際に書き込む際にarchitectが下した
> 技術的な設計判断——(1) 店のページリンク（`<a>`）がpurpose宣言の走査対象外であることの確認、
> (2) 新設の地図要素の識別子設計、(3) 定休日（`regularHoliday`）をどの画面にも出さないと決めた
> こと——を記録する。人間のチャット裁定を経ない、architect自身の技術的な整合性判断であるため、
> `meta/adr/0064`の作法に従い`status: 提案中`・`approved_by: null`とする。あわせて、今回の
> ブラウザ契約起草で新たに見つかった1件の食い違い（確定後の「答えないまま締まりました」表示と
> APIスキーマの不一致）を、解消せず報告する（P-08）。**2026-09-05、この食い違い（決定4・
> 未決事項3）は人間のチャット裁定により決着した——末尾の未決事項節を参照。**

## 文脈

### 0. 検証の申告（meta/adr/0039）

本ADRが前提とする事実は、`gathering-scheduling-api.yaml`（v0.7.0、`ADR-0044`/`ADR-0045`で
既に確定・コミット済み）のスキーマと、designerの画面ファイル（`E:\AWS\dsg-out\party\
PickFive.dc.html`／`Vote.dc.html`／`Organizer.dc.html`／`Final.dc.html`）の実際の記述を
読んで確認した。**確認していないのは、これらのHTMLファイルが人間による最終承認を経た「確定
版」であるか、それとも一部が依然として選択肢を提示する下書き（`Vote.dc.html`のQ1〜Q4のような）
のままかである**——`Vote.dc.html`自体がQ1（並び順）・Q2（検索基点の開示）を選択肢として提示して
いたが、これらは`ADR-0044`決定2・`ADR-0045`が既に人間裁定で決着させている論点と同一であり、
本ADRはその決着済みの答えを正とする。

## 決定

### 決定1. 店のページリンク（`<a>`）はpurpose宣言の走査対象外とする

`PickFive.dc.html`自身が「店のページリンクは`<a>`なのでpurpose宣言の走査に掛かる……
architectが判断すること」と申し送っていた。`unavailableControls.
forbiddenFormControlCategories`（`gathering-scheduling-browser-interface.yaml`）は
`[select, input, textarea, checkbox, radio, range, combobox, listbox, slider,
spinbutton, button]`であり、素の`<a>`を含まない。この契約は既に`candidate-gathering-entry`
（`candidate-search-browser-interface.yaml`）と同じ「`formControl: false`、purpose宣言不要」
という様式の先例を持っている。今回新設する`gathering-open-shop-list-item-provider-page-link`・
`gathering-shop-vote-question-provider-page-link`の2要素を、`<a href>`として実装する限り
同じ様式で扱う——新しいallowedPurposesは追加しない。

### 決定2. 新設の地図要素は、candidate-searchの識別子を再利用しない、この契約固有の識別子とする

`unavailableControls.forbiddenTestIds`は`candidate-map`・`candidate-origin-marker`・
`private-search-origin`の再利用を禁じているが、地図という概念そのものを禁じているわけではない
——`ADR-0044`決定4・`ADR-0045`はいずれも、これらの禁止識別子とは別の、gathering固有の地図要素を
将来定義してよいことを前提としていた。本ラウンドで以下を新設する。

- 幹事の5件選定画面（`shortlistSelection.list`）: `gathering-open-shop-map`／
  `gathering-open-shop-map-marker`（店のピンのみ、検索基点は出さない——`ADR-0044`決定4）。
- 参加者の投票画面（`shopVoteQuestion`）: `gathering-shop-vote-map`／
  `gathering-shop-vote-map-marker`（店のピン）に加え、`gathering-search-origin-marker`
  （検索基点、`ADR-0045`）。`candidate-origin-marker`とは別の識別子とする——同じ識別子を使うと
  `forbiddenTestIds`の禁止に抵触する。

幹事の投票中タリー画面（`shortlistedShopVotes`、`Organizer.dc.html`状態②）には地図・店の
ページリンクを追加しない——designerの2026-09-04改訂はこの画面に三段階の内訳だけを反映しており、
`TDR-GTH-38`の受入文自体も「その日に開いている店の一覧」（`shortlistSelection`）だけを対象に
している。この非対称は設計上の判断であり、契約の見落としではない。

### 決定3. 定休日（`regularHoliday`）はどの会画面にも出さない

`Final.dc.html`の確定した店の帯には「定休 日曜・祝日」という行が残っているが、
`regularHoliday`は`gathering-scheduling-api.yaml`のどのスキーマ（`OpenShopPreviewItem`／
`ShortlistedShop`／`ParticipantShopVoteOption`／`LiveProjectedShop`）にも存在しない。

**足さないと決めた**。理由は3点——

1. 本ラウンドの依頼はブラウザ契約（`gathering-scheduling-browser-interface.yaml`）の書き換えに
   限定されている。`regularHoliday`を追加するにはAPIスキーマ（v0.7.0、既にコミット済み）の
   改訂を伴い、本ラウンドの範囲外である。
2. `PickFive.dc.html`自身が同じラウンドで「定休日を行から外した」と明記しており、その理由
   （「この一覧はすでに『開いている店』だけであり、定休日を出しても常に無意味な値しか出ない」）
   は`Final.dc.html`の帯にも一部当てはまる——確定した店は既に「開催日に開いている」ことが
   前提であり、`regularHoliday`が示す情報は決定そのものには影響しない。
3. `ADR-0044`決定4が明示する地図・店の情報6項目（位置・徒歩のめやす・席数のめやす・禁煙対応・
   予算感の目安・店のページへのリンク）に`regularHoliday`は含まれていない——人間裁定が具体的に
   列挙した範囲の外にある。

`Final.dc.html`自身は「確定後のこの帯はあとから何度でも開かれる記録なので残した」という
別の理由（再訪時の参考情報）を挙げているが、この理由は`ADR-0044`決定4が列挙した6項目とは
独立の、新しい製品判断であり、本ADRの範囲では決めない——将来出す判断をするなら、APIスキーマの
拡張を伴う独立した人間判断・ADRが要る。

### 決定4. 未解決のまま報告する：確定後の未回答店の表示とAPIスキーマの不一致

`Final.dc.html`のB-3「あなたが店にどう答えたか」一覧は、投票開始後に絞り込みへ加わったが一度も
回答していない店（例示: ▽▽ラーメン）も「答えないまま締まりました」という行として描いている。
一方、`gathering-scheduling-api.yaml`の`ParticipantDecisionShopVote`
（`decision.yourShopVotes`）は、`yourVote`がnullの店を明示的に除外する——この除外規則は
`adr/0041`由来の既存の設計判断であり、`adr/0044`の三段階化でも変わっていない。

この2つは矛盾する：designerの絵は5行（回答2件・回答なし1件を含む）を想定しているが、APIの
`yourShopVotes`配列は回答した店の分（例では4件）しか返さない。**解消しない**——APIを変える
（nullの`yourVote`を持つ店も含める）か、designerの絵からこの行を落とすかの判断は、本ADRの
範囲（ブラウザ契約の技術的整合性）を超える独立した人間判断であり、`gathering-scheduling-
browser-interface.yaml`の`finalizedView.decision.shopVote.unresolvedDesignNote`として
報告するにとどめる（P-08）。

## 検討した代替案

- **`regularHoliday`をAPIスキーマへ追加し、`Final.dc.html`の帯をそのまま実装する**:
  **不採用（今回は見送り）**。本ラウンドの依頼範囲（ブラウザ契約）を超え、既にコミット済みの
  APIスキーマv0.7.0への再改訂を要する。将来、人間が「確定後の店の情報に定休日を含めたい」と
  明示的に判断すれば、独立したADRとして起こすのが適切。
- **店のページリンクに新しいpurpose（例: `gathering-open-shop-provider-page-open`）を追加する**:
  **不採用**。`<a href>`としての実装がすでに`forbiddenFormControlCategories`の外側にあり、
  `candidate-gathering-entry`の先例と同じ扱いで足りる——新しいpurposeを追加する理由がない。
- **未回答店の表示食い違いを、APIの`yourShopVotes`にnullステータスの行を含める形で今回decide
  してしまう**: **不採用**。P-08（契約を満たせない時は止まって報告する）に従い、これは
  ブラウザ契約の技術的整合性の範囲を超える製品判断であり、人間の判断を仰ぐべき論点である。

## 帰結

- `contracts/gathering-scheduling-browser-interface.yaml`をv0.5.2→v0.6.0へ改訂した
  （本ADRと同一PRで提出）。三段階投票・地図と店の情報・参加者の並びの安定化・検索基点の開示の
  観測面をすべて記述し、`profiles.localAcceptance.verifiesScenarios`へTDR-GTH-38/39/40/41を
  追加した。
- `contracts/test-support-api.yaml`をv1.5.2→v1.5.3へ改訂した——TDR-GTH-41の
  `x-acceptance-scenarios`登録漏れを解消した（新しいseamは要らない）。
- `gathering-scheduling-api.yaml`・`gathering-scheduling.feature`・`product-brief.md`は
  本ADRでは変更しない——本ADRは既存契約（v0.7.0で確定済み）の上に、ブラウザ観測面の起草時に
  下した技術的判断を記録するにとどまる。
- `ARCHITECTURE.md`・`design.md`は変更しない——本ADRは新しいモジュール境界を生まない。

## 未決事項（次工程・人間への申し送り）

1. **本ADRは人間のチャット裁定を経ていない**（`meta/adr/0064`書式に従い`status: 提案中`・
   `approved_by: null`とした）。決定3・決定4の判断そのものに異論があれば、人間のレビューを経て
   `承認済み`へ改める。
2. 決定3（定休日を出さない）は、`Final.dc.html`の「あとから何度でも開かれる記録」という
   designerの理由への直接の反論ではなく、本ラウンドのスコープ外という理由による見送りである。
   人間が定休日の表示を望むなら、別ADRでAPIスキーマ拡張から着手する必要がある。
3. ~~決定4（確定後の未回答店の表示）は完全に未解決である——次にこの画面の契約・実装に触れる者は、
   人間に判断を仰ぐこと。~~ **2026-09-05、決着した**（`meta/adr/0064`書式、人間裁定・チャット
   選択肢UI）。人間の裁定は「答えないまま締まりました」と出す——確定後の参加者画面には、投票に
   かかった店が全部並び、自分が答えなかった店もそう分かる形にする、というもの。理由はP5の意図
   （自分がどう答えたかを振り返れる）に忠実であること。この裁定を受け、以下を改訂した（本注記と
   同一PR）——`gathering-scheduling-api.yaml`（v0.7.0→v0.8.0）: `ParticipantDecisionShopVote.
   status`を`nullable: true`へ改め、`decision.yourShopVotes`が確定時点で`Gathering.
   shortlistedShops`にあった店を全件含むようにした（未回答の店は`status: null`）。
   `gathering-scheduling-browser-interface.yaml`（v0.6.0→v0.7.0）: `finalizedView.decision.
   shopVote.unresolvedDesignNote`を、`statusValues`へ`UNANSWERED`センチネルを加えた確定要件へ
   書き換えた（`scheduleQuestion`/`shopVoteQuestion`が既に使うnull-to-sentinel様式の再利用）。
   `gathering-scheduling.feature`: TDR-GTH-34へ、投票にかけられた店の中に一度も答えなかった店が
   1件ある前提と、その店が「答えないまま締まった店」として示されることを検査する一文を追加した。
   **本決定3節・決定4節本文・検討した代替案・帰結の各節はP-06に従い書き換えていない**——この
   注記のみが決着の記録である。
4. `Organizer.dc.html`状態②の「店を絞りなおす」「5件を差し替える」2ボタンの区別（`ADR-0042`が
   残した未決事項）は本ADRの範囲外であり、引き続き未決のままである。
