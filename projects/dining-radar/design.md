# design.md — Toyama Dining Radar 設計骨子

> **承認者向けサマリ**: 非公開のruntime検索条件から店舗候補と代替候補を得るDjangoモノリスの設計骨格である。外部provider連携、候補の除外・順位付け、利用履歴を分離し、公開Gitにはschema migrationと合成fixtureだけを置く。実データの長期保存はprovider規約を確認できた場合に限る。

## スコープ

このfoundationは、非公開のruntime検索条件で外部候補を探し、利用済み・ブラックリストを除外して候補と代替候補を示すための責務分割だけを定める。画面、endpoint、DB schema、API接続、認証情報、実データは定めない。候補提案の現在の画面・APIの振る舞いは、ADR-0005とcandidate-search契約が定める。

## 処理の流れ

```text
runtime検索条件
  -> Hot Pepper adapter
  -> provider形式を内部候補へ正規化
  -> 利用済み・ブラックリスト除外
  -> 順位付け
  -> 候補と代替候補の提示（必要なcreditを併記）
```

候補の複数人利用可否や予約可否は、providerが返す参考情報であり保証しない。providerの店舗事実は変更せず、アプリ側は選択・除外・順序付けのみを行う。

## 候補提案の画面投影

```text
サインイン済みの幹事が候補提案画面を開く
  -> 一つの初期切り口による候補カードと店舗だけの地図を表示
  -> カードとマーカーを相互に強調して比較
  -> 「別の切り口で再提案」を選ぶ
  -> 最大3つの次の切り口をモーダルで表示
  -> 一つを選ぶ
  -> 新しい候補提案でカード・地図全体を置き換える
```

初期表示では検索範囲・ジャンルなどの補助条件やコンセプト選択を置かない。切り口の選択は再提案時だけであり、候補を追加表示しない。地図には候補店舗だけを出し、検索基点・経路・現在地・徒歩時間を出さない。詳細な受け入れ状態とbrowser-facing APIは `contracts/candidate-search.feature` と `contracts/candidate-search-api.yaml` を参照する。

## 非公開データの扱い

| データ | 置き場 | 公開リポジトリに置かないもの |
|---|---|---|
| 検索基点・探索範囲 | runtime非公開設定 | 実在の地名、座標、距離、既定値 |
| API credential | server runtime secret | 値、キー入りURL、ログ、エラー、トレース |
| providerレスポンス | request中だけ | raw response、実店舗ID、店舗情報、画像、dump、実fixture |
| schema migration | Git | 実データを投入するdata migration、実fixture、DB dump |
| 利用済み・ブラックリスト | Git外のprivate runtime DB | Gitへの実データ・dump。provider IDまたはHMACは規約確認後にだけ選ぶ |

Hot Pepper APIキーはprovider指定のクエリパラメータとしてserverから送る。adapterはURLをredactし、clientや観測可能な出力にキーを出さない。初期版はproviderレスポンスをcache・永続化しない。

長期照合は、provider規約を確認した後にprivate runtime DBのprovider IDを用いるか、`HMAC-SHA-256(server_secret, provider_shop_id)` を用いるかを選ぶ。HMACは擬似化に過ぎず、provider規約上の保存を当然に許可するものではない。provider確認前は、長期の利用済み・ブラックリスト保存を公開運用しない。

## provider境界

- Hot Pepperは唯一の初期providerであり、スクレイピングとfallbackは使わない。
- providerのcreditを表示する。provider画像は初期版で使わない。
- provider規約を、公開運用前、cache・画像・永続化を追加する前に再確認する。
- network、資格情報、rate limit、provider停止は外部境界の失敗として扱い、合成fixtureによるテストを基本とする。

## 後続スライスへの条件

- 実装前に、provider IDまたはHMACを用いる長期照合をproviderへ確認するか、保存なしの代替へ決める。
- 実装時に、必要なcreditの正確な表示文言・リンクを公式ガイドラインから確定する。
- providerが安全な通信経路をどう公開仕様化しているかを実装時に確認する。
