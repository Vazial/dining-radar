---
id: 0033
scope: project/dining-radar
status: 承認済み
date: 2026-08-29
approved_by: "人間裁定（2026-08-29 チャット: スマホも地図主体にし、指のスワイプで送る。契約にスワイプ送りの定義が
無いことに対し、orchestrator が「モバイル用のモードを契約に新設する（代償=契約とテストの追加）」と
「送りボタンをDOMに残して隠す（代償=テストが押すボタンを人間が押せない）」の2案を提示し、前者が
選ばれた）"
supersedes: []
superseded_by: null
relates_to: [P-02, P-03, P-04, P-05, P-06, TDR-CS-02, ADR-0020, ADR-0025, ADR-0031, ADR-0032]
---

# ADR-0033: モバイル幅の地図主役デッキに「スワイプで送る」ための契約面を足し、旧リスト主役モードを退役させる

> **承認者向けサマリ**: 人間裁定（2026-08-29チャット）により、1024px未満（モバイル幅）も地図主役になる。
> 「地図で見る」帯・全画面シート・戻るバー（`renderModes.listPrimaryLayout`の2要素、
> `candidate-map-open`／`candidate-map-sheet-close`）は無くし、デッキの送りは指のスワイプで行う——PC版
> （decision8=案あ、`adr/0031`）が採った送りボタンはモバイルには置かない。designerが`Mobile.dc.html`で
> 報告したとおり、契約にはスワイプ送りに対応する`browserAction`が無い。本ADRは4点を決める。
>
> **(1)** `renderModes.listPrimaryLayout`を退役させる。どの幅もこの2要素を選ばなくなったため、契約は
> もう定義しない。代わりに`mapPrimaryTouchLayout`を新設し、`mapPrimaryLayout`（PC・送りボタン）と
> 互いに排他な、名前付きモードを引き続き2つ保つ——両方とも地図主役になり、違いはデッキの送り方だけに
> なる。**(2)** 件数カウンタ（`candidate-deck-position`）を、どちらか一方のモード専有ではなく両モード
> 共通の要素として扱うよう`renderModes`の構造を調整する。**(3)** `pageDeckSwipeForward`・
> `pageDeckSwipeBackward`を新設し、合成のポインタ/タッチジェスチャで検証する。両端での挙動は
> （ボタンの`disabled`のような離散状態が無いため）「境界を超える送りは表示窓を変えない」という
> no-op要求で表す。**(4)** L4検証が、`activeContext.md`のG1（合成クリックは人間の指の到達可能性を
> 証明しない）と同種の限界を、ドラッグ操作へ初めて広げることを契約に明記する——広げないのではなく、
> 広げることを隠さずに書く。
>
> designerが板で挙げた2案のうち、人間は「モバイル用の新モードを契約に追加する」を選んだ——「送りボタンを
> DOMに残し視覚的に隠す」案は、テストが押せるボタンを人間が押せない状態を自ら作ることになり、今日
> 2回の独立監査が止めたのと同じ形の穴を新たに作る、という理由による（文脈2参照）。
>
> 払うもの: `adr/0032`決定1(f)（幅ごとの`renderModes`正しさをL5の凍結不変条件に足した先行ADR）の
> 狭幅側の期待値の**意味**が変わる——`adr/0032`本文は編集しない（P-06）が、狭幅で期待するモードが
> `listPrimaryLayout`から`mapPrimaryTouchLayout`へ替わる。詳細は決定6。

## 文脈

### 1. 何が起きたか

2026-08-29、人間が「もう地図主体にしてクリックして開く意味もなくしたほうがいいかもしれないね」と発言し、
続けて「少なくともスマホは前のやつでいいかな・・・地図に店舗カードを浮かせて、スクロールで切り替え」と
裁定した。designerが`Mobile.dc.html`（アートボードM1）を描き、契約ギャップを自ら報告した——
`renderModes`（`adr/0031`が新設）は`listPrimaryLayout`と`mapPrimaryLayout`の2つのみを定義し「常に
どちらか一方が成立する」としているが、`mapPrimaryLayout`の注記は「地図主役の**デスクトップ**レイアウト
のために本改訂が導入する新要素」と明記されている。送りボタンを前提にした`pageDeckNext`／
`pageDeckPrevious`（`input: candidate-deck-next`／`candidate-deck-previous`）は、押せる要素の存在を
前提にしており、指で送る操作に対応する定義が契約のどこにも無い。

同時に、designerは2案を提示し「どちらか一方を選ばない——契約解釈にまたがる判断であり、architectと
人間の双方に関わる」とした。

- **案あ（designer板の呼称）**: `renderModes`に3つ目の名前付きモードを追加し、`candidate-deck-previous`
  ／`-next`を持たないこと、代わりにスワイプで表示窓が動く新規`browserAction`を定義する。
- **案い**: `candidate-deck-previous`／`-next`をDOM上は存在させる（スクリーンリーダー用に隠す、または
  極小のヒットエリアで画面端に置く）が、主要な操作導線としては見せない。

### 2. orchestrator が2案を代償つきで提示し、人間が前者を選んだ

orchestratorが本ADRの発注文で次のように整理した（依頼文からの引用）。

> 「モバイル用のモードを契約に新設する（代償=契約とテストの追加）」と「送りボタンをDOMに残して隠す
> （代償=テストが押すボタンを人間が押せない）」の2案を提示し、前者が選ばれた

**人間の判断は「無くす」という言葉自体に既に表れている**（「開閉…は無くす」「送りボタンは前のやつでいい
かな」ではなく「スクロールで切り替え」）。案いを却下する理由はそれだけではない——本プロジェクトは
2026-08-29の同じ日に、独立監査が2回、**構造上ぜったいに失敗しない検査**（同一出どころの値どうしの
比較、恒真assertion）をブロッカーとして止めた事故を踏まえて`meta/adr/0065`（欠陥注入での確認義務）を
定めたばかりである。案いを採ると、`allowedPurposes`に`candidate-deck-page-previous`／`-next`を
持たせたまま`data-candidate-control-purpose`付きのボタンをDOM上に残すことになり、既存の
`pageDeckNext`／`pageDeckPrevious`のacceptanceは**引き続き緑を返す**——しかし人間の指では実質
到達不能な要素を押して緑を得ているだけであり、「検査が実際の操作を証明しない」という、`meta/adr/0065`
が名指しした欠陥と**同じ形**になる。今日という同じ日にこの穴を自分から作ることは避けるべきと判断し、
案あを推す理由に加えた。

### 3. `adr/0031`が既に用意していた前提が、ここで初めて崩れる

`adr/0031`の`renderModes.description`は「`listPrimaryLayout`と`mapPrimaryLayout`のちょうど2つの
モードしか定義しておらず、常にどちらか一方が成立する」という構造を導入した。この構造は、**いずれかの
幅で必ず`listPrimaryLayout`が選ばれ続ける**ことを暗黙の前提にしていた——`adr/0032`決定1(f)が、狭幅の
ページロードで`listPrimaryLayout.testIds`が全て存在することをL5の凍結不変条件に加えたのは、この前提の
上に立っている。

本裁定はその前提を崩す。1024px未満でも地図主役になるということは、`candidate-map-open`／
`candidate-map-sheet-close`を選ぶ幅が**もう存在しない**ということである。この2要素は、`adr/0031`が
初めて契約化した時点（2026-08-28）から1日で退役する。

## 決定

### 決定1. `renderModes.listPrimaryLayout`を退役させ、`mapPrimaryTouchLayout`を新設する

`listPrimaryLayout`を契約から削除する。`candidate-map-open`／`candidate-map-sheet-close`はこの契約が
もう定義しない要素になる——`adr/0023`がreproposal関連の要素一式を丸ごと削除した先例（TDR-CS-07廃止）に
倣い、「使われなくなったモードを死んだまま契約に残す」のではなく、退役した要素を単に定義から外す形を
採った。理由は3つある。

- **契約に嘘を書かないため**: 実装がどの幅でも生成しない2要素を、契約が「ある幅では存在する」と言い
  続けるのは、`renderModes.invariant`の文言そのもの（「A test id listed under one mode is present
  only while that mode holds」）と矛盾はしないが、実質的に一度も真にならない条件を契約に残すことになる。
- **`adr/0023`の先例と一貫させるため**: 機能が退役したときは、隠して残すのではなく契約から外す、という
  やり方が既にこのプロジェクトの慣行である。
- **`meta/adr/0065`の教訓を先取りするため**: 一度も到達しない条件をL4が持ち続けると、その条件が
  「検査されているが実際には検査になっていない」状態を生む土壌になる。

`mapPrimaryLayout`（PC・送りボタン、`adr/0031`から無変更）と`mapPrimaryTouchLayout`（モバイル・
スワイプ、本ADRで新設）を、引き続き互いに排他な名前付き2モードとして契約する。両方とも地図主役であり、
違いはデッキの送り方（ボタンかスワイプか）だけになる。

### 決定2. `candidate-deck-position`（件数カウンタ）を両モード共通の要素にする

`adr/0031`時点では`candidate-deck-position`は`mapPrimaryLayout`専有のtestIdだった（`listPrimaryLayout`
には位置カウンタの概念自体が無かったため）。本ADR以降は、名前を持つ2モードのどちらでもこの要素が要る
——`renderModes`の各モードの`testIds`配列（互いに排他な要素だけを列挙する場所）からは外し、
`deckNavigation.position.presenceRule`自身が「`mapPrimaryLayout`または`mapPrimaryTouchLayout`が
成立する間は常に存在する」と直接述べる形にした。`renderModes.invariant`にもこの扱いを明記し、
「一方のモードの下でのみ存在し他方では不在」という排他性の主張は、各モード固有の要素だけに適用される
ことを明らかにした。

### 決定3. `pageDeckSwipeForward`／`pageDeckSwipeBackward`を新設する

`candidate-deck-swipe-surface`（デッキの浮遊カードを包む、スワイプ入力を受け付ける範囲のコンテナ）を
新設し、`mapPrimaryTouchLayout`専有のtestIdにする。ボタンではないため
`allCandidateScreenFormControlsMustDeclarePurpose`の対象外であり、新しい`allowedPurposes`は要らない。

`browserActions`に`pageDeckSwipeForward`・`pageDeckSwipeBackward`を新設する。`pageDeckNext`／
`pageDeckPrevious`と同じ`unaffected`6項目（`cardsAndMarkersSet`・`dataCandidateRefValues`・
`dataSelectionStateValues`・`appliedFilters`・`pendingFilters`・`conditionSummary`）を要求し、
公開APIを一切呼ばない純粋なクライアント側の表示窓移動であることも同じ形で明記した——ボタン2つを
方向2つの別名の目的にした`adr/0031`決定1の様式（`candidate-filter-apply`／`-revert`と同じ「別名の
操作」パターン）を、ボタンの無いこの操作にも踏襲した。

**両端の扱いはボタンと違う形にした。** ボタンには`disabled`という離散的な第三の状態があるが、連続的な
ドラッグにはそれが無い。`disabledState`のMustは`mapPrimaryLayout`（ボタンのある側）専有のまま
無変更にし、`mapPrimaryTouchLayout`には代わりに`boundaryOvershoot`という条項を置いた——境界を
超える方向へジェスチャが完了しても、表示窓を変えず・エラーにせず・公開APIを呼ばないことを要求する。
これは`pageDeckNext`の`precondition`ガード（既に窓の全件が見えているなら明示的に失敗させる）の
連続ジェスチャ版であり、境界での挙動という同じ性質を、ボタンの無いモードに合った形で表現した。

### 決定4. L4検証が、G1と同種の限界をドラッグ操作へ広げることを明記する

`activeContext.md`は既存の未解決論点G1として「合成クリックは人間の指がピンに到達できることを証明
しない」ことを記録している。`pageDeckSwipeForward`／`Backward`のL4検証は、Playwrightの合成ポインタ/
タッチイベント列（downーmoveーupの合成シーケンス）でジェスチャを模擬する——これは「送りのコード経路が
実際に動くこと」は証明するが、「実機で人間の指が本当にこの範囲をつまんでスワイプできること」までは
証明しない。

依頼文が明示的に警戒したとおり、**これはG1の範囲をクリックからドラッグへ新たに広げる**ことを意味する。
本ADRはこれを黙って通さず、契約本文（`pageDeckSwipeForward`の`verificationAllocation.L4`）に明記した
——「G1の既存の範囲を狭めも広げもしない」ではなく、「G1と同種の、これまで無かった種類の限界を今回
新たに1つ加える」と正直に書く。G1自体を閉じる対応は本ADRの範囲外のまま据え置く。

### 決定5. `selectMarker.deckVisibility`をモバイルでも成立させる

`deckVisibility`の適用条件を「`mapPrimaryLayout`が成立する間」から「`mapPrimaryLayout`または
`mapPrimaryTouchLayout`が成立する間」へ一般化した。地図上のピンをタップして選択を切り替える操作は、
可視窓が常に1件（設計上の見積もり、`Mobile.dc.html`）であるモバイルでも成立する——designerが板の
論点3で報告したとおり、「選ばれたカードをそのまま表示に置き換えるだけで満たせる」ため、ボタンによる
ページ送りを経由する必要がない、という設計上の見立てを契約の言葉に落とした。

### 決定6. `adr/0032`決定1(f)の狭幅側の期待値の意味を更新する（本文は編集しない）

`adr/0032`は「ADRは1決定1枚・編集禁止」（P-06）の対象であり、本ADRはその本文を書き換えない。しかし
決定1(f)は「`listPrimaryLayout`が期待される幅…のそれぞれについて…`renderModes.listPrimaryLayout.
testIds`がすべて存在し…であることを検査する」と具体的に書いており、この検査対象は決定1により
もう存在しない。

本ADRは`adr/0032`を上書きするのではなく、その後継として効く新しい決定を置く——**狭幅側でL5が期待する
モードを、`listPrimaryLayout`から`mapPrimaryTouchLayout`へ読み替える**。(f)が持っていた構造
（狭幅では一方のモードのtestIdsが全て存在し他方が全て不在、広幅ではその逆）自体は無変更で、どちらの
モード名を狭幅に割り当てるかだけが変わる。幅の具体的な数値は`adr/0032`決定2のとおり引き続きL5テスト
（developer保守）が持ち、本ADR・契約は数値を持たない。この読み替えは契約ファイル自身の
`renderModes.verificationAllocation.L5`にも明記した（契約はADRと異なり編集可能な文書であるため）。

### 決定7. 契約バージョンを1.5.0→1.6.0へ上げる。Gherkinは無変更

`candidate-search.feature`は変更しない——`adr/0031`と同じ理由で、デッキの送り方（ボタンかスワイプか）
は`TDR-CS-02`（「幹事が候補を比較する」）という既存の業務シナリオのUI実装詳細であり、新しい業務能力を
語っていない。

## 検討した代替案

- **案い（送りボタンをDOM上に残し視覚的に隠す）**: 不採用。文脈2のとおり、人間の「無くす」という
  裁定と正面から矛盾するだけでなく、`meta/adr/0065`が同じ日に名指しした「検査が実際の操作を証明
  しない」という欠陥と同じ形を、契約自身が新たに作り込むことになる。
- **`listPrimaryLayout`を契約に残したまま、狭幅では絶対に真にならない条件として据え置く**: 不採用。
  一度も到達しない条件を契約に残すと、いずれ気づかれずに死んだ記述として放置されるリスクがあり、
  `adr/0023`のTDR-CS-07廃止の先例（退役した要素は契約から外す）とも整合しない。
- **`candidate-deck-swipe-surface`を新設せず、`candidate-card`自体を`pageDeckSwipeForward`／
  `Backward`の`input`にする**: 不採用。デッキの窓の仕組み（`adr/0031`帰結が確認したとおり、非表示の
  カードもDOMからは除去されずCSSクリップされているだけ）の下では、どのカード要素を掴んでいるかが
  ジェスチャの最中に一意に定まらない。スワイプを受け付ける範囲を独立したコンテナとして契約するほうが、
  L4がジェスチャを発火する座標を一意に決められる。
- **境界の挙動をボタンと同じ`disabledState`様式（無効化される要素を用意する）にする**: 不採用。
  連続的なドラッグ操作には元々「無効化」に相当する離散状態が無い。ボタンの無いモードに架空の無効化
  対象を作るより、「境界を超えたジェスチャは表示窓に対してno-opである」という要求のほうが、実際に
  ある操作の性質に即している。
- **G1の限界をpageDeckSwipeの契約文に書かず、暗黙のままにする**: 不採用。依頼文が名指しで警戒した
  とおり、明記しないまま検査範囲を広げることは、G1がこれまで持っていた合意の外側へこっそり出ることに
  なる。契約本文に明記することで、次にこの限界を閉じる判断をする者（G1自体の解消はorchestrator/
  architectの今後の判断）が、範囲がいつどう広がったかを契約から辿れるようにした。

## 帰結

- `contracts/candidate-search-browser-interface.yaml`を`1.6.0`へ改訂した（本PRに同梱）。
  `renderModes.listPrimaryLayout`の削除、`renderModes.mapPrimaryTouchLayout`の新設、
  `deckNavigation.swipeSurface`・`deckNavigation.position.presenceRule`・`deckNavigation.
  disabledState`・`deckNavigation.orderingInvariant`の更新、`browserActions.pageDeckSwipeForward`／
  `pageDeckSwipeBackward`の新設、`selectMarker.requiredOutcome.deckVisibility`の一般化。
- `contracts/candidate-search.feature`は無変更（決定7）。
- `adr/0032`決定1(f)は本文editなしのまま、本ADR決定6により狭幅側の期待値の意味が更新される。
- **既存の申し送りとの突き合わせ（`activeContext.md` Open questions）**: 今回の改訂で解消するものは
  **無い**。
  - F1b（輪の分数ラベルの集合比較）・可視ラベルの`data-testid`欠落は、徒歩圏リング表示の話であり、
    デッキの送り方とは起源が別で、本改訂のどの決定もこの2要素に触れていない。
  - デッキ送りの前後で`pendingFilters`が不変であることが未検証という指摘（`reviews/
    audit-desktop-deck-navigation.md` G2）は、**契約は既に`pendingFilters`を`unaffected`に含めており
    （`adr/0031`時点から）、欠けているのはテスト側の検証コード（`DisplaySnapshot`に`pending_filters`
    フィールドが無い）である**——契約の文言を直すことでは閉じない、tester/developerの領分の欠落。
    本ADRは`pageDeckSwipeForward`／`Backward`にも同じ`unaffected`6項目を要求することで、この欠落を
    新しいアクションに複製しないようにはしたが、既存のPC側の欠落そのものは埋めていない。実装スライスへ
    申し送る: `DisplaySnapshot`へ`pending_filters`を足す際は、デスクトップ側とモバイル側の両方の
    送りアクションを対象にすること。
- **限界**: 決定4のとおり、`pageDeckSwipeForward`／`Backward`のL4検証は合成ジェスチャであり、実機での
  人間の指の到達可能性は証明しない（G1と同種、新たに広がった範囲として明記済み）。隣カードの覗きの幅・
  不透明度、地図ジェスチャとの競合の実機挙動（designer板「論点3」）は、本ADRの対象外のまま
  designer／実装スライスの領分として残す——契約はこの粒度（レンダーされたジオメトリ・ジェスチャの
  実際の当たり判定）を測らない、という既存の`renderModes.verificationAllocation`のL4/L5境界線を
  そのまま踏襲した。
