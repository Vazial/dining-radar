---
id: 0061
scope: project/dining-radar
status: 承認済み
date: 2026-09-17
approved_by: "人間裁定（2026-09-17 チャット選択肢UI、実機フィードバック第2便・束C『参加者を呼ぶ・
  答える』）。CQ1 回答リンク: b『発行で小窓が開き、そこでコピー』——『リンクを発行』を押すと1本発行
  して小窓が開き、URLの一部と大きな『リンクをコピー』。押すとクリップボードへ書き込み、ボタンが
  『✓ コピーしました』に。小窓は『閉じる』／×。一覧には『いま発行』の行が増える。行ごとの『コピー』
  （今の再コピー）は残る。退けた案: a『行が増えてその行でコピー』・c『本数を決めてまとめて発行』。
  板: E:/AWS/dsg-out/party2/c2/C1-b-*。CQ2 参加者の日程回答: a『1日ずつ、答えると自動で次の日へ』
  ——上に『答えた N / 12』と区切りの棒、『◯/◯は「行ける」にしました』、右下『とばす』、左下『前の日』、
  『日の一覧』（スマホは下から出るシート、PCは左に常に出る）、一覧から日へ飛べる。全部答えると
  『12件すべて答えました』と自分の答えの一覧（押すとその日へ）。『結果をのぞく』『あとで答える』と
  その確認の面は無くす（adr/0050決定1・adr/0055決定3を覆す）。未回答のままでも閉じてよく、答えは
  いつでも変えられる。退けた案: b『答えてから次へ』。レイアウトは D1『一覧に数も並べる・答えは手元』
  （一覧は『日｜○△×の数｜あなたの答え』の3列、有力は札と行の左端の線）を F2 で整える——横棒の下に、
  その日のほかの参加者の名前と答えを並べる（『○ あおい』『× そら』、名無しは名無しと出す）。これは
  参加者どうしで他の参加者の名前と日程の答えが見えるようになる製品境界の拡張であり（今は人数だけ。
  adr/0050決定2・adr/0055決定4の続き）、人間は選択肢の説明でこの点を読んだうえで案F2を選んだ。退けた
  案: D2『一覧は自分の答えだけ』・F1『カードを縮めて下に寄せる』。板: c2/C2-a-*（流れ）、c2r/D1-*
  （一覧）、c2r2/F2-*（カード）。CQ3 聞く順: a『日付の順』——adr/0060決定6と一致、変更なし。CQ4
  確定後の参加者画面: 『決まりました』・日時・決まった店のカード1枚・決まった店と集まる場所だけの
  地図。他の候補の店と票は出さない（adr/0055決定8の反転）。板: c2/C4-*。押したカードが並び替えで
  動く（指摘8の一部）は、日付順・1日ずつ表示で解消（別途の契約変更は無い）。有力の印の参加者側の
  見せ方（adr/0060で仮置き）は、一覧の『有力』札と行の左端の線、有力な日のカードの上の緑の帯
  （D1-SpLeader）で確定——ただし本ADRはこの視覚表現自体を固定しない（契約が元々固定していない可視
  表現の範囲）。"
supersedes: []
superseded_by: null
relates_to:
  [P-01, P-04, P-06, P-08, P-11, ADR-0036, ADR-0050, ADR-0055, ADR-0056,
   ADR-0058, ADR-0060, FR-034, TDR-GTH-03, TDR-GTH-06, TDR-GTH-07, TDR-GTH-09,
   TDR-GTH-12, TDR-GTH-17, TDR-GTH-34, TDR-GTH-36, TDR-GTH-56, TDR-GTH-63]
---

# ADR-0061: 回答リンクの発行とコピーを2段に分け、日程回答を1日ずつの流れへ作り直し、確定後の参加者画面から他の店の票を消す

> **承認者向けサマリ**: 実機フィードバック第2便・束C（参加者を呼ぶ・答える）の4つの論点
> （CQ1〜CQ4）を人間がチャット選択肢UIで裁定した。決定は4点——(1) 回答リンクの発行を、
> 発行と同時にコピーする1段の操作から、発行して小窓を開きその中でコピーする2段の操作へ分ける
> （`ADR-0036`決定4・`ADR-0058`の1段モデルを置き換える。クリップボード書き込みのMustは消えず、
> 小窓の「リンクをコピー」へ移る）。(2) 参加者の日程回答画面に、候補日ごとに他の参加者の名前と
> 回答を表示する——これまでは人数の内訳（○△×それぞれ何人）だけだったが、幹事にはすでに開いて
> いる「誰が・どの候補日に・何と答えたか」（`ADR-0055`決定4）と同じ情報を、参加者どうしにも開く。
> **これは製品の可視性の境界を動かす決定であり、人間は選択肢の説明でこの点を読んだうえで選んだ**。
> (3) 日程回答の画面を、候補日を1日ずつ進み、答えると自動で次の日へ進む形に作り直し、「あとで
> 答える」「結果をのぞく」の2つの操作を廃止する（`adr/0050`決定1・`adr/0055`決定3を覆す）——
> どちらも、この製品が既に持つ別の性質（毎回その場で保存する・他の参加者の集計は常に見える）に
> よって不要になった。(4) 確定後の参加者画面から、決まった店以外の情報を一切消す——他の候補の店
> とその票を見せない（`ADR-0055`決定8の反転）。CQ3（聞く順は日付順）は`ADR-0060`決定6と一致し、
> 変更を要さない。
>
> **副産物として見つけた2つの整合性の穴も、同じ作業のうちに閉じた**（新しい決定ではなく、is
> 既存の承認済み決定の転記の是正）: (a) `gathering-scheduling.feature`のFeature説明文（業務の
> 要約段落）が、`adr/0055`決定7（確定後の「あなたの日程への回答」1行も消す、2026-09-12）より
> 前の状態のまま「自分自身の開催日への回答が示される」と書き続けていた——TDR-GTH-34自体は正しく
> 改訂されていたが、この要約段落だけ追随していなかった。(b) `allowedPurposes`が
> `gathering-create-review-open`・`-review-cancel`・`-review-month-navigate`
> （`ADR-0060`決定5が新設した3つのpurpose）を一度も登録していなかった——`ADR-0060`自身の起草
> 時の抜けであり、本ADRが同じ配列を触るのを機に閉じる。

## 文脈

### 0. 検証の申告（meta/adr/0039）

本ADRが前提とする既存契約の記述は、`gathering-scheduling-browser-interface.yaml`
（contractVersion 0.22.0、`ADR-0060`まで反映済み）・`gathering-scheduling-api.yaml`
（v0.16.0）・`gathering-scheduling.feature`（TDR-GTH-01〜63）を実際に読んで確認した——
`participantLinkCopy.requiredOutcome`のクリップボード書き込みMust（`ADR-0058`）、
`scheduleQuestion.cardinality`が「同時表示か1日ずつかを固定しない」としていたこと、
`answerLater`/`peekResults`とその確認面の全文、`shopVoteQuestion.presenceRule`・
`shopVoteMap.presenceRule`・`finalizedView.decision.requirement`・`replacesQuestionSurfaces`
が確定後も店の投票タリーを見せる設計になっていたこと（`ADR-0055`決定8）、`allowedPurposes`の
現在の配列、`gathering-scheduling.feature`のTDR-GTH-34本文とFeature説明文の食い違いを、
それぞれ実際の記述として引用のとおり確認した。designerの板（`E:\AWS\dsg-out\party2\c2\`・
`c2r\`・`c2r2\`）と`feedback-2026-09-14.md`・`activeContext.md`の裁定の控えも実際に読んだ。
確認していないのは、これらの決定を実装したコードの挙動そのもの——architectは実装コードを
読まない・書かない。

### 1. 何が起きたか

実機フィードバック第2便・束C（参加者を呼ぶ・答える）について、designerが板を描き、人間が
2026-09-17にチャット選択肢UIで4つの論点（CQ1〜CQ4）を裁定した（approved_by参照）。CQ2の
裁定は3段階を経た——(a) 答え方そのもの（1日ずつ・自動で次へ）、(b) その流れのレイアウト
（D1「一覧に数も並べる・答えは手元」）、(c) レイアウトの余白を埋める案（F2「他の参加者の
名前と答えを並べる」、製品境界の拡張を伴う）。人間は各段階で示された選択肢の説明を読んだ
うえで選んだ。

### 2. CQ2のレイアウト裁定が製品境界を動かす理由

F2案は、日程回答カードの3本の集計バーの下に「その日のほかの参加者の名前と答え」を並べる
——これは見た目の整えごとではなく、**これまで人数の内訳だけしか見えなかった参加者どうしの
可視性を、個人の名前と回答の対まで開く**決定である。`adr/0050`決定2（2026-09-08〜09）が
開いたのは「自分が答えていなくても他の参加者の集計が見える」という**人数レベル**の可視性
だった。`adr/0055`決定4（2026-09-12）は、幹事に対して「誰が・どの候補日に・何と答えたか」
という**個人レベル**の可視性を開いたが、これは幹事だけに向けたものであり、参加者どうしには
及んでいなかった。本ADRの決定2は、参加者どうしの可視性を人数レベルから個人レベルへ、幹事に
対してと同じ深さまで引き上げる——2つの決定の系譜がここで合流する。この性質は選択肢の説明文に
明記され、人間はそれを読んだうえでF2を選んだ（依頼文の要求どおり、境界の拡張だと理解した
うえでの選択であることをここに記録する）。

### 3. CQ1・CQ4は既存決定の反転である

CQ1は`ADR-0036`決定4（2026-08-30、「1クリック=1本」の1段モデル）と`ADR-0058`（2026-09-14、
その1段の中にクリップボード書き込みのMustを足した）が確立した設計を、1段から2段へ組み替える
——書き込みそのものをやめるのではなく、どの操作がそれを担うかを変える。CQ4は`ADR-0055`決定8
（2026-09-12、「確定後も参加者は店ごとの票を見られるままにする」）を、同じ人間が実物の板を
見て再度覆すものである——`ADR-0055`決定8自体、この画面の自己矛盾（`presenceRule`と
`replacesQuestionSurfaces`が食い違っていた）を「見える」側で解消した経緯を持つが、本ADRは
「見せない」側で再解消する。P-06に従い、`ADR-0036`・`ADR-0055`・`ADR-0058`の本体は書き換え
ない——本ADRが新しい決定として該当部分だけを置き換える。

## 決定

### 決定1（CQ1）. 回答リンクの発行とコピーを2段の操作に分ける

`participantLinkCopy`（testId: `gathering-participant-link-copy`、見出しは「リンクを発行」
に変わる——可視文言はこの契約が元々固定していない）の`requiredOutcome`を書き換える。
活性化は引き続き`issueParticipantLinks`を`count: 1`で呼び、`Gathering.
totalIssuedParticipantLinks`/`activeParticipantLinkCount`を1ずつ増やし、
`gathering-participant-link-list`に新しい項目を1つ増やす（ここまでは無変更）。**変わるのは
その先**——この活性化はもうクリップボードへ書き込まない。代わりに新設の
`gathering-participant-link-issue-dialog`（小窓）を表示に変え、返ってきた
`IssuedParticipantLink.url`を、この小窓自身の`data-issued-link-url`属性として持たせる。

小窓の中に、新設の2つの操作を置く。

- **`gathering-participant-link-issue-dialog-copy`**（「リンクをコピー」、大きなボタン）:
  活性化すると、小窓の`data-issued-link-url`が持つ値をブラウザのクリップボードへ書き込む。
  **`ADR-0058`が発行操作そのものに課したクリップボード書き込みのMustは、ここへ移る**——
  取り消すのではなく、担当する操作を付け替える。書き込みが拒否・非対応だった場合の扱い
  （無音失敗、説明文を出さない、FR-034）は`ADR-0058`の決定2・3をそのまま引き継ぐ。
- **`gathering-participant-link-issue-dialog-close`**（「閉じる」／「×」）: 活性化すると
  小窓が消える。公開操作は呼ばない。この契約は「閉じる」と「×」を1つのコントロールとして
  実装するか2つの冗長なコントロールとして実装するかを固定しない——どちらであっても、活性化
  すればこの帰結を満たす。

一覧（`gathering-participant-link-list`）に新しく増える項目（今回発行した1件）の見え方
（例えば「いま発行」という札）は、この契約が元々固定していない可視文言の範囲に留まる——
新しい項目が増えること自体は既存の`requiredOutcome`が既に求めている。行ごとの再コピー
（`participantLinkList.item.recopy`）は無変更のまま残る——クリップボード書き込みのMustも
その場所にすでにあり（`ADR-0058`）、今回の変更の影響を受けない。

### 決定2（CQ2、F2案）. 参加者の日程回答画面に、候補日ごとの他の参加者の名前と回答を表示する

`gathering-scheduling-api.yaml`の`ParticipantScheduleQuestion`へ新規`respondents`
（`ScheduleRespondent`の配列、常に非null）を追加する。1つの候補日に回答した参加者リンク
1件につき1エントリ——このビューアー自身が回答済みならその分も含む。`ScheduleRespondent`は
`displayName`（自己申告名、nullは「名無し」）と`response`（GOING/MAYBE/NOT_GOING、
未回答は配列に現れないので値としてUNANSWEREDを持つことはない）の2フィールドだけを持つ
——参加者リンクのID・トークンはいずれも露出しない（`ParticipantShopVoteOption.
addedAfterVotingStarted`が確立した「署名付きリンクの参加者への開示は最小限に保つ」という
設計判断をここでも踏襲する）。この配列は`tally`と同じ「本人の回答の有無によらず常に見える」
という可視性（`adr/0050`決定2）の下にあり、`ParticipantLinkSummary.scheduleResponses`
（`ADR-0056`決定1）が幹事に対して既に開いている同じデータの、参加者どうし向けの鏡像である。

`gathering-scheduling-browser-interface.yaml`の`scheduleQuestion`へ、`tally`の兄弟として
新規`respondentList`（testId: `gathering-schedule-respondent-list`、子要素
`gathering-schedule-respondent-item`）を追加する。各項目は`data-response-value`
（GOING/MAYBE/NOT_GOING）と`data-participant-named`（`participantLinkList.item`が既に
使う「true」/「false」の語彙）を持つ表示専用の要素——DOM順は固定しない。名前の実際の可視
テキストは`participantLinkList.item`と同じ理由でこの契約は機械検証の対象にしない
（TDR-GTH-16の「名無しを含む」区別可能性の要求と同じ扱い、文字列の完全一致は求めない）。

`gathering-scheduling.feature`へ新規シナリオTDR-GTH-64を追加する（下記「帰結」参照）。この
配列を店の投票（`shopVoteQuestion`）にも同じ形で広げるかどうかは、本ADRでは決めない——
今回の人間裁定は日程回答の画面（束Cの対象）に限られており、店の投票側は次のラウンドへ持ち越す
（下記「未決事項」）。

### 決定3（CQ2、答え方本体）. 日程回答を1日ずつ進む流れへ作り直し、「あとで答える」「結果をのぞく」を廃止する

`scheduleQuestion.cardinality`を、「同時表示か1日ずつかをこの契約は固定しない」という記述
から、「常にちょうど1つの`gathering-schedule-question`だけがDOMに到達可能である」という
Mustへ変える——2026-08-30の起草時から2026-09-16まで契約が許容してきた同時表示という選択肢
は、この変更でもう許されない。

`responseOptions.requiredOutcome`へ自動送りを追加する: 回答が成立した直後、
`scheduleQuestion.orderingInvariant`の順で次の候補日が存在すれば、その候補日の
`gathering-schedule-question`が新しく到達可能になる（自動で次の日へ）。最後の候補日を
答えたときに何が到達可能になるかは、この契約は固定しない。

新設の3つの操作を`participantAnswer`へ追加する。

- **`gathering-participant-answer-skip`**（「とばす」、右下）: 活性化すると、
  `scheduleQuestion.orderingInvariant`の次の候補日が到達可能になる。答えずに飛ばした候補日
  の`data-your-response`は変わらない（UNANSWEREDのままでよい）。公開操作は呼ばない。
- **`gathering-participant-answer-previous`**（「前の日」、左下）: 活性化すると、順で1つ前の
  候補日が到達可能になる。今の候補日が順で最初であるときは無効化される（disabledState）。
  公開操作は呼ばない。
- **`gathering-participant-day-list`**（「日の一覧」、スマホは下から出るシート、PCは左に
  常設——この契約は表示形態を固定しない）: 候補日それぞれに1つの
  `gathering-participant-day-item`（`data-candidate-date-id`・`data-your-response`）を持つ、
  常に全件を並べる一覧。DOM順は`scheduleQuestion.orderingInvariant`と同じ（開催日の早い順、
  `ADR-0060`決定6）。項目を活性化すると、その候補日が到達可能になる（公開操作は呼ばない、
  回答値も変えない）。**全部答え終えたときの「12件すべて答えました」という完了の面は、この
  一覧自身が兼ねる**——別の要素は新設しない。完了しているかどうかは
  `gathering-participant-progress`の既存の2つの属性（`data-total-candidate-dates`と
  `data-answered-candidate-dates`が等しいかどうか）から導出できるため、新しい真偽値は要らない。

**`answerLater`・`peekResults`（それぞれの確認面・エコー要素を含む）を全廃する**——`adr/0050`
決定1（2026-09-08〜09、両方を実際に動く操作にした）と`adr/0055`決定3（2026-09-12、
「あとで答える」の確認文を実物の再掲へ差し替えた）を、単なる見た目の変更ではなく、両方の
操作自体の撤去として覆す。撤去できる理由は、この製品が既に持つ2つの性質による——(a) 回答は
「1問ごとにその場で保存する」設計（`answerLater`自身の`requiredOutcome`が根拠にしていたのと
同じ設計）であるため、いつ画面を閉じても回答は失われない——離脱前の確認そのものが要らない。
(b) `adr/0050`決定2により他の参加者の集計は常に見えるため、わざわざ「のぞく」操作を挟む
理由がない。人間の裁定はこの2点を追認するものであり、`gathering-participant-day-list`が
「自分の答えの一覧」という`answerLater`確認面が担っていた役割を引き継ぐ。

### 決定4（CQ3）. 聞く順は日付順のまま——変更なし

`ADR-0060`決定6が2026-09-16にすでに確定させた「候補日は開催日の早い順に並ぶ」という並びを、
参加者の日程回答画面のCQ2再設計後も維持する。人間の裁定（CQ3 a「日付の順」）は既存の契約
どおりであることの確認であり、新しい契約変更を要さない——`scheduleQuestion.orderingInvariant`
はすでにこの並びを固定している（決定3の1日ずつフロー・決定2の`respondentList`・決定3の
`dayList`は、いずれもこの既存の並びをそのまま使う）。

### 決定5（CQ4）. 確定後の参加者画面から、他の候補の店とその票を消す——`ADR-0055`決定8の反転

`shopVoteQuestion.presenceRule`・`shopVoteMap.presenceRule`を、「確定後も present のまま」
という`ADR-0055`決定8の記述から、「`ParticipantView.decision`が非nullになると absent」
という、`scheduleQuestion`と同じ扱いへ戻す。`finalizedView.replacesQuestionSurfaces`から
除外していた`gathering-shop-vote-question`（とその`gathering-shop-vote-tally`）を、
`gathering-shop-vote-map`とともにこのリストへ戻す。`finalizedView.decision.requirement`の
「確定後も店の生きた集計を見られる」という記述を、「確定後は他のどの店の情報も見えない」へ
書き換える。

**この反転は`TDR-GTH-34`の既存の本文と、実は最初から一致していた**——同シナリオは
「自分自身の過去の回答や、他の参加者の回答・投票、店ごとの回答の一覧は示されない」と一貫して
述べており、`ADR-0055`決定8（2026-09-12）がブラウザ契約側だけを「見える」へ変えた際、この
`.feature`本文は追随して書き換えられていなかった（`ADR-0055`の帰結節はTDR-GTH-34について
「決定7・8による書き換え不要」としか触れていない——見落としである）。したがって
2026-09-12から今回までの間、`gathering-scheduling-browser-interface.yaml`と
`gathering-scheduling.feature`は確定後の店の可視性について互いに矛盾した状態にあった
可能性がある——本ADRはこれを「見えない」側で解消し、両者を再び一致させる。実装がこの間に
どちらの記述に従っていたかは、architectは実装コードを読まないため確認できない——次に
このスライスを扱う開発者・testerへの申し送りとする（下記「未決事項」）。

確定後の参加者画面が示すのは、決定内容（決定した開催日時・店）と、店の場所を示す地図
（決まった店のピンと検索基点、経路の線も同心の輪も描かない、`ADR-0056`決定10）だけである
——この2要素はすでに`gathering-participant-decision`/`gathering-participant-decision-map`
として契約済みであり、決定5はこれらに変更を加えない。

### 決定6（副産物・技術判断）. 発見した2つの整合性の穴を閉じる

architectの技術判断による改訂であり、人間のチャット裁定を経ない（`meta/adr/0064`の作法、
`ADR-0057`決定5・`ADR-0060`が同じ経路で先例を持つ）。

- **`gathering-scheduling.feature`のFeature説明文（業務要約段落）を是正する**: 「参加者には
  確定した開催日と店に加えて、自分自身の開催日への回答が示される」という一文は、
  `adr/0050`決定3（2026-09-08〜09、店ごとの一覧を削る）が定めた段階の記述のまま、
  `adr/0055`決定7（2026-09-12、その1行も消す）に追随せず取り残されていた——TDR-GTH-34自体は
  正しく改訂済みだったが、この要約段落だけが古い状態を語り続けていた。決定5・決定2の反映と
  あわせて、この段落を現状（決定内容と地図だけを示す、日程回答には他の参加者の名前も見える）
  に合わせて書き改める。
- **`allowedPurposes`へ`gathering-create-review-open`・`gathering-create-review-cancel`・
  `gathering-create-review-month-navigate`を追加する**: `ADR-0060`決定5がこれら3つの
  purposeを新設したが、`unavailableControls.allowedPurposes`の配列へ登録し忘れていた
  ——起草時の抜けである。本ADRが同じ配列（決定1・3が追加する新しいpurposeのため）を触るのを
  機に、あわせて閉じる。新しい業務判断は伴わない。

## PR #196 監査Minorの扱い

`activeContext.md`が記録するPR #196マージ後監査のMinor（`issue_participant_link_from_dashboard`
に埋めたクリップボード検査を、GivenとしてこれのTDR-GTH-16/17/18/19/36が暗黙に継承しており、
回帰時に無関係シナリオも赤くなる）は、**契約の変更ではなくテストコードの構造の問題であり、
architectが起草する契約はこれを直接扱わない**。ただし決定1（発行を2段の操作に組み替える）は、
この`issue_participant_link_from_dashboard`というDSLヘルパー自体を実装が書き直さざるを得ない
契機になる——発行の活性化がもう小窓を開くだけになり、クリップボードへの書き込みは
`gathering-participant-link-issue-dialog-copy`という別の活性化に移るため、このヘルパーは
どのみち新しい形へ作り直される。**この書き直しの機会に、クリップボード検査をヘルパー自身の
必須の結果から切り離し、TDR-GTH-03・TDR-GTH-17固有の`Then`検査へ限定することを、
developer・testerへの申し送りとして明記する**（下記「未決事項」）——共有Givenヘルパーに
検査を埋め込むと、そのヘルパーをGivenとして使う無関係なシナリオ（TDR-GTH-16/18/19等、
リンクが1件発行済みであることだけを前提にする）まで、クリップボードの実装都合で赤くなる。
これは契約の要求ではなく、次に選ばれるテスト実装の設計判断であるべきだと考える。

## 検討した代替案

- **CQ1で、行の再コピーと同じ「行が増えてその行でコピー」（板の案a）を採る**: 却下（人間裁定）。
  人間はb「発行で小窓が開き、そこでコピー」を選んだ——一覧が伸びていく中で毎回どの行が最新か
  探す負担を避けられる。
- **CQ1で、本数を決めてまとめて発行する（板の案c）**: 却下（人間裁定）。`ADR-0036`決定4が
  一度検討し人間が退けた「まとめ発行」を、今回も採らない。
- **CQ1で、クリップボード書き込みのMustを小窓の表示自体（活性化の結果）に付ける**: 却下。
  板は「リンクをコピー」という明示的な押下操作を示しており、小窓が開いた時点で自動的に
  コピーする設計は板と一致しない——人間が「押すとコピーされ、ボタンが変わる」という2段目の
  操作を明示的に選んでいる。
- **CQ2で、「答えてから次へ」（板の案b）を採る**: 却下（人間裁定）。人間はa「答えると自動で
  次の日へ」を選んだ——ボタンをもう1つ挟まずに済む。
- **CQ2のレイアウトで、D2「一覧は自分の答えだけ」を採る**: 却下（人間裁定）。人間はF2（他の
  参加者の名前と答えも並べる）を選んだ——選択肢の説明で製品境界が動くことを理解したうえでの
  選択である。
- **CQ2のレイアウトで、F1「カードを縮めて下に寄せる」を採る**: 却下（人間裁定）。
- **CQ2で、respondentsをshopVoteQuestion（店の投票）にも同時に広げる**: 却下（スコープ限定）。
  今回の人間裁定は日程回答の画面（束C、CQ2）に限られており、店の投票側に同じものを広げるか
  どうかは人間が検討していない——次のラウンドへ持ち越す。
- **CQ2で、「あとで答える」「結果をのぞく」を廃止せず、文言だけ調整する**: 却下（人間裁定・
  依頼文の明示）。この2操作自体を無くす方向が明示的に選ばれている。
- **決定3で、`gathering-participant-day-list`とは別に「12件すべて答えました」専用の完了要素を
  新設する**: 却下。完了状態は既存の`gathering-participant-progress`の2つの属性から導出でき、
  新しい真偽値・新しいtestIdを増やす理由がない——dayList自身がその役割を兼ねる。
- **CQ4で、店の情報のうち店名だけは残し票だけ消す**: 却下（人間裁定）。人間の言葉「他の候補の
  店と票は出さない」は、店の情報自体も含めて出さないという意味として解釈した——決まった店の
  情報（決定内容）とは別物として扱う。
- **決定6（Feature説明文の是正）を見送り、次に触る回へ持ち越す**: 却下。同じ段落を決定2・決定5
  が実際に書き換える必要があり、古い一文をそのまま残すと新しい記述と地の文で矛盾する——
  同じ作業のうちに閉じるのが自然だった。

## 帰結

- `contracts/gathering-scheduling-browser-interface.yaml`（改訂、現行contractVersion 0.22.0 ->
  0.23.0）: 決定1（`participantLinkCopy.requiredOutcome`の書き換え、`issueDialog`/
  `dialogCopy`/`dialogClose`の新設）、決定2（`scheduleQuestion.respondentList`の新設）、
  決定3（`scheduleQuestion.cardinality`のMust化、`responseOptions.requiredOutcome`への自動
  送り追加、`answerLater`/`peekResults`の全廃、`daySkip`/`dayPrevious`/`dayList`の新設）、
  決定5（`shopVoteQuestion.presenceRule`・`shopVoteMap.presenceRule`・`finalizedView.decision.
  requirement`・`replacesQuestionSurfaces`の反転）、決定6（`allowedPurposes`への3件の追加）を
  反映する。**具体的なYAML編集は本ADRと同じ提出物（`spec-bundle-c`のdiff指定、
  `browser-interface.spec`）を参照。**
- `contracts/gathering-scheduling-api.yaml`（改訂、現行v0.16.0 -> v0.17.0）: 決定2
  （`ParticipantScheduleQuestion.respondents`・新規スキーマ`ScheduleRespondent`の追加）を
  反映する。**具体的なYAML編集は同diff指定（`api.spec`）を参照。**
- `contracts/gathering-scheduling.feature`: 新規シナリオTDR-GTH-64（決定2）を追加する。
  Feature説明文（業務要約段落）を決定2・決定5・決定6に合わせて書き改める。TDR-GTH-34は本文
  変更なし（決定5により、この契約が改めてTDR-GTH-34の既存の主張と一致する）。既存シナリオ
  （TDR-GTH-01〜63、TDR-GTH-34を含む）は本文を変更していない。**具体的な差分は同diff指定
  （`feature.spec`）を参照。**
- `contracts/test-support-api.yaml`: 変更しない——決定1・2・3・5のいずれも、
  `gathering-scheduling-api.yaml`が既に公開している境界（createGathering・addCandidateDates・
  issueParticipantLinks・setScheduleResponse・setParticipantDisplayName・confirmCandidateDate
  等）だけで構築・検証できる新しいGiven状態を要求しない（`ADR-0037`決定1と同じ理由）。
- `product-brief.md`（改訂）: §2「参加者の回答と店への三段階の回答」を、決定2（日程回答は
  名前つきで他の参加者に見える）・決定3（「あとで答える」「結果をのぞく」の廃止とその理由）・
  決定5（確定後は決まった店以外を出さない、`adr/0055`決定8のこの記述を再度覆す）に合わせて
  改訂する。**具体的な差分は同diff指定（`product-brief.spec`）を参照。**
- `ARCHITECTURE.md`・`design.md`: 変更しない——本ADRは会スコープの契約内部の規則変更・
  画面内の操作の組み替えであり、モジュール境界・製品の担当領域そのもの（誰がどの画面を持つか）
  を変えない。決定2は可視性の境界を動かすが、それは`product-brief.md`が記録する製品境界であり、
  `design.md`が記録するモジュール構造ではない。

## 未決事項（次工程・人間への申し送り）

1. **店の投票（`shopVoteQuestion`）にも`respondents`と同種の名前つき表示を広げるか**
   （決定2の対象外）は、本ADRでは決めない——次のラウンドで人間が検討することを推奨する。
2. **`issue_participant_link_from_dashboard`のクリップボード検査をヘルパー自身から切り離す**
   （PR #196監査Minor）: developer・testerが決定1の実装（2段の操作）に合わせてこのDSL
   ヘルパーを書き直す際、クリップボード検査をヘルパーの必須の結果から外し、TDR-GTH-03・
   TDR-GTH-17固有の`Then`検査へ限定することを推奨する——共有Givenヘルパーに検査を埋め込むと、
   これをGivenとして使う無関係なシナリオまで巻き添えで赤くなる。これは契約が固定する事項では
   なく、テスト実装の設計判断として申し送る。
3. **決定5の反転が確定するまでの間、実装がどちらの記述（`ADR-0055`決定8の「見える」か、
   `TDR-GTH-34`本文の「見えない」か）に従っていたか**は、architectは実装コードを読まないため
   確認できない——次にこの画面を触る開発者・testerが、現在の実装の挙動を確認したうえで
   決定5の反転（「見えない」）に合わせて直す必要がある。
4. **「N件」と同様、小窓の「✓ コピーしました」等の可視文言・見た目**は、この契約が元々固定
   していない範囲に留まる——固定するかどうかの判断は次工程に残す。
