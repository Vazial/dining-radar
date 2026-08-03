# design.md — Toyama Dining Radar 設計骨子

> **承認者向けサマリ**: 非公開のruntime検索条件から店舗候補と代替候補を得るDjangoモノリスの設計骨格である。外部provider連携と候補の適格性判定・順位付けを分離し、公開Gitにはschema migrationと合成fixtureだけを置く。この製品は実データの長期保存、利用履歴、ブラックリストを持たない。

## スコープ

このfoundationは、非公開のruntime検索条件で外部候補を探し、候補と代替候補を示すための責務分割だけを定める。この製品は利用済み・ブラックリストを実装せず、同じ画面で既に表示した候補を再提案時に二次的に順位低下させる。画面、endpoint、DB schema、API接続、認証情報、実データは定めない。候補提案の現在の画面・APIの振る舞いは、ADR-0005とcandidate-search契約が定める。

候補提案は、管理者が作成した有効な個別幹事 account の same-origin Django session だけに開く。公開signup、
メールreset、SSOは初期スコープにない。認証・公開運用の状態と設定境界は ADR-0006、
`contracts/authentication.feature`、`contracts/authentication-api.md` が定める。ここでは認証画面、
管理画面、host、domain、email、session expiryの具体を定めない。

## 処理の流れ

```text
runtime検索条件
  -> Hot Pepper adapter
  -> provider形式を内部候補へ正規化
  -> 順位付け
  -> 同じ画面で既に表示した候補を再提案時に二次的に順位低下
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
  -> 同じ画面で既に表示した候補は未表示候補より後ろに表示する
```

初期表示では検索範囲・ジャンルなどの補助条件やコンセプト選択を置かない。切り口の選択は再提案時だけであり、候補を追加表示しない。同じ画面では、既表示候補を除外せず未表示候補より後ろへ置く。この比較状態はブラウザ内だけで、更新またはサインアウトで消える。地図には候補店舗だけを出し、検索基点・経路・現在地・徒歩時間を出さない。詳細な受け入れ状態とbrowser-facing APIは `contracts/candidate-search.feature` と `contracts/candidate-search-api.yaml` を参照する。

## 非公開データの扱い

| データ | 置き場 | 公開リポジトリに置かないもの |
|---|---|---|
| 検索基点・探索範囲 | runtime非公開設定 | 実在の地名、座標、距離、既定値 |
| API credential | server runtime secret | 値、キー入りURL、ログ、エラー、トレース |
| providerレスポンス | request中だけ | raw response、実店舗ID、店舗情報、画像、dump、実fixture |
| schema migration | Git | 実データを投入するdata migration、実fixture、DB dump |
| 利用済み・ブラックリスト | この製品では実装しない | provider ID、HMAC由来トークン、候補履歴、実店舗データの保存 |

Hot Pepper APIキーはprovider指定のクエリパラメータとしてserverから送る。adapterはURLをredactし、clientや観測可能な出力にキーを出さない。初期版はproviderレスポンスをcache・永続化しない。

この製品では長期照合を行わない。再提案時だけ、ブラウザが同じ画面で以前に表示した `providerPageUrl` と今回の候補を比較し、既表示候補を未表示候補より後ろに置く。比較状態はserverへ送らず、storage、cookie、URL、ログへ書かず、更新またはサインアウトで破棄する。利用済み・ブラックリストを再検討する場合は、新たな人の意思決定、provider規約の再確認、新規ADRで判断する。

## provider境界

- Hot Pepperは唯一の初期providerであり、スクレイピングとfallbackは使わない。
- providerのcreditを表示する。provider画像は初期版で使わない。
- provider規約を、公開運用前、cache・画像・永続化を追加する前に再確認する。
- network、資格情報、rate limit、provider停止は外部境界の失敗として扱い、合成fixtureによるテストを基本とする。

## 後続スライスへの条件

- 実装前に、表示済み候補の画面内だけの順位低下が候補履歴やprovider-response cacheを作らないことを確認する。
- 実装時に、必要なcreditの正確な表示文言・リンクを公式ガイドラインから確定する。
- providerが安全な通信経路をどう公開仕様化しているかを実装時に確認する。
