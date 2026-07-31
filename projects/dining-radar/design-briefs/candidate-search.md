# Design brief — candidate proposal screen

> Status: revised for ADR-0005 after human screen review on 2026-08-01. The receiver must show the initial proposal immediately and move concept selection into the re-proposal modal. See `design/reconciliation/candidate-search.md`. This brief replaces both the fixed-count / “more” direction and the initial secondary-condition / always-visible concept-grid direction. All design data must be synthetic and non-sensitive; visible copy remains draft copy pending implementation and L5 review.

## 目的

月1回程度の少人数ランチ会の幹事が、非公開の検索地点をブラウザへ出さずに、サインイン後すぐランチ候補を地図とカードで比較し、合わなければモーダルで別の切り口を選んで提案全体を作り直せる画面を設計する。

画面の視覚的な発想、情報の優先順位、レイアウト、インタラクションの表現は担当するDesigner runtimeが決める。ClaudeではDesignerがGeminiへ依頼し、CodexではDesigner契約と本briefを読んだCodex自身が設計する。どちらも同じ契約・privacy境界・reconciliationを通す。以下は契約上の境界とレビュー可能性を示すものであり、UI案そのものを指定するものではない。

## 対象ユースケース

サインイン済みの幹事が画面を開くと、一つの初期切り口による候補店舗と位置関係がすぐ表示される。初回に検索範囲、ジャンル、コンセプトを選ばせない。気に入らなければ「別の切り口で再提案」を選び、現在の切り口を除く最大3つの選択肢をモーダルで確認する。一つを選ぶと新しい提案を依頼し、以前の候補へ足すのではなく現在のカードと地図全体を置き換える。

外部ページでメニュー、営業状況、予約可否などを最終確認するところまでの導線を示す。ログイン、アカウント管理、公開デプロイの画面は設計しない。

レビュー用成果物では、次の契約状態を合成データで到達可能にする。レビュー専用の状態切替は、提案するプロダクトUIと誤認されないよう明示し、構成の決定は担当するDesigner runtimeに委ねる。

- `TDR-CS-00`: 未認証。サインイン案内だけを示し、再提案の切り口、カード、地図、補助条件は見せない。
- `TDR-CS-01`: 初回操作を求めず、一つの説明可能な初期提案と地図を直ちに示す通常状態。
- `TDR-CS-02`: 表示中の提案を地図とカードで比較し、カードとマーカーを相互に強調する状態。
- `TDR-CS-03`: 最大3つの `reProposalOptions` を示すモーダル、選択後の再提案中、以前の提案を追加せず完全に置き換えた後の状態。
- `TDR-CS-04`: 補助条件、初回コンセプト選択、手動ソートを置かず、切り口選択を再提案時だけに限定した状態。
- `TDR-CS-05`: 成功応答だが `proposal` がnullで、候補がない状態。
- `TDR-CS-06`: 候補情報を取得できない `503 PROVIDER_UNAVAILABLE`。
- `TDR-CS-07`: 表示された選択肢にない切り口による `400 PROPOSAL_REPROPOSAL_KIND_INVALID`。
- `TDR-CS-08`: 短時間の反復による `429 PROPOSAL_RATE_LIMITED`。`Retry-After` に対応する待機案内を安全に示す。
- API境界の補足状態: `403 REQUEST_REJECTED`。内部事情を示さず、再読み込み後の再試行を案内する。

## ドメインルール（最小限）

- 検索基点と実際の探索距離はserver-onlyである。地点、地名、座標、数値距離、基点マーカー、経路、現在地、徒歩時間を入力・表示・推測しない。
- ランチ営業は常に必須条件であり、解除できるフィルタにはしない。
- 検索範囲、ジャンルその他の補助条件を置かない。手動ソート、価格帯、支払方法、空席、予約可否、特定日判定も追加しない。
- 一つの応答は、直ちに表示する一つの `proposal` と、現在の切り口を除く最大3つの `reProposalOptions` を持つ。切り口は `title` と `rationale` で理由を説明する。同じ提案内で店舗は重複しない。再提案前後で同じ店舗が現れる可能性はある。
- モーダルを開く操作だけではAPIを呼ばない。モーダルの切り口を選ぶと、`reproposalKind` を含む新しい提案要求を送り、以前の応答を完全に置き換える。
- 店舗情報はproviderの参考情報であり、保証や推測を加えない。nullableな紹介、営業時間、定休日、総席数、アクセスは、欠損時に中立なドラフトコピー（例: 「情報なし」）で扱う。
- `conceptRef` と `candidateRef` は現在の応答内だけのUI identityである。画面に表示せず、永続識別子として扱わない。
- Hot Pepperのcreditは正確な文言 `Powered by ホットペッパーグルメ Webサービス` を `http://webservice.recruit.co.jp/` へのリンクとして示す。店舗詳細リンクも示すが、provider画像は使わない。
- 地図は表示中の候補店舗が見渡せる範囲を表し、カードとマーカーを相互に強調する。OpenStreetMapの帰属表示を常に示す。
- ラベル、空状態、エラー文言などのコピーはすべてドラフトであり、最終確定ではない。

## 現在のバックエンドAPI（列挙）

### `POST /candidate-proposals`

認証済みsame-origin sessionとCSRFを前提とする。初回表示では空のrequestを送り、再提案では次だけを持つ。

- `reproposalKind`: 現在の `reProposalOptions` から選んだ一つの `ConceptKind`。初回は省略する。永続履歴やprovider識別子ではない。

成功応答は `proposal`、`reProposalOptions[]`、`providerCredit` を返す。`proposal` は候補なしならnull、それ以外は次を持つ。

- `conceptRef`
- `kind`: `PROXIMITY` / `CAPACITY_REFERENCE` / `GENRE_VARIETY` / `AMENITY_REFERENCE`
- `title`
- `rationale`
- `candidates[]`

`reProposalOptions[]` は最大3件で、現在表示中のkindを含めず、各要素は `kind`、`title`、`rationale` だけを持つ。候補、provider ID、検索基点を含まない。

各 `Candidate` は次を持つ。

- `candidateRef`
- `name`
- `genre`
- nullableな `description`
- nullableな `businessHours`
- nullableな `regularHoliday`
- nullableな `totalSeats`
- nullableな `access`
- `location`: `{ latitude, longitude }`。本番で候補マーカーを描くためだけの店舗位置。
- `providerPageUrl`

問題応答は `400 PROPOSAL_REPROPOSAL_KIND_INVALID`、`401 AUTHENTICATION_REQUIRED`、`403 REQUEST_REJECTED`、`429 PROPOSAL_RATE_LIMITED`、`503 PROVIDER_UNAVAILABLE`。画面にはAPIの安全な `message` だけを使い、private origin、credential、provider内部事情を補足しない。

上記APIにない機能が理想の体験に必要だと判断した場合は、存在を仮定せず、成果物内の `Required API additions` block commentに列挙してよい。追加が不要なら `Required API additions: None required.` と正確に記す。

## 解決したい問題

- 旧案の固定5件、追加表示、手動ソート、数値距離、座標入力、補助条件を完全に捨て、初期候補の比較を主役にする。
- 初回の選択をなくし、別の提案が必要な時だけ最大3つの「選ぶ理由」をモーダルで理解しやすくする。
- 地図と情報量の多い店舗カードを相互に追えるようにしつつ、非公開の検索基点を示唆しない。
- 再提案がページ追加ではなく全体置換であることを、操作前・処理中・置換後に誤解なく伝える。
- 候補なし、取得失敗、切り口不正、認証要求、request拒否、rate limitを、安全で互いに区別できる状態として見せる。
- providerの参考情報を、空席・予約・距離・営業可否の保証へ見せない。

## 制約からの解放

既存APIに縛られず、幹事にとって最も明快で魅力的な視覚構成と操作体験を描いてよい。必要なAPI能力が上記に存在しない場合は、契約済みとみなさず `Required API additions` として明示する。APIの細部や将来機能を網羅するより、即時表示される地図とカードの比較・再提案モーダルという中心体験の質に出力を集中する。

## 技術前提

- 成果物は、隔離された査読専用receiver `projects/toyama-dining-radar/design-preview/` だけで描画する。Django本体、provider、実APIへ接続しない。
- React + TypeScriptのdefault-export TSX screenとし、Tailwindおよびreceiverで利用可能なshadcn/ui component、Lucide iconを使ってよい。
- 合成表示データとレビュー状態だけをscreen内に持たせる。network call、persistence、local storage、本番状態管理を持たせない。
- 実店舗、実地点、地名、緯度経度、数値距離、provider response、provider ID、credential、keyed URL、provider画像を含めない。店舗名・ジャンル・紹介などは、架空であることが明確な日本語サンプルにする。店舗詳細リンクは `https://example.invalid/` 配下の不活性な合成URLにする。
- ADR-0003のprivacy boundaryにより、API-shapedな `location.latitude` / `location.longitude` の数値fixtureをrepositoryへ置かない。レビュー地図のmarker配置は非地理的なreview-only layout dataで表し、source commentで本番の `Candidate.location` に対応することを注記する。このlayout dataはAPI fieldでもAPI追加要求でもない。
- 実Leaflet tileやOpenStreetMap tileを取得しない。地図の配置・カードとの相互強調・帰属表示を確認できる合成map surfaceとして設計し、実接続は後続実装に残す。
- provider creditの契約済みURLと、一般公開のOpenStreetMap attribution linkを除き、実外部サービスへの通信を発生させない。

## 成果物の指定

`projects/toyama-dining-radar/design-preview/src/screens/CandidateSearchPreview.tsx` のrawで完全な実行可能ソースだけを返す。Markdown fence、説明文、実装計画、package file、receiver scaffolding、Django code、自己完結HTMLを返さない。成果物は無改変で配置・描画できなければならない。

成果物には次を含める。

- 中心体験として、初回操作なしの一提案表示、地図＋店舗カード比較、カード・マーカー相互強調、最大3つの再提案切り口を示すモーダル、選択後の全体置換を操作可能にする。補助条件と常設コンセプト一覧は置かない。
- `Candidate` の表示対象である `name`、`genre`、`description`、`businessHours`、`regularHoliday`、`totalSeats`、`access`、`providerPageUrl` をカードで確認可能にする。nullable値の中立な欠損表示を少なくとも一例含める。
- Hot Pepperの正確なlinked creditと、見えるOpenStreetMap attribution treatmentを含める。
- `TDR-CS-00`〜`TDR-CS-08`、loading、`403 REQUEST_REJECTED`、再提案前後をレビュー可能な、明確にreview-onlyと分かる状態切替を含める。未認証状態ではproduct control/result surfaceを完全に隠す。
- 合成データの一貫性を保ち、固定件数ページング、候補追加、手動ソート、実距離、徒歩時間、基点・現在地・経路、provider画像、保証されないbadgeやscoreを作らない。
- source commentで、主要な可視要素・状態を対応するTDR-CS scenario ID、API field、problem codeへ注記する。`conceptRef` / `candidateRef` はsource内のcurrent-response identityにだけ使い、画面には表示しない。
- source内に独立した `Required API additions` block commentを置き、必要な追加を列挙するか、不要なら正確に `Required API additions: None required.` と記す。

担当するDesigner runtimeは、これらの契約境界を保ったまま、画面の視覚的構成、主要ブロックの存在と配置・階層、情報密度、responsive behavior、product copyの草案を自由に設計する。
