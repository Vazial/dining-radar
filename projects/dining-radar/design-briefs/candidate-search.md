# Design brief — candidate proposal screen

> Status: Codex escape-path receiver is reviewable, and its screen direction was human-approved in chat on 2026-08-01. The promotional copy was then reduced for an everyday organizer tool. See `design/reconciliation/candidate-search.md`. This brief replaces the superseded fixed-count / “more” design direction. All design data must be synthetic and non-sensitive; visible copy remains draft copy pending implementation and L5 review.

## 目的

月1回程度の少人数ランチ会の幹事が、非公開の検索地点をブラウザへ出さずに、選ぶ理由の異なるランチ候補のコンセプトを選び、店舗を地図とカードで比較し、合わなければ別の観点で提案全体を作り直せる画面を設計する。

画面の視覚的な発想、情報の優先順位、レイアウト、インタラクションの表現は担当するDesigner runtimeが決める。ClaudeではDesignerがGeminiへ依頼し、CodexではDesigner契約と本briefを読んだCodex自身が設計する。どちらも同じ契約・privacy境界・reconciliationを通す。以下は契約上の境界とレビュー可能性を示すものであり、UI案そのものを指定するものではない。

## 対象ユースケース

サインイン済みの幹事が、相対的な検索範囲の希望と任意のジャンルを補助条件として候補提案を依頼する。最大3つのコンセプトから一つを選び、その理由を理解しながら候補店舗を地図とカードで比較する。気に入らなければ、既出の観点を避ける再提案を依頼し、以前の提案へ候補を足すのではなく現在の提案全体を置き換える。

外部ページでメニュー、営業状況、予約可否などを最終確認するところまでの導線を示す。ログイン、アカウント管理、公開デプロイの画面は設計しない。

レビュー用成果物では、次の契約状態を合成データで到達可能にする。レビュー専用の状態切替は、提案するプロダクトUIと誤認されないよう明示し、構成の決定は担当するDesigner runtimeに委ねる。

- `TDR-CS-00`: 未認証。サインイン案内だけを示し、コンセプト、カード、地図、補助条件は見せない。
- `TDR-CS-01`: 最大3つの説明可能なコンセプトを示す通常提案。
- `TDR-CS-02`: 選択したコンセプトの候補を地図とカードで比較し、カードとマーカーを相互に強調する状態。
- `TDR-CS-03`: 再提案中と、以前の提案を追加せず完全に置き換えた後の状態。
- `TDR-CS-04`: 相対範囲またはジャンルを補助条件として使う状態。コンセプト選択が主操作で、手動ソートは置かない。
- `TDR-CS-05`: 成功応答だが `concepts` が空で、条件に合う候補がない状態。
- `TDR-CS-06`: 候補情報を取得できない `503 PROVIDER_UNAVAILABLE`。
- `TDR-CS-07`: 対応していない補助条件による `400 PROPOSAL_CONDITIONS_INVALID`。
- `TDR-CS-08`: 短時間の反復による `429 PROPOSAL_RATE_LIMITED`。`Retry-After` に対応する待機案内を安全に示す。
- API境界の補足状態: `403 REQUEST_REJECTED`。内部事情を示さず、再読み込み後の再試行を案内する。

## ドメインルール（最小限）

- 検索基点と実際の探索距離はserver-onlyである。地点、地名、座標、数値距離、基点マーカー、経路、現在地、徒歩時間を入力・表示・推測しない。
- ランチ営業は常に必須条件であり、解除できるフィルタにはしない。
- 補助条件は、APIが返す相対範囲 `NEARBY` / `STANDARD` / `WIDE` と、APIが返すジャンル選択肢だけである。手動ソート、価格帯、支払方法、空席、予約可否、特定日判定を追加しない。
- 一つの応答には最大3コンセプトがあり、各コンセプトは `title` と `rationale` で選ぶ理由を説明する。同じコンセプト内で店舗は重複しない。異なるコンセプト間や再提案前後で同じ店舗が現れる可能性はある。
- コンセプト選択は同じ応答を使うbrowser-local操作で、追加APIを呼ばない。再提案だけが新しい提案要求であり、以前の応答を完全に置き換える。
- 店舗情報はproviderの参考情報であり、保証や推測を加えない。nullableな紹介、営業時間、定休日、総席数、アクセスは、欠損時に中立なドラフトコピー（例: 「情報なし」）で扱う。
- `conceptRef` と `candidateRef` は現在の応答内だけのUI identityである。画面に表示せず、永続識別子として扱わない。
- Hot Pepperのcreditは正確な文言 `Powered by ホットペッパーグルメ Webサービス` を `http://webservice.recruit.co.jp/` へのリンクとして示す。店舗詳細リンクも示すが、provider画像は使わない。
- 地図は表示中の候補店舗が見渡せる範囲を表し、カードとマーカーを相互に強調する。OpenStreetMapの帰属表示を常に示す。
- ラベル、空状態、エラー文言などのコピーはすべてドラフトであり、最終確定ではない。

## 現在のバックエンドAPI（列挙）

### `GET /candidate-search-filters`

認証済み幹事向け。次を返す。

- `rangePreferences[]`: `{ key, label }`。`key` は `NEARBY` / `STANDARD` / `WIDE` で、数値距離を含まない。
- `genreOptions[]`: provider由来の `{ code, label }`。
- `providerCredit`: `{ text, url }`。

安全な問題応答として `401 AUTHENTICATION_REQUIRED`、`429 PROPOSAL_RATE_LIMITED`、`503 PROVIDER_UNAVAILABLE` がある。

### `POST /candidate-proposals`

認証済みsame-origin sessionとCSRFを前提とする。requestは次だけを持つ。

- `rangePreference`: `NEARBY` / `STANDARD` / `WIDE`。省略時のAPI defaultは `NEARBY`。
- `genreCodes[]`: filter APIから得たcode。省略または空配列ならジャンル制約なし。
- `previousConceptKinds[]`: 再提案時に現在画面ですでに提示した `ConceptKind` を渡し、未提示の適格な観点を優先するための一時的な文脈。永続履歴ではない。

成功応答は `concepts[]` と `providerCredit` を返す。`concepts` は0〜3件で、各要素は次を持つ。

- `conceptRef`
- `kind`: `PROXIMITY` / `CAPACITY_REFERENCE` / `GENRE_VARIETY` / `AMENITY_REFERENCE`
- `title`
- `rationale`
- `candidates[]`

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

問題応答は `400 PROPOSAL_CONDITIONS_INVALID`、`401 AUTHENTICATION_REQUIRED`、`403 REQUEST_REJECTED`、`429 PROPOSAL_RATE_LIMITED`、`503 PROVIDER_UNAVAILABLE`。画面にはAPIの安全な `message` だけを使い、private origin、credential、provider内部事情を補足しない。

上記APIにない機能が理想の体験に必要だと判断した場合は、存在を仮定せず、成果物内の `Required API additions` block commentに列挙してよい。追加が不要なら `Required API additions: None required.` と正確に記す。

## 解決したい問題

- 旧案の固定5件、追加表示、手動ソート、数値距離、座標入力を完全に捨て、コンセプトを選ぶ体験を主役にする。
- 最大3つの異なる「選ぶ理由」と、選択後の店舗比較を一つの画面で理解しやすくする。
- 地図と情報量の多い店舗カードを相互に追えるようにしつつ、非公開の検索基点を示唆しない。
- 再提案がページ追加ではなく全体置換であることを、操作前・処理中・置換後に誤解なく伝える。
- 候補なし、取得失敗、条件不正、認証要求、request拒否、rate limitを、安全で互いに区別できる状態として見せる。
- providerの参考情報を、空席・予約・距離・営業可否の保証へ見せない。

## 制約からの解放

既存APIに縛られず、幹事にとって最も明快で魅力的な視覚構成と操作体験を描いてよい。必要なAPI能力が上記に存在しない場合は、契約済みとみなさず `Required API additions` として明示する。APIの細部や将来機能を網羅するより、コンセプト選択・地図とカードの比較・再提案という中心体験の質に出力を集中する。

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

- 中心体験として、補助条件の選択、提案依頼、最大3コンセプトの理由つき選択、選択コンセプトの地図＋店舗カード比較、カード・マーカー相互強調、再提案による全体置換を操作可能にする。
- `Candidate` の表示対象である `name`、`genre`、`description`、`businessHours`、`regularHoliday`、`totalSeats`、`access`、`providerPageUrl` をカードで確認可能にする。nullable値の中立な欠損表示を少なくとも一例含める。
- Hot Pepperの正確なlinked creditと、見えるOpenStreetMap attribution treatmentを含める。
- `TDR-CS-00`〜`TDR-CS-08`、loading、`403 REQUEST_REJECTED`、再提案前後をレビュー可能な、明確にreview-onlyと分かる状態切替を含める。未認証状態ではproduct control/result surfaceを完全に隠す。
- 合成データの一貫性を保ち、固定件数ページング、候補追加、手動ソート、実距離、徒歩時間、基点・現在地・経路、provider画像、保証されないbadgeやscoreを作らない。
- source commentで、主要な可視要素・状態を対応するTDR-CS scenario ID、API field、problem codeへ注記する。`conceptRef` / `candidateRef` はsource内のcurrent-response identityにだけ使い、画面には表示しない。
- source内に独立した `Required API additions` block commentを置き、必要な追加を列挙するか、不要なら正確に `Required API additions: None required.` と記す。

担当するDesigner runtimeは、これらの契約境界を保ったまま、画面の視覚的構成、主要ブロックの存在と配置・階層、情報密度、responsive behavior、product copyの草案を自由に設計する。
