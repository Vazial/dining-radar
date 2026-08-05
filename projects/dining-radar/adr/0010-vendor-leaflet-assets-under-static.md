---
id: 0010
scope: project/toyama-dining-radar
status: 承認済み
date: 2026-08-04
approved_by: "本PRのマージをもって承認（ADR-0035 方式(i)、人間裁定 2026-08-04: Leafletは static/ にdistを同梱して自オリジンから配信する。現在の https://unpkg.com からの読み込みは廃する。却下: (npm＋ビルド段の追加)／(CDNのまま SRI だけ足す)）"
supersedes: []
superseded_by: null
relates_to: [P-01, P-02, TDR-CS-01, TDR-CS-02]
---

# ADR-0010: Leafletは`static/`にdistを同梱し自オリジンから配信する

> **承認者向けサマリ**: 現在の候補提案画面（`home.html`）はLeafletのJS/CSSを
> `https://unpkg.com` から都度取得している。この製品は非公開の検索基点・provider秘密・実データを
> browserに出さないことをADR-0002・0004・0008で繰り返し境界化してきたが、認証済み・セッション付きの
> 画面が毎回サードパーティCDNへ通信すること自体は、どのADRの脅威モデルにも入っていなかった。人間は
> Leafletのdistを `static/` に同梱し自オリジンから配信する案を採用し、npm＋ビルド段を追加する案と、
> CDNを維持しSRIだけ足す案を却下した。契約ファイルの変更は不要——本ADRはタイル提供者（OSM）の扱いを
> 変更せず、地図ライブラリ自体の配信元だけを変更する。

## 文脈

`src/dining_radar/web/templates/web/home.html` は次の2行でLeafletを読み込んでいる。

```html
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
```

この製品の`ARCHITECTURE.md`・`product-brief.md`・ADR-0002/0004/0008は、ブラウザが通信してよい相手を
慎重に境界化してきた——providerへは server からだけ、OSM標準タイルへは
`Referrer-Policy: strict-origin-when-cross-origin` で公開originだけを送る、非公開の検索基点は
一切出さない、等。しかし unpkg.com という**第三のオリジン**への通信は、これらのADRのどの決定にも
現れていない。認証済み・セッション付きの画面が毎回のロードでこのオリジンへ接続することは、次の2点で
この製品の既存の境界思想と整合しない。

1. **可用性**: unpkg.comが不調・遮断された場合、地図機能全体が失われる。この製品が既に持つ
   「タイル提供者を将来差し替えられる境界を保つ」（`product-brief.md`）という考え方は、地図タイルだけ
   でなく地図ライブラリ自体の配信元にも同様に適用できる。
2. **サプライチェーン**: 認証済みセッションを持つ画面へ、リポジトリ管理外の第三者が配信する
   実行可能スクリプトを都度読み込むことは、この製品がこれまで避けてきた種類の外部依存である。
   Referrer-Policyの検討はOSMタイル宛の通信にだけ及んでおり、unpkg.com宛の通信（Referer・
   User-Agent・IPの開示を含む）はどのADRの対象にもなっていない。

`web` module は既に自身のJS（`candidate.js`）を `static/` から配信しており、Djangoのstaticfiles機構
だけで完結している。ビルド段（bundler）は導入していない。

## 決定

### 1. Leafletのdist（JS・CSS・マーカーアイコン一式）を`static/`配下に同梱し、自オリジンから配信する

`home.html` は `https://unpkg.com` を参照せず、Djangoのstaticfiles機構（既存の `candidate.js` と同じ
経路）でLeafletのJS/CSS/アイコン画像を配信する。これにより、地図UIを表示するために認証済み画面が
接触する外部オリジンは、既にADR-0008が境界化しているOSM標準タイルサーバだけになる。

Leafletのライセンス（BSD-2-Clause）に従い、同梱したdistと同じ場所にライセンス表記を含める。

### 2. 却下した代替案とその理由

- **npm＋ビルド段の追加**: `web` moduleは「vanilla JS・no bundler」で実装されている
  （developerの実装選択）。単一の第三者ライブラリを自オリジン配信するためだけに、Node製ビルド
  ツールチェーンをDjangoプロジェクトへ新規導入するのは、解決したい問題（配信元の変更）に対して
  変更の footprint が過大である。distを直接同梱する方法は、既存の静的ファイル配信の仕組みを
  そのまま使え、新しいビルド依存を持ち込まない。
- **CDNのまま SRI（Subresource Integrity）だけ足す**: SRIは配信中の改ざん検知には有効だが、
  (a) 可用性問題（CDN障害時に地図が機能しなくなる）を解決せず、(b) 認証済み画面が毎回
  unpkg.comへ接続しReferer/User-Agent/IPを渡すという通信そのものは残る。この製品が慎重に扱って
  きた「ブラウザが誰と通信するか」という境界の観点では、SRIは改ざん耐性を上げるだけで接続自体を
  無くさない。

### 3. 契約への影響

`contracts/candidate-search-browser-interface.yaml`・`contracts/candidate-search-api.yaml`は、
地図タイル提供者（`data-map-tile-provider=openstreetmap-standard`）と帰属表示だけを規定しており、
Leafletライブラリ自体の配信元には言及していない。本ADRはタイル提供者の扱いを変更しないため、
**契約ファイルの変更は不要**である。

## 帰結

- `static/` にLeafletのdistとライセンス表記が加わる。`home.html` のLeaflet読み込みが自オリジン参照に
  変わる。実装（テンプレート修正・アセット配置）はdeveloper/orchestratorの作業であり、本ADRはその
  方針だけを定める。
- Leafletのバージョン更新は、npm auditのような自動検知が無いため、同梱dist差し替えという手動運用に
  なる。これは新しい運用負担だが、現時点でCVE監視の仕組みを追加する必要性は確認されていない
  （P-05: 摩擦が出てから対応する）。
- ARCHITECTURE.mdの「データと秘密の境界」節に、Leaflet本体を自オリジンから配信し外部CDNへ接続しない
  旨を追記する（本PRに同梱）。
