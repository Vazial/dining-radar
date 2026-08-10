---
id: 0019
scope: project/toyama-dining-radar
status: 承認済み
date: 2026-08-09
approved_by: "本PRのマージをもって承認（ADR-0035方式(i)の準用。人間裁定 2026-08-09 chat、実データの
  フィールド調査を踏まえた所感: 『近さ・ジャンル・禁煙は良い切り口』『予算感・総席数は加工が必要そうな
  参考情報』『cardが不可なら現金のみの可能性を注意として教えたほうがいい』。orchestratorが提示した3つの
  注意点（ディナー予算からのランチ推論は不確定な断定になる／席数の多さと予約の取りやすさは無関係／
  GENRE_VARIETYは実データの縮退を理由に廃止済み）を踏まえ、具体の切り口設計・境界・却下項目は
  architectの翻訳判断に委ねられている。同日、architectが予算感を全面却下したドラフトを
  orchestrator経由で確認した人間は『ざっくりの段階表示ができるなら入れてほしい』と再確認・差し戻した
  （決定8参照）。本ADRはこの差し戻しを反映した最終稿である"
supersedes: []
superseded_by: null
relates_to:
  [P-01, P-02, P-04, P-05, P-06, P-08, P-10, TDR-CS-01, TDR-CS-02, TDR-CS-03,
   TDR-CS-04, TDR-CS-09, TDR-CS-10, TDR-CS-12, ADR-0002, ADR-0004, ADR-0005,
   ADR-0008, ADR-0011, ADR-0015, ADR-0016, ADR-0017]
---

# ADR-0019: 実データのフィールド調査を反映し、切り口をジャンル・禁煙中心へ組み替え、席数・予算感を目安表示へ、カード可否を注意表示へ、アクセスをカードから外す

> **承認者向けサマリ**: orchestratorが実データ64件で行ったフィールド調査（一回限りの診断。実店舗名・
> 住所・座標は取得も記録もしていない）を受け、人間が「近さ・ジャンル・禁煙は良い切り口」「総席数・
> 予算感・card可否は加工すれば参考情報として使える」という所感を示した。本ADRはこれを次のとおり契約へ
> 翻訳する。**当初のドラフトは予算感を全面却下したが、その根拠の一部が循環していたことをorchestratorが
> 指摘し、人間が再確認のうえ差し戻した（決定8）。本文は差し戻し後の最終判断を反映する。**
>
> **(1)** `ConceptKind`を`PROXIMITY`・`GENRE_FOCUS`（新規）・`NON_SMOKING_REFERENCE`（新規）・
> `IZAKAYA_BAR_INCLUDED`（既存）の4種へ組み替える。`CAPACITY_REFERENCE`・`AMENITY_REFERENCE`は廃止する
> ——後者は実データで構成要素（個室5件・座敷5件・掘りごたつ4件等）が薄く切り口として機能しないと
> 判明したため（背景で供給された事実）、前者は人間の発言そのもの（「わざわざ数値でソートする意味は
> ない」）が示すとおり、比較の切り口としての価値を人間自身が否定しているためである。**4種を維持する
> ことで、`reProposalOptions.maxItems: 3`（表示中1つを除いた残りが常に3つ以下）という構造的制約を
> 一切変更せずに済む**——`ConceptKind`の追加・削除がこの容量制約と衝突しないかを確認することは、
> FR-010・FR-011がこのプロジェクトに残した明示的な申し送りであり、本ADRはその確認を実行した結果として
> 4種を選んでいる。予算感（decision 8）も切り口にはせず、この4種の構成に影響しない。
>
> **(2)** `GENRE_FOCUS`は、既定母集団の中で最多のジャンル1つに絞り込み、近い順に並べる。**この母集団は
> `PROXIMITY`の母集団の真部分集合になることが構造上保証され**（成立するのは既定母集団に2種類以上の
> ジャンルがある場合だけで、そうでなければこの切り口自体を提示しない）、`GENRE_VARIETY`が実データで
> 犯した「`PROXIMITY`と完全に同じ集合・同じ順序を返す」という失敗（ADR-0016）を構造的に再発させない。
>
> **(3)** `NON_SMOKING_REFERENCE`は、禁煙区分（全面禁煙／一部禁煙／禁煙席なし、実データで100%充足かつ
> 分布あり）を第一の並び順とし、近さを第二の並び順とする。既定母集団に2種類以上の禁煙区分がある場合
> だけ提示する。`AMENITY_REFERENCE`を置き換える。
>
> **(4)** 総席数は比較の切り口から外し、すべてのカードに常時示す「規模の目安」（少なめ／標準／多め、
> 暫定しきい値: 20席以下／21〜60席／61席以上）に変える。「予約のとりやすさ」という言葉・含意は一切
> 使わない——orchestratorが提示した注意点2（席数の多さと予約可否は無関係）をそのまま採用する。生の
> `totalSeats`はAPIに残すが、可視のカード表示は目安ラベルに変わる（ADR-0011の「可視整形と生値の等価性
> 検査を分離する」機構を、totalSeats以外にも初めて適用する）。
>
> **(5)** `card`（カード利用可否）は切り口にも比較材料にもしない。利用不可のときだけ、カードに「クレジット
> カードは利用できません」という確認済み事実だけの注意を出す。**「現金のみ」とは断定しない**——`card`が
> 追跡するのはクレジットカード可否のみであり、電子マネー等の他の決済手段を含まないため、現金限定という
> 主張は`card`フィールドが裏づけない推論である（orchestratorが提示した注意点1と同型の判断）。
>
> **(6)** アクセス（`access`）はカード・APIから完全に外す。地図が同じ情報を代替し、実測でもカードの
> 1フィールドとして無視できない高さを占めていた（人間の先行する指摘）。
>
> **(7)** `band`・`karaoke`・`show`・`pet`・`tv`・`english`・`free_food`・`barrier_free`・
> `horigotatsu`・`tatami`・`private_room`（片側に極端に偏る）、`sub_genre`（38%欠落）、
> `wedding`・`charter`・`parking`（自由記述が汚い。`parking`は実店舗名を含む例が観測された——将来
> raw値をそのままbrowserへ返す設計を検討する際の注意点として記録する）、`small_area`/`middle_area`/
> `large_area`（場所を示す）、`midnight`（ランチ会に無関係）、`budget_memo`（充足率30%、自由記述）は、
> いずれも切り口・表示項目として採用しない。
>
> **(8)** 予算感（`dinnerBudgetTier`）は、**ディナー予算をディナー予算と明示したうえでの粗い3段階
> （少なめ／標準／多め相当。暫定しきい値: 〜2,000円／2,001〜4,000円／4,001円〜）として採用する**。
> ランチ価格の推論・断定は一切行わない。切り口にはせず、`capacityTier`と同じくカードの常時表示項目
> とする。**当初のドラフトはこれを全面却下したが、その却下理由が部分的に循環していた**（`product-
> brief.md`の除外記述として引用した文の一部が、今回のセッションで私自身が書き足しADR-0019を根拠に
> していた）ことをorchestratorが指摘し、人間が「ざっくりの段階表示ができるなら入れてほしい」と再確認・
> 差し戻したため、この判定に改めた（決定8で経緯と訂正を記録する）。
>
> 契約への波及: `candidate-search-api.yaml`（v0.9.0）・`candidate-search.feature`
> （`TDR-CS-02`改訂、新規`TDR-CS-12`）・`candidate-search-browser-interface.yaml`（v0.7）・
> `test-support-api.yaml`（v0.7.0）の4ファイル。`design.md`・`ARCHITECTURE.md`・`product-brief.md`も
> 更新する——`product-brief.md` §3・§7の改訂は**人間の再承認点**であり、承認の実体は本PRのマージで
> ある。friction-logには、循環した却下理由の訂正をFR-012として新規記録する（決定13）。

## 文脈

### 0. 検証の申告（meta/adr/0039）

このADRが依拠するフィールド分布の数値（充足率・分布・偏り）は、**すべてorchestratorが実データ64件に
対して行った一回限りの診断から供給されたものであり、私（architect）自身が取得・測定したものではない**。
私はBashもWebFetchも持たず、Hot Pepperの生レスポンスを見ていない。実店舗名・住所・座標はorchestrator
自身も記録していないと明言しており、私もそれらを一切受け取っていない。本ADRが提案するしきい値
（席数の少なめ／標準／多め区分の境界値、予算感の少なめ／標準／多め区分の境界値、ジャンル絞り込みの
「最多ジャンル」判定）は、この一回限りの診断結果に基づく**暫定値**であり、統計的に厳密な区分ではない。
将来より多くの実データが得られた時点で見直すべきものとして扱う（decision 4・8・9参照）。

govlintの実行はorchestratorに委ねる（私はBashを持たない）。本ADRが変更する契約ファイルのステータス行・
frontmatter形式は、meta/adr/0035・meta/adr/0043の機械検証要件に従って記述したが、実行による確認は
していない。

### 1. 何が供給されたか（orchestratorの調査結果、要約）

実データ64件のうち、**充足率100%かつ分布が実際に候補を割れるフィールド**は `genre`（居酒屋24件ほか
8ジャンル）・`capacity`（11〜200、中央値50）・`non_smoking`（全面禁煙37・一部禁煙14・禁煙席なし13）・
`card`（利用可48・利用不可16）・`budget`（1,501〜2,000円: 18、2,001〜3,000円: 11、3,001〜4,000円: 19、
4,001〜5,000円: 10、5,001〜6,000円: 4、6,001〜7,000円: 1、7,001〜8,000円: 1）・`child`・`course`・
`free_drink`。片側に極端に偏り切り口として弱いフィールド（`band`・`karaoke`・`show`・`pet`・`tv`・
`english`・`free_food`・`barrier_free`・`horigotatsu`・`tatami`・`private_room`)、使えないフィールド
（`sub_genre`・`wedding`・`charter`・`parking`・`small_area`/`middle_area`/`large_area`・
`midnight`）が個別に報告された。**現在の`AMENITY_REFERENCE`が合算する`private_room`・
`non_smoking`・`parking`・`wifi`・`barrier_free`のうち、`non_smoking`以外はいずれも片側に極端に
偏るか使えないと判明した**——`AMENITY_REFERENCE`が実データで機能しない理由の実体である。`budget`は
`code`・`name`・`average`・`budget_memo`の4フィールドを持ち、`budget_memo`だけは充足率30%で内容が
「お通し代：有り」「17時以降チャージ料あり」等の自由記述だと個別に報告された。

### 2. 人間の指摘と方向（2026-08-09、チャット）

> 「近さ」「ジャンル」「禁煙」は良い切り口（そのままのデータとして使える）
>
> 「予算感」→ ランチの正確な数値はわからないが、段階に分けて予算感を見せる、もしくは他情報と
> 合わせてランチ1000円以下が見通せれば使えそう
>
> 「総席数」→ わざわざ数値でソートする意味はないが、大中小にできれば使えそう
>
> 「card」→ 利用不可のとき現金のみの可能性を注意として教えたほうがいい（ジャンルではないかも）

先行する同じ会話での指摘: 「地図があるからアクセスの項目はいらないかも」「別の選び方がほぼ機能して
いないね」「画面のレイアウトも合わせて自然なように調整して」。

orchestratorは3つの注意点をこの所感の前に人間へ提示済みである。**(1)** ディナー予算からランチ価格を
見通すことは提供元データが裏づけない推論である。**(2)** 席数の多さから予約の取りやすさを導くことも
推論である。**(3)** `GENRE_VARIETY`は実データの縮退を理由にADR-0016で廃止済みであり、ジャンルを
切り口として戻すなら縮退しない別の組み方が要る。具体の設計・境界・却下は本ADR（architectの翻訳
判断）に委ねられている。

### 3. 差し戻しと訂正（同日、2026-08-09）

当初のドラフトで私は、予算感について人間が併記した2案——(a)「ランチ1000円以下を見通す」推論、
(b)「段階に分けて予算感をディナー予算と明示して見せる」——のうち、(a)は注意点1のとおり不確定な断定に
なるため不採用としたが、**(b)も含めて全面不採用**と判定した。その根拠として`product-brief.md`
§3・§7が「既に持つ明確な除外決定」を挙げた。

orchestratorはこの根拠を検証し、`product-brief.md`のその除外記述のうち「実データのフィールド調査で
価格帯情報自体は取得できることが確認できたが…ADR-0019。理由はADR-0019決定8を参照」という一節が、
**今回のセッションで私自身が書き足したものであり、ADR-0019自身を根拠にADR-0019の結論を正当化する
循環になっていた**ことを指摘した。この事実を人間に提示し、通すか差し戻すかの判断を仰いだ結果、人間は
「ざっくりの段階表示ができるなら入れてほしい」と回答し、決定8を差し戻した。

**独立に実在する制約**: `product-brief.md` §3の原文（このADR以前から存在する文）「価格帯は Hot
Pepper の情報がディナー寄りであるため表示しない」、および §7の「価格帯・ディナー予算の表示」を
除外項目とする記述は、私が今回付け加えた部分を除けば実在する。この除外はADR-0015が確立した
「確認できないことを断定しない」原則に紐づく——価格帯がディナー寄りである以上、これをランチ価格の
指標として使うことはできない、という制約である。決定8はこの実在する制約を破らずに、人間の再確認を
反映する。

## 決定

### 1. `ConceptKind`を4種へ組み替える。総数は変えない

`PROXIMITY`・`GENRE_FOCUS`（新規）・`NON_SMOKING_REFERENCE`（新規）・`IZAKAYA_BAR_INCLUDED`
（既存、変更なし）の4種とする。`CAPACITY_REFERENCE`・`AMENITY_REFERENCE`は廃止する（decision 4・6が
その代替を定める）。予算感（decision 8）も切り口にせず、この4種の構成には影響しない。

**容量制約の確認（FR-010・FR-011への応答）**: `reProposalOptions.maxItems: 3`は、表示中の1つを除いた
残りが常に3つ以下であることを要求する。4種のままであれば、この関係は自動的に満たされる
（4−1=3≤3）。ADR-0016が`GENRE_VARIETY`削除によって確立したのと同じ構造的な安全域を維持するために、
**本ADRは新しい切り口を2つ追加する一方で既存の2つを廃止し、総数を4のまま据え置く**という設計を
意図的に選んだ——`GENRE_FOCUS`と`NON_SMOKING_REFERENCE`をただ追加するだけなら5種になり6−1=4>3で
再びFR-010と同じ容量超過を起こしていた。ADR-0016決定4の申し送り（「将来6つ目の切り口を追加する場合、
追加するarchitectは…確認すること」）を、本ADRはこの形で履行する。`reProposalOptions.maxItems`・
`TDR-CS-03`本文の「3つ以下」はいずれも変更しない。

### 2. `GENRE_FOCUS`: 最多ジャンルへ絞り込み、近い順に並べる。構造的に縮退しない

**判定: ジャンルを切り口として復活させる。** 理由は、実データでの充足率・分布（背景1節）が良好である
という人間の所感を採用しつつ、ADR-0016が`GENRE_VARIETY`を廃止した理由（実データで`PROXIMITY`と完全に
同一の集合・順序に縮退した）を再発させない組み方が可能だと判定したためである。

**アルゴリズム（非拘束の推奨。developerの裁量を残す）**:

1. 既定母集団（`DEFAULT_EXCLUDED_GENRES`を除いた候補、ADR-0015と同じ母集団）の中で、最も件数の多い
   ジャンルを1つ選ぶ。同数の場合の決定的なタイブレークはdeveloperが選んでよい（例: 検索地点から最も
   近い候補が属するジャンルを優先する）。
2. その1ジャンルに属する候補だけを、`PROXIMITY`と同じ近さの基準で並べる。

**説明可能性の条件（Must）**: 既定母集団に含まれるジャンルが2種類未満（すなわち1種類しかない）場合、
この切り口は構成しない。**この条件により、`GENRE_FOCUS`が提示される時は必ず、その候補集合が
`PROXIMITY`の候補集合（既定母集団全体）の真部分集合になる**——`PROXIMITY`は全ジャンルを含み、
`GENRE_FOCUS`は1ジャンルだけを含むため、2種類以上のジャンルが存在する限りこの包含関係は厳密である。
`GENRE_VARIETY`が犯した失敗は「同じ母集団を並べ替えるだけで、たまたま出力の集合と順序が完全一致した」
ことだったが、`GENRE_FOCUS`は**母集団そのものを狭める**ため、同じ失敗の型を構造的に再現しない。

**残存リスク（正直に記録する）**: この保証は「集合が完全一致しない」ことだけを保証し、「体験として
新鮮に感じられる」ことまでは保証しない。たとえば検索地点付近の候補が既に単一ジャンルに極端に偏って
いる場合、`GENRE_FOCUS`が選ぶ「最多ジャンル」がほぼ`PROXIMITY`の上位そのものと重なることはあり得る
——ただしこれは集合が完全一致する`GENRE_VARIETY`の失敗とは異なる種類の弱さであり、今回は受容する。
次の実データレビューでこの切り口の重複率を確認することを、developerではなくorchestratorへの
申し送りとして記録する（帰結節）。

**表示中の切り口名は動的である**: `GENRE_FOCUS`の`title`・`rationale`は、選ばれたジャンル名を埋め込む
（例:「『和食』を中心に探す」）。これは`ReproposalOption.title`/`CandidateConcept.title`の型
（`string`）を変更しない——同じ入力（同じ候補集合）に対して常に同じ出力になる限り、
`ConceptKind.description`が要求する「explainable, deterministic」を満たす。動的文言はこのプロジェクトで
初めてだが、既存スキーマの制約に抵触しない。

### 3. `NON_SMOKING_REFERENCE`: 禁煙区分を第一の並び順にする。`AMENITY_REFERENCE`を置き換える

`AMENITY_REFERENCE`（`private_room`・`non_smoking`・`parking`・`wifi`・`barrier_free`の合算スコア）を
廃止する。背景1節のとおり、構成する5フィールドのうち`non_smoking`以外は実データで片側に極端に偏るか
使えないと判明しており、合算スコアという設計自体が実データでほぼ意味を持たない値になっていた。

`non_smoking`単独は充足率100%かつ実質的な3値分布（全面禁煙37・一部禁煙14・禁煙席なし13）を持つ。
これを単独の切り口`NON_SMOKING_REFERENCE`として独立させる。並び順は禁煙区分を第一キー（全面禁煙 →
一部禁煙 → 禁煙席なし → 不明の順）、近さを第二キーとする。

**説明可能性の条件（Must）**: 既定母集団に含まれる禁煙区分が2種類未満の場合、この切り口は構成しない
——decision 2と同じ理由（区分に変化がなければ並び順の基準が実質的に無意味になり、`PROXIMITY`との
偶然の一致リスクだけが残る）。この条件は`GENRE_FOCUS`のような厳密な部分集合保証は与えない
——`NON_SMOKING_REFERENCE`は母集団を絞り込まず並び替えるだけであり、`AMENITY_REFERENCE`・
`CAPACITY_REFERENCE`と同じ性質のリスク（`PROXIMITY`と偶然に同じ順序になる可能性）を理論上残す。ただし
この可能性は`GENRE_VARIETY`が実際に踏んだ「常に一致する」という系統的な失敗ではなく、特定データでの
偶然の一致にとどまるため、既存の`CAPACITY_REFERENCE`・`AMENITY_REFERENCE`と同水準のリスクとして受容
する。次の実データレビューでの確認をorchestratorへの申し送りとする（decision 2と同様）。

**表示上、禁煙区分自体も見せる**: `AMENITY_REFERENCE`の内部スコア（`amenity_score`）はブラウザへ
一度も返さない設計だったが（`normalize.py`の既存docstring）、`NON_SMOKING_REFERENCE`はこの前提を
変える——並び替えの根拠を利用者が確認できるよう、禁煙区分を新しいカード項目
`nonSmokingStatus`として常時表示する（decision 5参照。すべての切り口で表示し、`NON_SMOKING_REFERENCE`
選択時だけに限定しない——他のフィールドと同じ扱いに揃える）。

### 4. 総席数を切り口から外し、規模の目安（少なめ／標準／多め）へ変える

`CAPACITY_REFERENCE`を`ConceptKind`から廃止する。理由は人間の発言そのもの
——「わざわざ数値でソートする意味はない」——であり、実データの弱さの指摘（`AMENITY_REFERENCE`のよう
な充足率の問題）ではない。**この判断は人間の所感を否定していない**——人間は「大中小にできれば使え
そう」と併記しており、これは切り口（並び替えの基準）としてではなく、**カードに常時示す参考情報**
としての要望である。

新しいCandidateフィールド`capacityTier`（`SMALL`・`MEDIUM`・`LARGE`、`totalSeats`が`null`の時だけ
`null`）を追加する。しきい値は本ADR時点の暫定値とする——**20席以下をSMALL、21〜60席をMEDIUM、
61席以上をLARGE**とする。この境界は、背景1節が報告した範囲（11〜200、中央値50）から導いた区切りで
あり、統計的に厳密な三分位ではない。0節が述べたとおり暫定値であり、より多くの実データが得られた時点で
見直しうる。

**呼び方の制約（Must）**: `capacityTier`のラベル・rationale・APIのdescriptionのいずれも「予約の
とりやすさ」「取りやすそう」という言葉・含意を一切使わない。この目安が示すのは店舗の総席数の規模
だけであり、空席・予約可否とは無関係である（orchestratorの注意点2をそのまま契約に落とす）。可視の
ラベル案（非拘束）: `SMALL`→「少なめ」、`MEDIUM`→「標準」、`LARGE`→「多め」。

生の`totalSeats`は引き続きAPIスキーマに残す（`Candidate.required`のまま）。ただしカードの**可視の値は
`capacityTier`由来のラベルに変わり**、`totalSeats`の生の値は`data-raw-value`属性でだけ機械検証する
——ADR-0011が総席数の単位表示（「38席」）のために確立した「可視整形と生値の厳密等価検査を分離する」
機構を、初めて総席数以外の値（今回は`totalSeats`自身の可視表現がまるごと目安ラベルに置き換わる、より
大きな変形）にも適用する。この機構の再利用そのものが、この種の乖離をL4以前に構造的に防ぐという
ADR-0011の狙いを裏づける。

### 5. `card`は切り口にしない。利用不可の時だけ確認済み事実の注意を出す。「現金のみ」とは断定しない

`card`をいかなる`ConceptKind`にも、いかなる並び替え基準にも使わない——人間自身が「ジャンルではない
かも」と留保しているとおり、これは比較の切り口ではなくカード上の注記である。

新しいCandidateフィールド`cardPaymentAvailable`（`boolean | null`）を追加する。値が`false`の時だけ、
カードに次の注意を出す: **「クレジットカードは利用できません。お支払い方法は店舗にご確認ください。」**
値が`true`または`null`の時は、この注意もいかなる支払い関連の表示も出さない。

**「現金のみ」と断定しない理由（Must）**: `card`フィールドが追跡するのはクレジットカードの可否だけ
であり、電子マネー・QRコード決済など他のキャッシュレス手段を一切カバーしない。「クレジットカードが
使えない＝現金のみ」という推論は、`card`フィールドが裏づけない事実の断定であり、orchestratorが提示した
注意点1（ディナー予算からランチ価格を見通す推論と同型の問題）と同じ種類の誤りになる。ADR-0015が
`lunch`フィールドについて確立した「確認できないことを確定的な否定として書かない」という制約
（`candidate-search-api.yaml`の既存rationale制約、「must not promise…other unavailable facts」）を、
本ADRは支払い方法にも同じ厳格さで適用する。したがって注意文は「クレジットカードは利用できません」
という確認済みの事実だけを述べ、支払い手段の推測（現金のみ等）を一切含めない。

`product-brief.md` §7は現在「現金のみ・PayPay可否などの支払方法も、信頼できる取得項目がないため
表示・絞り込みしない」と定めている。この決定は**広い「支払方法」全般**（現金限定の断定、PayPay等の
個別キャッシュレス手段の可否）についてのものであり、今回追加する`cardPaymentAvailable`は
**クレジットカード可否という単一の信頼できる取得項目**を新たに使う。この違いは決定12で
`product-brief.md`への具体的な改訂として反映する——既存の広い除外方針そのものは変更しない
（現金限定の断定、PayPay等の個別可否は今後も表示・絞り込みしない）。

### 6. アクセス（`access`）をカードとAPIから完全に外す

`access`を`Candidate.required`・`properties`から削除する（サーバはこのフィールドをもう返さない。
ADR-0017が`businessHours`について行ったのと同じ扱い——「返すが表示しない」ではなく削除する）。
理由は人間の先行する指摘（「地図があるからアクセスの項目はいらないかも」）そのものである——地図が
既に候補店舗の位置を示しており、`access`の自由記述はその代替情報として冗長である。将来、詳細画面等で
再びこの情報が必要になった場合は、その時点で新しいADRとして再導入すればよく、今回削除しても情報は
失われない（`providerPageUrl`が引き続き詳細確認の導線を保つ）——ADR-0017決定7が`businessHours`削除に
ついて述べた理由と同型である。

### 7. `AMENITY_REFERENCE`が使っていた他のフィールドと、その他の疎・汚いフィールドは採用しない

`private_room`・`parking`・`wifi`・`barrier_free`は、いずれも背景1節の調査で片側に極端に偏るか
（`private_room`5件・`barrier_free`8件等）、値が汚い（`parking`）と判明した。これらを単独の切り口や
表示項目として新たに採用しない。`parking`の生値には実店舗名を含む例（「あり：富山大和駐車場」）が
観測された——現状の実装はこの生テキストをブラウザへ一度も返しておらず（`_amenity_available`は
可用性の真偽だけを見る)、本ADRもこれを変更しないが、**将来`parking`の生テキストをそのままブラウザへ
返す設計を検討する際は、店舗の駐車場名が実質的に周辺の地名・施設名を開示しうることをADR-0002・
ADR-0004の「生活圏を推測できる情報を出さない」境界に照らして再検討すること**を、developerではなく
将来この分野に触れるarchitectへの申し送りとして記録する。

`band`・`karaoke`・`show`・`pet`・`tv`・`english`・`free_food`・`horigotatsu`・`tatami`（片側に
極端に偏る）、`sub_genre`（38%欠落）、`wedding`・`charter`（自由記述が汚い）、
`small_area`/`middle_area`/`large_area`（場所を示すため使用不可）、`midnight`（ランチ会に無関係）、
`budget_memo`（充足率30%、チャージ料等の自由記述。decision 8参照）も、同様の理由でいずれも採用しない。

### 8. 予算感（`dinnerBudgetTier`）を段階表示として採用する。ランチ価格の推論はしない

**判定の経緯（訂正記録）**: 当初のドラフトで私は、「段階に分けて予算感をディナー予算と明示して見せる」
という人間の併記案を、`product-brief.md` §3・§7が「既に持つ明確な除外決定」を根拠に不採用と判定した。
しかしorchestratorの指摘により、この根拠が部分的に循環していたことが判明した——§3・§7の当該文の
うち「実データのフィールド調査で価格帯情報自体は取得できることが確認できたが…ADR-0019。理由は
ADR-0019決定8を参照」という一節は、今回の作業で私自身が書き足したものであり、**ADR-0019自身を根拠に
ADR-0019の結論を正当化する循環**になっていた。この点を人間に確認したところ、人間は「ざっくりの
段階表示ができるなら入れてほしい」と回答し、決定8を差し戻した（文脈3節）。

**独立に実在する制約の再確認**: `product-brief.md` §3の原文（このADR以前から存在する文）「価格帯は
Hot Pepper の情報がディナー寄りであるため表示しない」、および §7の「価格帯・ディナー予算の表示」を
除外項目とする記述は、私が今回付け加えた部分を除けば実在する。この除外はADR-0015が確立した
「確認できないことを断定しない」原則に紐づく——価格帯がディナー寄りである以上、これをランチ価格の
指標として使うことはできない、という制約である。**本決定はこの制約を破らない**——採用するのは
「ディナー予算をディナー予算と明示したうえでの段階表示」であり、そこからランチ価格を推論・断定する
ことは一切行わない。

**判定: 採用する。**

1. **表示するもの**: `budget`（Hot Pepperの提供元データ、実データで充足率100%）を、ざっくりした
   3段階に丸めて表示する。生の帯（例:「3,001〜4,000円」等7区分）をそのまま出すのではなく、粗い段階
   （人間の言葉「ざっくりの段階表示」）にする。新しいCandidateフィールド`dinnerBudgetTier`
   （`LOW`・`MID`・`HIGH`、`budget`の参照値が無い時だけ`null`）を追加する。

   **暫定しきい値（0節と同じ性質の暫定値）**: 背景1節で報告された分布（1,501〜2,000円: 18、
   2,001〜3,000円: 11、3,001〜4,000円: 19、4,001〜5,000円: 10、5,001〜6,000円: 4、
   6,001〜7,000円: 1、7,001〜8,000円: 1、合計64・充足率100%）から、2,000円と4,000円を境界に
   区切る——**LOW: 〜2,000円（18件）、MID: 2,001〜4,000円（30件）、HIGH: 4,001円〜（16件）**。
   18/30/16というおおむね均等な3分割になる。`capacityTier`の区切り（decision 4）と同じく統計的に
   厳密な三分位ではなく、より多くの実データが得られた時点で見直しうる暫定値である。

2. **ディナー予算であることの明示（Must）**: 可視ラベルには必ず「ディナー」という語（またはそれに
   相当する、ランチではないと明確に分かる語）を含める。可視ラベル案（非拘束）: `LOW`→「ディナー目安
   〜2,000円」、`MID`→「ディナー目安 2,001〜4,000円」、`HIGH`→「ディナー目安 4,001円〜」。APIの
   `description`、カードのラベル文言、いかなるrationale・注意文も、この目安から**ランチ価格を
   推論・断定してはならない**——「ランチはおおむね◯◯円以下」のような文言、ランチ価格のしきい値
   （例: 1000円）への言及は一切禁止する。この禁止はADR-0015が`lunch`フィールドについて確立した
   「確認できないことを断定しない」原則の直接の適用である。

3. **切り口にはしない**: `capacityTier`と同じ扱いとする——`dinnerBudgetTier`は`ConceptKind`の値にせず、
   比較の並び替え基準にも使わない。すべてのカードに常時表示する参考情報とする。人間の発言「段階に
   分けて予算感をみせる」は表示の要望であり、並べ替えの要望ではない。この扱いにより`ConceptKind`は
   4種のまま変わらない（decision 1は無変更）。

4. **`budget_memo`は採用しない**: `budget.budget_memo`（背景1節: 充足率30%、内容は「お通し代：有り」
   「17時以降チャージ料あり」等の自由記述）は、他の疎・汚いフィールド（decision 7）と同じ理由
   ——充足率が低く、内容がディナー営業特有の事情を含む自由記述である——で採用しない。

5. **`rawValueAttribute`機構の3例目への拡張**: `dinnerBudgetTier`の可視ラベルは、生のenum値
   （`LOW`等）とは異なる日本語ラベルになるため、`nonSmokingStatus`（decision 3）・`totalSeats`
   （decision 4）と同じ`rawValueAttribute: data-raw-value`機構を適用し、生のenum文字列を機械検証
   する。

6. **モジュール配置**: `capacityTier`と同じ理由（ランキングに一切関与しない）で、`web`側（例:
   serializer相当の層）が`budget`の生の参照値からしきい値判定を行うことを推奨する（decision 10と
   同じ非拘束の推奨）。`integrations/hotpepper/normalize.py`は`budget.average`（背景1節で報告された
   生フィールド。正確な名称は`ADR-0002`決定7が求める公開運用前の再確認対象であり、本ADRは確定させ
   ない）を読み、`NormalizedCandidate`へ通過させるだけでよい。

7. **カード高さへの影響**: 人間が実測した現状のカード高さ（285px／画面844px、`access`・営業時間を
   外した後の値）には、新しい1行を追加する余地がある。表示形式（独立した行にするか、`totalSeats`や
   `nonSmokingStatus`と同じ行に併記するか）は本ADRでは確定しない——`meta/adr/0021`が定めるとおり、
   画面レイアウトの最終調整はdeveloperの裁量である。ただし、`dinnerBudgetTier`が独立の必須フィールド
   として`Candidate`に追加される以上、**カードのどこかに必ず表示されること**（`requiredFields`への
   追加）はMustとする。

8. **`product-brief.md` §3・§7の改訂は人間の再承認点である**: 決定12で改訂内容を示す。この改訂は
   `product-brief.md`という既に人間承認済みの文書の除外方針を変更するため、契約と同じ扱いの再承認点
   とする——承認の実体は本PRのマージである。

### 9. `normalize.py`が新たに取り込む必要のあるフィールド

developerへの実装申し送りとして、次を記録する（正確な生フィールド名・値の語彙は、
`ADR-0002`決定7・`normalize.py`の既存docstringが求める「公開運用前の再確認」の対象であり、本ADRは
確定させない——0節が述べたとおり、私自身は公式ドキュメントを確認していない）。

- `non_smoking`: 既に`_AMENITY_FIELDS`に含まれ可用性の真偽だけに使われている。新たに、生の文字列
  内容から`FULL`/`PARTIAL`/`NONE`の3値へ分類するロジックが要る（例: 「全面禁煙」を含む→`FULL`、
  「禁煙」を含み「全面」を含まない→`PARTIAL`、それ以外の既知の否定マーカー→`NONE`、未知の値→`null`
  として断定しない）。
- `card`: 新規に取り込む。生の文字列内容（背景1節の実データでは「利用可」「利用不可」の2値が観測
  された）から`boolean | null`へ変換する。「不可」を含む→`false`、「不可」を含まず「可」を含む→
  `true`、それ以外→`null`。
- `budget.average`: 新規に取り込む（decision 8）。生の数値をそのまま`NormalizedCandidate`へ通過させ、
  しきい値判定は`web`側で行う（decision 10）。

### 10. モジュール配置の指針（非拘束、developerの裁量を残す）

- `non_smoking`の3値分類とその内部表現（`NormalizedCandidate`上の新フィールド、例:
  `non_smoking_tier`）は、既存の`amenity_score`と同様に`normalize.py`が計算し、`recommendation`が
  ランキング入力として使う——`non_smoking`が`NON_SMOKING_REFERENCE`のランキング基準である点で
  `amenity_score`と同じ位置づけになる。ただし`amenity_score`と異なり、この値はブラウザへ表示する
  必要がある（decision 3）。`normalize.py`の既存docstring「none of these raw values are ever
  included in a browser-facing Candidate」は、この変更により禁煙区分について成立しなくなるため、
  実装時にこの一文を訂正すること。
- `card`の真偽変換と`budget.average`の通過は、ランキングに一切使わないため、他の非ランキング系
  フィールド（`access`が過去にそうだったように）と同様、`normalize.py`が生成する
  `NormalizedCandidate`の通過フィールドとして扱ってよい。
- `capacityTier`・`dinnerBudgetTier`のしきい値計算（decision 4・8）は、ランキングに一切関与しない
  ため`recommendation`（純粋・フレームワーク非依存という制約を持つモジュール、`ARCHITECTURE.md`）に
  置く必然性がない。`web`の責務（`design.md`・`ARCHITECTURE.md`の「候補表示」）の一部として`web`側
  （例: serializer相当の層）で計算することを推奨する——ただし、しきい値定数は1箇所にまとめ、本ADRを
  参照するコメントを付けること（`DEFAULT_EXCLUDED_GENRES`と同じ規律）。この配置はdeveloperが実装
  時に見直してよい非拘束の推奨である。
- `GENRE_FOCUS`・`NON_SMOKING_REFERENCE`のconcept構築関数、`CAPACITY_REFERENCE`・
  `AMENITY_REFERENCE`関連コード（`_AMENITY_FIELDS`・`_amenity_score`・`_amenity_available`・
  `_build_capacity_reference`・`_build_amenity_reference`・対応する`_TITLES`/`_RATIONALES`
  エントリ・`_PRIORITY_ORDER`内の該当項目、`NormalizedCandidate.amenity_score`フィールド）の
  削除は、developerの実装スライスで行う（帰結節）。

### 11. 契約への波及の判定

- **`candidate-search-api.yaml`**: 変更する。`ConceptKind` enumを4種へ組み替え、descriptionを改訂
  する。`Candidate`から`access`を削除し、`capacityTier`・`nonSmokingStatus`・
  `cardPaymentAvailable`・`dinnerBudgetTier`を追加する（`totalSeats`は残すが description を改訂
  する）。`version`を`0.7.0`から`0.9.0`へ上げる（decision 4・6の分で`0.8.0`、decision 8の差し戻し分で
  さらに`0.9.0`）。
- **`candidate-search.feature`**: 変更する。`TDR-CS-02`のThen節から「アクセス」を外し、総席数・
  禁煙対応・ディナー予算を目安表現に改める。ディナー予算のめやすがディナーの価格であると分かるように
  示されることをThen節に追加する。新規`TDR-CS-12`（カード払い不可の注意）を追加する。**これは人間の
  再承認点であり、承認の実体は本PRのマージである。** 既存の他シナリオ（`TDR-CS-00`・`01`・`03`〜
  `11`）は文言変更なし——`ConceptKind`の中身の変更を`.feature`はそもそも記述していないため
  （ADR-0016決定1と同じ判定）。
- **`candidate-search-browser-interface.yaml`**: 変更する。`requiredFields`から`access`
  （`candidate-card-access`）を削除し、`nonSmokingStatus`（`candidate-card-non-smoking`、
  `rawValueAttribute: data-raw-value`）・`dinnerBudgetTier`（`candidate-card-dinner-budget`、
  `rawValueAttribute: data-raw-value`）を追加する。`totalSeats`のnullBehavior説明を、可視値が
  `capacityTier`由来のラベルになったことに合わせて改訂する。新しい条件付き要素
  `cardPaymentCaution`（`candidate-card-payment-caution`）を追加する。`requestUnavailableEnumLens`の
  参照enum値を`AMENITY_REFERENCE`から`NON_SMOKING_REFERENCE`へ差し替える（廃止された値を参照し
  続けるわけにはいかないため）。`contractVersion`を`0.5`から`0.7`へ上げる。
- **`test-support-api.yaml`**: 変更する。`NORMAL_WITH_REPEAT`の保証を拡張し、既定母集団に2種類以上の
  ジャンル・2種類以上の禁煙区分を含むこと、`cardPaymentAvailable`が`false`の候補と
  `true`または`null`の候補を両方含むこと、`dinnerBudgetTier`が非`null`の候補を少なくとも1件含む
  ことを明記する。`AMENITY_REFERENCE`への参照を`NON_SMOKING_REFERENCE`へ差し替え、この1モードでは
  禁煙区分の変化を持たせず`NON_SMOKING_REFERENCE`自体が構成不能になるようにする
  （`TDR-CS-07`の決定的検証を維持する、decision 3の説明可能性条件をそのまま利用した設計）。
  `version`を`0.5.0`から`0.7.0`へ上げる。

### 12. `design.md`・`ARCHITECTURE.md`・`product-brief.md`・friction-log.mdの判定

- **`design.md`**: 更新する。「切り口（コンセプト）は現在4種類」の記述をPROXIMITY・GENRE_FOCUS・
  NON_SMOKING_REFERENCE・IZAKAYA_BAR_INCLUDEDへ改める。処理の流れに、カード表示専用の派生値
  （`capacityTier`・`cardPaymentAvailable`・`dinnerBudgetTier`）の算出は順位付けに関与しないことを
  明記する。
- **`ARCHITECTURE.md`**: 更新する。`web`モジュールの責務記述に「候補の表示用派生値
  （席数の目安・予算感の目安等）の算出」を含める（decision 10）。`integrations/hotpepper`が新たに
  読む生フィールド（`non_smoking`・`card`・`budget.average`）を反映する。
- **`product-brief.md`**: 更新する。**この改訂は人間の再承認点であり、承認の実体は本PRのマージ
  である**（decision 8-8）。§2のコンセプト例を新しい4種に合わせる。§3の店舗カード項目から
  「アクセス情報」を削り、総席数の記述を目安表現に改め、カード払い不可の注意とディナー予算の目安を
  追加する——価格帯を「表示しない」としていた既存文を、「ディナー予算の粗い段階を、ディナーである
  ことを明示したうえで表示する。ランチ価格は推測・断定しない」という記述に改める。§7の支払方法・
  価格帯の除外記述を、`cardPaymentAvailable`（クレジットカード可否）と`dinnerBudgetTier`
  （ディナー予算の段階表示）という2つの単一の信頼できる項目についてだけ例外を設ける形に改める
  （現金限定の断定、PayPay等の個別キャッシュレス可否、ディナー予算からのランチ価格推測は引き続き
  対象外のまま）。§8の未決事項記述を本ADRの結果に合わせて更新する。
- **friction-log.md**: 決定13で判定する。

## 検討した代替案

- **`ConceptKind`を5種以上にし、`reProposalOptions.maxItems`を引き上げる**: 不採用。ADR-0016が
  「必要な分だけ確定する」（P-02）という理由で見送った同じ変更であり、`TDR-CS-03`の「3つ以下」という
  人間承認済みの業務文言の再承認も要る。総数を4に据え置くことで、この重い変更を避けられた。
- **`IZAKAYA_BAR_INCLUDED`を廃止して枠を空ける**: 不採用。これはADR-0015で人間が明示的に選んだ機能
  であり、今回の会話で人間はこれに一切触れていない。無関係な既存決定を、今回の話題に押し込む形で
  変更しない。
- **`GENRE_FOCUS`を導入せず、「ジャンル」の所感には応えない**: 検討したが不採用。実データの分布
  （背景1節）は良好であり、かつ`GENRE_VARIETY`とは異なる構造的に縮退しない組み方（decision 2）が
  見つかったため、人間の所感に応えられると判断した。
- **カード払い可否を切り口（`ConceptKind`の値）として追加する**: 不採用。人間自身が「ジャンルでは
  ないかも」と留保しており、二値かつ片方が「注意」の性質を持つ情報を独立した比較の切り口として
  並べる意義が薄い。注記として扱う方が忠実な翻訳である。
- **総席数を切り口として残しつつ、ラベルだけ目安表現にする**: 不採用。人間の発言
  「わざわざ数値でソートする意味はない」は、並び替え基準としての価値そのものを否定しており、
  ラベル変更だけでは応えたことにならない。
- **予算感を全面却下する（当初のドラフト）**: 不採用（decision 8参照）。根拠の一部が循環しており、
  人間の再確認で差し戻された。
- **ディナー予算からランチ1000円以下を推測する**: 不採用（decision 8）。確認できない事実の断定に
  なる。この判定は差し戻し後も変わらない。
- **`budget.name`の生の7区分をそのまま表示する**: 不採用。人間の言葉「ざっくりの段階表示」に沿い、
  より粗い3段階（decision 8）へ丸めた。

## 帰結

- `candidate-search-api.yaml`（`v0.9.0`）・`candidate-search.feature`（`TDR-CS-02`改訂、
  `TDR-CS-12`追加）・`candidate-search-browser-interface.yaml`（`v0.7`）・`test-support-api.yaml`
  （`v0.7.0`）が改訂対象になる。いずれも人間の再承認点であり、承認の実体は本PRのマージである。
- `design.md`・`ARCHITECTURE.md`・`product-brief.md`を本PRで更新する。**`product-brief.md` §3・§7の
  改訂は人間の再承認点である**（decision 8-8・12）。
- developerの実装スライスへの申し送り:
  1. `recommendation/pipeline.py`から`ConceptKind.CAPACITY_REFERENCE`・`ConceptKind.AMENITY_REFERENCE`・
     `_build_capacity_reference`・`_build_amenity_reference`・対応する`_TITLES`/`_RATIONALES`
     エントリ・`_PRIORITY_ORDER`内の該当項目・`NormalizedCandidate.amenity_score`を削除し、
     `ConceptKind.GENRE_FOCUS`・`ConceptKind.NON_SMOKING_REFERENCE`とその構築関数を追加すること
     （decision 2・3・10）。
  2. `integrations/hotpepper/normalize.py`から`_AMENITY_FIELDS`・`_amenity_score`・
     `_amenity_available`・`access`関連の抽出処理を削除し、`non_smoking`の3値分類、`card`の真偽変換、
     `budget.average`の通過を追加すること（decision 6・8・9・10）。docstringの「none of these raw
     values are ever included in a browser-facing Candidate」を、禁煙区分について訂正すること。
  3. `capacityTier`・`dinnerBudgetTier`のしきい値定数（20/60、2000/4000、decision 4・8）を1箇所に
     まとめ、本ADRを参照するコメントを付けること。
  4. `previouslyShownProviderPageUrls`（ADR-0017）の既存降格ロジックは、`GENRE_FOCUS`・
     `NON_SMOKING_REFERENCE`にもそのまま適用されること（`build_concepts`の既存構造を変更しないため
     自動的に成立するはずであり、実装時に確認すること）。
  5. `test-support-api.yaml`のNORMAL_WITH_REPEATモードの拡張が、`TDR-CS-02`・`TDR-CS-12`の
     L4検証を実際に決定的に成立させることを確認すること。
- orchestratorへの申し送り: 次の実データレビューで、`GENRE_FOCUS`が`PROXIMITY`と実質的に重複した
  候補を返す頻度、`NON_SMOKING_REFERENCE`が`PROXIMITY`と偶然同じ順序を返す頻度を確認すること
  （decision 2・3の残存リスク）。`capacityTier`・`dinnerBudgetTier`のしきい値（decision 4・8）も、
  より多くの実データが得られた時点で見直しの要否を確認すること。
- friction-logにFR-012を新規記録する（決定13）。

## friction-logの判定

**決定8の循環した却下理由についてはFR-012として記録する。それ以外は記録しない。**

本ADRの主要な作業は、人間の新しい所感（2026-08-09）と、それに先立つorchestratorのフィールド調査
という新しい入力を契約へ翻訳することであり、大半はAIの見落とし・誤りではなく正常な設計サイクルで
ある。`meta/permissions.md`の記録ルール（人間判断の発生そのものはfrictionではない。AIの迷い・誤り・
見逃しが関与した場合のみ記録する）に照らし、大半は記録対象ではない。

ただし決定8は例外である。当初のドラフトで私は、`product-brief.md`の除外記述を「既に持つ明確な除外
決定」として引用したが、その引用文の一部は今回のセッションで私自身が書き足し、かつADR-0019自身を
根拠にしていた——**これは私自身の誤り（循環した正当化）であり、AIの迷い・誤りが関与した事例に当たる**。
orchestratorがこの循環を検知して人間へ提示し、人間が再確認・差し戻したことで訂正された。この経緯を
friction-logにFR-012として新規記録する（本PRに同梱）。cause_keyは新規に発行する
（`adr-cites-own-session-edit-as-independent-precedent`）——過去のcause_key（`record-update-
needs-second-pr`等）とは機構が異なる（あちらは承認記録のタイミング問題、こちらは根拠citation自体の
循環）ため、既存キーを再利用しない。

FR-010・FR-011が申し送った「`ConceptKind`を変更する際は`reProposalOptions.maxItems`との容量関係を
確認すること」は、本ADRの決定1で明示的に実行した——確認を怠ったのではなく、確認した結果として総数を
4に据え置く設計を選んだ。これは申し送りが意図したとおりの動作であり、friction化する事象ではない。
