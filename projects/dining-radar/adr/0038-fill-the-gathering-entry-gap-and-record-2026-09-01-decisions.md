---
id: 0038
scope: project/dining-radar
status: 承認済み
date: 2026-09-01
approved_by: "人間裁定（2026-09-01 チャット、選択肢UIで確定: 第1弾『会の作成と日程調整』はPR #181で
  本番デプロイ済みだが、人間が実機を確認し『幹事画面ってあるの？新機能が見て取れない』と所見を出した
  ——ランチ候補画面から会へ辿る導線が無く、会をつくる画面も会の一覧も無かった。designerが
  `E:\\AWS\\dsg-out\\party\\Entry.dc.html`／`AddDate.dc.html`／`Handoff.dc.html`で入口画面群を
  描き、人間が次の6件を裁定した。(1) D10: 会をつくった瞬間、局面はすでに『日程を聞き中』である。
  『下書き』の局面は廃止する——会の作成には候補日が1つ以上必要という既存の制約（ADR-0035決定1）の
  もとでは一度も出現しない局面だった（Entry.dc.htmlのD10決定表では、この内容は『案B』の列に
  記載されている）。(2) 候補日を追加するフォームは、Organizer.dc.htmlのA①パネル内にその場で開く
  インライン形式（AddDate.dc.html案A）を採る。足したあともフォームは閉じない。(3) ランチ候補画面
  ヘッダーへ会への入口を置く形は、枠付きボタン＋進行中（日程を聞き中・店を選び中）の会の件数バッジ
  （Handoff.dc.html案B）を採る。件数が0のときはバッジを出さない。(4)〜(6) 候補デッキの見た目調整
  3件（PCカードレイアウト案Bの空き場所確保、候補デッキの件数ページャー、スマホでのカード高さ削減）
  はdesignerが契約条件を確認済みで契約影響なしと確定した——ただしPCカード案Bの空き場所に
  `candidate-card-payment-caution`のtest idを付けないことをあわせて申し送る。）"
supersedes: []
superseded_by: null
relates_to: [P-02, P-06, P-08, ADR-0013, ADR-0034, ADR-0035, ADR-0036, ADR-0037]
---

# ADR-0038: 会の入口欠落（幹事画面・会一覧・作成画面）を埋める契約追補と、2026-09-01の6件の人間裁定を記録する

> **承認者向けサマリ**: 会スコープ契約第1弾はPR #181で本番デプロイ済みだったが、人間が実機を確認し
> 「幹事画面ってあるの？新機能が見て取れない」と所見を出した——ランチ候補画面から会へ辿る導線が無く、
> 会をつくる画面も会の一覧も無かった。designerがこの欠落を認め（「designer の穴である」
> `Entry.dc.html`本文）、`Entry.dc.html`（会の一覧・会をつくる）・`AddDate.dc.html`（候補日追加
> フォーム）・`Handoff.dc.html`（候補画面ヘッダーからの導線）の3枚で入口画面群を描き、人間が
> 2026-09-01のチャット（選択肢UI）で6件を裁定した。本ADRはこの裁定を記録し、第1弾の契約
> （`gathering-scheduling.feature`・`gathering-scheduling-api.yaml`・
> `gathering-scheduling-browser-interface.yaml`）へ追補し、あわせて`candidate-search-browser-
> interface.yaml`へ最小限の観測面を追加するための設計判断を記す。
>
> **設計判断の要点**: (1) D10（下書き局面の廃止）を`product-brief.md`§2・`GatheringPhase`の
> スキーマ説明文へ反映した——`GatheringPhase`列挙自体は`ADR-0035`起草時点から一貫して
> `[SCHEDULING, SELECTING_SHOP, FINALIZED]`の3値であり、値の変更は伴わない（下書き相当の値を
> 一度も持ったことがない）。(2) 会の一覧・会をつくる画面のためにAPI操作`listGatherings`・
> `getInProgressGatheringCount`を新設した——後者は候補画面が全件取得して数える過剰取得を避けるための
> 専用の小さな集計エンドポイントである。(3) designerが「決められなかった」として明示的にarchitectへ
> 送った2点——候補日の重複時の扱い、時刻の要否——を、契約段階の設計判断として決着させた（重複は拒否、
> 時刻は既存の`date-time`形式が元から要求していたことの確認）。(4)
> `candidate-search-browser-interface.yaml`への追補は最小限にとどめた——`candidate-gathering-entry`
> を素の`<a>`要素として定義し、`allCandidateScreenFormControlsMustDeclarePurpose`の走査対象外に
> することで新しい`allowedPurposes`エントリを不要にした（`candidate-map-open`等の既存の様式の再利用）。
> (5) **FR-028として食い違いを1件、解消せず報告する**: 依頼文はD10を「案A」と呼んでいるが、
> `Entry.dc.html`のD10決定表を実際に読むと、採用された内容（下書き局面の廃止・作成直後から
> 「日程を聞き中」）は表の**案B**の列に記載されており、表の**案A**は逆の内容（下書きを実体化し、
> 最初のリンク発行で「日程を聞き中」へ進める）を指す。本ADRは、依頼文が示した内容そのもの（下書き
> 局面の廃止）を実装したが、この呼称の食い違いをどちらが正しいかを判断せずここに記録する。

## 文脈

### 1. 何が起きたか

会スコープ契約第1弾「会の作成と日程調整」はPR #181でマージ・本番デプロイ済みだった。人間が実機を
確認したところ、ランチ候補画面（既存のTDR-CS画面）から会へ辿る導線が存在せず、会をつくる画面も
会の一覧そのものも存在しないことが判明した——「幹事画面ってあるの？新機能が見て取れない」という
所見である。

`Entry.dc.html`はこの欠落の原因を次のように総括する：「A 板は『会が既にある』状態から描かれていた
ためで、会の一覧も、会をつくる画面も、この設計に存在していなかった——designer の穴である」。
`design/explorations/README.md`の「この設計の穴」節が既に「会をつくる画面を描いていない」と記して
いたにもかかわらず、それが実機の欠落として表面化するまで埋められていなかった。

designerは3枚のキャンバスでこの欠落を埋めた。

- `Entry.dc.html`: E-1（会の一覧）・E-1b（会が0件のときの案内）・E-2（会をつくるフォーム）、
  および D10（つくった直後の会の局面）の決定表。
- `AddDate.dc.html`: A①「候補日を足す」ボタンの先が未定義だった問題（`ADR-0036`未決事項2）を
  埋める、候補日追加フォームの2案（案A: その場に開くインライン、案B: ダイアログ）。
- `Handoff.dc.html`: ランチ候補画面から会への導線の3案（案A: テキストリンク、案B: 枠付きボタン＋
  件数バッジ、案C: 上部帯）。

人間は2026-09-01のチャット（選択肢UI）で、前文の`approved_by`に記録した6件を裁定した。

### 2. designerが明示的にarchitectへ送った2点

`AddDate.dc.html`は次の2点を「designerでは決められなかった」として明示的に架空の решение にせず
architectへ送った。

1. 同じ日時の候補日を二重に足そうとしたときの扱い（拒否／許容）。
2. 候補日の時刻入力を必須にするか任意にするか。

architectはこの2点を契約段階の設計判断として決着させる（決定3・決定4）。これは人間の再裁定を
要する製品判断ではなく、契約の一貫性を保つための実装細部の決定であると判断した——理由は各決定の
本文に記す。

### 3. `Handoff.dc.html`が指摘した新しい結合

`Handoff.dc.html`は、採用された案B（枠付きボタン＋進行中件数バッジ）について「候補画面が会の件数を
取りに行く必要が生じ、2つの機能が初めて結合する」と明示的に指摘している。本ADRの決定5・6は、この
結合をどう契約化するかを扱う。

## 決定

### 決定1. D10（下書き局面の廃止）を反映する

`product-brief.md`§2の状態機械を「下書き→日程を聞き中→店を選び中→確定」の4局面から「日程を聞き中
→店を選び中→確定」の3局面へ改める。**これはスキーマの変更を伴わない**——`gathering-scheduling-
api.yaml`の`GatheringPhase`列挙は`ADR-0035`起草時点から一貫して`[SCHEDULING, SELECTING_SHOP,
FINALIZED]`の3値であり、下書き相当の値を一度も持ったことがない（会の作成には候補日が1つ以上
必要という`ADR-0035`決定1の制約のもとでは、「候補日がまだ無い下書き」は最初から出現し得なかった）。
本決定は`product-brief.md`の記述をこの既存の設計へ追いつかせるものであり、`GatheringPhase`の
`description`をこの経緯が読み取れるよう更新するにとどめる。

### 決定2. 会の一覧・会をつくる画面のAPI操作を新設する

`gathering-scheduling-api.yaml`へ次の2操作を新設した。

- `GET /gatherings`（`listGatherings`）: 幹事が幹事を務める全ての会を`createdAt`降順（新しい順）で
  返す。確定済みの会も一覧に残り続ける（削除操作は`ADR-0035`決定1のD4により置かない）。
- `GET /gatherings/in-progress-count`（`getInProgressGatheringCount`）: `SCHEDULING`・
  `SELECTING_SHOP`局面の会の件数だけを返す（`FINALIZED`は除く——用が済んでいるため、
  `Handoff.dc.html`のdesigner判断を踏襲）。ランチ候補画面ヘッダーのバッジ専用の、小さく独立した
  集計エンドポイントとした——候補画面が`listGatherings`の全件を取得してクライアント側で数える
  過剰取得を避けるためである（検討した代替案を参照）。

`Gathering`スキーマへ`createdAt`（`date-time`、必須）を追加した——一覧の「新しい順」を実現するために
必要な値であり、これまでの契約は会の作成時刻を公開していなかった。

### 決定3. 候補日の重複は拒否する

`addCandidateDate`・`createGathering`の候補日入力に、同一会内で同一`startAt`（分単位まで一致）の
候補日が既に存在する場合の拒否を追加した——新しいエラーコード`DUPLICATE_CANDIDATE_DATE`（409）を
新設し、`createGathering`・`addCandidateDate`双方のレスポンスへ追加した。

**理由**: 許容する案（同じ日時が複数回一覧に並ぶ）は、`AddDate.dc.html`の案B（ダイアログ）が
「重複に気づけるよう既存の候補日をダイアログ内に書き写す」という追加のUI要素を要求した理由と
同じ問題——同じ日時が複数回、参加者の回答画面にも並ぶことになり、`respondedParticipantCount`の
分母計算・参加者への表示のいずれにも意味のある区別がつかない——を抱える。拒否のほうが、
候補日の集合を意味のある集合（各要素が一意の日時を持つ）として保てる。

### 決定4. 候補日の時刻は既に必須である（明確化のみ）

`CandidateDateInput.startAt`は`format: date-time`（ISO 8601）であり、この形式は時刻成分を必須と
する——時刻だけを独立に「必須／任意」にする設計の余地は、そもそもこのフィールドの型に存在しない。
`AddDate.dc.html`が挙げた「時刻を必須にするか任意にするか」という論点は、フィールドの型を正しく
読めば既に決着していたものであり、新しい決定ではなく`startAt`の`description`への明確化の追記で
足りると判断した。

### 決定5. 候補画面ヘッダーの「会」導線・バッジを契約化する

`Handoff.dc.html`の案B（採用）に基づき、`gathering-scheduling-browser-interface.yaml`へ新規名前
空間`organizerGatheringList`・`organizerGatheringCreate`を追加し、`gathering-list`・
`gathering-list-item`・`gathering-list-empty`・`gathering-create-open`・`gathering-create-*`の
観測面を定義した。候補日追加フォーム（決定6参照）とあわせ、既存の`addCandidateDateOpen`が指して
いた「まだ承認された画面を持たない」状態（`ADR-0036`未決事項2）を解消した。

### 決定6. 候補日追加インラインフォームを契約化する

`AddDate.dc.html`の人間裁定（案A: その場に開くインライン）に基づき、
`organizerDashboard.candidateDateList.addCandidateDateOpen`が開く先を、`gathering-add-candidate-
date-form`・`gathering-add-candidate-date-input`・`gathering-add-candidate-date-submit`／
`-cancel`として定義した。フォームは提出成功後も閉じない（「足したあとフォームは閉じない」という
人間裁定の言明どおり）——閉じるのはキャンセル操作のときだけである。重複拒否（決定3）時は入力値を
保持したままフォームを開いたままにする。

### 決定7. `candidate-search-browser-interface.yaml`への追補は最小限にとどめる

候補画面ヘッダーの「会」ボタンとバッジの観測面を、既存の承認済み契約（v1.6.0）へ次の最小限の
追補として加えた（v1.7.0）。

- `candidate-gathering-entry`（導線本体）を、`<button>`でも`role="button"`でもない素の`<a href>`
  （または`candidate-map-open`と同じ様式のtabindex付き`<div>`）として定義した。これにより、
  `unavailableControls.allCandidateScreenFormControlsMustDeclarePurpose`の走査対象
  （`forbiddenFormControlCategories`が拾う要素・role）に該当せず、新しい`allowedPurposes`
  エントリを追加する必要がない——`Handoff.dc.html`自身がこの設計（素の`<a>`を使えば44pxの当たり
  判定は運用上の約束として満たしつつ`role="button"`を避けられる）を明示的に検証済みであり、
  `candidate-origin-marker`・`candidate-map-open`の既存の「表示専用/ナビゲーションのみ」様式を
  そのまま再利用する。
- `candidate-gathering-entry-badge`（件数バッジ）は`data-in-progress-gathering-count`属性を持ち、
  件数が0のときは存在しない（`Handoff.dc.html`: 「0のときはバッジを出さない」）。値は
  `gathering-scheduling-api.yaml`の`getInProgressGatheringCount`から得る——これが
  `Handoff.dc.html`が指摘した「2つの機能が初めて結合する」点であり、新規の
  `gatheringEntry.crossContractReference`節でこの結合を明示した。`candidate-search-api.yaml`
  自体は変更していない（件数は候補提案の応答に含めない）。
- この導線を活性化しても、候補提案・選択・絞り込み・基点・探索範囲のいずれも変わらない——
  `unavailableControls.locationRangeControlProhibition`の振る舞いベースの例外条件（識別子ではなく
  活性化の結果で判定する）を満たす、純粋なページ間遷移として`browserActions.openGatheringEntry`を
  定義した。

**「最小限にとどめる」という判断そのものについて**: これは第7回のタスク依頼が明示的にarchitectの
裁量へ委ねた点である。既存の1.6.0契約は多数の`renderModes`・`filterPanel`・`deckNavigation`等の
確立した節を持つ大きな承認済み契約であり、会スコープの都合でその構造を変える理由は無い。追加した
のは`authenticatedInitialOutcome.present`への1エントリと、新規の独立した`gatheringEntry`節のみで
ある——既存のどの節（`browserControlSurface`・`unavailableControls`・`browserActions`等）の中身も
書き換えていない。

### 決定8. 候補デッキの見た目調整3件は契約影響なしと確認する

人間裁定の(4)〜(6)（PCカードレイアウト案Bの空き場所確保、候補デッキの件数ページャー、スマホでの
カード高さ削減）について、designer自身が契約条件を確認済みであり、architectとしても
`contracts/candidate-search-browser-interface.yaml`の変更を要しないことを確認した。唯一の制約
——PCカード案Bが作る空き場所に`candidate-card-payment-caution`のtest idを付けないこと——は、
同ファイルの`cardDataAttributes.cardPaymentCaution.presenceRule`が既に強制している
（`cardPaymentAvailable`が実際に`false`の候補にだけ存在を許す）ため、この一文を同presenceRuleの
説明へ追記する形で足りると判断し、契約の実体は変更していない。

## 検討した代替案

- **`getInProgressGatheringCount`を新設せず、候補画面が`listGatherings`を取得して自前で数える**:
  却下。バッジ1個の値のために全会の一覧（候補日・回答数等を含む完全なレコード）を取得するのは
  過剰であり、`listGatherings`のレスポンスサイズは会の総数に比例して増え続ける一方、バッジが必要と
  するのは整数1個である。
- **候補日の重複を許容する**: 却下（決定3）。同一日時の候補日が複数存在すると、参加者の回答画面・
  幹事の分母計算のいずれにも意味のある区別がつかなくなる。
- **時刻を任意入力にする**: 却下（決定4）。`startAt`の型（`date-time`）が既に時刻を要求しており、
  時刻だけを独立に任意にする設計は既存のスキーマと矛盾する。
- **`candidate-gathering-entry`を`role="button"`付きの要素にする**: 却下（決定7）。
  `allCandidateScreenFormControlsMustDeclarePurpose`の走査対象になり、新しい`allowedPurposes`
  エントリと`data-candidate-control-purpose`の宣言が必要になる——`Handoff.dc.html`自身がこの
  複雑さを避けるために素の`<a>`を選んだ理由と同じである。
- **designerが提案した`gathering-list-item-phase`を独立のtest idにする**: 却下。
  `gathering-scheduling-browser-interface.yaml`は`gathering-list-item`への`data-gathering-phase`
  属性として同じ情報を表現しており、これで十分観測可能である——designerのtest id提案は「契約では
  ない」（`Entry.dc.html`本文が自ら明記するとおり）ため、既存の属性ベースの様式を優先した。
- **D10のラベル食い違い（案A/案B）を、依頼文とキャンバスのどちらが正しいか判断して1本化する**:
  却下。FR-028は食い違いを解消せず報告することを求めており、architectがどちらのラベルが「正しい」
  かを裁定する立場にはない。採用した内容（下書き局面の廃止）自体は依頼文・キャンバスの両方が
  一致して指す同じ結論であり、実装上の混乱は無い——混乱するのはラベルの呼称だけである。

## 帰結

- `contracts/gathering-scheduling-api.yaml`（更新、`version` 0.2.0→0.3.0、ステータス: 承認待ち）:
  `listGatherings`・`getInProgressGatheringCount`・`GatheringListResponse`・
  `InProgressGatheringCountResponse`を新設。`Gathering.createdAt`を追加。`DUPLICATE_CANDIDATE_DATE`
  エラーコードと`createGathering`・`addCandidateDate`の409レスポンスを追加。`GatheringPhase`・
  `CandidateDateInput.startAt`の`description`を明確化した（決定1・4）。
- `contracts/gathering-scheduling-browser-interface.yaml`（更新、`contractVersion` 0.2→0.3、
  ステータス: 承認待ち）: `organizerGatheringList`・`organizerGatheringCreate`名前空間、
  `addCandidateDateForm`、関連の`browserActions`・`allowedPurposes`・`verifiesScenarios`を追加した。
- `contracts/gathering-scheduling.feature`（更新）: TDR-GTH-21〜25を追加した。既存シナリオ
  （TDR-GTH-01〜20）の本文は変更していない。
- `contracts/candidate-search-browser-interface.yaml`（更新、`contractVersion` 1.6.0→1.7.0、
  ステータス: 承認済みだった本体に対する未承認の追補）: `candidate-gathering-entry`を
  `authenticatedInitialOutcome.present`へ追加し、新規`gatheringEntry`節を追加した（決定7）。
  `cardDataAttributes.cardPaymentCaution.presenceRule`の説明へ、決定8の申し送りを1文追記した。
- `product-brief.md`: §2の状態機械を3局面へ改め（決定1）、§2「幹事ダッシュボード」・§6・§8・§9へ
  本ADRの経緯を反映した。
- `adr/0036-adopt-gathering-scheduling-browser-interface-contract.md`: 未決事項2（候補日追加
  フォームの画面）・3（リンク管理面の画面が正規パイプライン未通過）を、本ADRへの参照とともに決着
  として記録した（決定・検討した代替案・帰結の本文はP-06に従い変更していない）。
- `ARCHITECTURE.md`・`design.md`: 変更しない——本ADRは既存スライスの契約追補であり、モジュール
  境界・依存方向を変えていない。

## 未決事項（次工程・人間への申し送り）

1. **D10のラベル食い違い（決定・検討した代替案を参照）**: 依頼文は採用内容を「案A」と呼んだが、
   `Entry.dc.html`のD10決定表では同じ内容が「案B」の列にある。実装は内容（下書き局面の廃止）で
   一致しており動作上の問題は無いが、今後この裁定を引用する際にどちらのラベルを正式とするかは
   人間の確認待ちとする。
2. **`ADR-0035`から持ち越し、引き続き未決**: 会データの保持期間・削除方針、署名付きリンクの
   有効期限日数・レート制限の具体値（いずれも根拠の薄い暫定値）。
3. **候補画面ヘッダー・バッジのデザインはdesignerパイプラインを未通過**: `Handoff.dc.html`は
   `E:\AWS\dsg-out\Desktop.dc.html`・`Mobile.dc.html`を出発点にした入力用の板であり、
   「designer は実機も本番のスクリーンショットも見ていない」（同ファイル本文）。本ADRが契約化した
   観測面は、正規パイプラインでこの画面が描き直され人間が承認された後、必要であれば追補する
   （`ADR-0013`と同じ順序）。
