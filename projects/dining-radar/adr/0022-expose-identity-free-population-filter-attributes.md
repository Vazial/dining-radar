---
id: 0022
scope: project/toyama-dining-radar
status: 提案中
date: 2026-08-11
approved_by: null
supersedes: []
superseded_by: null
relates_to: [P-01, P-02, P-03, P-05, P-08, TDR-CS-02, TDR-CS-03, TDR-CS-04, TDR-CS-09, TDR-CS-10, TDR-CS-13, ADR-0005, ADR-0008, ADR-0015, ADR-0019, ADR-0023]
---

# ADR-0022: 保留中の絞り込み件数のため、識別子を持たない母集団属性を返す

> **提案の根拠**: 人間は2026-08-11のchatで、privacyに反しないことを条件に、既存の成功レスポンスにある属性を正式なAPI属性として追加する方向を了承した。本ADRはそのprivacy境界と厳格なschemaを明文化する提案であり、承認記録はPR mergeまで作らない。

## 背景

絞り込み面では、幹事がパネル内で保留中の条件を変えた直後に、その条件に一致する候補数を示す。条件を一つ変更するたびにproviderへ問い合わせると、待ち時間・rate limit・不要な外部通信を増やし、まだ適用していない条件が検索済みであるかのようにも見せてしまう。

この件数だけをブラウザで計算するには、fresh searchで得た重複除去済み母集団のうち、フィルタ判定に必要な最小属性が必要である。既存実装は成功レスポンスへ `populationAttributes` を含めている一方、`CandidateProposalResponse` は `additionalProperties: false` でこのキーを宣言していない。これはpublic API contractとの不整合である。

## 決定

`POST /candidate-proposals` の200応答に、必須の `populationAttributes` を追加する。これは表示する候補カードではなく、同一fresh searchの**重複除去後・任意のfilter適用前**の母集団を、保留中filterの件数計算だけに使う匿名属性列である。

各行は次の5属性だけを持ち、`additionalProperties: false` とする。

- `genre`
- `nonSmokingStatus`（`FULL` / `PARTIAL` / `NONE` / `null`）
- `cardPaymentAvailable`（`true` / `false` / `null`）
- `dinnerBudgetTier`（`LOW` / `MID` / `HIGH` / `null`）
- `defaultExcluded`

この列には、店舗名、候補参照値、provider ID、provider page URL、店舗座標、検索地点、検索範囲、距離、近い順・provider順その他の順位情報、経路、徒歩時間、現在地、画像、説明、営業時間、席数、または個別店舗を識別・追跡できる属性を含めない。行の順序は公開意味を持たず、ブラウザは行の位置を候補・地図marker・距離・順位と結び付けてはならない。

`populationAttributes` は一つの成功レスポンスの本文でのみ渡り、ブラウザは保留中の件数表示にだけ使う。storage、cookie、URL、ログ、trace、server-side cache、durable historyへ保存しない。これはprovider response cacheでも、候補履歴でもない。

nullableな三つの属性は既存filterモデルと同じく、`null` を不一致や否定と扱わない。特に `dinnerBudgetTier` はproviderのディナー予算由来の粗い区分であり、ランチ価格を推測・断定しない。`cardPaymentAvailable=false` はクレジットカード不可だけを意味し、現金のみを意味しない。

## Privacy評価

この属性集合自体は、非公開検索地点、距離、経路、徒歩時間、現在地、provider資格情報、または店舗識別子を含まないため、ADR-0005/ADR-0008の直接的な非開示境界を広げない。表示済み候補の同じfilter属性はすでにカードから観測できる。未表示店舗については、識別子のない集合所属だけが分かる。

ただし、属性配列の行順を距離・順位・provider返却順と解釈できる形で公開すれば、個別属性が匿名でも私的検索地点について追加推論を許すおそれがある。そのため、このADRは行順に公開的意味を与えず、将来の実装が順位・距離・IDとの対応を追加することを明示的に禁止する。ここにない属性を追加する場合、privacy評価と新たなADRを必要とする。

## 代替案

- **`populationAttributes`を返さない**: 保留中件数をなくすか、各操作でserver/provider検索を行う必要がある。前者は絞り込みの結果予測を失い、後者は未適用状態と検索済み状態の区別・外部呼出し量を悪化させる。
- **店舗識別子や座標を返す**: 件数計算には不要であり、ADR-0005/ADR-0008の非公開地点・provider識別子境界に反するため採用しない。
- **サーバー側の専用count endpointを追加する**: 同じfresh populationを再取得するか、provider response cacheを導入する設計判断を要する。本リリースでは採用しない。

## 結果

API v1.0.1 draftは`populationAttributes`を厳密に定義する。browser-interfaceとtest-support contractはこの匿名配列をDOMまたはacceptance-only seamとして公開しないため、今回変更しない。`ARCHITECTURE.md`と`design.md`にもモジュール責務や設計上の公開面の新規変更はないため、今回更新しない。

実装側では、公開schemaがこの属性を許可しないまま成功応答に載せることを禁止する。testerは、属性行に禁止属性がないこと、nullが否定扱いされないこと、保留中の件数にのみ使われることをpublic responseとDOM結果から検証する。
