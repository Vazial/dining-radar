---
id: 0047
scope: project/dining-radar
status: 承認済み
date: 2026-09-06
approved_by: "人間裁定（2026-09-06 チャット選択肢UI）: 「短いお知らせを出す」。文言の趣旨は
  「うまく読み込めませんでした。時間をおいて開き直してください」程度。やり直すボタンは置かない
  （選択肢として提示したうえで、お知らせのみが選ばれた）。"
supersedes: []
superseded_by: null
relates_to: [P-01, P-02, P-08, ADR-0013, ADR-0035, ADR-0036, ADR-0037, ADR-0043, TDR-GTH-42]
---

# ADR-0047: 参加者画面の読み込み失敗に短いお知らせを追加する

> **承認者向けサマリ**: developerが調査中、参加者用JavaScriptにエラー処理が一切無く、サーバ側で
> 何か起きると画面に何も出ない（設問もエラー表示も出ず真っ白）ことを発見した。既存の
> `gathering-participant-link-error`（`linkError`）は、サーバが`LINK_NOT_FOUND`等の意味のある
> `ProblemResponse`コードを返した場合の観測面であり、今回の穴（応答が得られない・想定外の失敗）
> とは別の状態である。人間は2026-09-06のチャット選択肢UIで「短いお知らせを出す」を選んだ——
> 「うまく読み込めませんでした。時間をおいて開き直してください」程度の趣旨で、**やり直すボタンは
> 置かない**（選択肢として提示したが選ばれなかった）。本ADRはこの裁定をブラウザ契約
> （`gathering-scheduling-browser-interface.yaml`）へ`gathering-participant-load-error`という
> 新しい観測面として書き込み、これを受け入れテストで決定的に作るためのseam
> （`test-support-api.yaml`の`seedParticipantLinkServerError`）を新設する。

## 文脈

### 0. 検証の申告（meta/adr/0039）

本ADRが前提とする既存契約の記述（`linkError`の4コード、`validLinkOutcome`／`invalidLinkOutcome`
の構造、`scheduleQuestion.presenceRule`等の局面依存の存在規則）は、いずれも
`gathering-scheduling-browser-interface.yaml`（v0.7.0）を読んで確認した。**確認していないのは、
参加者用JavaScriptの実際の実装コード**——developerの報告（「エラー処理が無く、何も出ない」）を
そのまま契約上の穴として扱い、実装ファイル自体は読んでいない（architectは実装コードを読まない、
`.claude/agents/architect.md`の禁止事項どおり）。

### 1. 何が起きたか

developerが調査中、参加者画面（署名付きリンク、`participantAnswer`）のJavaScriptに
エラー処理が無いことを発見した。サーバ側で何らかの失敗が起きると（ネットワーク断・
パース不能な応答・`linkError`が定める4つの`ProblemResponse`コードのいずれでもない失敗など）、
画面には設問もエラー表示も出ず、参加者はリンクを開いただけで何も分からない状態になる。

この状態は、契約が既に持つ`invalidLinkOutcome`（`gathering-participant-link-error`、
`LINK_NOT_FOUND`/`LINK_EXPIRED`/`LINK_REVOKED`/`LINK_RATE_LIMITED`のいずれかを意味のある
応答として受け取った場合の観測面）とは**別の状態**である——`invalidLinkOutcome`はサーバが
明示的に理由を返した拒否を扱い、今回の穴は**応答が得られない、または契約が想定するどの形にも
一致しない**場合を扱う。

### 2. 人間裁定

2026-09-06、チャット選択肢UIで人間に選択肢を提示し、「短いお知らせを出す」が選ばれた。文言の
趣旨は「うまく読み込めませんでした。時間をおいて開き直してください」程度。**やり直すボタンは
置かない**——選択肢の1つとして提示したが、選ばれたのはお知らせのみの案だった。

## 決定

### 決定1. 新しい観測面`gathering-participant-load-error`を、`linkError`とは別の状態として定義する

`browserEntry.participantAnswer`に、既存の`validLinkOutcome`・`invalidLinkOutcome`と並ぶ
3つ目の帰結として、参加者向けの取得が「有効なリンクとして完結する（`validLinkOutcome`）」でも
「意味のある拒否として完結する（`invalidLinkOutcome`）」でもない場合の帰結を追加する。この場合
`gathering-participant-load-error`だけが存在し、設問・エラー面・名前操作を含む他のすべての
参加者向け要素は不在になる——読み込めていないのだから設問も決定も出ない、という自然な帰結であり、
既存の`scheduleQuestion.presenceRule`・`finalizedView.presenceRule`等とは矛盾しない（これらは
「有効なリンクが読み込めた後」の局面依存規則であり、今回の状態はその手前で止まる）。

### 決定2. 操作は置かない

人間裁定どおり、`gathering-participant-load-error`の中に purpose 宣言を持つ操作的コントロールは
置かない——`allowedPurposes`への追加は無い。再度試す唯一の方法は、同じ参加者リンクを開き直す
（ページの再読み込み）ことであり、この契約はそのための専用のショートカット操作を要求しない。

### 決定3. 技術的な内部情報を開示しない

既存の`linkError`は「会の名前・参加者の名前や回答・その他会の内容を開示しない」ことをMustにして
いる。今回のお知らせはその性質上むしろ開示リスクが高い——HTTPステータスコード・例外メッセージや
スタックトレース・リクエスト/トレースID・ホスト名など、実装の内部情報が見えてしまう典型的な
状況（サーバ側の未処理の失敗）で表示されるためである。`linkError`の開示規律を踏襲し、これらの
技術的な内部情報を可視文言・属性のいずれにも出さないことをMustにする。

### 決定4. 受け入れテスト用のseamを新設する（`seedParticipantLinkServerError`）

`ADR-0037`決定1の原則（公開境界だけで作れる状態には新しいseamを追加しない）を確認した——
しかし今回の状態（サーバが`ProblemResponse`の形にも成功応答の形にも一致しない失敗を返す）は、
`gathering-scheduling-api.yaml`の公開操作を正しく呼ぶ限り決して作れない。これは
`seedExpiredParticipantLink`（90日待てない）・`seedRateLimitedParticipantLink`（閾値に達する
まで実際に叩けない）と同じ種類の例外——「公開境界の外側の状態を、時間をかけず決定的に作る」
必要性である。既存2seamと同じ設計（`ParticipantLinkTokenSeed`を再利用し、次の1回の該当リクエスト
だけに適用、204を返す）に倣い、`seedParticipantLinkServerError`を新設する。次に一致する
`getParticipantView`呼び出しは、`linkError`が定めるどの`ProblemResponse`コードにも一致しない
HTTP 500応答（本文は空、または`ProblemResponse`スキーマに準拠しない内容のいずれでもよい——
この契約はどちらかを特定しない、`gathering-participant-load-error`の要件が両方を同一に扱う
ため）を返す。新しいスキーマは要らない——既存の`ParticipantLinkTokenSeed`をそのまま再利用する。

## 検討した代替案

- **既存の`seedRateLimitedParticipantLink`を`gathering-participant-load-error`のGivenとして
  流用する**: 不採用。`LINK_RATE_LIMITED`は`linkError`が既に定める意味のあるProblemResponse
  コードであり、`rateLimitedScheduleResponse`という既存のbrowserActionsエントリと同じ状態を
  指す。今回架空したい状態（意味のある応答が一切得られない）とは異なる状態であり、流用すると
  「読み込み失敗」と「レート制限」という別々のシナリオが同じ決定的Givenを指す紛らわしさを生む。
- **`gathering-participant-load-error`を`linkError`の5つ目の値として追加する**（例:
  `data-link-error-code`に`UNKNOWN`のような値を足す）: 不採用。`linkError`はサーバが**意味のある**
  ProblemResponseコードを返した場合の観測面であり、今回の状態はまさに「意味のある応答が
  得られない」ことが本質である。同じ属性・同じ要素に押し込むと、この区別（サーバが明示的に
  拒否した／応答そのものが得られなかった）が契約から読み取れなくなる。
- **やり直すボタンを置く**: 人間裁定で不採用（選択肢として提示したが選ばれなかった）。

## 帰結

- `contracts/gathering-scheduling-browser-interface.yaml`をv0.7.0→v0.8.0へ改訂した（本ADRと
  同一PR）。`browserEntry.participantAnswer`へ`unexpectedLoadFailureOutcome`を追加し、
  `browserControlSurface.participantAnswer`へ`loadFailure`（`gathering-participant-load-error`）
  を追加した。`profiles.localAcceptance.verifiesScenarios`へTDR-GTH-42を追加した。
- `contracts/gathering-scheduling.feature`へTDR-GTH-42を追加した——参加者画面の読み込みに
  失敗したとき短いお知らせが示され、設問もやり直す操作も示されないことを検査する。
- `contracts/test-support-api.yaml`をv1.5.3→v1.5.4へ改訂した——`seedParticipantLinkServerError`
  を新設し、`resetGatheringSchedulingAcceptanceState`の`x-acceptance-scenarios`へTDR-GTH-42を
  追加した。
- `gathering-scheduling-api.yaml`・`product-brief.md`は本ADRでは変更しない——本ADRが追加する
  振る舞いは、公開APIが文書化する応答ではなく「文書化されたどの応答にも一致しない失敗」への
  クライアント側の振る舞いであり、公開契約の追加を要さない。
- `ARCHITECTURE.md`・`design.md`は変更しない——本ADRは新しいモジュール境界を生まない。

## 未決事項（次工程・人間への申し送り）

1. 本ADRの核（お知らせを出す・やり直すボタンを置かない）は人間裁定済みである。可視文言の
   正確な日本語表現は契約が固定しない（決定1参照）——実装時に人間が確認してよい。
2. HTTP 500応答の本文の形（空か、非準拠のJSONか）はseamの設計判断であり、両方を等しく扱う
   ことを`gathering-participant-load-error`の要件が既に保証している——実装が両方をカバー
   できているかはL1/L4で確認する。
