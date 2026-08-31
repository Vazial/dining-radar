ADR-0001/0002に従うfoundation設計である。候補提案の現在の利用者体験はADR-0005・ADR-0023・ADR-0025と
candidate-search契約へ投影する。HTTP endpoint、DB schema、具体的な依存は未決定である。

```text
[browser]
    |
[Django web] -> [authentication] -> [suggestions] -> [recommendation]
                            |
                            +-> [Hot Pepper adapter] -> [provider API]
```

## 候補提案の現在の投影

ADR-0023の絞り込みモデルとADR-0025の検索基点・徒歩時間の開示は、同じモノリスの中で次のように流れる。
これは責務とデータの流れを示す地図であり、具体的なHTTP形状・型・実装方式は
`contracts/candidate-search-api.yaml` が持つ。

```text
[authenticated browser]
    | screen opens / applies a pending filter change / requests the same
    | applied filters again ("search again")
    v
[Django session + CSRF boundary]
    v
[candidate-proposal web boundary]
    v
[suggestions: one fresh proposal]
    +-> [recommendation: fetch the full normalized population (paging until
    |    results_available is exhausted, adr/0023 decision 3), apply soft
    |    filters (genre, izakaya/bar inclusion, non-smoking, card payment,
    |    budget tier) and the hard walking-time-max filter to the whole
    |    population, fixed nearest-first ordering with unconfirmed-last
    |    grouping, near-pool randomized selection up to 5, walking-time
    |    computation (adr/0023, adr/0025)]
    |        |
    |        +-> up to 5 candidates + identity-free populationAttributes
    |            (adr/0022) + searchOrigin coordinates (adr/0025)
    v
[Hot Pepper adapter] -> [provider API]
    |
    +-> normalized candidate fields for the current response only

[browser current-screen memory]
    +-> up to 5 proposal cards (incl. walkingTimeMinutes, adr/0025) <->
    |   candidate map markers, plus one search-origin marker and
    |   walking-time-band rings (adr/0025 decision 1)
    +-> always-visible filter panel (applied/pending split; a pending edit
    |   issues no request until "apply" commits it as one fresh proposal;
    |   "revert" restores applied without any public operation) and a
    |   "search again" control that repeats the applied filters
    |   (adr/0023 decision 8, adr/0025 decision 3)
    +-> populationAttributes used only to compute a local pending-match
        count preview (adr/0022); never rendered as shop identity, never
        stored
```

`authentication` は管理者が作成・無効化する個別幹事 account と same-origin Django session を扱う。
候補提案 boundary は有効な session を前提とし、未認証または無効化済み account に候補・地図・絞り込み
パネルを返さない。公開時の HTTPS、Secure/HttpOnly/SameSite cookie、CSRF、login throttle の要求は
ADR-0006 と `contracts/authentication.feature` / `contracts/authentication-api.md` が持つ。host、
domain、email、SSO、session expiry、具体的な管理 UI はこの設計図では決めない。

認証済み画面は、絞り込みなしの初期候補（既定では、ランチ営業の実施が確認しづらいジャンル（居酒屋・
バー等）を除いた母集団からの最大5件）と、検索基点マーカー・徒歩圏の同心リング・候補店舗マーカーを
示す地図を直ちに表示する（adr/0025決定1）。カードとマーカーは相互に強調して比較する。

常設の絞り込みパネル（ジャンル・居酒屋バーを含めるか・禁煙・カード払い・予算感・徒歩の上限の6項目、
adr/0015・adr/0023・adr/0025決定3）が、範囲入力や切り口選択に代わる補助条件の唯一の経路である。
パネルは `applied`（表示中の候補を作った条件）と `pending`（編集中の条件）を分け、コントロールの変更は
`pending` だけを動かし検索を行わない。「適用」が保留中の条件で新しい候補を1件のfresh proposalとして
依頼し、「取り消し」は保留中の条件を `applied` へ戻すだけで公開操作を行わない。「もう一度探す」は
`applied` のまま同じ抽出をやり直すだけの経路であり、独自の順位付け基準を持たない（adr/0023決定4・8）。

切り口（`ConceptKind`）と再提案モーダルは廃止した（ADR-0023）——生き残っていた4切り口はいずれも
「絞り込み」か「並べ替え」に分解できることが実装コードとの照合で確認され、統一名で両者を隠す抽象を
維持する理由がなかった。

各絞り込みの候補は、取得・正規化した母集団全体への絞り込み・並べ替え適用後、近い方から上位N件
（非拘束の推奨値20）の抽出プールから無作為抽出した最大5件である（ADR-0023決定4）。表示順は常に
「確認済み一致→情報なし、各段は距離昇順」の1種類だけであり、選択肢は設けない。絞り込み条件のうち
ジャンル・居酒屋バーを含めるか・禁煙・カード払い・予算感はソフトフィルタ（確認できた非該当だけを除き、
情報なしの候補は除外せず後方へ回す）、徒歩の上限だけはハードフィルタである——`walkingTimeMinutes`に
「情報なし」が存在しないため、確認できない値を保持するというソフトフィルタの前提がそもそも当たらない
（ADR-0023決定2、ADR-0025決定3）。ランチ営業の実施が確認しづらいジャンルは既定の母集団から除き、
それを含める絞り込みを幹事が選んだときだけ母集団に含める。除外の結果すべての絞り込みで候補が0件に
なる場合は、既定除外だけを緩めて再計算する——幹事が明示的に選んだ他の絞り込みは緩めない
（ADR-0023決定6）。

保留中の絞り込みが何件に効くかをブラウザ側で計算できるよう、応答は識別子を持たない母集団属性表
`populationAttributes`（ジャンル・禁煙区分・カード払い可否・予算感・徒歩時間帯・既定除外か否かの
5属性。店舗名、候補参照値、provider ID、provider page URL、店舗座標、検索地点、検索範囲、距離、
近い順・provider順その他の順位情報、経路、現在地、画像、説明、営業時間、席数、または個別店舗を
識別・追跡できる属性は含まない）を運ぶ（ADR-0022）。行の順序は公開意味を持たず、ブラウザは行の位置を
候補・地図marker・距離・順位と結び付けてはならない。

既表示候補の再提案時降格（ADR-0008決定2、ADR-0017）は廃止した——近傍プールからの無作為抽出そのものが
表示の多様性を担う（ADR-0023決定5）。サーバは既表示候補の一覧を送受信・保存しない。

検索基点は認証済み画面のマーカーとして表示してよく、そこを中心とする徒歩圏の同心リングを描いてよい
（ADR-0025決定1・7。ADR-0004決定2、ADR-0008決定4のうち browser への非開示だけを撤回した）。候補
カードは徒歩時間の目安（`walkingTimeMinutes`、分単位の整数）を表示してよい——推定であり実測経路では
ないと分かる文言を伴うことがMustである（ADR-0025決定2）。徒歩経路と現在地の描画は行わない
（ADR-0025決定6）。

候補提案画面はサーバから空のマウント点だけを受け取り、候補カード・地図・絞り込みパネル・エラー表示は
すべてクライアント側JavaScriptが生成する（ADR-0009）。この画面のL4検証は、サーバ応答時点のHTMLではなく
実行後のDOMを対象にするため、JS実行可能なブラウザ自動化を用いる。TDR-AUTHの画面(プレーンHTTP＋HTML
パースで検証可能)とはこの点で執行モデルが異なる。

## モジュール境界

| モジュール | 責務 | 禁止・境界 |
|---|---|---|
| `authentication` | 管理者作成の個別account、session、login/logout/password change、account有効性の保護境界 | 公開signup、メールreset、SSO、実account・session・secretをGitまたはbrowser出力へ置かない |
| `web` | 利用時の絞り込み条件入力、候補表示、credit表示、候補の表示専用派生値（総席数の目安`capacityTier`・予算感の目安`dinnerBudgetTier`等）の算出（adr/0019）、識別子を持たない母集団属性`populationAttributes`の応答への同梱（adr/0022） | providerキー・実URL・provider固有形式を扱わない。店舗座標・徒歩経路・現在地・設定探索範囲の値を出さない |
| `gathering` | 会・候補日・参加者リンク・出欠回答のORM永続化と業務ロジック（局面遷移・denominator算出・リンクの有効期限/失効/レート制限、`gathering-scheduling-api.yaml`、adr/0035〜0037）。この製品が初めて持つ永続データ（ADR-0034決定6）で、`web`と異なりDjango ORMへ直接依存してよい | provider由来の店舗属性（店名・ジャンル・座標・営業情報等）を一切永続化しない（店の情報は`suggestions`/`recommendation`から毎回引き直す）。`integrations`へは`web`と同様`suggestions`経由でのみ到達する |
| `suggestions` | provider と recommendation pipeline を調停する | provider事実を保存・改変しない |
| `recommendation` | 正規化済み候補への絞り込み（ジャンル・居酒屋バーを含める・禁煙・カード払い・予算感はソフトフィルタ、徒歩の上限はハードフィルタ）の適用、固定の近い順並べ替え（確認済み一致→情報なし、各段は距離昇順）、近傍プールからの無作為抽出、検索基点からの徒歩時間の算出（adr/0023、adr/0025）。`capacity_tier`（総席数の目安、adr/0019）と、会スコープ向けの曜日ベース定休日照合`is_confirmed_closed_on_weekday`/`open_shop_population`（adr/0035決定6・adr/0037決定3）も、`web`と`gathering`の双方が同じ閾値・判定を共有するためここに置く | Django、HTTP、ORM、provider形式へ依存しない |
| `integrations/hotpepper` | server側通信、クエリキー送信、URL redaction、取得段階の切り捨て防止（`results_available`が`results_returned`を上回る場合のページング。adr/0023決定3）、正規化（`genre`・`non_smoking`・`card`・`budget.average`等の生フィールドをこのアプリの内部表現へ変換する。adr/0019） | 実レスポンスをfixture・cache・DBへ残さない |

## データと秘密の境界

この製品は訪問履歴・ブラックリスト・長期候補照合を実装しない。provider ID と HMAC 由来トークンは保存しない。方針を再検討するには、新たな人の意思決定、provider 規約の再確認、新規 ADR を必要とする。

検索基点は認証済み browser へ開示してよい——地図上のマーカーとして表示し、そこを中心とする徒歩圏の同心リングを描いてよい（ADR-0025決定1・7。ADR-0004決定2、ADR-0008決定4のうち browser への非開示だけを撤回した）。候補ごとの徒歩時間の目安（`walkingTimeMinutes`）も表示してよい（ADR-0025決定2、値は推定であり実測経路ではないと分かる文言を伴うことがMust）。ただし次は無変更のまま維持する: 検索基点の実座標・既定探索距離の値は環境変数などのruntime非公開設定に置き、Gitには一切置かない（ADR-0002、ADR-0025決定4）。公開URL・ログ・エラー・trace・Gitへの非開示は維持する（ADR-0025決定7）。徒歩**経路**と利用者本人の現在地の描画は行わない（ADR-0025決定6）。設定探索範囲そのものの値はAPI応答・DOM・公開URL・ログ・traceのどこにも出さない——同心リングの本数・半径の選び方から間接的に推測されうることは許容するが、これは推測可能性の許容であって値そのものの露出ではない（ADR-0025決定9）。

保留中の絞り込みが何件に効くかをブラウザ側で計算できるよう、応答は識別子を持たない母集団属性表`populationAttributes`（ジャンル・禁煙区分・カード払い可否・予算感・徒歩時間帯・既定除外か否かの5属性）を運ぶ。店舗名、候補参照値、provider ID、provider page URL、店舗座標、検索地点、検索範囲、距離、順位情報、経路、現在地、画像、説明、営業時間、席数、または個別店舗を識別・追跡できる属性は含まない。行の順序は公開意味を持たず、候補・地図marker・距離・順位と結び付けてはならない（ADR-0022）。

`previouslyShownProviderPageUrls`のような既表示候補の一覧送受信は現在この製品に存在しない（ADR-0023決定5がADR-0008決定2・ADR-0017の再表示降格を廃止した）。

`card`（カード払い可否）の注意表示は、確認済みの事実（クレジットカード利用不可）だけを述べ、「現金のみ」等の未確認の支払方法を主張しないことをMustとする（adr/0019決定5）。`dinnerBudgetTier`（予算感の目安）はディナー予算由来の粗い区分であり、ランチ価格を推論・断定しないことをMustとする——この開示はカードごとに繰り返さず、展開中の絞り込みパネル内の一箇所にだけ置く（adr/0019決定8、adr/0023決定10による適用単位の変更。カード・絞り込み選択肢の可視ラベルは低・中・高の段階語のみを示し、金額・円レンジ・段階から金額への対応は表示しない）。

Leaflet/OSM の公開運用は `Referrer-Policy: strict-origin-when-cross-origin` とし、タイル提供者へ公開 origin だけを送る（基点は渡さない、adr/0025決定5）。provider 通信は HTTPS のみとする。Leaflet 本体（JS/CSS/マーカーアイコン）は `static/` に同梱し自オリジンから配信する（ADR-0010）。認証済み画面が地図UIのために接触する外部オリジンは OSM 標準タイルサーバだけであり、第三者CDNへは接続しない。

- credentialはserverのruntime secretにだけ置く。provider仕様で必要なクエリパラメータはadapterからのみ送り、キー入りURLを観測可能な出力に残さない。
- session signing secret、CSRF secret、実account・password hash・login履歴はprovider credentialと同じく runtime/private store に閉じ、Git、browser、観測可能な出力に置かない。
- browser-facingの保護requestは同一originの有効なDjango sessionとCSRFを必要とする。外部公開ではHTTPSとSecure/HttpOnly/SameSite cookieを用い、credentialを伴う任意origin CORSまたはlocal-storage tokenを導入しない。
- 初期版はproviderレスポンスを保存・cacheしない。合成fixtureだけをコミットする。
- schema migrationはGitで版管理するが、実データを投入するdata migration、実fixture、DB dumpはGitへ置かない。
- provider事実は変更せず、アプリは候補の選択・順序・除外だけを行う。画面には必要なprovider creditを表示し、provider画像は使わない。
- provider ID と HMAC 由来トークンを private runtime DB に保存する選択肢は、この製品の方針に含めない。方針を再検討する場合だけ、新たな人の意思決定、provider 規約の再確認、新規 ADR を必要とする。

## 検証境界

- L1: `recommendation` と調停の純粋ロジックを合成データで検証する。
- L1: `web`が配信するクライアント側JavaScript（`candidate.js`等）は、jsdom等の合成DOM実装上で動く
  JS単体テスト・lintで検証する（ADR-0014）。カバレッジ・mutationの数値基準はPython側と同じ床
  （branch coverage 90%・mutation score 80%）を用いる。ただし実ブラウザのレイアウト・タイミングに
  構造的に依存し合成DOMでは原理的に再現できない範囲（例: Leafletのマーカー生成タイミング）は、
  このゲートの対象から名指しで除外してよく、その範囲は引き続きL4（次項）とL5（実機測定）が検証する。
  このテスト専用のNode/npmプロジェクトは出荷される`candidate.js`のビルド・バンドルとは無関係であり、
  画面設計レビュー用の受け皿（`ADR-0003`が定めていたが`ADR-0028`が廃止した`design-preview/`。現在の
  画面設計の成果物は`design/wireframes/`が持つ）とも同居しない。
- L2: provider固有依存のadapter外流出、`web`からadapter/ORMへの直接アクセス、`recommendation`へのframework依存を検出する。
- L3: 合成fixtureでadapterの正規化・redactionを検証する。資格情報を用いるlive APIテストはしない。
- L3: TDR-AUTH-06 の deployment 向け cookie/CSRF/CORS/token 非使用は設定・security-boundary 検証で確認する。ローカル acceptance profile の HTTP は public HTTPS の代替ではなく、実 transport は deployment slice が確認する。
- L4: TDR-AUTH-01〜05・07 の利用者操作・観測は `contracts/authentication-browser-interface.yaml`、TDR-CS-00〜16 は `contracts/candidate-search-browser-interface.yaml` の browser control surface と既存 browser-facing 境界だけを通す。公開境界だけでは作れない認証の Given、candidate の合成状態選択、security-boundary 観測、シナリオ間の初期化は、acceptance-test 構成にだけ存在する `contracts/test-support-api.yaml` の機械可読 seam を使う。この seam は合成 account・session・login throttle state・閉じた candidate 状態と有効な acceptance 設定に限定し、実 account、非公開の検索基点実座標・設定探索範囲の値、provider data、secret、production 設定には触れない——検索基点の座標そのもの（`searchOrigin`）と候補ごとの徒歩時間（`walkingTimeMinutes`）は ADR-0025 が公開APIとDOMの両方で開示してよいと定めた値であり、この非開示の対象外である。TDR-AUTHの画面はサーバ応答時点のHTMLで観測できるが、TDR-CSの候補提案画面はクライアント側JavaScriptが描画するため、TDR-CSのL4はJS実行可能なブラウザ自動化を用いて実行後のDOMに対して行う（ADR-0009）。絞り込みの`applied`/`pending`分離、保留中の絞り込みが何件に効くかの予告（`populationAttributes`から算出、ADR-0022）、ジャンル選択肢の折り畳み、検索基点マーカー・徒歩圏の同心リングの表示専用性（活性化しても状態を変えない）、徒歩の上限フィルタは、いずれも`candidate-search-browser-interface.yaml`が機械観測可能な形で定める。
