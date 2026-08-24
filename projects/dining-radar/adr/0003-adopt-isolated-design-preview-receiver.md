---
id: 0003
scope: project/dining-radar
status: superseded
date: 2026-08-01
approved_by: "本PRのマージをもって承認（ADR-0035 方式(i)）"
supersedes: []
superseded_by: 0028
relates_to: [P-01, P-02, P-03, P-04, P-07, P-08, TDR-CS-00, TDR-CS-01, TDR-CS-02, TDR-CS-03, TDR-CS-04, TDR-CS-05, TDR-CS-06, TDR-CS-07, TDR-CS-08]
---

# ADR-0003: 候補提案画面のレビュー専用 design-preview receiver を隔離する

> **承認者向けサマリ**: 承認済み候補提案契約に基づく画面を、人間が実装前に確認できるよう、Django本体・外部通信・private runtime dataから隔離したTSX receiverで描画する。これは出荷アプリや独立SPAではなく、合成データだけを使うレビュー用の画面である。

## 文脈

PR #65で候補探索の初期契約がマージされ、その後の人間による画面確認をADR-0005とAPI v0.4へ反映した。
次の設計骨格合意では、幹事が初期候補を直ちにカードと地図で比較し、必要な時だけモーダルで別の
切り口を選び、再提案で前の応答を置き換える体験を、実装前に
確認可能にする必要がある。

この確認は実店舗、非公開の検索基点、provider応答、資格情報を必要としない。一方、レビュー用画面を
本番Djangoアプリまたはprovider clientとして扱うと、ADR-0002の公開リポジトリ／runtime境界と、
ADR-0005の非公開基点・地図通信の境界を誤って広げるおそれがある。

## 決定

### 1. レビュー専用 receiver

`projects/dining-radar/design-preview/` を、デザイン成果物を人間が確認するだけの
隔離されたreceiverとする。画面の成果物は
`src/screens/CandidateSearchPreview.tsx` のdefault exportである。receiverはReact、TypeScript、
Tailwind、shadcn/uiおよび利用可能なアイコンを使ってよい。

receiverは、Djangoの本番アプリ、独立して出荷するSPA、provider client、private runtime dataの保管場所、
または認証実装ではない。本番の配信ルート・ビルドへ含めず、本番コードからimportしない。具体的な
entry、build設定、import境界およびその検証はdeveloperが決めて実装する。これはADR-0022が定める
design-preview隔離原則の、このプロジェクトでの適用である。

### 2. 合成表示と通信禁止

receiverは画面内の合成表示データとレビュー用の一時状態だけを用いる。実店舗、provider応答・ID・画像、
資格情報、検索基点、実在の地名、座標、数値距離、キー入りURL、永続化データを置かない。候補の位置関係は、
座標値を持たない合成の地図表現で示してよい。

network request、provider call、Django API call、Leaflet/OpenStreetMapタイル取得、ブラウザ位置情報、
local storage、cache、永続化を禁止する。実際のLeaflet/OSM通信、認証済みAPI、CSRF、providerページへの
接続は実装スライスで扱う。

候補カードの合成「詳細」リンクには `https://example.invalid/` 配下だけを用いる。例外として、承認済み
API契約が必須とするHot Pepper creditの固定文言と固定リンク
`Powered by ホットペッパーグルメ Webサービス` → `http://webservice.recruit.co.jp/` は、providerデータや
実店舗URLではなく表示義務の契約リテラルとしてそのまま表示してよい。

### 3. 契約との照合境界

候補提案の受け入れ契約とAPI契約が、画面の振る舞いと表示可能なデータのSSOTである。このADRは
切り口数、APIフィールド、状態遷移を新たに決めない。receiverの設計は、少なくともTDR-CS-00〜08の
通常・未認証・空・安全なエラー・rate-limit状態、初期候補の即時表示、再提案モーダルでの切り口選択、
カード／マーカーの相互強調、前の応答を置き換える再提案を、合成状態としてレビュー可能にしなければならない。

レビュー状態を切り替える仕組みは、プロダクト操作と視覚的・意味的に分離する。それは本番の機能や
追加APIを提案するものではない。設計成果物は、配置前に現行契約とreconcileし、実装スライスの前に
再度照合する。

### 4. Runtime別のデザイン作成経路

同じDesigner契約を共有しつつ、ClaudeではDesignerがGeminiへデザインを依頼し、CodexではDesigner契約、
承認済みbrief、契約を読んだCodex自身がデザインを作成する。外部AIのround 1が契約を満たさなかったため、
2026-08-01に人間がCodex自身によるescape pathを選択した。

作成経路にかかわらず、成果物は同じreceiverへ配置し、同じ契約・privacy境界・reconciliation・人間の画面
レビューを通す。このruntime差は画面の要件や承認基準を変えない。共有 `meta/**` の恒久的なrole配線は、
Claudeとの並行作業を調整した別スライスで扱う。

## 検討した代替案

- **Django本体へ仮画面を入れる**: 認証、provider通信、出荷経路との混同を招き、実装承認前のレビュー境界を
  失うため不採用。
- **実APIとLeaflet/OSMをレビュー時から接続する**: private originと外部通信を必要とし、合成データだけで
  確認できる設計レビューの目的を超えるため不採用。
- **静的なスクリーンショットだけでレビューする**: 状態、再提案モーダル、カードとマーカーの相互作用、
  再提案の置換を確認できないため不採用。

## 帰結

- 旧来の固定5件追加表示を前提とするデザインブリーフとプレビューは、承認済み契約に沿うレビュー成果物へ
  置き換える。
- receiverの型検査・ビルド可能性と、契約／プライバシー境界との照合を設計PRで確認する。通常の受け入れ
  テスト、実API通信、認証、provider規約の実運用確認はこのスライスに含めない。
- Codexのデザイン作成経路では、外部AI成果物の無改変原則ではなく、Codexが作成したsourceを通常の
  reviewable artifactとして扱う。外部AI成果物を使う場合の証跡・無改変原則は引き続きその経路だけに適用する。
- 本ADRはADR-0035方式(i)で記録する。この設計PRをマージすることが、このreceiver境界への人間承認となる。

---

**2026-08-24 追記（superseded）**: 本ADRの決定1・2は`ADR-0028`が置き換えた——`design-preview`受け皿は
使われておらず（CIが一度も検査しない、`meta/adr/0050`が外部AI経路を全廃してから更新も無い）、人間が
2026-08-24にこれを廃止すると選んだ。決定3・4は、その中身がすでに全プロジェクト共通の designer 役割
契約（`meta/adr/0050`）へ移っており、プロジェクト固有に引き継ぐものが無いため`ADR-0028`は継承しない。
詳細は`ADR-0028`を参照。本文は編集しない（P-06）。
