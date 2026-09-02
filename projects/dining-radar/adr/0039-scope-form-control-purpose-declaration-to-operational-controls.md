---
id: 0039
scope: project/dining-radar
status: 提案中
date: 2026-09-02
approved_by: null
supersedes: []
superseded_by: null
relates_to: [P-06, P-08, ADR-0013, ADR-0036, ADR-0038]
---

# ADR-0039: フォームコントロールのpurpose宣言義務を「操作的コントロール」に限定し、値入力コントロールの適用範囲を明確化する

> **承認者向けサマリ**: 統合PRの合流でdeveloperが`gathering-scheduling-browser-interface.yaml`
> v0.3を実装したところ、FR-028経由で契約の穴が1件確定した——素の値入力欄
> （`gathering-create-name-input`・`gathering-create-candidate-date-input`・
> `gathering-add-candidate-date-input`）が横断検査
> `assert_gathering_screen_has_no_forbidden_surfaces`（`allGatheringScreenFormControlsMustDeclare
> Purpose`の機械化）に引っかかるが、`allowedPurposes`の語彙が動詞的な操作名だけで構成されており、
> 値をただ保持するだけの入力欄に対応する語彙が無かった。本ADRはこれを、architectの技術判断として
> （人間のチャット裁定を経ずに）決着させる——`meta/adr/0064`の作法に従い`status: 提案中`・
> `approved_by: null`とし、人間のレビュー対象として記録する。
>
> **採った解決**: developerが提示した2案のうち、(a)「該当3件へ`formControl: false`相当の除外宣言を
> 個別に追加する」ではなく、(b)を発展させた第3の形——**「操作的コントロール」と「値入力コントロール」を
> 契約上区別し、後者を`allGatheringScreenFormControlsMustDeclarePurpose`の対象外とする、ただし
> 追跡可能性（`valueEntryControlTestIds`への登録＋消費先の操作的コントロールの明記）を条件とする**
> ——を採用した。単純な`formControl: false`の個別付与は、実際には正真正銘のフォームコントロールで
> ある値入力欄を「フォームコントロールではない」と偽って回避する形になり、`candidate-gathering-entry`
> （実際に`<a>`要素でありフォームコントロールではない）に使った同フラグの意味と衝突する——将来、
> 本当は監査すべき隠れた入力欄まで同じフラグで覆い隠せてしまう先例になりかねない。今回の設計は、
> 個々の値入力欄を「フォームコントロールである」と認めたまま、購入義務（purpose宣言）の適用範囲
> そのものを、この規則の起源（`ADR-0013`: 全操作を`allowedPurposes`と突き合わせ、隠れた操作を
> 許さない）に照らして「操作」に限定し、値入力欄については「どの操作がこの値を消費するか」を
> 契約内に明記することを条件に対象外とした——これにより将来の値入力欄（参加者の名前入力など）にも
> 一貫して同じ規律が及び、かつ追跡できない値入力欄は従来どおり一般則の対象に残る。

## 文脈

### 1. 何が起きたか

`gathering-scheduling-browser-interface.yaml` v0.3は、`organizerGatheringCreate`
（`gathering-create-name-input`・`gathering-create-candidate-date-input`）と
`candidateDateList.addCandidateDateForm`（`gathering-add-candidate-date-input`）の観測面を
`ADR-0038`で追加した。統合PRでdeveloperがこれを実装したところ、横断検査
`assert_gathering_screen_has_no_forbidden_surfaces`（`unavailableControls.
allGatheringScreenFormControlsMustDeclarePurpose`の機械化）が、この3件の素の値入力欄に対して
`data-gathering-control-purpose`の宣言を要求し、失敗した。

developerの分析は正確である——`allowedPurposes`の17件（`gathering-add-candidate-date-open`・
`gathering-create-submit`等）はいずれも動詞的な操作名であり、「会の名前を保持するだけの入力欄」
「候補日の日時を保持するだけの入力欄」に対応する語彙が無い。developerはネイティブ`<input>`を
使わない回避（走査を欺く改悪）を明示的に不採用とした——architectもこれに同意する。この判断自体は
本ADRの対象ではない。

### 2. developerが提示した2案

1. 該当3件に`formControl: false`相当の除外宣言を契約に追加する。
2. `allGatheringScreenFormControlsMustDeclarePurpose`の対象を操作的要素に限定する一文を追加する。

依頼は「将来の値入力欄（参加者の名前入力等、participantAnswer側に既にある）にも一貫して効く形」を
選ぶことを明示的に求めた。

### 3. `candidate-search-browser-interface.yaml`の同種ルールの現状確認

`candidate-search-browser-interface.yaml`は`forbiddenFormControlCategories`に`input`を含め、
`allCandidateScreenFormControlsMustDeclarePurpose: true`を要求する——`gathering-scheduling-
browser-interface.yaml`が今回まで`forbiddenFormControlCategories`を明示していなかったのとは対照的
である。ただしTDR-CSは自由入力欄（テキスト入力）を1つも持たない——`forbiddenPurposes`が
`free-text-search`を明示的に禁止しており、検索条件はすべて選択式（ジャンル選択・トグル・予算段階
選択等）である。したがって「値をただ保持するだけの入力欄」問題は、TDR-CSでは製品判断（自由入力
検索を禁じる）によって最初から発生しない設計になっていた——顕在化しなかったのは、この規則が値入力
欄の扱いを正しく想定していたからではなく、値入力欄そのものが存在しなかったからである。

`candidate-search-browser-interface.yaml`には`semanticAttributes.controlCategory`
（`data-candidate-control-category`）という、purposeとは別の「カテゴリ」属性の枠組みが既にあるが、
実際の使用例（`data-candidate-control-category`の値は既存箇所でいずれも`"button"`）は値入力欄と
操作的コントロールを区別する目的では使われていない。`candidate-gathering-entry`
（`ADR-0038`が追加）が使う`formControl: false`は、この要素が実際には`<button>`でも`role="button"`
でもない素の`<a>`であることに基づく——「フォームコントロールという事実に反する主張」ではなく、
「事実としてフォームコントロールではない」ことの宣言である。これは今回の値入力欄3件とは性質が
異なる——値入力欄は実際にネイティブ`<input>`であり、フォームコントロールという事実そのものは
否定できない。

### 4. `gathering-participant-name-input`の現状

`participantAnswer.nameControl`は`status`（`gathering-participant-name-status`）・`open`
（`gathering-participant-name-open`）・`submit`（`gathering-participant-name-submit`）を
構造化して定義していたが、`gathering-participant-name-input`自体は`open.requiredOutcome`の
説明文中に登場するだけで、`browserControlSurface`上の構造化されたtestId宣言（`testId:`キーを
持つ独立のエントリ）を持っていなかった。この横断検査が実際にparticipantAnswer画面へ対しても
走っているかどうかは本ADR起草時点で未確認であり、「意図して免除されている」のか「単に検査対象と
して認識されず素通りしている」のかが区別できない状態だった——依頼文もこの点の確認を明示的に
求めている。

## 決定

### 決定1. 「操作的コントロール」と「値入力コントロール」を契約上区別する

`unavailableControls.allGatheringScreenFormControlsMustDeclarePurpose`が要求するpurpose宣言は、
**操作的コントロール**——自身の活性化がこの契約のどこかのrequiredOutcomeの引き金になる要素
（`allowedPurposes`の17件がすべてこれに該当する）——にだけ及ぶと明確化する。**値入力コントロール**
——値を保持するだけで、その値の消費は別の操作的コントロール（通常はsubmit）のrequiredOutcomeが
引き受けるネイティブ`input`（text/date/time/datetime-local/number）・`textarea`——は対象外とする。

無条件の免除ではない。値入力コントロールが免除されるのは、次の2条件を同時に満たす場合に限る。

1. そのtestIdが新設した`unavailableControls.valueEntryControlTestIds`に列挙されていること。
2. `browserControlSurface`内で、どの操作的コントロールのrequiredOutcomeがこの値を消費するかが
   明記されていること。

この2条件が揃わない値入力コントロールは、従来どおり一般則（purpose宣言必須）の対象のままである。
これにより、「無条件に値入力欄を素通りさせる」設計にはならない——`ADR-0013`が確立したこの規則の
起源（全操作を`allowedPurposes`と突き合わせ、隠れた操作を許さない）を、値をただ保持するコントロール
にまで機械的に広げすぎていた部分だけを是正しつつ、追跡不能な新規入力欄が無審査で紛れ込む余地は
残さない。

`select`・`checkbox`・`radio`・`combobox`・`listbox`・`range`・`slider`・`spinbutton`・`button`、
および対話的ARIA roleを持つ要素は、この免除の対象外のままとする——これらは既知の選択肢群から選ぶ
操作、またはそれ自体が操作であり、`candidate-search-browser-interface.yaml`の`*-selection`・
`*-toggle`系purposeが示すとおり、既に有意味なpurpose語彙を持てる。

### 決定2. developerの案(a)（個別`formControl: false`）を不採用とする

`candidate-gathering-entry`が使う`formControl: false`は「実際にフォームコントロールではない」
という事実の宣言である。今回の3件の値入力欄は実際にはネイティブ`<input>`であり、同じフラグを
付与すると「フォームコントロールである」という事実と矛盾する宣言になる——将来、監査すべき隠れた
入力欄までこの同じフラグの下に紛れ込ませる先例を作りかねない。決定1の「操作的/値入力の区別＋
追跡可能性の条件」のほうが、事実に反する宣言を要求せずに同じ問題を解決できる。

### 決定3. `forbiddenFormControlCategories`を本契約にも明示する

`gathering-scheduling-browser-interface.yaml`はこれまで、横断検査が実際にどの要素種別を走査
対象とするかを本ファイル単体では明示していなかった（`candidate-search-browser-interface.yaml`は
明示している）。今回、同じ列挙（`select, input, textarea, checkbox, radio, range, combobox,
listbox, slider, spinbutton, button`、共有testerDSLの`FORM_CONTROL_SELECTOR`と一致）を本契約にも
明記した——この穴が起草時点で見えなかった一因は、この暗黙の前提が本ファイルから読み取れなかった
ことにもある。

### 決定4. `gathering-participant-name-input`を同じ規律のもとに置く

`participantAnswer.nameControl`へ`input`エントリ（`testId: gathering-participant-name-input`）を
新設し、`valueEntryControlTestIds`へ追加した。消費先の操作的コントロールは`nameControl.submit`
（`gathering-participant-name-submit`）であり、その`requiredOutcome`にこの値を消費する旨を明記した。
これにより、この入力欄が「意図して免除されている」状態に変わり、「たまたま検査に引っかかって
いないだけ」という不確定な状態を解消した——依頼文が求めた「一貫して効く形」を、既存の入力欄1件へも
遡って適用したことになる。

## 検討した代替案

- **developer案(a): 該当3件へ`formControl: false`を個別に追加する**: 却下（決定2）。事実に反する
  宣言であり、将来の隠れた入力欄を覆い隠す先例になる懸念がある。
- **`allowedPurposes`へ`text-entry`のような汎用的な1エントリを追加し、すべての値入力欄がこれを
  宣言する**: 却下。これは実質的にpurpose宣言義務を無内容化する——「何であれtext-entryと書けば
  通る」状態は、`allowedPurposes`が個々の操作を名指しで列挙するという本来の設計（`ADR-0013`の
  起源）と噛み合わない。値入力欄が「宣言不要」であることを明示するほうが、無内容な宣言を強制する
  よりも正直である。
- **`data-gathering-control-category`のような新しいDOM属性を追加し、実行時にカテゴリを機械観測
  する**: 却下（過剰）。`candidate-search-browser-interface.yaml`の`semanticAttributes`はこの
  枠組みを持つが実際にはほぼ使われておらず（値はすべて`"button"`）、今回の問題は契約
  （どの値入力欄がどの操作に紐づくか）を明記すれば足り、新しいDOM属性・実行時契約を追加する
  必要はない。
- **`gathering-participant-name-input`の扱いを本ADRでは触れず、既存のまま放置する**: 却下。
  依頼文が明示的にこの入力欄の現状確認と整合を求めており、「意図して免除」と「たまたま検査対象外」
  を区別しないままにすることは、本ADRが解決しようとしている監査の穴をこの1件について未解決の
  ままにする。

## 帰結

- `contracts/gathering-scheduling-browser-interface.yaml`（更新、`contractVersion` 0.3→0.4、
  ステータス: 承認待ち）: `unavailableControls`へ`forbiddenFormControlCategories`・
  `operationalControlScope`・`valueEntryControlTestIds`・関連のnoteを追加した。
  `organizerGatheringCreate.nameInput`・`candidateDateRow.dateInput`・
  `candidateDateList.addCandidateDateForm.dateInput`の各エントリへ`valueEntryControl`の説明を
  追加した。`participantAnswer.nameControl`へ`input`エントリを新設した。関連する
  `requiredOutcome`本文へ、どの値入力欄がどの操作に消費されるかの明記を追加した。
- `contracts/gathering-scheduling-api.yaml`・`contracts/gathering-scheduling.feature`は変更して
  いない——本ADRは業務behaviorを変えないtest infrastructure層の観測契約の是正にとどまる
  （`ADR-0013`が確立した「control-surfaceの是正は業務契約に触れない」という前例のとおり）。
- `product-brief.md`・`ARCHITECTURE.md`・`design.md`は変更しない。
- tester側の横断検査（`assert_gathering_screen_has_no_forbidden_surfaces`）の実装追随は、本ADRの
  完了後にorchestratorが指示する（依頼文のとおり、本ADRの範囲外）。

## 未決事項（次工程・人間への申し送り）

1. 本ADRはarchitectの技術判断であり、人間のチャット裁定を経ていない（`meta/adr/0064`書式に従い
   `status: 提案中`・`approved_by: null`とした）。決定1〜4の設計そのものに異論があれば、人間の
   レビューを経て`承認済み`へ改める。
2. `candidate-search-browser-interface.yaml`の`semanticAttributes.controlCategory`
   （`data-candidate-control-category`）は、本ADRの`operationalControlScope`と概念的に重なる
   枠組みを既に持ちながら実際には使われていない。両契約間でこの概念を将来統一するかどうかは、
   本ADRでは決めない——TDR-CSが自由入力欄を持たない以上、今この統一を急ぐ必要はないと判断した。
