# activeContext.md — Toyama Dining Radar

> P-11: このファイルは常に「現在」を表す。恒久的な決定はADR、承認済みの成果物はgitに置く。

## 現在

foundationの設計文書をレビュー中である。目的は、月例ランチ会の幹事が、利用時に設定する検索基点の徒歩圏で、複数人利用の参考情報を持つ店舗候補と代替候補を得ることである。候補数は固定しない。利用済みの店舗は通常除外し、ブラックリストは登録・解除できる。

初期providerはHot Pepperグルメ WebサービスのAPIであり、スクレイピングやそのfallbackは採用しない。connpassは別プロジェクトである。

## 確定した方針

- 検索基点と探索範囲は、利用時の非公開設定として扱う。公開リポジトリ、fixture、設計例、デプロイ既定値へ実在の生活圏を示す名称・座標・距離を置かない。
- APIキー、秘密値、実APIリクエストURL、provider由来の実レスポンス・実店舗ID・画像・店舗情報、実データを投入するdata migration、実fixture、DB dumpをリポジトリへ入れない。schema migrationはGitで版管理し、テストは合成fixtureだけを用いる。
- APIキーはprovider仕様に従い、serverからproviderへ送るクエリパラメータだけで利用する。ブラウザ、アプリの公開URL、ログ、エラー、トレースへキー入りURLを出さない。
- 初期版はproviderレスポンスをcache・永続化しない。将来cacheを導入する場合は、その時点のprovider規約を再確認し、少なくとも規約の更新・削除期限を守る。
- providerの店舗事実は改変・再配布しない。アプリケーション固有の処理は候補の選択、除外、順序付けに限る。必要なcreditを表示し、初期版ではprovider画像を使わない。
- 利用済み・ブラックリスト等の実データはGit外のprivate runtime DBにだけ置く。provider IDを保存するか、サーバー秘密鍵を用いるHMACトークンで照合するかは、現行provider規約の確認後に選ぶ。確認前は長期保存を導入しない。

## 次に行うこと

1. ADR-0001/0002、ARCHITECTURE、designのfoundationレビューを完了する。
2. provider由来IDをprivate runtime DBへ保存するか、HMACトークンで照合するかを、規約確認後に決める。確認できなければ保存なしにする。
3. foundation承認後、最初の実装スライスの受け入れ契約を起草する。

## 未確定

- 推薦順位の重み、評価・学習の方法。
- 複数人利用・予約可否の扱い。API情報は保証ではなく参考とする。
- provider IDまたはHMACトークンを含む長期照合データがprovider規約上許容されるか。
