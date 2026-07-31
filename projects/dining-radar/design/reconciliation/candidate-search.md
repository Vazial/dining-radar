# Candidate search design reconciliation — external round 1 and Codex escape path

> **結論**: external round 1は承認済み契約を満たさなかった。人間が2026-08-01にCodex自身によるescape pathを選択し、Codex版receiverへ完全置換した。現成果物は必須操作・状態・表示項目・privacy境界・buildを満たし、画面の方向性は同日のchatで人間承認済みである。販促的なコピーを減らす指摘も反映した。

## 照合対象

- `product-brief.md`
- `contracts/candidate-search.feature` の `TDR-CS-00`〜`TDR-CS-08`
- `contracts/candidate-search-api.yaml` v0.3.0
- ADR-0002（公開repositoryと外部データの境界）
- ADR-0003（review-only receiverと合成データ境界、提案中）
- ADR-0004（非公開基点・コンセプト選択・全体置換の再提案）
- `design-briefs/candidate-search.md`
- 外部AI成果物 `design-preview/src/screens/CandidateSearchPreview.tsx`（`gemini-3.1-flash-lite`、無改変）

行番号はround-1成果物を無改変で受け取った時点のものを指す。

## 受け入れシナリオとの照合

| シナリオ | 判定 | 成果物の対応 | 不一致 |
|---|---|---|---|
| `TDR-CS-00` | 部分適合 | 未認証用の案内を表示する（65行目）。 | review footerは残るが、コンセプト・カード・地図・補助条件は表示されない。中心制約は満たす。 |
| `TDR-CS-01` | 部分適合 | 2つのコンセプトに `title` と `rationale` を表示する（33〜53、72〜81行目）。 | 幹事が補助条件を選び「候補を提案するよう依頼する」開始操作が存在しない。合成店舗名は明確に架空と判別できない。根拠文の一部はprovider fieldから説明できない（下記参照）。 |
| `TDR-CS-02` | 不適合 | コンセプト選択後にカードと地図欄を並べ、カード選択状態を変える（84〜106行目）。 | 地図は文字だけのplaceholderでmarkerがなく、markerからcardを強調できない。card選択時には内部 `candidateRef` 相当値を地図欄へ表示する（90行目）。カードに必須の `genre`、`regularHoliday`、`access` を表示しない。表示候補が見渡せるmap範囲も表現しない。 |
| `TDR-CS-03` | 不適合 | `Scenario` typeにIDだけ存在する（57行目）。 | 再提案操作、処理中状態、`previousConceptKinds` の扱い、以前の応答を追加せず全体置換した後の状態がすべて存在しない。review switcherにも `TDR-CS-03` がない（117行目）。 |
| `TDR-CS-04` | 不適合 | 対応なし。 | `rangePreferences`、`genreOptions`、ランチ必須の表示、提案開始操作がない。コンセプト選択を補助条件より主とする体験を確認できない。review scenario type/switcherにもIDがない。 |
| `TDR-CS-05` | 適合 | 候補なしを独立状態として示す（68、117行目）。 | 取得失敗とは区別される。コピーはドラフトとして扱う。 |
| `TDR-CS-06` | 部分適合 | provider unavailableに相当する安全な独立状態を示す（66、117行目）。 | `503 PROVIDER_UNAVAILABLE` とのsource annotationがなく、problem codeとの対応を監査しにくい。 |
| `TDR-CS-07` | 不適合 | 対応なし。 | `400 PROPOSAL_CONDITIONS_INVALID` の状態と安全な案内がなく、review scenario type/switcherにもIDがない。 |
| `TDR-CS-08` | 適合 | rate limitと待機時間を独立状態として示す（67、117行目）。 | `(Retry-After: 30s)` は合成review値として扱える。最終コピーは未確定。 |
| API補足 `403 REQUEST_REJECTED` | 不適合 | 対応なし。 | 独立状態、安全な再読み込み案内、problem code annotationがない。 |
| loading | 不適合 | 対応なし。 | 初回提案中・再提案中のどちらもreviewできない。 |

## API形状との照合

### `GET /candidate-search-filters`

`rangePreferences[]`、`genreOptions[]`、filter取得状態は成果物に存在しない。よって `TDR-CS-04` の補助条件を操作できず、filter APIの `401` / `429` / `503` 境界も成果物から照合できない。

### `POST /candidate-proposals` request

`rangePreference`、`genreCodes[]`、`previousConceptKinds[]` はいずれも成果物に存在しない。特に `previousConceptKinds[]` の欠落により、再提案が「既出観点を避けて別の適格な観点を優先する」現在画面だけの文脈であることを表現できない。

### `CandidateProposalResponse`

- `concepts[]`: 2件で最大3件の制約内。各concept内に同じ合成candidateの重複はない。
- `conceptRef`: `id` へ写像したコメントはある（26行目）が、field名を用いたannotationは限定的である。
- `kind` / `title` / `rationale` / `candidates`: 合成modelには存在する。
- `providerCredit`: footerに表示されるが、契約済みcredit全文を一つのlinkにしていない（125〜127行目）。ブリーフが要求する「正確な文言をlinked creditとして示す」を満たさない。

### `Candidate`

| API field | source | visible UI | 判定 |
|---|---|---|---|
| `candidateRef` | `id`へ写像（14行目） | marker placeholder内に値を表示（90行目） | 不適合。current-response identityは表示してはならない。 |
| `name` | あり | あり（95行目） | 適合 |
| `genre` | あり | なし | 不適合 |
| `description` | nullableであり | あり、欠損時は中立表示（96行目） | 適合 |
| `businessHours` | nullableであり | あり、欠損時は中立表示（98行目） | 適合 |
| `regularHoliday` | nullableであり | なし | 不適合 |
| `totalSeats` | `string | null`（20行目） | あり（99行目） | 不適合。APIは `integer | null` であり、表示時にのみ「席」を付けるべきfieldである。 |
| `access` | nullableであり | なし | 不適合 |
| `location` | なし | markerもreview-only layout mappingもない | 不適合。数値座標fixtureは禁止だが、非地理的layout dataから本番 `location` への注記が必要。 |
| `providerPageUrl` | あり | linkあり（101行目） | 適合 |

## ドメイン・privacy境界との照合

### 適合している点

- live API call、persistence、local storageを持たない。
- 実座標、API key、provider response/ID/imageを置かない。
- 店舗detail linkは `https://example.invalid/` を使う。
- 実tileを取得せず、OpenStreetMap attribution treatmentを示す。
- 固定件数paging、追加表示、手動sort controlを持たない。

### 不適合または確認不能な点

1. **合成データの架空性が明確でない**: `和食 暖簾`、`Bistro 24`、`Grand Cafe`（40〜50行目）は実店舗と衝突しないと判別できず、ADR-0002/0003とブリーフが要求する「架空であることが明確なサンプル」を満たさない。
2. **禁止された距離例をfixtureへ埋め込む**: `駅より徒歩3分`（40行目）は、ADR-0003がrepositoryのdesign dataで禁じるdistance exampleであり、契約が表示を禁じる徒歩時間でもある。現在は `access` 自体が未表示だが、source data境界として不適合である。
3. **説明できない推測**: `広めの席間隔を確保できる`、`会話を重視する会に最適`（48行目）は、`totalSeats` その他の現在API fieldだけでは説明できない。空間の広さ・席間隔・用途への最適性を保証する表現で、ADR-0004のreference-only境界に反する。
4. **internal identityの露出**: 90行目の `Marker: {activeCandidateId}` は `candidateRef` 相当値をvisible UIへ出す。
5. **source annotation不足**: 主要状態はscenario IDだけを一部コメントするが、API field/error codeへの注記と `TDR-CS-03/04/07/08` の主要要素注記が不足する。

## 成果物形式との照合

- default exportのReact component本体は存在する。
- ただしファイルは1行目と132行目にMarkdown code fenceを含み、raw TSXではない。そのままではTypeScript sourceとしてparseできず、「rawで完全な実行可能ソースだけ」「無改変で配置・描画可能」という成果物指定に不適合である。
- 3行目には未使用importが複数あり、receiverのTypeScript設定によっては追加のcompile failure要因になる。ただしfenceだけで既にparse不能なため、designerはbuild可否を推測で確定しない。
- review-only switcher自体はproduct UIから視覚的に分離されている（114〜120行目）。
- `Required API additions: None required.` のblock commentは存在する（5〜7行目）。この判断は妥当である。今回の不一致を解くための新規backend APIは不要で、成果物が既存APIと契約を表現できていないことが原因である。

## Refinement / escape-path request

round-1 TSXをagentが修正・書き直すことは、meta/ADR-0020・0021の人間review前無改変原則に反するため行わない。次のどちらかを人間が選ぶまで、追加commissionを実行しない。

### 案A — external-AI refinement（推奨）

同じ承認済みデザインブリーフと本reconciliation reportをcritique inputとして、approved direct API routeでround 2を依頼する。成果物は同じexact output pathへ外部AI自身に完全置換させ、再び無改変でreconciliationする。

round 2の最低受け入れ条件:

1. markdown fenceなしのraw runnable TSX。
2. `TDR-CS-00`〜`TDR-CS-08`、loading、`403 REQUEST_REJECTED`、再提案前後をすべてreview可能にする。
3. 相対範囲・ジャンル・提案開始・最大3concept選択・card/marker相互強調・再提案による全体置換を操作可能にする。
4. 全card field、neutral null handling、full linked provider credit、OSM attributionを示す。
5. internal identity、数値座標/距離/徒歩時間、実在性が曖昧なsample、provider fieldから説明できない保証を除く。
6. 非地理的review-only marker layoutを `Candidate.location` へsource commentで対応付ける。
7. scenario ID、API field、problem codeのsource annotationを揃える。

### 案B — escape path

同じ外部modelでのrefinementを行わず、デザインブリーフ改訂または別の許可された外部tool/modelへ切り替える。model利用可否・費用・運用規約を伴うため、designerは独断で選択しない。

## Human screen review readiness

**Historical round-1 result: Not ready.** 中心体験の骨格である補助条件、提案開始、実map markers、双方向強調、再提案全体置換が欠落し、成果物形式もraw TSXではなかった。この結果を受け、人間が次のCodex escape pathを選択した。

## Codex escape path — current receiver

### 人間の判断と由来

- 2026-08-01: 同じexternal modelでのrefinementを行わず、Codex自身がDesigner契約と承認済みbriefに基づき作成する案を人間が選択した。
- 2026-08-01: 人間が画面の方向性を承認し、「有料アプリ感」が強い販促的なcatch copyを減らすよう指摘した。
- 2026-08-01: 人間が、補助条件と初回コンセプト選択を削除し、ログイン後すぐ候補と位置関係を表示するよう裁定した。別の切り口は再提案時のモーダルだけで選び、選択後に提案全体を置き換える。この判断はADR-0005とAPI v0.4へ反映した。
- 現在の `CandidateSearchPreview.tsx` は外部AI round-1成果物ではなく、Codex作成のreviewable artifactである。したがってround-1の行番号付き照合は履歴として残し、現成果物の判定には用いない。

### 現成果物の照合

| 境界 | 判定 | 現成果物 |
|---|---|---|
| `TDR-CS-00`〜`TDR-CS-08` と補足 `403` / loading | 適合 | product UIから分離したreview consoleで全状態を切り替えられる。未認証時は候補、条件、地図を表示しない。 |
| 初期提案 | 適合 | 補助条件、提案開始、常設コンセプト一覧を置かず、一つの初期提案の地図とカードを直ちに示す。ランチ必須はserver-sideの不変条件として、解除controlを置かない。 |
| 切り口選択と再提案 | 適合 | 現在のkindを除く最大3つの `reProposalOptions` をモーダルで理由つき表示する。選択後は再提案中を示し、選んだkindの一提案で前のカードと地図を完全置換する。 |
| 地図とカード | 適合 | 非地理的な合成位置図でmarker/cardを相互強調し、全候補を見渡せる。実装時の `Candidate.location` との境界をsource commentで示す。 |
| 店舗表示項目 | 適合 | name、genre、description、businessHours、regularHoliday、totalSeats、access、providerPageUrlと中立null表示を持つ。 |
| provider / map credit | 適合 | Hot Pepperの固定linked creditとOpenStreetMap attribution treatmentを示す。店舗linkは `example.invalid` のみ。 |
| privacy / repository | 適合 | 実地点、地名、座標、距離、実店舗、provider ID/response/image、key、永続化、live API/tile requestを持たない。 |
| 成果物形式 | 適合 | raw TSXのdefault exportを独立Vite receiverで型検査・buildできる。 |
| copy tone | 適合 | heroを「ランチ候補」という機能名と短い説明に縮め、販促tagline、英語catch copy、装飾heroを除いた。 |

### Human screen review readiness

**Ready for revised screen review; interaction direction approved.** ADR-0005のinteractionはchatで人間承認済みであり、現receiverは更新後の見た目を設計PRで再確認できる。Django本番実装、認証、実API、Leaflet/OSM通信の承認ではない。
