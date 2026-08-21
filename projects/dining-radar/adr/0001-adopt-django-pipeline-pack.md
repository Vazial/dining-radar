---
id: 0001
scope: project/dining-radar
status: 承認済み
date: 2026-07-30
approved_by: "本PRのマージをもって承認（人間合意 2026-07-30: Django中心のPython構成でfoundationを起草する）"
supersedes: []
superseded_by: null
relates_to: [P-02, P-03, P-09]
---

# ADR-0001: パイプラインパックをDjangoモノリスとして採用する

> **承認者向けサマリ**: Djangoの単一アプリケーションを採用し、候補取得から除外・順位付け・代替提示までを段階的なpipelineとして分離する。外部API連携、推薦処理、利用履歴をモジュール境界で分け、実データはGit外で扱う。独立SPA、サービス分割、全面的なDDDは初期スコープに含めない。

## 文脈

本アプリは、利用時に与えられる非公開の検索基点・探索範囲から外部候補を取得し、利用済み・ブラックリストを除外して順位付けし、必要なら代替候補を出す。複雑な状態遷移はまだ少なく、主要価値は外部候補の正規化と段階的な変換である。

## 決定

Python + Djangoの単一アプリケーションにパイプラインパックを採用する。

1. DjangoはHTTP/Web入出力、設定、アプリケーション所有データの永続化を担う。schema migrationはGitで版管理し、実データを投入するdata migrationはGitへ入れない。独立SPA、別API、workerは実測された必要性まで導入しない。
2. `suggestions` は、外部検索、正規化、適格性判定、利用済み・ブラックリスト除外、順位付け、追加候補選択を調停する。
3. `recommendation` は正規化済み候補の除外・順位付けだけを担う純粋なPython pipelineとし、Django、HTTP、ORM、provider固有形式へ依存しない。
4. `integrations/hotpepper` はprovider通信、秘密値・URLのredaction、外部形式から内部候補への変換、provider表示義務のための情報受け渡しを担う。
5. `records` はGit外のprivate runtime DBにある利用済み・ブラックリストを扱い、実データのmigration、fixture、dumpをGitへ出さない。provider IDを保存するか、秘密鍵付きHMACトークンを用いるかは、provider規約の確認後に選ぶ。確認前は長期照合を導入しない。
6. L2では、`recommendation` へのDjango/provider依存流入、`web` からadapter・ORMへの直接アクセス、provider固有形式のadapter外流出を禁止する。

## 検討した代替案

- **シンプルCRUD**: 履歴・ブラックリストには合うが、候補生成と代替提示の変換責務が埋もれるため不採用。
- **軽量／全面DDD**: 初期に必要な不変条件・状態遷移に対して過剰なため不採用。
- **独立SPAまたはサービス分割**: provider連携と秘密をserver側に閉じる必要があり、初期の規模に見合わないため不採用。

## 帰結

- 推薦処理を合成fixtureで単体検証でき、provider変更の影響をadapter境界へ閉じられる。
- provider由来データとアプリケーション所有データの混在を避けやすい。
- 推薦規則が複雑な状態遷移を持つようになれば、新ADRで再選定する。
- Python/Djangoのversion、依存、HTTP endpoint、DB schema、受け入れ契約は後続スライスで決める。
