# ARCHITECTURE.md — Toyama Dining Radar

ADR-0001/0002に従うfoundation設計である。HTTP endpoint、DB schema、具体的な依存は未決定である。

```text
[browser]
    |
[Django web] -> [suggestions] -> [recommendation]
                            |             |
                            |             +-> [records: private runtime data]
                            |
                            +-> [Hot Pepper adapter] -> [provider API]
```

## モジュール境界

| モジュール | 責務 | 禁止・境界 |
|---|---|---|
| `web` | 利用時の検索条件入力、候補表示、credit表示 | providerキー・実URL・provider固有形式を扱わない |
| `suggestions` | provider、records、pipelineを調停 | provider事実を保存・改変しない |
| `recommendation` | 正規化済み候補の除外、順位付け、代替候補選択 | Django、HTTP、ORM、provider形式へ依存しない |
| `integrations/hotpepper` | server側通信、クエリキー送信、URL redaction、正規化 | 実レスポンスをfixture・cache・DBへ残さない |
| `records` | Git外のprivate runtime DBにある利用済み・ブラックリスト | 実データのmigration・fixture・dumpをGitへ出さない。provider IDまたはHMACは規約確認後だけ選ぶ |

## データと秘密の境界

- 検索基点・探索範囲はruntimeの非公開設定であり、公開リポジトリやデプロイ既定値へ実在の名称・座標・距離を置かない。
- credentialはserverのruntime secretにだけ置く。provider仕様で必要なクエリパラメータはadapterからのみ送り、キー入りURLを観測可能な出力に残さない。
- 初期版はproviderレスポンスを保存・cacheしない。合成fixtureだけをコミットする。
- schema migrationはGitで版管理するが、実データを投入するdata migration、実fixture、DB dumpはGitへ置かない。
- provider事実は変更せず、アプリは候補の選択・順序・除外だけを行う。画面には必要なprovider creditを表示し、provider画像は使わない。
- provider IDとHMACトークンのどちらをprivate runtime DBに保存するかは、provider規約の確認後に選ぶ。HMACは可逆ではないが匿名化の保証ではない。確認前は長期保存機能を公開運用しない。

## 検証境界

- L1: `recommendation` と調停の純粋ロジックを合成データで検証する。
- L2: provider固有依存のadapter外流出、`web`からadapter/ORMへの直接アクセス、`recommendation`へのframework依存を検出する。
- L3: 合成fixtureでadapterの正規化・redactionを検証する。資格情報を用いるlive APIテストはしない。
- L4: foundation後の受け入れ契約で定める。
