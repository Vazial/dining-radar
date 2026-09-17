---
id: 0062
scope: project/dining-radar
status: 承認済み
date: 2026-09-17
approved_by: "人間裁定（2026-09-17 チャット選択肢UI、実機フィードバック第2便・束D『投票・確定』）。
  DQ1 店の候補（幹事の『店を選び中』）: a『地図いっぱい・一覧を浮かせる』（PCは左に浮かせた一覧
  パネル、スマホは下のシート。各行は番号ピン・店名・いちばん人気の札・ジャンル・徒歩 約◯分・席・
  禁煙・予算・票の棒と○△×の数。店のページは右端の固定列。パネルの下にピンが隠れる代償を説明の
  うえで選択）。『あとから入りました』は出さない——adr/0056決定6の幹事側を覆す。参加者側・APIの
  値も不要と判断し合わせて消す（人間『参加者側・APIの値も不要なら消す』、保留『会モードの候補
  画面のカードにも出すか』も同時に閉じる）。板: E:/AWS/dsg-out/party2/d2/D1-a-*。DQ2 決めるボタン:
  a『画面の下に貼り付けた帯』（日を決める画面は『◯/◯を選んでいます｜◯/◯に決める』、店は
  『◯◯を選んでいます｜この店で確定』。スマホは下のナビのすぐ上。選ぶ前は押せない状態）——
  adr/0060未決事項2（『決める』ボタンの押しやすい位置）をこれで閉じる。退けた: b（選んだ所にも
  ボタン）。板: d2/D2-a-*。DQ3 確定の確認: 人間『日時とお店があればいい。参加者は書かなくていい』
  ——aの3行から参加者の行を除いた2行（日時・お店）。変える前の状態・回答リンクの行は書かない。
  ボタンは『もどる』『確定する』。板: d2/D3-a-*（参加者の行を除いたもの）。退けた: 3行そのまま・
  1行だけ。DQ4 確定後の幹事画面: 店を選び中と同じ骨組み（地図いっぱい、決まった店と集まる場所
  だけ）。PCは案1『パネルに全部（上に「決まりました・行ける N人」、日時、決まった店の行＋店の
  ページ、その下に「回答◯人｜回答リンク◯本」のタブ、パネルの中で送る）』、スマホは案2ベースで
  畳む（シートは決まったことだけ、『回答を見る』『回答リンク』の行を押すと開く）。『行ける N人』
  は決まった日に○と答えた人数。板: E:/AWS/dsg-out/party2/d4r/G1-Pc*・G2-Sp*。退けた: D4（決まる前
  と共通レイアウトの初案。上から縦に積む形——人間『余白がアンバランス、スクロールしないと見られ
  ない』）。指摘18〜26すべてこの束で扱った——18(地図の大きさ)・19(『徒歩◯分』表記)はDQ1、
  20(店のページの位置)はDQ1（配置は実装選択、契約変更なし）、21(あとから入りました)はDQ1、
  22〜24(確定確認の位置・文言)はDQ3、25(変える前の状態)はDQ3、23(スクロールしないと押せない)は
  DQ2、26(決まったことがスクロールしないと見えない)はDQ4で閉じた。人間はUI形状・業務規則の裁定
  のみを下し、契約上の具体化（testIdの置き場所・属性名・retire対象がAPIまで及ぶか・.feature
  シナリオの書き換え方）はarchitectの裁量に委ねられた——本ADRの決定1〜5がその具体化にあたる。"
supersedes: []
superseded_by: null
relates_to:
  [P-01, P-04, P-06, P-08, P-11, ADR-0025, ADR-0041, ADR-0042, ADR-0044,
   ADR-0046, ADR-0054, ADR-0055, ADR-0056, ADR-0059, ADR-0060, ADR-0061,
   TDR-GTH-33, TDR-GTH-34, TDR-GTH-38, TDR-GTH-39, TDR-GTH-52, TDR-GTH-53,
   TDR-GTH-57, TDR-GTH-58, TDR-GTH-59, TDR-GTH-60, TDR-GTH-61, TDR-GTH-62,
   TDR-GTH-63, TDR-GTH-64]
---

# ADR-0062: 投票中の一覧に店の詳細を足し、確定の確認を2行へ縮め、確定後の幹事画面を決まった店だけの表示にする

> **承認者向けサマリ**: 実機フィードバック第2便・束D（2026-09-14 activeContext記録の指摘18〜26）を
> 受け、designerが板（`party2/d2`・`party2/d4r`）を描き、人間が2026-09-17にチャット選択肢UIで
> 確定させた。決定は5点。
>
> **(1)** 幹事の投票中一覧（`organizerDashboard.shortlistedShopVotes.list.item`）の
> `detailFields`へ、ジャンル・席数・禁煙・予算・徒歩の目安（「徒歩」の語を含む表記へ強化）の5点を
> 追加し、逆に「あとから入りました」の印（`data-added-after-voting-started`）を幹事・参加者
> 双方の画面と`gathering-scheduling-api.yaml`から退役させる——`ADR-0056`決定6の幹事側を覆し、
> 未使用になった参加者側の値・API値も同じ回のうちに畳む。**(2)** 日程確定・店確定それぞれの
> 「決める」ボタンの押しやすい位置（`ADR-0060`未決事項2）は、既存の`disabledState`
> （選択前は押せない）がすでに人間の要求を満たしているため、契約変更なしで閉じる——画面下への
> 貼り付けはgeometry（この契約が元々固定しない範囲）。**(3)** 確定の確認ダイアログ
> （`gathering-finalize-confirm-dialog`）から、3行の変化前後表（`gathering-finalize-confirm-
> changes`、`ADR-0054`決定5・`ADR-0056`決定11）を全廃し、日時1行・お店1行だけを示す構造
> （`gathering-finalize-confirm-date`/`-shop`）へ置き換える。**(4)** 確定後の幹事ダッシュボード
> （`organizerDashboard.finalizedSummary`）から、5件の投票内訳（`gathering-shortlisted-shop-list`/
> `-item`、これまで「票の記録」として確定後も残っていた）を退役させ、代わりに決まった店1件の
> 名前・地図・店のページへのリンクを`decisionBanner`へ追加する——`ADR-0061`決定5が参加者側に
> 行った簡素化と対になる、幹事側の同じ簡素化。「行ける N人」「回答◯人」「回答リンク◯本」は
> いずれも既存の別属性（確定済み候補日自身の`data-going-count`・`gathering-responded-summary`・
> `gathering-unanswered-summary`）から導出でき、新しい属性は増やさない。**(5)** 副産物として、
> `ADR-0060`/`ADR-0061`が`gathering-scheduling.feature`へ追加したTDR-GTH-57〜64が
> `profiles.localAcceptance.verifiesScenarios`へ一度も登録されていなかったこと（`allowedPurposes`
> について`ADR-0061`決定6が見つけたのと同じ種類の登録漏れ）を見つけ、閉じる。
>
> 払うもの: 幹事の投票中一覧の視覚的な列位置（店のページへのリンクの固定列化を含む）・確定後の
> パネルのタブ切り替えとスマホでの折りたたみの実装（アイコン・アニメーション・スクロール）は
> いずれも実装選択のまま固定しない。参加者向けの店の投票画面へ同じジャンル要求・「徒歩」表記を
> 広げるかどうかは、本ADRの範囲外として残す。

## 文脈

### 0. 検証の申告（meta/adr/0039）

本ADRが前提とする既存契約の記述は、`gathering-scheduling-browser-interface.yaml`
（contractVersion 0.23.0、`ADR-0061`まで反映済み）・`gathering-scheduling-api.yaml`（v0.17.0）・
`gathering-scheduling.feature`（TDR-GTH-01〜64）を実際に読んで確認した——
`organizerDashboard.shortlistedShopVotes.list.item.detailFields`が地図と店のページへのリンクしか
持たず、参加者側`shopVoteQuestion.detailFields`が既に持つジャンル以外の4点（席数・禁煙・予算・
徒歩）を欠いていたこと、`data-added-after-voting-started`が幹事・参加者双方の画面と
`ParticipantShopVoteOption`の3箇所に存在し`gathering-scheduling.feature`のどのシナリオからも
参照されていないこと（`grep`で確認）、`gathering-finalize-confirm-dialog.changesTable`が3行の
`gathering-finalize-confirm-changes-row`（before/after付き）を要求していたこと、
`organizerDashboard.finalizedSummary.unchangedRecords`が`gathering-shortlisted-shop-list`/
`-item`を確定後も「票の記録」として残す設計だったこと、`Gathering.finalizedShopId`が単なる
文字列IDでしかなく決まった店の名前・地図座標・ページURLは`Gathering.shortlistedShops`配列を
`shopId`で突き合わせて初めて得られること、`profiles.localAcceptance.verifiesScenarios`が
TDR-GTH-56で止まっており`ADR-0060`/`ADR-0061`が追加したTDR-GTH-57〜64がどれも登録されて
いないことを、それぞれ実際の記述として確認した。designerの板（`E:\AWS\dsg-out\party2\d2\`・
`party2\d4r\`）と`feedback-2026-09-14.md`・`activeContext.md`の裁定の控えも実際に読んだ。
確認していないのは、これらの決定を実装したコードの挙動そのもの——architectは実装コードを
読まない・書かない。

### 1. 何が起きたか

実機フィードバック第2便・束D（投票・確定）について、designerが板を描き、人間が2026-09-17に
チャット選択肢UIで4つの論点（DQ1〜DQ4）を裁定した（approved_by参照）。指摘18〜26のすべてを
この束で扱う——18・19・20・21はDQ1、22〜24・25はDQ3、23はDQ2、26はDQ4がそれぞれ閉じる。

### 2. DQ4がADR-0061決定5と対になる理由

`ADR-0061`決定5（2026-09-17、同日先行）は、参加者の確定後画面から他の店の情報・票を全廃し
「決まった店だけ」を示す形へ戻した。本ADR決定4は、幹事の確定後画面についても同じ簡素化を行う
——これまで幹事側だけは「票の記録」として5件の投票内訳が確定後も残る非対称な設計だったが、
人間が実機の板を見て「決まった店と集まる場所だけ」を選んだことで、この非対称は解消される。
参加者側の`ADR-0056`決定10（決定地図の追加）を幹事側にも初めて適用する形になる点も同じ構造
——「参加者に先に開いた観測面を、後から幹事にも同じ形で開く」というこの契約の既存の流儀
（`ADR-0056`決定6の「幹事・参加者に同じ言葉で出す」の逆方向）をここでも踏襲する。

## 決定

### 決定1（DQ1）. 投票中一覧に詳細5点を足し、「あとから入りました」を退役させる

`organizerDashboard.shortlistedShopVotes.list.item.detailFields`へ、新規`walkingTime`
（testId: `gathering-shortlisted-shop-walking-time`）・`genre`
（testId: `gathering-shortlisted-shop-genre`）・`capacityTier`
（testId: `gathering-shortlisted-shop-capacity-tier`）・`nonSmokingStatus`
（testId: `gathering-shortlisted-shop-non-smoking`）・`dinnerBudgetTier`
（testId: `gathering-shortlisted-shop-dinner-budget`）を追加する。genre以外の4点は
`participantAnswer.shopVoteQuestion.detailFields`が既に持つ同名フィールドと同じ形——testIdの
存在だけを要求し、可視文字列そのものは機械検証しない（`gathering-shop-vote-question-capacity-
tier`等と同じ「no data-value-state attribute required」の convention）。**genreは参加者側の
`shopVoteQuestion`が今も要求していない値をこの画面だけ新たに要求する**——板D1が「ジャンル」を
明示的に一覧の可視フィールドとして描いており、参加者側の対応する画面（`ADR-0044`起草時に
「name/genreはこの契約がDOM表現を固定しない」と定めた対象）を今回同時に変える人間裁定は
出ていないため、非対称のまま残す（「検討した代替案」参照）。

`walkingTime`だけは内容のMustを持つ——可視文字列に近似を示す語（`約`・`推定`等、
`candidate-search-browser-interface.yaml`の`walkingTimeEstimateWording`、`adr/0025`決定2と
同じ規約）と「徒歩」の語の両方を含むこと（例:「徒歩 約12分」）を要求する。人間裁定
「『◯分』→『徒歩◯分』」（板D1の行の可視フィールド列挙）の直接反映であり、`item.attributes.
walkingTimeMinutes`（`data-walking-time-minutes`）が既に持つ生の値を複製せず、その値を
飾る可視文字列だけに新しいMustを課す——`candidate-search-browser-interface.yaml`が同じ値
（raw attributeと可視文字列）に対して既に採用している役割分担そのままである。**参加者側の
`shopVoteQuestion.detailFields.walkingTime`、および`candidate-search-browser-interface.yaml`
自身の`walkingTimeEstimateWording`へこの「徒歩」語の要求を広げるかどうかは、本ADRの範囲外**
——板D1が対象にしたのは幹事の投票中一覧という1画面であり、他の2画面を人間が同時に裁定した
事実はない。

「店のページを見る」の横位置がずれる不具合（指摘20）は、この項目の位置自体をこの契約が固定して
いない（`detailFields.providerPageLink`は既存のまま、`右端の固定列`という配置はgeometry）ため、
契約変更を要しない——実装のみで対応する。

**`data-added-after-voting-started`を、この画面・参加者側の`shopVoteQuestion`・
`gathering-scheduling-api.yaml`の`ParticipantShopVoteOption.addedAfterVotingStarted`の
3箇所すべてから退役させる**——`ADR-0056`決定6（2026-09-13、幹事側に新設し参加者側へ鏡写しした
決定）を幹事側から覆し、参加者側・API側の値も同じ回のうちに畳む。人間の言葉「あとから入りました
は要らないかも」（板の説明を読んだ上での確定）と、依頼文が明記した「参加者側・APIの値も不要
なら消す」を受けての判断——`gathering-scheduling.feature`のどのシナリオもこの属性・「あとから
入りました」という語を参照していないこと（`grep`で確認、文脈0節）を根拠に、参加者側・API側の
値も真に不要と判断した。これにより、`activeContext.md`が記録していた保留事項「会モードの候補
画面のカードに『あとから入りました』の印を出すか——`Candidate`に値が無い」も同時に閉じる
——答えは「どの画面にも出さない」であり、`candidate-search-api.yaml`の`Candidate`型へこの値を
新設する必要は生じない。

### 決定2（DQ2）. 「決める」ボタンの押しやすい位置は契約変更なしで閉じる

`ADR-0060`未決事項2（「『決める』ボタンの押しやすい位置は、束Dの確定ボタンと合わせて直す前提」）
を、契約変更なしで閉じる。人間裁定は「画面の下に貼り付けた帯」への配置と「選ぶ前は押せない状態」
を求めているが、後者は`organizerDashboard.confirmDate.disabledState`（「候補日が1つも
tentative-selectedでない間は無効」）と`shortlistedShopVotes.finalizeOpen.disabledState`
（「finalize-selectedな項目が1つもない間は無効」）が**既に**満たしている——この契約は元々
「押せない状態」というMustだけを固定し、ボタンの画面上の位置（geometry）は固定していない
（この契約の一貫した流儀、`ADR-0059`決定5・`ADR-0060`決定5の「位置表示・固定・スクロールの
具体的な実装はこの契約が固定する対象ではない」と同じ扱い）。したがって「画面の下に貼り付ける」
という配置の変更は実装のみで完結し、この契約の新しいMustを要しない。

### 決定3（DQ3）. 確定の確認を「日時」「お店」の2要素へ縮める

`organizerDashboard.shortlistedShopVotes.finalizeConfirmDialog`の`changesTable`
（`gathering-finalize-confirm-changes`、3行の`before`/`after`セルを持つ表、`ADR-0054`決定5・
`ADR-0056`決定11）を全廃し、`confirmSummary`（新設のYAML構造名、既存のtestId命名規則には
影響しない）として次の2要素へ置き換える。

- `date`（testId: `gathering-finalize-confirm-date`）: `data-confirmed-candidate-date`を
  持つ、表示専用の要素。`confirmDate.requiredOutcome`が局面がSCHEDULINGを過ぎたときに既に
  固定した確定済み候補日と同じ値を示す（この値自体はこのダイアログが新しく作るものではない）。
- `shop`（testId: `gathering-finalize-confirm-shop`）: `data-shop-id`・`data-shop-name`を
  持つ、表示専用の要素。`gathering-finalize-open`が活性化された時点で`data-finalize-
  selected="true"`だった`gathering-shortlisted-shop-item`（`finalizeConfirm`が実際に
  `finalizeGathering`を呼ぶのと同じ店）のshopId/nameをそのまま映す。

人間の言葉「日時とお店があればいい。参加者は書かなくていい」を受け、3つの主題
（participant-link-issuance・participant-screen・date-and-shop）のうち後者だけを残し、前2つの
主題（回答リンクの発行可否・参加者の画面がどう変わるか）は削る。**変わる前の状態（`before`
セル）も削る**——このダイアログはSELECTING_SHOPの間だけ開かれるため、「変わる前」は常に
「未確定」という固定文字列でしかなく、人間は板を見てこの値に情報価値を認めなかった
（依頼文「変える前の状態は書かない」）。ボタンの可視文言（「もどる」「確定する」）は、この
契約が元々固定していない範囲（`gathering-finalize-cancel`/`gathering-finalize-confirm`という
既存のtestId/purposeはどちらも無変更）。

`gathering-scheduling.feature`のTDR-GTH-53（「幹事が日と店を確定する前に、確認の一段で変わる
ことの一覧を見る」）を書き換える——シナリオIDは維持し（`P-06`と同じ精神、同じ業務行為への
言及を保つ）、Then節を「確定しようとしている開催日時とお店が示される」へ改める。

### 決定4（DQ4）. 確定後の幹事画面を、決まった店だけの表示へ作り直す

`organizerDashboard.shortlistedShopVotes.presenceRule`を、「`Gathering.votingStartedAt`が
非nullである間は局面を問わず存在する」という記述から、「`Gathering.votingStartedAt`が非null
かつ`Gathering.finalizedShopId`がnullである間（＝局面がSELECTING_SHOPである間）だけ存在する」
へ書き換える——これまでlist/itemはfinalizeSelectを除いて確定後も「票の記録」として残っていた
（`adr/0042`起草時からの設計）が、`ADR-0061`決定5が参加者側に行ったのと同じ簡素化を幹事側にも
適用する。

`organizerDashboard.finalizedSummary.decisionBanner`へ、新規`finalizedShopName`
（`data-finalized-shop-name`）属性を追加し、`Gathering.shortlistedShops`配列のうち
`shopId`が`finalizedShopId`と一致するエントリの`name`と等しいことを要求する——**この値は
新しいAPIフィールドを要求しない**（`Gathering.shortlistedShops`配列自体は局面がFINALIZEDに
なっても引き続きAPIレスポンスに含まれる、この契約が変えるのはDOM上の`gathering-shortlisted-
shop-list`/`-item`の`presenceRule`だけであり、この配列そのものをAPIが返さなくなるわけでは
ない）。同じ配列の同じエントリから、新規の子要素`map`（テストID`gathering-decision-shop-map`、
`gathering-participant-decision-map`と同じ3属性の形——`overlayMarkerCount`は常に"2"、
`overlayLineCount`/`overlayRingCount`は常に"0"、経路の線も徒歩の範囲の輪も描かない、
`ADR-0056`決定10と同じ理由）と`providerPageLink`（テストID`gathering-decision-shop-page-
link`）を追加する——参加者側の`participantAnswer.finalizedView.decision`が既に持つ形を、
幹事に対して初めて開く。

**「行ける N人」（板D4の見出し）・「回答◯人」「回答リンク◯本」（同じ板のタブ）はいずれも
新しい属性を要求しない**——「行ける N人」は`data-confirmed="true"`を持つ
`gathering-candidate-date`自身の既存`data-going-count`（`ADR-0060`決定7）から、「回答◯人」は
`gathering-responded-summary`の既存`data-responded-count`から、「回答リンク◯本」は
`gathering-unanswered-summary`の既存`data-active-issued-links`から、それぞれ導出できる
——同じ値を`decisionBanner`へ複製することは、`ADR-0059`決定6・`ADR-0060`決定7が既に確立した
「複製は将来のドリフトの温床」という判断を踏襲して避ける。

`organizerDashboard.finalizedSummary.unchangedRecords`を書き換え、確定後も残る要素の一覧から
`gathering-shortlisted-shop-list`/`-item`を外し、代わりに`decisionBanner`が今回新設する
値がこの一覧の旧来の役割（「どの店が決まったか」の唯一の記録）を引き継ぐことを明記する。
`shortlistedShopVotes.finalizeSelect`のpresenceRule説明文（「Final.dc.html A③の票の記録
パネルにはラジオが無い」という、list/itemが残る前提の書きぶり）も、list/item自体が不在になる
今回の変更に合わせて書き改める。

PCのタブ切り替え（「回答」「回答リンク」）・スマホでの折りたたみ（行を押すと開く）は、
`organizerDashboard.responseTable`・`organizerDashboard.participantLinkList`の**どちらの
presenceRuleも変えない**（両方とも既に全局面で無条件に存在し続けると定義済み）——この契約は
折りたたみ・タブという表示上のグルーピングをMustにしない。この契約が既にrenderModesの概念を
持たない（`candidate-search-browser-interface.yaml`と異なり、PC/スマホの構造差をこのファイルは
これまでも固定してこなかった）ことと整合する判断であり、`gathering-scheduling.feature`が
`responseTable`/`participantLinkList`の中身を確定後も観測できることに変わりはない。

新規`gathering-scheduling.feature`シナリオTDR-GTH-65（幹事も決まった店の地図を見られる、
TDR-GTH-52の幹事版）・TDR-GTH-66（確定後、幹事には決まった店の情報だけが示される、TDR-GTH-34の
幹事版）を追加する（下記「帰結」参照）。

### 決定5（副産物・技術判断）. `verifiesScenarios`の登録漏れを閉じる

architectの技術判断による改訂であり、人間のチャット裁定を経ない（`meta/adr/0064`の作法、
`ADR-0061`決定6・`ADR-0060`が同じ経路で先例を持つ）。`gathering-scheduling.feature`の
TDR-GTH-57〜64（`ADR-0060`決定1・2・7・8、`ADR-0061`決定2が追加した8本）が、
`profiles.localAcceptance.verifiesScenarios`へ一度も登録されていなかった——`ADR-0061`決定6が
`allowedPurposes`について見つけたのと同じ種類の登録漏れであり、本ADRが同じ配列（決定4の
TDR-GTH-65/66を足すため）を触るのを機にあわせて閉じる。新しい業務判断は伴わない。

## 検討した代替案

- **DQ1で、参加者側`shopVoteQuestion.detailFields`にもgenreの要求を同時に広げる**: 却下。
  板D1は幹事の投票中一覧という1画面の裁定であり、参加者側の画面を人間が同時に確認した事実は
  ない——同じ要求を広げる決定は次回、参加者側の画面を扱う回にarchitectが人間へ確認すべき
  ものとして残す（下記「未決事項」）。
- **DQ1で、「徒歩」語の要求を`candidate-search-browser-interface.yaml`の
  `walkingTimeEstimateWording`本体まで広げる**: 却下。同じ理由——板が対象にしたのは投票中
  一覧の1画面であり、店を絞る画面（束E、未着手）は別スコープ。
- **DQ1で、`data-added-after-voting-started`の参加者側・API側だけ残し幹事側だけ退役させる**:
  却下。依頼文の「参加者側・APIの値も不要なら消す」を受けてこの値の必要性を検討したが、
  `gathering-scheduling.feature`のどのシナリオもこの語・属性を参照していないことが確認でき、
  片側だけ残す積極的な理由が無かった——両側とも消す方が、将来「なぜ幹事側にだけ無いのか」を
  説明する必要を生まない。
- **DQ2で、選んだ後の項目自体にもボタンを置く**（板の案b）: 却下（人間裁定）。人間はa
  「画面の下に貼り付けた帯」を選んだ。
- **DQ2で、新しい`disabledState`の文言・エラーコードを追加する**: 却下。既存の
  `disabledState`が要求する性質（押せない）に変更はなく、新しい観測面を追加する理由が無い
  ——位置の変更だけが人間裁定の中身である。
- **DQ3で、3行のうち`date-and-shop`の`before`セルだけ残し「未確定」という固定文字列を
  machine-assert する**: 却下。人間の言葉は「変える前の状態は不要」であり、固定文字列であっても
  行として画面に残すこと自体を人間が退けている。
- **DQ3で、`gathering-finalize-confirm-changes`というtestId名をそのまま残し中身だけ差し替える**:
  却下。「変化前後の表」という名前が指す構造そのものが無くなるため、新しいtestId
  （`gathering-finalize-confirm-date`/`-shop`）を新設する方が、次にこの契約を読む人にとって
  名前と中身が一致する。
- **DQ4で、`gathering-shortlisted-shop-list`/`-item`を確定後も残し、決まった店だけを
  `data-finalize-selected`相当の目印で強調する**（旧D4寄りの折衷案）: 却下。人間が明示的に
  退けたD4（決まる前と共通レイアウトの初案）は縦積みレイアウトの問題（余白・スクロール）を
  理由に退けられたものであり、やり直し後の確定案は「決まった店と集まる場所**だけ**」という
  文言を明確に含む——5件の内訳を残す設計とは相容れない。
- **DQ4で、決まった店の名前・地図を新しいAPIフィールド（例:`Gathering.finalizedShop`という
  LiveProjectedShop型のオブジェクト）として追加する**: 却下。`Gathering.shortlistedShops`
  配列が既にこのデータ（`name`・`location`・`providerPageUrl`）を持ち、局面がFINALIZEDに
  なっても配列自体は返り続ける（`presenceRule`はDOM上の話でありAPIペイロードの話では
  ない）——新しいAPIフィールドを増やす理由が無い。
- **DQ4で、「行ける N人」を`decisionBanner`自身の新しい属性として複製する**: 却下。
  `ADR-0059`決定6・`ADR-0060`決定7が既に確立した「複製は将来のドリフトの温床」という判断を
  踏襲した——既存の`gathering-candidate-date`自身の`data-going-count`から導出できる。
- **DQ4で、スマホの折りたたみ（「回答を見る」「回答リンク」を押すと開く）を、
  `auth-account-menu-toggle`と同じ形のdisclosureトグル（新設purpose）としてMust化する**:
  却下。この契約はこれまで`organizerDashboard`のPC/スマホ構造差にrenderModesの概念を一度も
  持ち込んでこなかった（`candidate-search-browser-interface.yaml`側の設計であり、この契約は
  内容だけを固定する流儀を貫いてきた）——ここで初めて幅依存の開閉をMust化すると、この契約の
  一貫した設計原則から外れる。折りたたみの有無に関わらず`responseTable`/`participantLinkList`
  自体のpresenceRuleは変わらないため、機械検証の対象を失わない。

## 帰結

- `contracts/gathering-scheduling-browser-interface.yaml`（改訂、現行contractVersion 0.23.0 ->
  0.24.0）: 決定1（`shortlistedShopVotes.item.detailFields`への5フィールド追加、
  `data-added-after-voting-started`の幹事・参加者双方からの削除）、決定3
  （`finalizeConfirmDialog.changesTable`の全廃と`date`/`shop`への置換）、決定4
  （`shortlistedShopVotes.presenceRule`のFINALIZED時absent化、`finalizedSummary.
  decisionBanner`への`finalizedShopName`/`map`/`providerPageLink`追加、`unchangedRecords`の
  書き換え）、決定5（`verifiesScenarios`へTDR-GTH-57〜66を追加）を反映する。**具体的なYAML
  編集は本ADRと同じ提出物（`spec-bundle-d`のdiff指定）を参照。**
- `contracts/gathering-scheduling-api.yaml`（改訂、現行v0.17.0 -> v0.18.0）: 決定1
  （`ParticipantShopVoteOption.addedAfterVotingStarted`の削除）を反映する。**具体的なYAML編集は
  同diff指定を参照。**
- `contracts/gathering-scheduling.feature`: TDR-GTH-53を書き換える（決定3）。新規
  TDR-GTH-65・TDR-GTH-66を追加する（決定4）。既存シナリオ（TDR-GTH-01〜64、TDR-GTH-53を含む
  IDそのもの）は変更しない——TDR-GTH-53は同じ業務行為（確定前の確認）についての言及を保った
  まま本文だけを改める。**具体的な差分は同diff指定を参照。**
- `contracts/test-support-api.yaml`: 変更しない——決定1・3・4のいずれも、
  `gathering-scheduling-api.yaml`が既に公開している境界（createGathering・
  addCandidateDates・confirmCandidateDate・setShortlistedShops・setShopVotes・
  finalizeGathering等）だけで構築・検証できる新しいGiven状態を要求しない（`ADR-0037`決定1・
  `ADR-0060`帰結・`ADR-0061`帰結と同じ理由）。
- `product-brief.md`・`ARCHITECTURE.md`・`design.md`: 変更しない——本ADRは会スコープの契約
  内部の画面構成・観測面の変更であり、製品境界・モジュール境界を変えない。

## 未決事項（次工程・人間への申し送り）

1. **参加者側`shopVoteQuestion.detailFields`へのgenre要求拡大、および`candidate-search-
   browser-interface.yaml`の`walkingTimeEstimateWording`への「徒歩」語の要求拡大**は、本ADRの
   範囲外——次にこれらの画面を扱う回に、architectが人間へ確認することを推奨する。
2. **確定後パネルのPC/スマホ折りたたみ（タブ・行の開閉）の実測**（44px下限、開閉アニメーション
   等）は、`ADR-0059`決定5・`ADR-0060`決定5と同じくorchestratorの領分——実装が固まった段階で
   確認する。
3. **`gathering-shortlisted-shop-page-link`と同様、`gathering-decision-shop-page-link`が
   `formControlExemptTestIds`へ登録されていることの以後の維持**は developer/tester の実装時の
   注意点として申し送る——本ADR自身は登録済みとして帰結節のdiffに含めている。
4. **decision5が見つけた登録漏れの再発防止**（`allowedPurposes`・`verifiesScenarios`など、
   新設した識別子を配列へ登録し忘れる類の欠落）は、`ADR-0061`決定6・本ADR決定5の2回続けて
   architect自身が起草後に見つけている——3回目が起きた場合は、機械検査（新設testId/シナリオIDが
   これらの配列に含まれることをgovlintで検証する）を検討する材料として記録しておく。
