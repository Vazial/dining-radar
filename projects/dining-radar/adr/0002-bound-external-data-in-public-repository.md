---
id: 0002
scope: project/dining-radar
status: 承認済み
date: 2026-07-30
approved_by: "本PRのマージをもって承認（人間合意 2026-07-30: public repositoryでは実データ・秘密・生活圏情報を扱わない）"
supersedes: []
superseded_by: null
relates_to: [P-01, P-02, P-03, P-08]
---

# ADR-0002: 外部店舗データと非公開設定を公開リポジトリから分離する

> **承認者向けサマリ**: 公開リポジトリにはAPIキー、実店舗データ、生活圏を示す検索条件、実データのfixture・migration・dumpを置かない。APIキーはserver側だけで扱い、初期版はproviderレスポンスを保存・cacheしない。長期照合はprovider規約の確認後にprivate runtime DBでのみ行い、確認できなければ保存しない。

## 文脈

Hot Pepperグルメ WebサービスのAPIを候補取得に用いる。公開ソース、実行環境、provider規約への適合を混同しない。providerはAPIキーを必須のクエリパラメータとして定め、credit表示を求める。公開リポジトリに実店舗データ、秘密、生活圏を残さないことも必要である。

## 決定

1. 公開リポジトリにはAPIキー、秘密値、実リクエストURL、実レスポンス、実店舗ID、店舗情報、provider画像、実データを投入するdata migration、実fixture、DB dumpを置かない。schema migrationはGitで版管理する。テストには合成fixtureを用いる。`.env.example` は変数名と安全な説明だけを置く。
2. 検索基点と探索範囲はruntime設定として利用者が与え、リポジトリ・設計例・既定値に実在の生活圏を示す地名、座標、距離を置かない。
3. APIキーはserverからproviderへ送るprovider指定のクエリパラメータだけで使う。キー入りURLをclient、ログ、エラー、トレース、監視へ出さず、adapterでredactionする。通信はproviderが対応する安全な経路を使い、対応状況は実装時に確認する。
4. 初期版は実APIレスポンスをcache・永続化しない。将来cacheを導入する場合はprovider規約を再確認し、少なくとも定められた更新・削除期限を守る。
5. 店舗名・住所・評価等のprovider事実を改変、再配布、アプリDBへ複製しない。アプリ独自の候補選択、除外、順序付けはprovider事実そのものを変更しない。画面にはproviderが指定するcreditを表示する。初期版ではprovider画像を表示しない。
6. 利用済み・ブラックリストの長期照合データはGit外のprivate runtime DBだけに保存する。provider IDを保存するか、`HMAC-SHA-256(server_secret, provider_shop_id)` のトークンで照合するかは、現行provider規約の確認後に選ぶ。server secretは実行環境だけに置く。HMACは擬似化であって匿名化や規約適合の保証ではないため、確認前は長期保存機能を公開運用しない。
7. 取得失敗、認証失敗、rate limit、provider停止はアプリ内で区別して扱う。スクレイピング、Webスクレイピングへのfallback、資格情報を必要とするlive APIテストは採用しない。

## 検討した代替案

- **APIキーをheaderに移す**: provider仕様と合わないため不採用。
- **実レスポンスをfixture・cache・DBに使う**: 公開リポジトリ境界とprovider規約の解釈リスクを増やすため、初期版では不採用。
- **単純ハッシュで店舗IDを保存する**: 候補集合との照合が可能であり、秘密鍵のない識別子になるため不採用。規約確認後の選択肢はprivate runtime DBのprovider IDまたは秘密鍵付きHMACである。
- **実在の検索基点を既定値にする**: 公開ソースから生活圏を推測可能にするため不採用。

## 帰結

- source codeを公開しても、実データ、秘密、生活圏の露出を避けられる。
- provider IDまたはHMACを用いる長期照合は、規約上の可否が未確定である。確認できない場合はsession限りの除外または長期保存なしに退避する。
- providerの規約・表示要件は変わり得るため、公開運用前とcache・画像・永続化導入時に公式文書を再確認する。
