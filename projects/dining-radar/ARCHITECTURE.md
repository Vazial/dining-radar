# ARCHITECTURE.md — Toyama Dining Radar

ADR-0001/0002に従うfoundation設計である。候補提案の現在の利用者体験はADR-0005と
candidate-search契約へ投影する。HTTP endpoint、DB schema、具体的な依存は未決定である。

```text
[browser]
    |
[Django web] -> [authentication] -> [suggestions] -> [recommendation]
                            |
                            +-> [Hot Pepper adapter] -> [provider API]
```

## 候補提案の現在の投影

ADR-0005の候補提案は、同じモノリスの中で次のように流れる。これは責務とデータの流れを示す地図であり、
具体的なHTTP形状・型・実装方式は `contracts/candidate-search-api.yaml` が持つ。

```text
[authenticated browser]
    | screen opens / chooses a different lens
    v
[Django session + CSRF boundary]
    v
[candidate-proposal web boundary]
    v
[suggestions: one fresh proposal]
    +-> [recommendation: deterministic displayed lens]
    |        |
    |        +-> one proposal + next-lens labels
    v
[Hot Pepper adapter] -> [provider API]
    |
    +-> normalized candidate fields in the current response only

[browser current-screen memory]
    +-> one proposal's cards <-> shop-only map markers
    +-> re-proposal modal (next-lens labels only)
    +-> non-persistent shown-candidate comparison state
        -> lower repeated candidates in a replacement display only
```

`authentication` は管理者が作成・無効化する個別幹事 account と same-origin Django session を扱う。
候補提案 boundary は有効な session を前提とし、未認証または無効化済み account に候補・地図・切り口を返さない。
公開時の HTTPS、Secure/HttpOnly/SameSite cookie、CSRF、login throttle の要求は ADR-0006 と
`contracts/authentication.feature` / `contracts/authentication-api.md` が持つ。host、domain、email、SSO、
session expiry、具体的な管理 UI はこの設計図では決めない。

認証済み画面は最初の候補と店舗間の位置関係を直ちに表示する。範囲・ジャンルの補助条件を入力する
moduleやfilter taxonomyはこの流れに含まれない。別の切り口は、現在表示中の候補を追加せず、モーダルで
一つ選んだ後の新規proposalが置き換える。ブラウザへ渡る地図位置は候補店舗だけであり、検索基点、経路、
現在地、徒歩時間はこの流れのどこにも置かない。

## モジュール境界

| モジュール | 責務 | 禁止・境界 |
|---|---|---|
| `authentication` | 管理者作成の個別account、session、login/logout/password change、account有効性の保護境界 | 公開signup、メールreset、SSO、実account・session・secretをGitまたはbrowser出力へ置かない |
| `web` | 利用時の検索条件入力、候補表示、credit表示 | providerキー・実URL・provider固有形式を扱わない |
| `suggestions` | provider と recommendation pipeline を調停 | provider事実を保存・改変しない |
| `recommendation` | 正規化済み候補の適格性判定、順位付け、代替候補選択 | Django、HTTP、ORM、provider形式へ依存しない |
| `integrations/hotpepper` | server側通信、クエリキー送信、URL redaction、正規化 | 実レスポンスをfixture・cache・DBへ残さない |

## データと秘密の境界

この製品は訪問履歴・ブラックリスト・長期候補照合を実装しない。provider ID と HMAC 由来トークンは保存しない。方針を再検討するには、新たな人の意思決定、provider 規約の再確認、新規 ADR を必要とする。

正確な検索基点を browser、公開 URL、ログ、エラー、trace、Git へ出さないことは Must である。候補店舗と地図から地域をおおまかに推測できることの防止は Want であり、初期版では保証しない。

Leaflet/OSM の公開運用は `Referrer-Policy: strict-origin-when-cross-origin` とし、タイル提供者へ公開 origin だけを送る。provider 通信は HTTPS のみとする。

- 検索基点・探索範囲はruntimeの非公開設定であり、公開リポジトリやデプロイ既定値へ実在の名称・座標・距離を置かない。
- credentialはserverのruntime secretにだけ置く。provider仕様で必要なクエリパラメータはadapterからのみ送り、キー入りURLを観測可能な出力に残さない。
- session signing secret、CSRF secret、実account・password hash・login履歴はprovider credentialと同じく runtime/private store に閉じ、Git、browser、観測可能な出力に置かない。
- browser-facingの保護requestは同一originの有効なDjango sessionとCSRFを必要とする。外部公開ではHTTPSとSecure/HttpOnly/SameSite cookieを用い、credentialを伴う任意origin CORSまたはlocal-storage tokenを導入しない。
- 初期版はproviderレスポンスを保存・cacheしない。合成fixtureだけをコミットする。
- schema migrationはGitで版管理するが、実データを投入するdata migration、実fixture、DB dumpはGitへ置かない。
- provider事実は変更せず、アプリは候補の選択・順序・除外だけを行う。画面には必要なprovider creditを表示し、provider画像は使わない。
- provider ID と HMAC 由来トークンを private runtime DB に保存する選択肢は、この製品の方針に含めない。方針を再検討する場合だけ、新たな人の意思決定、provider 規約の再確認、新規 ADR を必要とする。

## 検証境界

- L1: `recommendation` と調停の純粋ロジックを合成データで検証する。
- L2: provider固有依存のadapter外流出、`web`からadapter/ORMへの直接アクセス、`recommendation`へのframework依存を検出する。
- L3: 合成fixtureでadapterの正規化・redactionを検証する。資格情報を用いるlive APIテストはしない。
- L3: TDR-AUTH-06 の deployment 向け cookie/CSRF/CORS/token 非使用は設定・security-boundary 検証で確認する。ローカル acceptance profile の HTTP は public HTTPS の代替ではなく、実 transport は deployment slice が確認する。
- L4: TDR-AUTH-01〜05・07 の利用者操作・観測は `contracts/authentication-browser-interface.yaml`、TDR-CS-00〜08 は `contracts/candidate-search-browser-interface.yaml` の browser control surface と既存 browser-facing 境界だけを通す。公開境界だけでは作れない認証の Given、candidate の合成状態選択、security-boundary 観測、シナリオ間の初期化は、acceptance-test 構成にだけ存在する `contracts/test-support-api.yaml` の機械可読 seam を使う。この seam は合成 account・session・login throttle state・閉じた candidate 状態と有効な acceptance 設定に限定し、実 account、非公開検索基点、provider data、secret、production 設定には触れない。
