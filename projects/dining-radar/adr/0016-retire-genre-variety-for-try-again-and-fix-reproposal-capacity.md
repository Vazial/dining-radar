---
id: 0016
scope: project/toyama-dining-radar
status: 承認済み
date: 2026-08-08
approved_by: "本PRのマージをもって承認（ADR-0035 方式(i)。人間裁定 2026-08-08 chat、実データでの2度目の実機レビュー後: 『そもそも別の選び方にしても候補がかわらないね』に対し、orchestratorが提示した2案（縮退時に非表示にするだけ／毎回違う店が出るよう決定性を再検討する）を却下し、『廃止して「もう一度探す」に置き換える』を採用。人間の言葉: 『そもそもシャッフルしてればジャンルもばらけるはずだから、選び方を廃止してシャッフル機能にするほうがいいかもしれないね／前回出した店舗は出さない（優先順位を下げる）の方針でどうかな』。モバイルの情報圧縮、モーダルのz-index、再提案の選択即時反映についても修正を裁定。ランダム性は足さず、既存の再表示降格（ADR-0008決定2）だけで引き直す方針は人間裁定として確定済みで、architectはこれを契約へ翻訳した"
supersedes: []
superseded_by: null
relates_to:
  [P-01, P-02, P-04, P-05, P-08, P-10, TDR-CS-03, TDR-CS-07, TDR-CS-09,
   TDR-CS-10, TDR-CS-11, ADR-0004, ADR-0005, ADR-0008, ADR-0013, ADR-0015]
---

# ADR-0016: GENRE_VARIETYを廃して「もう一度探す」に置き換え、reProposalOptionsの容量問題を構造的に解消する。再提案は選ぶだけで確定する

> **承認者向けサマリ**: 本番Hot Pepperプロファイルでの2度目の実機レビューで、人間が4件の指摘と1つの判断を
> 行った。本ADRが契約に翻訳するのは次の3点。**(1)** `GENRE_VARIETY`（いつもと違うジャンルを試す）は
> 実データで`PROXIMITY`と候補・順序ともに完全一致（5/5重複）しており、独立した切り口として機能して
> いなかった。人間裁定によりこれを`ConceptKind`から削除し、「もう一度探す」という新しい操作を追加する。
> **「もう一度探す」は切り口（コンセプト）ではない**——独自の順位付け基準を持たず、現在表示中の切り口を
> そのまま使って再検索するだけであり、ADR-0008決定2の既存の再表示降格だけに頼る。ランダム性は一切
> 追加しない（新しい店が出る保証はなく、これは`TDR-CS-03`が既に持つ「新しい提案が以前とすべて異なる
> 店舗になるとは限らない」という非保証と同じ性質である）。契約上は`ConceptKind`enumの一員にはせず、
> `reproposalKind`に現在表示中の値をそのまま再送できるようにするだけの拡張として表現した。**(2)**
> `GENRE_VARIETY`の削除により、`ConceptKind`は4種類になり、表示中の1つを除いた残り3つは
> `reProposalOptions.maxItems: 3`に必ず収まる——ADR-0015が`IZAKAYA_BAR_INCLUDED`を追加した際に
> 見落としていた容量衝突（5種類−表示中1つ=4つ>上限3つ）が、構造的に（優先順位のヒューリスティックに
> 頼らず）解消される。orchestratorが提示した「`IZAKAYA_BAR_INCLUDED`の優先順位を上げる」代替案は、この
> 構造解決により不要と判定した。**(3)** 再提案モーダルは、切り口を選ぶこと自体が新しい提案を確定させる
> ——`candidate-search.feature`のTDR-CS-03本文は既にこの一段階操作を記述しており業務契約は無変更、
> 変更が必要だったのは`candidate-search-browser-interface.yaml`側だけである。`candidate-reproposal-submit`
> というtest idと`reproposal-submit`というpurposeを廃止し、`allowedPurposes`という許可リストから
> 明示的に締め出すことで、developerが将来この操作に確認ボタンを再び持ち込むことを機械的に防ぐ。
> **モバイルのカード情報圧縮とモーダルのz-index問題は、契約を変えないCSS/レイアウトの洗練と判定し、
> ADR（meta/adr/0021が定めるdeveloperの改修裁量）に含めない**——orchestratorが実測した事実を本ADRの
> 帰結節にdeveloperへの申し送りとして記録するにとどめる。friction-logには、`GENRE_VARIETY`の縮退
> そのものは記録しない（`activeContext.md`が起草当初から「ranking algorithmは合成fixtureでしか検証
> されていない」と明示的に追跡していた既知のリスクの顕在化であり、AIの見落としではない）が、
> `IZAKAYA_BAR_INCLUDED`の容量衝突をADR-0015起草時に見落としたことは`FR-010`として新規記録する。

## 文脈

### 1. 何が観測されたか(orchestratorが実機・実データで計測し、architectへ事実として供給されたもの)

人間の`.env.local`（実キー・実座標）で本番プロファイルを起動し、APIとDOMを直接計測した（実店舗名・実座標は
一切記録していない）。初期提案（`PROXIMITY`）との比較で、各切り口の候補は次のとおりだった。

| 切り口 | 重複 | 並びも同一 |
|---|---|---|
| `CAPACITY_REFERENCE` | 0/5 | — |
| `AMENITY_REFERENCE` | 0/5 | — |
| `IZAKAYA_BAR_INCLUDED` | 2/5 | — |
| `GENRE_VARIETY` | **5/5** | **完全一致** |

初期提案の上位5件は既に和食・ラーメン・イタリアン・フレンチ・カフェ・スイーツ・焼肉・ホルモンの5ジャンル
すべてが異なっていた。`GENRE_VARIETY`の「ジャンルが偏らないよう各ジャンルから近い順に拾う」規則は、
この母集団では`PROXIMITY`と完全に同じ集合・同じ順序へ縮退した。

同時に、`IZAKAYA_BAR_INCLUDED`が実データで一度も提示されないことも判明した。説明可能なコンセプトは
（`GENRE_VARIETY`を含め）4つ成立していたが、`reProposalOptions.maxItems: 3`（`TDR-CS-03`本文も
「3つ以下」）で切り落とされ、`pipeline.py`の`_PRIORITY_ORDER`が`IZAKAYA_BAR_INCLUDED`を最後に置いて
いるため、実際のAPI応答は`[CAPACITY_REFERENCE, GENRE_VARIETY, AMENITY_REFERENCE]`の3件だけだった。
ADR-0015が実現しようとした「幹事が選べる」が成立していなかった。これはADR-0015決定9が「別途
orchestratorへ報告する」としていた保留事項の実体である。

このほか、モーダルの重なり（`#candidate-reproposal-overlay`が`position: fixed; z-index: auto`、
`.leaflet-container`が`position: relative; z-index: auto`でスタッキング文脈を作らないため、Leaflet内部の
pane（`z-index: 200〜400`）がルート文脈に参加し、モーダル側にz-index指定が無くDOM順だけで前面に出て
いる）と、モバイル（390×844）でカード5枚が文書約3.5画面分の縦の長さになる点も計測された。

### 2. 人間の指摘と判断(2026-08-08、チャット)

1. 「そもそも別の選び方にしても候補がかわらないね」→ orchestratorが提示した2案
   （(a)縮退時に提示しないだけにする／(b)毎回違う店が出るよう決定性を再検討する）をいずれも却下し、
   「廃止して『もう一度探す』に置き換える」を採用。人間の言葉:「そもそもシャッフルしてればジャンルも
   ばらけるはずだから、選び方を廃止してシャッフル機能にするほうがいいかもしれないね／前回出した店舗は
   出さない（優先順位を下げる）の方針でどうかな」。ランダム性は足さず、既存の再表示降格（ADR-0008
   決定2）だけで引き直す方針が確定した。
2. 「モバイルの場合、1店舗が縦長すぎてスクロールしないとみれないね、情報を圧縮したい」
3. 「選び方のモーダルが地図の下に隠れてしまってるね」
4. 「選び方のモーダルは選び方を選択したら動くようにしたい（わざわざ「この選び方で探す」ボタンは
   押さなくてよいのでは）」

指摘4について、`candidate-search.feature`のTDR-CS-03本文は既に「幹事が一つの切り口を選ぶと新しい
候補提案が依頼される」と書いており、人間の要望と一致していることをarchitectが確認した
（後述、決定4）。一方`candidate-search-browser-interface.yaml`は`reProposal.requiredTestIds.submit`
（`candidate-reproposal-submit`）を必須とし、`allowedPurposes`に`reproposal-submit`を持っていた。
業務シナリオとbrowser-interface契約が食い違っていた。

## 決定

### 1. `GENRE_VARIETY`を`ConceptKind`から削除する

実データでの重複が示すとおり、`GENRE_VARIETY`は「ジャンルを横断して比較する」という独自のrationaleを
主張しながら、実際には近い順に候補が既に多ジャンルにまたがっている限り`PROXIMITY`と区別できない出力を
返す。これは`ADR-0004`決定1が要求する「説明できるコンセプトだけを示す」の精神に反する——アルゴリズムは
正しく動作しているが、**主張している区別が実データ上で成立しない**という、コンセプトの前提そのものの
欠陥である。`candidate-search-api.yaml`の`ConceptKind` enumから`GENRE_VARIETY`を削除し、`.feature`は
どの契約もconceptの具体名を書いていないため変更を要しない。

### 2. 「もう一度探す」を導入する。これは`ConceptKind`の一員ではなく、別の操作として表現する

**判定: 「もう一度探す」は切り口（コンセプト）ではない。**理由は3点。

- `ConceptKind`の各値は`ReproposalOption`/`CandidateConcept`スキーマ上、必須の`rationale`
  （なぜこの候補群を選んだかの説明）を伴う、独自の順位付け基準を持つ比較の切り口である。「もう一度
  探す」は独自の基準を持たない——現在表示中の切り口の基準をそのまま再適用するだけであり、これを
  `ConceptKind`の新しい値として表現すると、`GENRE_VARIETY`が犯したのと同じ構造的な誤り
  （「区別できる」という主張を契約に持ち込みながら実際には区別を提供しない）を作り直すことになる。
- `TDR-CS-03`本文の「切り口」という語は、「再提案に使える切り口が3つ以下のポップアップで示される」
  「現在表示中の切り口は再提案の選択肢に含まれない」という、**表示中と異なる**ことを前提にした語彙で
  ある。「もう一度探す」は表示中の切り口をそのまま再送するため、この語彙の指す対象とは異なる操作
  であり、同じ枠に押し込めると「切り口」の定義自体が曖昧になる。
- `reProposalOptions`配列（`maxItems: 3`）の一員にしないことで、決定4が述べる容量問題の解決を
  ヒューリスティック（優先順位の調整）に頼らず構造的に達成できる（後述）。

**契約上の表現**: `CandidateProposalRequest.reproposalKind`の説明を拡張し、送ってよい値を
「`reProposalOptions`から選んだ、表示中と異なる切り口」に加えて「**現在表示中の`proposal.kind`を
そのまま送る**」ことも許すと明示する。新しいenum値・新しいフィールドは追加しない。ブラウザ側では、
常時利用可能な単一の操作（新しい`candidate-reproposal-try-again`コントロール）が、表示中の`proposal.kind`
を`reproposalKind`としてそのまま再送するPOSTを行う。

### 3. 決定性の要求を壊さないことの確認

`もう一度探す`は次のいずれの機構も追加しない。

- 乱数、ランダムシャッフル、非決定的な並び替えは一切導入しない。
- サーバーは`select_reproposal`（既存関数）が現在の候補集合から要求された`kind`を探して返すだけであり、
  「もう一度探す」専用の新しいランキングロジックを持たない。
- 「新しい提案が以前とすべて異なる店舗になるとは限らない」という非保証は、`TDR-CS-03`が既に持つ
  ものと同一であり、新しい種類の非決定性ではない。むしろ`もう一度探す`は、fresh provider searchと
  ADR-0008決定2のブラウザ内表示済み降格だけに頼るため、**同一母集団・同一ランキング基準では
  既表示店舗の並び順が変わるだけで、新しい店が入ってこない場合があり得る**——これは正直な帰結であり、
  隠さずADR本文とAPI契約の両方に明記する（後述、決定6）。この非保証は`product-brief.md`・
  `ADR-0004`・`ADR-0005`・`ADR-0008`が確立した「決定的ルールだけで選ぶ・生成AIを使わない・
  ランダム性を持ち込まない」という要求と矛盾しない——むしろ、もし新しい店を保証しようとして何らかの
  非決定的要素（シャッフル、時刻依存の並び替え等）を足していたら、その時点でこれらの文書と衝突していた。
  本ADRはその衝突を避けるために、保証を弱める（新しい店の保証をしない）方を選んだ。

### 4. `reProposalOptions`の容量問題は、`GENRE_VARIETY`削除により構造的に解消する

`ConceptKind`は4種類（`PROXIMITY`・`CAPACITY_REFERENCE`・`AMENITY_REFERENCE`・
`IZAKAYA_BAR_INCLUDED`）になった。表示中の1つを`reProposalOptions`が除外するため、残りは常に**最大
3つ**であり、`maxItems: 3`に必ず収まる。5種類だった旧構成（表示中1つを除いて残り4つ>上限3つ）とは
異なり、**どのビルド可能な組み合わせでも切り捨てが発生しない**。これは優先順位の並び（どれを最後に
置くか）に依存しないため、`_PRIORITY_ORDER`内の`IZAKAYA_BAR_INCLUDED`の位置（ADR-0015決定4が
非拘束の推奨として最後に置いた）を変える必要はない。

**orchestratorが提示した未裁定の代替案「`IZAKAYA_BAR_INCLUDED`の優先順位を上げ、押し出されるのは
`AMENITY_REFERENCE`とする」は不採用とする。** 理由: この案は「常に4つのうち1つを押し出す」という
容量超過そのものを残したまま、押し出す対象を変えるだけであり、根本原因（enum数5に対して上限3という
容量設計）を解決しない。`GENRE_VARIETY`の削除がその根本原因を構造的に取り除く以上、優先順位の
入れ替えというヒューリスティックは不要である。

**将来への申し送り**: この解消は「`ConceptKind`が4種類である」ことに依存する。将来6つ目の切り口を
追加する場合、追加するarchitectは「表示中1つを除いた残りが`maxItems: 3`に収まるか」を明示的に
確認すること（本ADRのFR-010が同じ確認の欠落を記録している）。

### 5. 再提案モーダルは選択即時に確定する。`candidate-reproposal-submit`と`reproposal-submit`を廃止する

`candidate-search.feature`のTDR-CS-03本文「幹事が一つの切り口を選ぶと新しい候補提案が依頼される」は
既に一段階操作を記述しており、**業務契約の変更は不要**と判定する。ずれていたのは
`candidate-search-browser-interface.yaml`だけである。

- `reProposal.requiredTestIds`から`submit`（`candidate-reproposal-submit`）を削除する。
- `unavailableControls.allowedPurposes`から`reproposal-submit`を削除する。これにより、確認ボタンを
  持つ実装は許可リストに反し、L4のcontrol-surface検査で機械的に拒否される——「選ぶだけで確定する」を
  文章の指示ではなく許可リストという機械強制で担保する（P-04、ADR-0013決定5の設計をそのまま踏襲）。
- `browserActions.submitReProposal`を`selectReProposal`に改称し、`inputs`の配列
  （`[candidate-reproposal-option, candidate-reproposal-submit]`）を単一の`input:
  candidate-reproposal-option`に変える——選ぶことそのものが操作を発火させる。

### 6. 契約への波及の判定

- **`candidate-search-api.yaml`**: 変更する。`ConceptKind` enumから`GENRE_VARIETY`を削除し、
  その説明文を更新する。`CandidateProposalRequest.reproposalKind`の説明を拡張し、表示中の`kind`を
  そのまま再送できることを明示する。`version`を`0.5.0`から`0.6.0`へ上げる。
- **`candidate-search.feature`**: 変更する。新規`TDR-CS-11`（同じ切り口のまま「もう一度探す」を選ぶ）
  を追加する。既存シナリオ（`TDR-CS-00`〜`TDR-CS-10`）は文言変更なし——`TDR-CS-03`は決定5の理由により
  そのまま成立すると判定した。**これは人間の再承認点であり、承認の実体は本PRのマージである。**
- **`candidate-search-browser-interface.yaml`**: 変更する。`candidate-reproposal-submit`と
  `reproposal-submit`を廃止し、`selectReProposal`へ改称する（決定5）。新しい常時利用可能な
  コントロール`candidate-reproposal-try-again`（purpose: `reproposal-try-again`）と対応する
  `browserActions.tryAgain`を追加する（決定2）。`contractVersion`を`0.3`から`0.4`へ上げる。
- **`test-support-api.yaml`**: 変更する。`NORMAL_WITH_REPEAT`モードの保証を拡張し、表示中の切り口を
  そのまま再送する「もう一度探す」要求でも、新規候補1件以上・既表示候補1件以上を含む応答が決定的に
  得られることを明記する（`TDR-CS-11`の決定的な検証を、新規モード追加なしで可能にする）。`version`を
  `0.3.0`から`0.4.0`へ上げる。

### 7. 指摘2（モバイルの情報圧縮）・指摘3（モーダルのz-index）は契約・ADRの対象外と判定する

いずれもcontrol surface・test id・purpose・業務behaviorを変えないCSS/レイアウトの洗練であり、
`meta/adr/0021`が定めるdeveloperの改修裁量（骨格を保つ限り操作感・細かいUIの洗練は自由）の範囲内と
判定する。プロジェクトADRを起票せず、developerへの申し送りとして本ADRの帰結節に記録するにとどめる。

### 8. friction-logの判定

- **`GENRE_VARIETY`の縮退そのものは記録しない。** `activeContext.md`は起草当初から「Two implementation
  choices remain verified only against synthetic fixtures: the per-concept ranking algorithm」と、
  ランキングアルゴリズムが合成fixtureでしか検証されていないことを明示的に追跡していた。これは
  ADR-0015決定8が「64件が全部表示された」問題を friction 扱いしなかった論理（`product-brief.md`
  §8・`activeContext.md`が実データでしか判明しない未決事項として既に先送りを意図的に記録していた）
  と同型であり、AIの見落としには当たらないと判定する。
- **`IZAKAYA_BAR_INCLUDED`の容量衝突は記録する。** `ADR-0015`が`IZAKAYA_BAR_INCLUDED`を5番目の
  `ConceptKind`として追加した際、既存の`reProposalOptions.maxItems: 3`という固定容量制約との
  組み合わせ（5種類−表示中1つ=4つ>上限3つ）は、実データを必要としない単純な計数で当時気づけた
  はずである。これはfriction-log FR-010として新規記録する（後述）。

## 検討した代替案

- **(a) 縮退時に`GENRE_VARIETY`を提示しないだけにする**: 却下（人間裁定）。「説明可能なコンセプトだけ
  示す」というADR-0004決定1の仕組みの範囲内で対処できなくもないが、人間は「そもそも選び方として
  廃止する」方を選んだ——縮退が起きない稀な母集団でだけ生き残るコンセプトを維持するコストに見合わない。
- **(b) 毎回違う店が出るよう決定性を再検討する**: 却下（人間裁定）。`product-brief.md`・
  `ADR-0004`・`ADR-0005`・`ADR-0008`・API仕様が確立した「決定的ルールだけで選ぶ」という要求と衝突する。
- **「もう一度探す」を新しい`ConceptKind`の値として追加する**: 不採用（決定2）。独自のrationaleを
  持たない操作を「区別できる切り口」の型に押し込むと、`GENRE_VARIETY`が犯した構造的誤りを再生産する。
- **`IZAKAYA_BAR_INCLUDED`の優先順位を上げ`AMENITY_REFERENCE`を押し出す**: 不採用（決定4）。
  容量超過そのものを解決しないヒューリスティックであり、`GENRE_VARIETY`削除による構造解決で不要になった。
- **`reProposalOptions.maxItems`を4以上へ引き上げる**: 検討しなかった。`TDR-CS-03`本文
  「再提案に使える切り口が3つ以下」という人間承認済みの業務文言と`candidate-search-api.yaml`
  双方の再承認が要る変更であり、決定4の構造解決で不要になったため、この重い変更を提案しない
  （P-02: 必要な分だけ確定する）。
- **`candidate-reproposal-submit`を残し、`allowedPurposes`の中で任意（optional）purposeとして許容する**:
  不採用。「選ぶだけで確定する」という人間の指示を機械強制するには、許可リストからの削除（存在すれば
  即座に契約違反になる）が必要であり、「あってもよい」という中間的な許可は同じ強制力を持たない
  （ADR-0013決定5の許可リスト設計の精神に反する）。

## 帰結

- `candidate-search-api.yaml`（`v0.6.0`）・`candidate-search.feature`（`TDR-CS-11`追加）・
  `candidate-search-browser-interface.yaml`（`v0.4`）・`test-support-api.yaml`（`v0.4.0`）が
  改訂対象になる。いずれも人間の再承認点であり、承認の実体は本PRのマージである。
- developerの実装スライスへの申し送り:
  1. `recommendation/pipeline.py`から`ConceptKind.GENRE_VARIETY`・`_build_genre_variety`・
     `_interleave_by_genre`・対応する`_TITLES`/`_RATIONALES`エントリ・`_PRIORITY_ORDER`内の該当項目を
     削除すること。
  2. 「もう一度探す」は、表示中の`proposal.kind`をそのまま`reproposalKind`として送るPOSTとして実装
     すること。サーバー側は既存の`select_reproposal`がそのまま機能するはずであり、新しいランキング
     ロジックを追加しないこと（決定3参照）。表示中の`kind`が新しい検索で説明不能になった場合は、
     既存の`ReproposalKindUnavailableError`/`PROPOSAL_REPROPOSAL_KIND_INVALID`経路（`TDR-CS-07`が
     カバーする形と同一）で扱われることを確認すること。
  3. モバイルのカード情報圧縮（orchestrator実測: 390×844で候補カード5枚が文書約3.5画面分）と、
     再提案モーダルの前面表示（orchestrator実測: `#candidate-reproposal-overlay`が
     `position: fixed; z-index: auto`、`.leaflet-container`が`position: relative; z-index: auto`で
     スタッキング文脈を作らず、Leaflet内部paneの`z-index: 200〜400`がルート文脈に参加している——
     モーダル側にz-index指定を追加してスタッキング文脈を明示的に作ることで解決できる可能性が高い）は、
     契約変更を伴わないCSS/レイアウトの洗練としてdeveloperの裁量に委ねる（決定7、meta/adr/0021）。
- friction-logにFR-010を新規記録する（本PRに同梱）。`GENRE_VARIETY`の縮退自体は記録しない
  （決定8）。
- `design.md`・`ARCHITECTURE.md`・`product-brief.md`を本PRで更新する（構造的な処理フローの変更
  ——「もう一度探す」という新しい常時操作の追加、および`GENRE_VARIETY`という具体例の陳腐化——を
  反映するため）。
