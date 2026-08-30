---
id: 0036
scope: project/dining-radar
status: 承認済み
date: 2026-08-30
approved_by: "人間裁定（2026-08-30 チャット、選択肢UIで確定: designerが正規パイプラインで描き直した
  会スコープのキャンバス（`E:\\AWS\\dsg-out\\party\\`）のうち、F｜会の進みかた・A｜幹事ダッシュボード
  （①日程を聞き中／②店を選び中・投票実施中の2局面）・B｜参加者の回答の3枚を、会スコープ契約第1弾
  『会の作成と日程調整』の画面骨格として承認する。orchestrator実測: A板1120×664（局面①）・
  1120×764（局面②）、B板375×812、いずれもはみ出し0・切り詰め0・44px未満のタップ対象0。承認投票
  （B-2）・確定の画面は本裁定の対象外のまま残る。）。追って同日、リンク発行の導線についても人間裁定
  （2026-08-30 チャット、選択肢UIで確定: 案A「1クリック=1本」。押すたびに新しいリンクが1本発行・
  コピーされ、その場で相手に配る運用とする。画面は現状のまま、architectの暫定解釈（count: 1）を
  確定させる。まとめて複数本を発行する画面は今回追加しない）で決着した。さらに同日、人間の懸念
  「リンクがわからなくなったら管理されなくなっちゃうかもね」を発端に、人間裁定（2026-08-30 チャット、
  選択肢UIで確定: 発行済みリンクの管理面「一覧＋再コピー＋失効」を第1弾に含める。失効したリンクは
  D2の分母（発行本数）からも外れる。失効は未回答のリンクに対する操作に限定する——回答済みの参加者を
  外すのは別ユースケースで第1弾外とする）で第1弾のスコープが拡張された。"
supersedes: []
superseded_by: null
relates_to: [P-01, P-02, P-05, P-06, P-07, P-08, P-11, ADR-0005, ADR-0006, ADR-0009, ADR-0013, ADR-0023, ADR-0034, ADR-0035]
---

# ADR-0036: 会の作成と日程調整の画面骨格を承認し、browser-interface契約を起草する（ADR-0035決定5の後段）

> **承認者向けサマリ**: `ADR-0035`決定5は、会スコープ契約第1弾のbrowser-interface契約の起草を
> 「designerが正規パイプラインで画面を描き直し、人間が実機で承認した後」に送っていた。2026-08-30、
> designerが `E:\AWS\dsg-out\party\` へ画面を描き直し、人間がチャット（選択肢UI）でこのうち
> F（会の進みかた）・A①②（幹事ダッシュボードの2局面）・B（参加者の回答）を第1弾の画面骨格として
> 承認した（orchestrator実測: A板1120×664/1120×764、B板375×812、いずれもはみ出し0・切り詰め0・
> 44px未満のタップ対象0）。本ADRはこの承認を記録し、`ADR-0013`の順序（画面が先、契約は追随する）に
> 従って`contracts/gathering-scheduling-browser-interface.yaml`を起草したことと、その中で下した
> 7件の設計判断を記す。
>
> **設計判断の要点**: (1) F（説明図）は観測面を持たず、その内容はA・Bが描く要素（局面インジケータ等）
> として観測する。(2) 幹事面（認証済みセッション）と参加者面（署名付きリンクのtoken自体が資格情報、
> Cookieなし）は、認証モデルが根本的に異なるが同じ1本の業務・API契約を観測するため、ファイルは
> 1本のまま`browserControlSurface`の名前空間で分ける。(3) D3（幹事の店リストは票の多い順固定・
> 切替なし）の**原則**を`forbiddenPurposes`の`manual-ordering`という抽象カテゴリとして今回取り込み、
> 承認投票の画面（次スライス）や、本ADRで新設した発行済みリンク一覧が追加されたときも契約改訂なしに
> 同じ禁止が及ぶようにした。(4) 承認済み画面の「回答リンクをコピー」という単一ボタンと、API契約の
> `issueParticipantLinks`のバッチ`count`パラメータの間にあった食い違いは、architectが起草時点では
> 「1クリック=1件発行」という補完的解釈を採用したのみで人間の判断へ持ち越していたが、**同日
> 2026-08-30、続く選択肢UIで人間が案A「1クリック=1本」を選び、この解釈のまま確定した**——押すたびに
> 新しいリンクが1本発行・コピーされ、その場で相手に配る運用であり、まとめて複数本を発行する画面は
> 今回追加しない。(5) 参加者面の状態変更操作はCSRF保護を要求しない（token自体がambientでない資格
> 情報であるため）という設計判断を明記した。(6) organizerDashboard・participantAnswerの双方を
> JS-capableなブラウザ自動化DSL（`ADR-0009`決定4がTDR-CSに適用したのと同じ実行モデル）で検証すると
> 明示した（`ADR-0013`決定7・FR-004の教訓の先取り適用）。(7) **同日さらに、人間の懸念「リンクが
> わからなくなったら管理されなくなっちゃうかもね」を受け、発行済みリンクの一覧・再コピー・失効を
> 第1弾のスコープへ追加する人間裁定が下った**——architectは一覧にトークン/URLを再露出しない設計
> （再コピーは1件専用の別操作に限定）を採用し、D2の未回答分母を「発行本数−失効本数」へ再定義し、
> 失効を未回答のリンクに限定するという人間の制約に設計上の問題を見出さなかったことを記録する。

## 文脈

### 1. 何が起きたか

`ADR-0035`は会スコープ契約第1弾「会の作成と日程調整」の受け入れ契約（`gathering-scheduling.feature`）
とAPI契約（`gathering-scheduling-api.yaml`）を起草したが、browser-interface契約は起草しなかった
（決定5）——理由は、参照したdesignerキャンバス（`Flow.dc.html`・`Organizer.dc.html`・
`Answer.dc.html`）が`ADR-0034`決定5により「人間への入力・出発点」として扱われ、承認済み設計として
扱われていなかったためである。`ADR-0013`が確立した「画面が先、契約は追随する」という順序に従い、
architectは画面が承認されるまでbrowser-interface契約の起草を待った。

2026-08-30、designerがこれらのキャンバスを正規パイプラインで描き直し（`ADR-0035`が既にこの経緯を
記録している）、続けて人間がチャット（選択肢UI）で画面骨格を承認した。承認対象はF・A①②・Bの3枚
（4局面）であり、承認投票（B-2）・確定の画面は対象外のまま残る。orchestratorが実測したところ、
A板（PC幅）は1120×664（局面①: 日程を聞き中）・1120×764（局面②: 店を選び中・投票実施中）、B板
（スマホ幅）は375×812で、いずれもはみ出し0・切り詰め0・44px未満のタップ対象0だった。

本ADRは、この承認を受けてbrowser-interface契約を起草するための設計判断を記す。

### 2. F（Flow.dc.html）の扱い

`Flow.dc.html`は会の状態機械・幹事と参加者それぞれの操作の全体像を示す静的な説明図であり、
ボタン・入力欄など操作可能な要素を持たない（本文中の`.act`要素は装飾的なカード表示であり、
実際のアプリケーション画面のコントロールではない）。したがって、F自体に対応するbrowser-interface
契約の観測面は存在しない——その内容（局面が4つあること、状態を進める操作が3つだけであること、
締切が無いこと、分母の区別）は、実際の操作画面であるA・Bが描く要素として現れており、本契約は
そちらを観測する（決定1）。

### 3. 幹事面と参加者面の認証モデルの違い

`Organizer.dc.html`（A①②）は既存の`organizerSession`（同一起源Django session cookie、
`candidate-search-browser-interface.yaml`・`authentication-browser-interface.yaml`が既に定める
認証済み幹事の境界）の内側にある。`Answer.dc.html`（B）は`ADR-0034`決定3が定めた署名付き共有
リンクの内側にあり、ログイン・Cookie・アカウントを一切持たない——URLに埋め込まれたtoken自体が
唯一の資格情報である。この2つは根本的に異なる認証モデルであり、`authentication-browser-interface.
yaml`の`unauthenticated`/`authenticated`のような同一ファイル内の状態分岐では表現しきれない
（参加者面は「認証されていない訪問者」ではなく「別の資格情報方式で認証された参加者」であり、
サインインフォームへの誘導は起きない）。

### 4. D3の原則と承認投票画面の不在

`ADR-0035`は承認投票（B-2）を第3弾へ送っており、本スライスの契約は店の一覧を持たない。一方、
2026-08-30の人間裁定D3（幹事の店リストは票の多い順に固定し、並べ替えの切替を置かない）は、
まさにその店の一覧に関する裁定である。本スライスのbrowser-interface契約にD3の対象要素
（店の一覧）を先取りして定義することはできない——`ADR-0035`決定2の範囲外であり、まだ存在しない
画面のtest idを捏造することになる。

### 5. 「回答リンクをコピー」とバッチ発行APIの食い違い（同日中に決着）

`Organizer.dc.html`は「回答リンクをコピー」という単一のボタンだけを示す。一方
`gathering-scheduling-api.yaml`の`issueParticipantLinks`は`count`（発行本数）を受け取る
バッチ操作として設計されている——`ADR-0035`起草時点では、この画面はまだ承認されておらず
（`ADR-0034`決定5により人間への入力・出発点として扱われていた）、この食い違いは「まだ拘束力の
無いモックの細部」として扱ってよかった。本ADRの起草により画面が承認済み設計になったことで、この
食い違いは承認済み2成果物（画面とAPI）の間の実際の不整合になり、architectは決定4で「1クリック=1件
発行」という補完的解釈を採用しつつ、これを解消せず人間へ申し送った。**同日2026-08-30、続く選択肢
UIで人間が案A「1クリック=1本」を裁定し、この解釈のまま運用として確定した**——押すたびに新しい
リンクが1本発行・コピーされ、その場で相手に配る（例えばSlackやメールで個別に送る）運用であり、
まとめて複数本を発行して一覧表示する画面は今回追加しない。決定4を参照。

### 6. 発行済みリンクの管理面を第1弾へ追加する人間裁定

「1クリック=1本」の運用が確定した直後、人間から懸念が出た——「リンクがわからなくなったら管理
されなくなっちゃうかもね」。1件ずつ発行する運用では、幹事がどのリンクを誰に配ったか、どれが
まだ届いていない・迷子になっているかを見失いやすい。加えて、`ADR-0035`が定めたD2の分母
（「まだn人が未回答」＝発行済みリンクの本数）は、幹事が誤って余分に発行したリンクや、宛先を
間違えて届かなかったリンクがあると、それらが実際には誰にも使われないまま「まだ1人未回答」として
恒久的に残り続けるという弱点を持っていた。

人間はチャット（選択肢UI）で、発行済みリンクの管理面（一覧・再コピー・失効）を第1弾のスコープへ
追加する裁定を下した。要求の中身は次の3点である。

1. 幹事画面に発行済みリンクの一覧を置く。各項目は発行順・回答済みかどうか・参加者の表示名
   （名無しを含む）を示し、再コピー・失効の操作を持つ。
2. 失効したリンクはD2の分母（発行本数）からも外れる——これが今回の裁定の核である。
3. 失効は「未回答のリンク」に対する操作に限定してよい——回答済みの参加者を外すのは別ユース
   ケースであり、第1弾の対象外のままとする。

本ADRの決定7は、この裁定を`gathering-scheduling-api.yaml`・`gathering-scheduling-browser-
interface.yaml`・`gathering-scheduling.feature`（TDR-GTH-16〜20）へ反映するための設計判断を記す。

## 決定

### 決定1. F（Flow.dc.html）は観測面を持たない

`Flow.dc.html`に対応する`browserControlSurface`の名前空間を設けない。その内容は
`browserControlSurface.organizerDashboard.phaseIndicatorAttributes`（局面インジケータ）・
`denominatorAttributes`（2種の分母）を通じて観測する。

### 決定2. 単一ファイルに2つの面を名前空間で分けて収める

`gathering-scheduling-browser-interface.yaml`を1本のファイルとし、`browserControlSurface`配下に
`organizerDashboard`（認証済み幹事、`organizerSession`）と`participantAnswer`（署名付きリンクの
token、Cookieなし）という2つの名前空間を設ける。`candidate-search`/`authentication`のように
業務契約ごとにファイルを分けなかった理由は、両者が観測する業務契約（`gathering-scheduling.
feature`）・API契約（`gathering-scheduling-api.yaml`）が同じ1本だからである——`candidate-search`と
`authentication`は最初から別の`.feature`ファイルとして分離されたスコープを持つが、
`gathering-scheduling`はスコープとしては単一であり、内部に2つの異なる資格情報方式を持つに
すぎない。

`browserEntry`・`unavailableControls`（`allGatheringScreenFormControlsMustDeclarePurpose`・
`purposeAttribute: data-gathering-control-purpose`）は両名前空間で共有し、`securityObservations`
だけは面ごとに完全に分けた（決定5参照）。

### 決定3. D3の原則を`forbiddenPurposes`の抽象カテゴリとして先取りする

`unavailableControls.forbiddenPurposes`へ`manual-ordering`（`candidate-search-browser-
interface.yaml`が既に使う同名カテゴリの再利用）を追加する。これは特定の要素に紐づく禁止ではなく、
「この製品の幹事向け一覧はいずれも手動並べ替えを持たない」という抽象カテゴリの禁止であり、今回
実際に存在する候補日一覧（`gathering-candidate-date-list`）と、決定7で新設する発行済みリンク一覧
（`gathering-participant-link-list`）に適用されると同時に、将来の承認投票スライス（第3弾）が店の
一覧を追加したときも、`allowedPurposes`/`forbiddenPurposes`を改訂することなく同じ禁止が自動的に
及ぶ。`secondary-condition`も同じ理由で先取りした——`ADR-0005`決定4の禁止4カテゴリのうち、この
2つは店の一覧を持たない現段階でも予防的に意味を持つ（例えば候補日一覧に将来「補助条件」を足す
実装を防ぐ）。

D3が指す実際の店の一覧（承認投票の対象一覧）は本ADRでは定義しない——`ADR-0035`決定2の範囲外で
あり、まだ画面が存在しない。

### 決定4. 「回答リンクをコピー」は「1クリック=1本」の運用として確定した

`gathering-participant-link-copy`（testId）が1回活性化されるたびに`issueParticipantLinks`を
`count: 1`で呼ぶ。押すたびに新しいリンクが1本発行・コピーされ、幹事はその場で相手（Slack・メール
など、アプリの外）に個別に配る運用である。

起草時点では、これは画面（承認済み・単一ボタン）とAPI（`count`を受け取るバッチ操作として設計）の
間にあった食い違いに対するarchitectの補完的な最小解釈にすぎず、解消されたものではないとして人間へ
申し送っていた。**2026-08-30、続く選択肢UIで人間が案A「1クリック=1本」を選び、この解釈のまま
運用として確定した**——`issueParticipantLinks`が受け取れる`count`が1より大きい値を許容すること
自体は`gathering-scheduling-api.yaml`のスキーマ上変更しない（複数人分を一度に発行したいという
将来の運用要求が出た場合に備えた拡張余地として残す）が、この第1弾の画面・契約が実際に呼び出すのは
常に`count: 1`であり、まとめて複数本を発行して一覧表示する専用画面は今回追加しない。

### 決定5. 参加者面の状態変更操作はCSRF保護を要求しない

`securityObservations.participantAnswer.csrf: not-required`とし、理由を契約本文に明記した。
CSRFが防ぐのは「ブラウザが自動的に運ぶ資格情報（Cookie）を、被害者が意図しないクロスサイト
リクエストに乗せられること」であり、参加者面はambientな資格情報を持たない——token自体が
URLに明示的に含まれる資格情報であり、それを知らない攻撃者は偽装リクエストを作れない。token を
知っている攻撃者は、正規の参加者と同じアクセス権を既に持っている。この判断はarchitectの
セキュリティ設計判断であり、`product-brief.md` §5はこれを明示的に決めていない——人間のレビュー
対象として契約本文にその旨を記した。

### 決定6. 実行モデルを明示する（`ADR-0013`決定7・FR-004の教訓の先取り適用）

`organizerDashboard`・`participantAnswer`の双方を、`ADR-0009`決定4がTDR-CSに適用したのと同じ
JS-capableなブラウザ自動化DSLで検証すると`renderModel`節に明記した——TDR-AUTHのプレーンHTTP
DSLではない。理由は、同時決めプレビュー・回答後のタリー開示・名前の後付け・リンク一覧の再コピー/
失効後の即時更新のいずれも、ページ全体の再読み込みを伴わないクライアント側の状態変化を観測対象と
するためである。`ADR-0013`決定7が`authentication-browser-interface.yaml`へ事後的に追加した教訓
（実行モデル前提を起草時点で契約本文に明示する）を、本契約は起草時点から満たす。

### 決定7. 発行済みリンクの管理面（一覧・再コピー・失効）を第1弾へ追加する

文脈6の人間裁定を反映し、`gathering-scheduling-api.yaml`・`gathering-scheduling-browser-
interface.yaml`・`gathering-scheduling.feature`（新規TDR-GTH-16〜20）へ次の設計を追加した。

**API面（新規操作3件）**:

- `listParticipantLinks`（`GET /gatherings/{gatheringId}/participant-links`）: 発行順
  （`issuedAt`昇順）で全リンクを返す。失効済みも削除せず`revoked: true`で一覧に残す——失効を
  監査可能な操作にするため。
- `recopyParticipantLink`（`POST .../participant-links/{linkId}/recopy`）: 1件だけを対象に
  URLを再取得する。
- `revokeParticipantLink`（`POST .../participant-links/{linkId}/revoke`）: `hasResponded`が
  falseの間だけ受理する（`PARTICIPANT_LINK_ALREADY_ANSWERED`で拒否）。

**設計判断7-a. トークンの一覧内再露出はしない**: `ParticipantLinkSummary`（一覧の各項目）には
token・URLを含めない。再コピーはトークン等の資格情報を返す唯一の経路として`recopyParticipantLink`
に限定し、1回の呼び出しにつき1件だけを露出する。一覧を見るだけの操作（最も頻度が高いと想定される
操作）が、複数の参加者アクセス資格情報を一度に返す経路にならないようにするためである——一覧
レスポンスが漏洩・ログ混入した場合の被害範囲を、個々のrecopy呼び出しの被害範囲（1件）まで
最小化する。この判断はarchitectの設計判断であり、`product-brief.md`・`ADR-0034`・`ADR-0035`は
再露出の可否を明示的に決めていない——人間のレビュー対象として契約本文にその旨を記した。

**設計判断7-b. 管理用識別子`linkId`とアクセス用資格情報`token`を分離する**: 発行済みリンクの
管理操作（一覧・再コピー・失効）は、参加者アクセスに使う`token`とは別の、組織者向けの不透明な
識別子`linkId`を経路に使う。`linkId`を知るだけでは参加者ビューへアクセスできない——これにより、
管理操作のURL・ログ・トレースに`token`（参加者アクセス資格情報）が一切現れずに済む。

**設計判断7-c. D2の未回答分母を「発行本数−失効本数」へ再定義する**: `Gathering.
totalIssuedParticipantLinks`（生涯発行本数、監査用、単調増加・失効の影響を受けない）はそのまま
残し、新設の`totalRevokedParticipantLinks`（生涯失効本数）・`activeParticipantLinkCount`
（＝発行本数−失効本数）を追加した。D2の分母（「まだn人が未回答」）は
`activeParticipantLinkCount - respondedParticipantCount`へ改め、`totalIssuedParticipantLinks`
単体には二度と依拠しない。これが今回の人間裁定の核（「失効したリンクは分母からも外れる」）に
対応する部分である。

**設計判断7-d. 失効済みトークンへの応答**: 参加者が失効済みリンクを開くと`LINK_REVOKED`
（410、`LINK_EXPIRED`と同じHTTPステータスだが別コード）を返す。失効と有効期限切れは原因が異なる
ため、`LinkExpiredOrRevoked`という1つの共有レスポンス定義の中で`code`フィールドにより区別する。

**「失効は未回答のリンクに限定する」という制約の検討（FR-028）**: 依頼文は「この限定に設計上の
問題があれば、解消せず報告」を求めている。architectはこの限定を検討し、**構造的な設計上の問題は
見出さなかった**。理由は次の3点である。

1. `hasResponded`は`respondedParticipantCount`と同じ定義（日程回答が1件以上あること）を使うため、
   名前だけを付けて日程には未回答の参加者は「未回答」側に含まれ、失効の対象になりうる——これは
   人間の裁定文言（「未回答のリンク」）と整合する自然な解釈であり、矛盾は無い。
2. 失効と参加者の回答が競合するタイミング（幹事が失効を押す直前に参加者が回答を送信する等）は、
   APIがリクエスト処理時点で`hasResponded`を再確認して`PARTICIPANT_LINK_ALREADY_ANSWERED`を
   返すため、データの不整合（回答済みなのに失効させてしまう）は構造的に起きない——実装が
   トランザクション境界を正しく置けば済む、通常の並行性の配慮であり、契約設計上の欠陥ではない。
3. 「回答済みの参加者を外す」という別ユースケースを今回含めない判断は、人間が明示的に選んだ
   スコープ限定であり、`gathering-scheduling-browser-interface.yaml`の
   `participantLinkList.item.revoke.disabledState`がこの境界をUIレベルでも機械的に閉じている
   （非活性化、取り除きではない——既存の`confirmDate.disabledState`と同じ流儀）。

**旧記述との整合（言及しておくべき点）**: `gathering-scheduling-api.yaml`の
`Gathering.anonymousRespondedParticipantCount`の説明は元々「this schema does not expose a
per-participant list」（designerの2026-08-30の板が個々の参加者一覧を意図的に持たないと述べていた
こと）と書いていた。本決定が新設する`listParticipantLinks`は、まさにその「参加者ごとの一覧」を
提供する——ただし対象が異なる（`anonymousRespondedParticipantCount`が指していたのは日程回答の
集計面、`listParticipantLinks`が指すのはリンクの発行・管理面）。同じ日のうちに、designerが意図的に
避けた集計面の個別一覧化とは別に、人間が管理面の個別一覧化を明示的に追加で裁定した、という経緯で
あり、矛盾ではなく後発の人間裁定による意図的な追加である。`gathering-scheduling-api.yaml`の当該
説明文は、この関係が読み取れるよう更新した。

## 検討した代替案

- **F にも観測面を定義する（説明図の各要素にtest idを振る）**: 却下。Fは操作可能な要素を持たない
  静的な説明図であり、L4のブラウザ自動化が検査すべき対象（操作の結果としての状態変化）を持たない。
  その内容は既にA・Bの実際の要素として現れている。
- **organizerDashboard/participantAnswerを別ファイルに分ける（`candidate-search`/`authentication`
  方式）**: 却下。両者が観測する業務・API契約は同じ1本であり、ファイルを分けると`.feature`・
  `-api.yaml`との対応関係（1業務契約=1browser-interface契約）が崩れる。名前空間の分離で
  認証モデルの違いを表現するにとどめた。
- **D3の店の一覧を先取りして定義する**: 却下。`ADR-0035`決定2の範囲外であり、まだ承認された
  画面が存在しない。抽象カテゴリの先取り（決定3）で原則だけを今のうちに機械強制する形にとどめた。
- **「回答リンクをコピー」の食い違いを、architectの判断でAPIまたは画面のどちらかに合わせて
  書き換える**: 却下（起草時点）。契約の確定は人間の承認によるものであり（P-07）、どちらの成果物を
  動かすかはarchitectが独断で決めてよい範囲を超える。最小限の補完解釈を契約に書き、食い違いそのもの
  を人間へ申し送ることを選んだ（P-08の精神、FR-028の教訓）。**同日、この申し送りに対して人間が
  案A（1クリック=1本）を選んだことで、この論点は決定4として確定した。**
- **参加者面にもCSRFトークンを要求する（一律の安全側の選択）**: 却下。参加者面にはCookie由来の
  ambient資格情報が無く、CSRFトークンを追加しても防げる攻撃が無い一方、署名付きリンクをメールや
  チャットで転送する際にCSRFトークンの受け渡しという余計な複雑さを持ち込むことになる。
- **複数本まとめて発行する画面を今回のうちに追加する（案B相当）**: 却下（人間裁定）。人間は案A
  「1クリック=1本」を選んだ。まとめ発行UIは将来の拡張候補として記録するにとどめる（決定4）。
- **リンク一覧の各項目にtoken/URLをそのまま含める**: 却下（設計判断7-a）。実装は単純になるが、
  一覧取得という最も頻繁に呼ばれるであろう操作が、発行済み全リンクの資格情報を一度に返す経路に
  なり、露出面が不必要に広がる。再コピーを専用の1件操作に分離するコストは小さいと判断した。
- **`totalIssuedParticipantLinks`自体の意味を「実効発行数」に書き換える（新フィールドを増やさない）**:
  却下。監査目的で「生涯何本発行したか」という値も引き続き有用であり、既存フィールドの意味を
  黙って変えるより、`totalRevokedParticipantLinks`・`activeParticipantLinkCount`を追加するほうが
  読み手にとって明示的である。
- **失効済みリンクを一覧から削除する**: 却下。失効は「後始末」の操作であり、何を・いつ失効させたかを
  幹事があとから確認できなくなるのは監査上望ましくない。`revoked: true`のまま残す設計を採った。

## 帰結

- `contracts/gathering-scheduling-browser-interface.yaml`（更新、`contractVersion` 0.1→0.2、
  ステータス: 承認待ち）に、リンク一覧（`gathering-participant-link-list`）・再コピー
  （`gathering-participant-link-recopy`）・失効（`gathering-participant-link-revoke`）の観測面と、
  再定義した分母（`data-active-issued-links`・`data-revoked-links`）を追加した。`participantLinkCopy.
  designNote`は決定4の確定を反映済みのまま変更していない。
- `contracts/gathering-scheduling-api.yaml`（更新、`version` 0.1.0→0.2.0）に
  `listParticipantLinks`・`recopyParticipantLink`・`revokeParticipantLink`と関連スキーマ
  （`ParticipantLinkSummary`・`ParticipantLinkListResponse`・`RevokeParticipantLinkResponse`）・
  エラーコード（`PARTICIPANT_LINK_NOT_FOUND`・`PARTICIPANT_LINK_ALREADY_ANSWERED`・
  `PARTICIPANT_LINK_REVOKED`・`LINK_REVOKED`）を追加し、`Gathering`へ
  `totalRevokedParticipantLinks`・`activeParticipantLinkCount`を追加した。
- `contracts/gathering-scheduling.feature`にTDR-GTH-16〜20を追加した。既存シナリオ（TDR-GTH-01〜15）
  は本文を変更していない——TDR-GTH-07は失効が無い場合の分母の挙動として引き続き正しいままである。
- designerのキャンバス板（`E:\AWS\dsg-out\party\`）自体の更新は、orchestratorが並行して依頼済みで
  ある——本ADRの決定7が定めたリンク管理面（一覧・再コピー・失効）を、次にdesignerが正規パイプラインで
  描き直す際の設計判断の前提として渡す。
- `design/explorations/**`・`ARCHITECTURE.md`・`design.md`は変更しない——構造上の決定ではなく
  test infrastructure層・API層の観測契約の拡張にとどまる。

## 未決事項（次工程・人間への申し送り）

~~1. 「回答リンクをコピー」とバッチ発行APIの食い違い（決定4）~~ **決着（2026-08-30、人間裁定:
   案A「1クリック=1本」）**。押すたびに新しいリンクが1本発行・コピーされる運用として確定した。
   まとめて複数本を発行する画面は追加しない。

1. **`ADR-0035`から持ち越し**: 会データの保持期間・削除方針、署名付きリンクの具体的な有効期限
   日数・レート制限閾値（いずれも根拠の薄い暫定値）、`test-support-api.yaml`のTDR-GTH向け拡張
   （本ADR・`ADR-0035`のいずれでも着手していない——決定7が追加したリンク管理3操作の分もこの拡張に
   含める必要がある）。
2. **候補日追加フォームの画面**: `gathering-add-candidate-date-open`が開く先の入力フォーム自体は
   まだ承認された画面を持たない（`Organizer.dc.html`はボタンの入口だけを示す）。designerが
   このサブフローを描き、人間が承認した時点で、対応するtest idをこの契約へ追記する。
3. **リンク管理面の画面自体はまだ正規パイプラインを通っていない**: 本ADRの契約はAPI・観測面の
   設計を先に定めたが、`gathering-participant-link-list`等に対応する画面（一覧の見た目、再コピー・
   失効ボタンの配置）はdesignerが未着手である。次にdesignerが描く際は、本ADR決定7の制約
   （トークン非露出、失効は未回答のみ）を設計の前提とすること。
