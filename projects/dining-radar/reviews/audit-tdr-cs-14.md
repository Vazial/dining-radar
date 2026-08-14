# TDR-CS-14（既表示優先度）acceptance 差分レビュー

- 担当: reviewer
- 対象: working tree（未コミット、tester作成）の `tests/acceptance/**` 差分
  - `dsl/candidate_search_browser.py`
  - `steps/candidate_search_steps.py`
  - `test_candidate_search_acceptance.py`
- 照合元: `contracts/candidate-search.feature`（TDR-CS-14新規、TDR-CS-11本文は無変更）、
  `contracts/candidate-search-browser-interface.yaml` v1.1.0（`shownPoolPriority`・
  `shownCandidateMemory`・`verificationAllocation`）、`contracts/test-support-api.yaml` v1.1.0
  （`SHOWN_POOL_PRIORITY`・`GENRE_ORDER_BY_COUNT`・`randomSeed`）、
  `adr/0024-refine-candidate-diversity-and-filter-discoverability-from-live-feedback.md`（2026-08-14追補込み）
- tester の意図説明・コメント・コミットメッセージは判断材料にしていない。対訳表とチェックリストは
  コードと契約だけを突き合わせて作成した。DSL/step本文中のコメント（例:
  「the contract's own sanctioned technique」）は、それ自体を根拠として採用せず、記載された契約箇所を
  自分で開いて独立に真偽を確認した。
- 実行結果: `python -m pytest tests/acceptance -q` を自分で実行し、**20 passed in 287.55s**（新規
  `test_tdr_cs_14_...` 含む）を確認した。ただし「緑」は以下の指摘の正しさを裏付ける証拠としては使って
  いない——対訳とチェックリストは静的に行った（過去にこのプロジェクトで「シナリオがDOM結果を確認しない
  まま緑になっていた」欠陥が実在するため、緑であることと仕様充足は別問題として扱う）。

## 結論

**ブロッカー級（承認不可レベル）の欠落は見つからなかった**が、是正または人間の明示確認を推奨する点が
4つある。うち1つ（F1）は「緑だが実質的に何も検証していないアサーション」に該当し、過去にこの
プロジェクトで実際に起きた欠陥クラスと同型である。もう1つ（F2）は契約が明記する検証手順の半分しか
実装されていない。F3・F4はtester自己申告の判断1・2に対応する、契約解釈上のグレーゾーンであり、
「たぶん合っている」で通さずここに明記する。

**2026-08-14 再監査で更新: F1・F2は解消を確認、F3は部分的に改善を確認した。文末の「再監査」節を参照。
以下の初回記述は削除せず、当時の指摘としてそのまま残す。**

## Scenario → step → DSL 対訳表（TDR-CS-14）

| # | シナリオ文 | 呼び出されるstep | DSLが実際にすること | 判定 |
|---|---|---|---|---|
| Given1 | 幹事に絞り込み条件に基づく候補が示されている | `organizer_has_filtered_candidates` | `open_candidate_screen()`: 認証済み画面へ遷移し初回`POST /candidate-proposals`を捕捉、応答schemaを照合 | 対応 |
| Given2 | 対象となる候補が表示件数を大きく上回る | `candidates_greatly_outnumber_the_display_count` | `populationAttributes`の`defaultExcluded=false`行数を数え、`>= DISPLAY_CAP*2`（10件）であることを確認 | 対応。ただし「大きく上回る」の量的基準は`SHOWN_POOL_PRIORITY`Givenが固定する母集団10件（表示上限5件のちょうど2倍）に依存した数値であり、これが「大きく」の妥当な下限かは契約側の判断（後述F4） |
| When | 幹事が同じ絞り込み条件のまま「もう一度探す」を繰り返す | `organizer_repeats_search_again_with_the_same_filters` | `repeat_search_again_through_shown_pool_cycle()`: `search_again()`を3回発火する**間**に、2回目の直前で`window.sessionStorage`へ直接、既に観測済みのURL7件を書き込む | **要確認（F3）**。「もう一度探すを繰り返す」という業務操作の中に、公開UI/APIでは起こり得ないストレージ直接操作が挟まっている |
| Then1 | まだ一度も示していない候補が優先して示される | `not_yet_shown_candidates_are_shown_first` | round A（初回）とround B（1回目の「もう一度探す」）の候補URL集合が互いに素であること、`shownPoolExhausted=false`であることを確認 | 対応。契約の3性質のうち「未表示5件以上→全て未表示から選ぶ」ケースを直接検証している |
| Then2 | 対象となる候補をひとわたり示し終えるまでは、一度示した店舗は表示から除かれるのではなく後回しにされるだけである | `previously_shown_candidates_are_postponed_not_excluded` | 部分充填ラウンドで、未表示3件が返却に全件含まれること、かつ返却と既表示7件との積が正確に2件（`5-3`）であることを確認 | 対応。**除外と優先度を区別できている**——既表示URLが実際に2件戻ってくることを直接数えるので、「既表示が0件しか出ない」という誤実装（それは除外そのもの）を検出できる |
| Then3 | 対象となる候補をすべて一度は示し終えたあとは、一度示した店舗も再び示され始めることがある | `previously_shown_candidates_can_reappear_after_a_full_cycle` | `shownPoolExhausted=true`を確認し、続けて`returned.issubset(all_urls)`を確認 | **要修正（F1）**。後段の`issubset`は、`SHOWN_POOL_PRIORITY`が母集団を固定10件に限定しているため、実装の正誤に関わらず常に真になる（母集団に存在しないURLはそもそも返せない）。実質的な検証は`shownPoolExhausted`フラグの1点だけ |
| Then4 | 画面を再読み込みしても、この記憶はタブを閉じるまでの間は保たれる | `shown_memory_survives_a_reload_within_the_tab` | reload前のsessionStorage内容を読み、reload後の初回requestの`shownProviderPageUrls`が同じURL集合であることを確認 | 対応 |
| Then5 | この記憶は長い時間が経つと自然に薄れ、何日も前に示した店舗まで避け続けることはない | `shown_memory_fades_after_its_retention_period` | 保持済みの1件の`storedAt`を21時間前に直接書き換えてsessionStorageへ書き戻し、次の「もう一度探す」の送信`shownProviderPageUrls`からそのURLが欠けていることを確認 | **不足（F2）**。契約が明記する検証は2つの観測の連言（後述）だが、実装は前半（送信から除かれること）だけで、後半（その候補が改めて「未表示」として扱われること）を確認していない |
| Then6 | この記憶は幹事のアカウントや別の端末には残らない | `shown_memory_is_not_shared_across_accounts_or_devices` | 同一アカウントで新規ブラウザコンテキスト（別タブ相当）を開いてサインインし、初回requestの`shownProviderPageUrls`が空/欠落であることを確認 | 対応。同一アカウントでも記憶が引き継がれないことを示しており、「サーバ非永続」の主張を実質的に裏付ける |

## TDR-CS-11 への追加分（本文は無変更、中間操作のみ追加）

| 追加箇所 | 呼び出されるstep | DSLが実際にすること | 判定 |
|---|---|---|---|
| 元のseed(7)で「もう一度探す」を再現する直前 | `organizer_searches_again_to_reproduce_the_original_sample` | `search_again_reproducing_original_seed()`: `window.sessionStorage`から`shownCandidateMemory`キーを直接削除してから`search_again()`を呼ぶ | **要確認（F3の派生、後述）** |

## 指摘

### F1 — TDR-CS-14 Then3 の後段アサーションが実質的に何も検証していない（Medium-High）

```python
def assert_previously_shown_candidates_can_reappear_after_a_full_cycle(self) -> None:
    rounds = require(self._shown_pool_rounds, "shown-pool cycle was not performed")
    self.assertions.assertTrue(rounds["exhausted"].payload["shownPoolExhausted"])
    all_urls = set(self._urls(rounds["a"])) | set(self._urls(rounds["b"]))
    returned = set(self._urls(rounds["exhausted"]))
    self.assertions.assertTrue(returned.issubset(all_urls))
```

`all_urls`は`SHOWN_POOL_PRIORITY`の母集団全体（固定10件）と一致することが、同じDSLメソッド内で
`self.assertions.assertEqual(len(all_urls), SHOWN_POOL_SIZE)`によって既に保証されている。この母集団
以外のURLをサーバが返すことはスキーマ上あり得ない（`test-support-api.yaml`のGiven定義がURLを10個に
固定している）ため、`returned.issubset(all_urls)`は実装が正しく動いていようが壊れていようが常に真になる
——`shownPoolExhausted`フラグの実装にバグがあっても、返却候補が母集団内の別の組み合わせである限りこの
行は落ちない。

シナリオが要求しているのは「一度示した店舗も再び示され始めることがある」という**再出現の観測**である。
`returned`と、それまでに蓄積された既表示集合（`partial_seen`または`all_urls`）との**積が空でない**こと
（あるいはこの時点では全10件が既表示なので`returned`全体が既表示集合と一致すること）を明示的に確認する
アサーションに置き換える必要がある。現状は`shownPoolExhausted`の1点だけが実質的な検証であり、`issubset`
行はレビューを読む人間に「候補の中身も確認している」という誤った印象を与える。

### F2 — TDR-CS-14 Then5（期限切れ）が契約の定める検証の半分しか実装されていない（Medium-High）

`shownCandidateMemory.expiry.verificationNote`（browser-interface.yaml）は次のように書く（強調は引用者）。

> ...it seeds an already-stale sessionStorage entry directly ... then asserts that entry is absent
> from the outgoing request's shownProviderPageUrls **and that its candidate is once again treated
> as not-yet-shown**.

`adr/0024`の「期限切れの検証」節も同じ内容を日本語で重ねて書いている。

> ...その`providerPageUrl`が次のリクエストの`shownProviderPageUrls`から除かれていること、**および
> その候補が改めて「未表示」として扱われることを観測すれば足りる**。

いずれも「除かれていること」と「未表示として扱われること」の**両方**を観測条件として挙げている
（「および」「and」で結ばれた連言）。実装は前半だけを見ている。

```python
def assert_shown_memory_fades_after_its_retention_period(self) -> None:
    ...
    sent = set((response.request_body or {}).get("shownProviderPageUrls") or [])
    self.assertions.assertNotIn(stale_url, sent)
```

`response.payload["candidates"]`に`stale_url`が含まれる（あるいは少なくとも優先度計算上「未表示」側に
回された）ことを示す後段の確認が無い。「送信から消えている」ことと「サーバがそれを未表示として扱う」
ことは、契約の文言上は同じ命題として書かれていない別々の観測点であり、後者を省略すると
「ブラウザ側は正しく刈り込んだが、サーバの集合演算にバグがあり期限切れURLを引き続き既表示として扱う」
という欠陥を検出できない（この特定の欠陥はTDR-CS-14の他のThenでも部分的に押さえられている可能性は
あるが、Then5自身はこの欠陥クラスに対して盲点である）。

### F3 — 「When」ステップに公開境界を越える状態操作が埋め込まれている（要人間/architect確認）

依頼文の判断1・2に対応する、独立に確認した内容を記す。

**判断2（部分充填ケースの直接注入）について**: `test-support-api.yaml`の`SHOWN_POOL_PRIORITY`説明を
自分で読んだ。該当箇所は次のとおりである。

> This mode does not, by itself, exercise the partial case (1-4 not-yet-shown members); that follows
> from the same set-membership properties ... applied to any shownProviderPageUrls value **the
> acceptance test constructs from previously observed providerPageUrl values**, and does not require
> a dedicated fixture.

これは確かに、部分充填ケースを「これまでに観測済みのURL値から構成する」ことを認める文言であり、
tester自己申告のとおり読める。実装（`_write_shown_candidate_memory`）が使う7件のURLは、実際に
round A・round Bという2回の公開API呼び出しから観測された値であり、捏造されたURLではない。また
10件母集団・5件表示上限という組み合わせでは、自然な「もう一度探す」の繰り返しだけでは「既表示0/5/10件」
の3点しか到達できず（2回繰り返すと必ず出し切ってしまう）、1〜9件の部分充填状態には原理的に到達できない
——したがって直接構成以外に部分充填ケースを機械的に作る方法がないというtesterの前提も、独立に確認した
限り正しい。**判断2そのものは契約の文言と整合していると判断する。**

ただし、実装上の懸念が1つ残る。この直接注入は、「もう一度探すを繰り返す」という**When**の一部として
`repeat_search_again_through_shown_pool_cycle()`という1つのDSLメソッドに埋め込まれており、Given
（前提状態の構成）とWhen（シナリオが記述する操作）の境界がコード上で見えなくなっている。
`meta/verification.md`は「状態の準備・検証はSUTの公開境界（API/UI）経由で行う。DB直接操作はGiven専用の
seamとして明示的に定義した箇所のみ許可」と定める。`sessionStorage`はDBではないが同種の内部状態であり、
`shownCandidateMemory`はbrowser-interface契約が観測対象として定義してはいるものの、**Given操作として
明示的に許可した文言があるのは期限切れテスト（`verificationNote`）だけ**である。部分充填ケースの
直接構成についても契約の別の場所（`SHOWN_POOL_PRIORITY`の`mode`説明）に根拠はあるが、それを**When**の
内部に無言で混在させる構造は、シナリオが記述する操作と実際にコードが行う操作の対応を読みにくくして
いる。少なくとも、注入部分を独立したGivenヘルパーとして切り出し、Whenは「クリック操作の反復だけ」に
留める構成の方が、対訳表の可読性と契約の追跡可能性の点で優れる。**内容自体は契約と矛盾しないため
ブロッカーとはしないが、structureの是正（またはこのままでよいという明示的な承認）を推奨する。**

**判断1（TDR-CS-11の`search_again_reproducing_original_seed`）について**: `test-support-api.yaml`の
`randomSeed`descriptionを自分で読んだ。

> Two calls with the same randomSeed, the same mode, semantically equivalent filters ..., **and the
> same shownProviderPageUrls** must return byte-identical candidates arrays in the same order.

このdescription自体が「同じ`shownProviderPageUrls`」を再現条件に含めており、TDR-CS-14導入前には
存在しなかった新しい前提である。この行はADR-0024のドラフトが導入したものであり、tester自身が書いた
ものではない。したがって、seedのみを揃えても中間の「もう一度探す」（seed 19）が`shownCandidateMemory`
へ蓄積を加えてしまい、最初の呼び出し（蓄積が空）と3回目の呼び出し（蓄積が非空）とで
`shownProviderPageUrls`が食い違い、この行の要求するbyte-identicalの再現条件そのものが崩れる
——これはtesterの説明どおりであり、独立に読んでも技術的に正しい。

一方で、この`clear_shown_candidate_memory()`は現実の利用者には実行不可能な操作である。TDR-CS-11の
シナリオ本文自体は`shownCandidateMemory`や`seed`について一切言及しない、純粋に業務レベルの記述
（「以前と異なりうる」「すべて異なるとは限らない」）であり、seedピン留めはその業務主張を機械的に
証明するための**既存の**テスト技法（本差分より前から存在する）である。今回の追加は、TDR-CS-14が
持ち込んだ新しい変数（既表示蓄積）が、この既存技法の前提（「同じseed・同じ条件なら同じ結果」）を壊す
ことに対する、狭い範囲の是正であり、シナリオが観測すべき業務上の振る舞いを回避する類のものではないと
判断する。ただし、この`sessionStorage`直接クリアという技法自体を「Given seam」として契約のどこかが
明示的に許可しているわけではなく（`shownCandidateMemory`節にも`verificationNote`にも「クリアして
再現条件を揃えてよい」という文言はない）、**判断2の期限切れテストほど明確な契約上の根拠はない**。
技術的必然性は認めるが、契約が明示的に許可したseamの範囲を1件超えて拡大解釈している点は、人間または
architectの確認を推奨する。

### F4 — 規約由来の数値・Given固定値への依存（Low、要確認のみ）

- `candidate-search.feature`のTDR-CS-14本文には時間数（20時間・24時間）が一切登場しない。DSL側の
  `SHOWN_MEMORY_MAX_AGE_HOURS = 20`は`shownCandidateMemory.expiry.maxAge`への参照コメント付きで定義
  されており、業務シナリオへの数値の漏出は確認できなかった——依頼文が懸念した「規約由来の数値が業務
  シナリオ側へ漏れていないか」は問題なしと判断する。
- `assert_eligible_population_greatly_exceeds_display_cap`の閾値`DISPLAY_CAP * 2`（10件）は、
  `SHOWN_POOL_PRIORITY`Givenが固定する母集団サイズ（ちょうど10件）と一致するよう選ばれた値であり、
  「大きく上回る」という業務文言の量的下限をtester自身が独自に決めたわけではなく、契約側が既に固定
  した唯一の値をなぞっているだけである。これ自体は妥当だが、対訳表としては「『大きく』の基準は
  Given側の都合で決まっている」ことを記録しておく。
- `repeat_search_again_through_shown_pool_cycle`内の`partial_seen = set(all_urls[: SHOWN_POOL_SIZE - 3])`
  の`3`は、未表示1〜4件という契約上の有効範囲内から選ばれた値だが、なぜ3（＝未表示3件）を選んだかの
  コメントがない。動作の正しさに影響しないため指摘に留める。

## L4 5観点チェックリスト

| 観点 | 判定 | 根拠 |
|---|---|---|
| 過不足 | 一部NG | F3: Whenステップの中にGiven相当の直接状態操作が無言で混在している。それ以外のThenはシナリオ文が言っている範囲を過不足なくカバーしている（TDR-CS-14の6つのThenすべてに対応するstep/DSLが存在する） |
| Givenの正当性 | OK | `a_large_pool_of_candidates_can_be_proposed`は公開境界（`test-support-api.yaml`の宣言済みseam）経由。`candidates_greatly_outnumber_the_display_count`は実際の公開応答（`populationAttributes`）から観測しており、実装の内部をなぞっていない |
| Thenの検証対象 | 一部NG | F1（Then3が実質的に`shownPoolExhausted`フラグ以外を検証していない）、F2（Then5が契約の定める2条件のうち1条件しか検証していない）。それ以外のThen（Then1・2・4・6）は業務上の結果を直接検証している |
| 失敗の握りつぶし | OK | 変更/新規のstepはすべて1DSL呼出しのみ。DSL側にも空catch・緩すぎる比較・sleep同期・リトライは見当たらない。`require()`はNoneを例外に変換し、`capture_candidate_proposal_response`はPlaywrightの`expect_response`で実ネットワーク応答を待つ（タイムアウト時は素直に失敗する） |
| 暗黙の前提 | 一部NG | F4に列挙のとおり数値そのものは概ね契約由来で明記されている。ただしF3のとおり「直接状態注入がどこまで許容されるseamか」という前提が、コードのコメント（tester自身の解釈）にしか書かれておらず、契約本文に「この技法を使ってよい」という文言があるのは期限切れケースだけである |

## contract ↔ test 対応・孤児監査

### 対応済み

- `shownPoolPriority`の3つの集合所属性質（未表示5件以上/1-4件/0件）は、いずれも公開APIの応答
  （`payload["candidates"]`・`payload["shownPoolExhausted"]`）から独立に観測されている。
- `shownCandidateMemory.updateRule`（reload後も保持）と`disclosure`（別コンテキストへ非共有）は、
  Then4・Then6でそれぞれ直接観測されている。
- `NORMAL_WITH_POOL`→`NORMAL_WITH_WEIGHTED_SAMPLING`の改名は、これを使うTDR-CS-01・02・04・11・13の
  全箇所（`lunch_candidates_can_be_proposed`・`seeded_lunch_candidates_can_be_proposed`・
  `candidate_state_uses_a_different_random_seed`・`candidate_state_reuses_the_original_random_seed`・
  DSL内エラーメッセージ）で機械的にリネームされているだけで、アサーションのロジックは変更されていない
  （diffで文字列置換のみであることを確認した）。改名漏れも見当たらない。

### 孤児または不完全な契約要求

- `shownCandidateMemory.expiry.verificationNote`の後半（「改めて未表示として扱われること」）—— F2。
- `proposal.shownPoolPriority`の再出現ケースの実質的検証 —— F1。
- **`GENRE_ORDER_BY_COUNT`（adr/0024決定1、genrePresentationの件数降順化）と`filterPanel.controlGrouping`
  （adr/0024決定2、居酒屋・バートグルのジャンル区分への移動）は、`tests/acceptance/`のどこにも
  参照がない**（`grep`で確認済み。ヒットするのは`tests/test_static_assets.py`・`tests/test_suggestions.py`
  という developer 側の単体テストのみ）。`candidate-search-browser-interface.yaml` v1.1.0は
  `genrePresentation`と`controlGrouping`の両方に新しい機械観測可能な要求を追加しているが、これに
  対応する新規Gherkinシナリオは存在しない（TDR-CS-14はdecision 4だけを対象にしている）ため、
  「孤児シナリオ」ではなく「対応するシナリオが最初から無い契約要求」という状態である。今回の差分の
  責任範囲外の可能性が高いが、この差分がADR-0024 v1.1.0契約全体のacceptance対応を完了させるものと
  誤解されないよう、ここに明記する。人間が「decision 1・2のL4は別スライスに残す」と明示的に決めて
  いるかどうかの確認を推奨する。

### 重複・死んだ受け入れ補助コード

見当たらなかった。新規メソッド（`search_again_reproducing_original_seed`・
`repeat_search_again_through_shown_pool_cycle`・`assert_eligible_population_greatly_exceeds_display_cap`・
`assert_not_yet_shown_candidates_are_prioritized`・
`assert_previously_shown_candidates_are_postponed_not_excluded`・
`assert_previously_shown_candidates_can_reappear_after_a_full_cycle`・
`assert_shown_memory_survives_a_reload`・`assert_shown_memory_fades_after_its_retention_period`・
`assert_shown_memory_is_not_shared_with_another_device`・`_urls`・`_eligible_population_count`・
`_read_shown_candidate_memory`・`_write_shown_candidate_memory`・`clear_shown_candidate_memory`・
`_browser_now_ms`）はいずれも1回以上、対応するstep経由で呼び出されている。既存stepとの同義重複も
確認できなかった。

## 修正後に必要な再監査条件（初回監査時点のもの）

1. F1（Then3の`issubset`の実質無効化）を、既表示集合との積が空でないことを直接確認するアサーションへ
   置き換えること。
2. F2（Then5が契約の定める検証の半分しか実装していない）を、期限切れURLが次の応答で「未表示」側として
   扱われることの直接観測へ拡張すること（例: そのURLが`candidates`に現れうること、または少なくとも
   優先度計算上「未表示」に分類されたことを示す観測）。
3. F3について、人間またはarchitectが「`SHOWN_POOL_PRIORITY`の部分充填ケースをWhenステップ内で
   sessionStorageへ直接注入する技法」と「TDR-CS-11の再現テストのためにsessionStorageを直接クリアする
   技法」の双方を、明示的なGiven seamとして承認するか、Given/Whenを分離する構造修正を求めるかを判断
   すること。
4. GENRE_ORDER_BY_COUNT・controlGroupingのL4対応が本当に別スライス送りでよいか、人間が明示すること。

---

## 再監査（2026-08-14、tester の F1・F2・F3 修正を受けて）

- 対象: 上記初回監査後に tester が更新した working tree 差分（同じ3ファイル）。初回監査で指摘した
  内容は上のセクションから削除・修正していない。以下は追記のみ。
- 実行結果（自分で実行）: `python -m pytest tests/acceptance -q -k "tdr_cs_14 or tdr_cs_11"` で
  **2 passed in 25.30s**、続けて `python -m pytest tests/acceptance -q` フルスイートで
  **20 passed in 286.59s**。両方とも自分で実行した。orchestrator が申告した「`select_with_shown_priority`
  の出し切り分岐を`return [], True`に書き換えて`AssertionError: 0 != 5`で落ちたのを確認し復元した」という
  欠陥注入・復元そのものは、私は実行していない（`src/**`を書き換えないという制約を守っているため）。
  以下のF1再判定は、コードと契約文の**論理的な突き合わせ**によるものであり、私自身の実行による実証では
  ない——この区別を明示する。

### F1再判定 — 新アサーションは「満数が返る」以外の壊れ方も捕まえるか

現在のコード（`assert_previously_shown_candidates_can_reappear_after_a_full_cycle`、抜粋）:

```python
self.assertions.assertEqual(len(returned), DISPLAY_CAP)
self.assertions.assertEqual(returned, returned & all_urls)
```

`returned`は`set(self._urls(rounds["exhausted"]))`、すなわち応答`candidates`配列の`providerPageUrl`を
集合化した値である。この2行を独立に読み解くと以下のことが言える。

1. **`len(returned) == DISPLAY_CAP`（5）** は、`returned`が**重複のない**5要素であることを要求する。
   応答の`candidates`配列が5件あっても同一`providerPageUrl`を繰り返して水増ししていれば、`set`化した
   時点で要素数が5未満に縮むため、この行で必ず落ちる。**「同じ候補を重複して5件にする」という
   orchestratorの想定した壊れ方は、このアサーションで捕まる。**
2. **`returned == returned & all_urls`** は`returned.issubset(all_urls)`と数学的に同値である
   （Pythonの集合演算では`s == s & t`は`s`が`t`の部分集合であることと等価）。`all_urls`はDSL内で
   `self.assertions.assertEqual(len(all_urls), SHOWN_POOL_SIZE)`により厳密に10要素であることが
   同じメソッド内で既に検証されている（`SHOWN_POOL_PRIORITY`Givenの母集団全体と一致）。したがって、
   応答が母集団に存在しない`providerPageUrl`（捏造・無関係の候補）を1件でも含めば、その要素は
   `returned & all_urls`から落ち、両辺が不一致になりこの行で落ちる。**「母集団とは無関係な候補を
   返す」というorchestratorの想定した壊れ方も、このアサーションで捕まる。**
3. 1と2を**両方同時に**満たすには、応答が「母集団に属する、互いに異なる5件」でなければならない。
   これは初回監査で指摘した「`issubset`単独では実装の正誤に関わらず常に真になる」という欠陥
   （母集団に存在しないURLをサーバがそもそも返せないため）を、`len==5`という独立した制約を追加する
   ことで解消している——`issubset`だけでは検出できなかった「候補数が足りない・重複している」という
   欠陥クラスを、`len(returned)==5`が新たに担う。

以上より、**F1の修正は当初の恒真性の問題を解消しており、orchestratorが提示した2種類の壊れ方
（重複による水増し・母集団外の候補）のいずれについても、私が独立にコードを読んだ限り検出できると
判断する。**

なお、これでも検出できない壊れ方が理論上ある。応答が母集団に属する異なる5件であっても、実際には
毎回同じ固定された5件（例えば常にround_a時点の最初の5件）を返すだけで、`shownPoolPriority`が
要求する「出し切り後は`shownProviderPageUrls`を無視して母集団全体から抽出する」という**再抽選**の
実質を伴わない実装であっても、たまたまこの1回のテスト実行では母集団の部分集合5件という条件文だけは
満たしてしまう。ただしこれは`distanceWeightedSelection`が持つ統計的性質（重み付き抽選が実際に機能して
いるか）に属する懸念であり、契約の`verificationAllocation`が
「L3/L4: not applicable to this statistical property」と明記してL1（多数回試行）に検証を割り当てている
対象そのものである。したがってこの残存ギャップはL4のテスト差分の欠陥ではなく、契約が最初から意図的に
L4の対象外とした範囲であると判断する。

### F2再判定 — 決定性の主張は契約の不変条件に照らして成り立つか

現在のコード（`assert_shown_memory_fades_after_its_retention_period`、抜粋）:

```python
entries = self._read_shown_candidate_memory()
self.assertions.assertEqual(len(entries), SHOWN_POOL_SIZE)
stale_url = entries[0]["url"]
...（stale_urlだけstoredAtを21時間前に書き換えてwrite-back）...
...
self.assertions.assertNotIn(stale_url, sent)
self.assertions.assertEqual(len(sent), SHOWN_POOL_SIZE - 1)
self.assertions.assertIn(stale_url, set(self._urls(response)))
```

tester の主張（「この時点でsessionStorageはちょうど10件、1件だけ古くすれば未表示は正確に1件になり、
`shownPoolPriority`の集合所属不変条件により全`randomSeed`で必ず含まれる」）を、このステップ**単体**では
なく、**このステップに到達するまでのDSL呼び出し列**を`shownCandidateMemory.updateRule`（reload後も
保持・出し切り時のみ全クリア）に沿って自分でトレースして検算した。

1. round A（初期表示）: 空の記憶に5件を追加 → 記憶=5件（round Aの5件）。
2. round B（`repeat_search_again_through_shown_pool_cycle`内の1回目の`search_again()`）:
   送信`shownProviderPageUrls`=round Aの5件、未表示5件（`SHOWN_POOL_SIZE`10 マイナス round Aの5）と
   一致し`shownPoolExhausted=false`。応答の5件（round Aと排反）を追加 → 記憶 = round A ∪ round B =
   **10件（母集団全体）**。
3. `seed_shown_candidate_memory_from_observed_urls(partial_seen)`: 記憶を7件（`partial_seen`）で
   **上書き**（追加ではない、`_write_shown_candidate_memory`は`setItem`）。
4. round partial（2回目の`search_again()`）: 送信=`partial_seen`7件、未表示3件、
   `shownPoolExhausted=false`。応答5件（未表示3件＋既表示から2件）を追加 → 記憶 =
   `partial_seen`(7) ∪ 応答の新規3件 = **10件（母集団全体）**。
5. round exhausted（3回目の`search_again()`）: 送信=10件全体、未表示0件、`shownPoolExhausted=true`。
   `updateRule`は「`shownPoolExhausted=true`のときは追加前に記憶を全クリア」と定めるため、記憶は
   **round exhaustedの応答5件だけ**にリセットされる（10件ではなくなる）。
6. `assert_shown_memory_survives_a_reload`（F2の直前のThen）: `page.reload()`により
   `initialProposal`相当のリクエストが発火する。送信=round exhaustedの5件、未表示は残り5件
   （母集団10 マイナス round exhaustedの5）、ちょうど5件＝表示上限と一致するため
   `shownPoolPriority`不変条件のケース1（未表示5件以上→返却は全て未表示から）により、返却5件は
   未表示側の5件**全部**になる（未表示側が過不足なく表示上限と一致する場合、抽選の余地なく全員が
   選ばれる）。`shownPoolExhausted=false`（未表示非ゼロ）なので記憶はクリアされず、round exhaustedの
   5件にreloadの5件（round exhaustedと排反）を追加 → 記憶 = **再び10件（母集団全体）**。

このトレースの結果、F2のステップに入る時点で記憶がちょうど10件になるという前提は、実装が契約どおり
正しく動く限り論理的に成立する。かつ、この前提はF2自身の最初の行
`self.assertions.assertEqual(len(entries), SHOWN_POOL_SIZE)`で**自己検証**されており、私のトレースの
どこかが誤っていた場合（あるいは実装がここまでのどこかで契約と違う挙動をした場合）は、この行で
即座に失敗する構造になっている——盲目的な前提ではない。

その上で本題の決定性を検算する。記憶が10件（母集団全体）の状態から**厳密に1件**（`stale_url`）だけを
`maxAge`超過にして書き戻すと、`shownCandidateMemory.requestRule`（読み取りのたびに期限切れを除去して
から送信）により、次のリクエストの送信`shownProviderPageUrls`は9件になる。この時点でサーバ側の
「未表示」＝母集団10件 マイナス 送信9件 = **ちょうど1件（`stale_url`自身）**。`shownPoolPriority`の
不変条件（`candidate-search-browser-interface.yaml`）は次のように書く。

> (2) When unseen has 1-4 members, every unseen member is among the returned candidates ...
> These three set-membership properties hold for every randomSeed ...

未表示がちょうど1件のとき、この性質は「その1件は必ず返却候補に含まれる」ことを、**乱数seedによらず**
無条件に要求する。したがって`stale_url`が次の応答の`candidates`に含まれることは、統計的な蓋然性では
なく契約が保証する決定的な帰結であり、`self.assertions.assertIn(stale_url, set(self._urls(response)))`
は**確率的に偶然通ることがある壊れやすいアサーションではなく、真に決定的なアサーションである**。
`assertEqual(len(sent), SHOWN_POOL_SIZE - 1)`（9件）も、期限切れ対象が厳密に1件であることから同様に
決定的である。

**結論: F2の決定性の主張は、私が契約の不変条件とDSL呼び出し列を独立にトレースした限り正しい。**
初回監査で指摘した「送信から消えることしか確認せず、改めて未表示として扱われることを確認しない」という
欠落は解消されている。

### F3再判定 — Given/Whenの分離と、tester の説明の妥当性

tester が動かしたのは「部分充填ケースの直接注入」（初回監査の判断2に対応する部分）だけであり、
`search_again_reproducing_original_seed`（TDR-CS-11の判断1に対応する部分、`clear_shown_candidate_memory()`
を直接呼ぶ側）は今回の差分で**構造上の変更を受けていない**。両者を分けて再判定する。

**判断2（部分充填の直接注入）について**: `seed_shown_candidate_memory_from_observed_urls(urls)`は、
ファイル内の配置そのものが「# Given seams」セクション（`set_candidate_state`の直後）へ移動しており、
独立した名前付きメソッドとして契約根拠（docstringで`test-support-api.yaml`の該当文言を引用）を明示して
いることを、diffの行位置から確認した。一方で、この呼び出しは依然として`test_candidate_search_acceptance.py`
上は`organizer_repeats_search_again_with_the_same_filters`という**単一のWhen step**の内部（DSL側の
`repeat_search_again_through_shown_pool_cycle`）から行われており、Gherkin上・step一覧上は独立した
Givenの行としては見えない。

tester の説明（「seedする値は同じWhen列の最初のクリック後にしか判明せず、TDR-CS-14の本文にその中間状態に
対応する行が無いため、Gherkinから見える独立したstepには分けられなかった」）を、契約本文に照らして
独立に検討した。

1. `test-support-api.yaml`の`SHOWN_POOL_PRIORITY`説明は、部分充填ケースについて明示的に
   「実行体が観測済みのURL値から構成する」ことを認め、かつ**「専用のfixtureを要求しない」
   （does not require a dedicated fixture）**と書いている。これは契約起草者（architect）が、この
   構成が独立したGiven seam・独立したシナリオ行を新設せずにテスト内部の技法として処理されることを
   既に前提していたと読める。
2. TDR-CS-14のWhen（「同じ絞り込み条件のまま『もう一度探す』を繰り返す」）は、繰り返し全体を
   1つの業務動作として集約する書き方である。これはTDR-CS-11が「seedを変える／同じseedへ戻す」という
   技術的操作の連鎖を「以前と異なりうる」「すべて異なるとは限らない」という1つの業務主張へ集約して
   いる既存の書き方（本差分より前から存在する）と同型であり、このプロジェクトで既に採用されている
   パターンである。
3. 実際に、値そのもの（`urls`引数）は「観測済みのURL」でなければならないという契約上の制約があるため、
   時系列上どうしても「最低1回はクリックしてラウンドAとBの応答を得たあと」でなければ`urls`が定まらない
   ——scenarioのGivenの時点（まだ何も「探し直して」いない時点）でこの値を確定させることは、契約の
   要求（観測済みURLから構成する）そのものと矛盾する。したがって、これを独立したGiven行としてWhenより
   前に置くこと自体が契約の要求と整合しない。

以上から、**tester の説明は妥当であり、シナリオ側にstepが不足している証拠ではないと判断する。**
TDR-CS-14の本文が「繰り返す」という1つの業務動作として部分充填の構成過程を明示的に語らないのは、
シナリオが技術的な中間状態（既表示7件・未表示3件という具体的な数）を業務の言葉で語る対象ではないと
判断された結果であり、これは規約由来の数値をGherkinに書かない（F4で確認済み）のと同種の、意図的な
抽象化だと解釈できる。ただし、初回監査で指摘した「Given相当の操作がWhenの内部に隠れていて対訳表の
可読性を下げる」という懸念自体は、Given seamとして独立した名前・docstring・契約引用を持つメソッドへ
切り出されたことで**部分的に緩和された**（呼び出し元がWhen stepのままである点は変わらない）。

**判断1（TDR-CS-11の`clear_shown_candidate_memory()`直接呼び出し）は今回のdiffで一切変更されていない。**
初回監査の判定（技術的必然性はあるが、契約上「クリアしてよい」と明示する文言は無く、期限切れケースほど
明確な契約上の根拠はない）はそのまま維持する。この点はまだ人間またはarchitectの確認を得ていない。

### 再監査の結論

- F1・F2は、私が独立に読み解いた限り、当初指摘した欠陥（恒真アサーション／検証項目の片方欠落）を
  実質的に解消している。F1については「重複による水増し」「母集団外候補」の2種の壊れ方を機械的に
  検出できることを論理的に確認した（自分で欠陥注入を実行してはいない。orchestratorが実行した1種類の
  欠陥注入の再現は行っていない）。F2の決定性の主張は`shownPoolPriority`不変条件（「全randomSeedで
  成立する」）と`shownCandidateMemory`の各ルールから導出可能であり、独立に検算して成立を確認した。
- F3は、部分充填ケースの直接注入について、tester の「シナリオ本文に対応する行が無い」という説明を
  契約文言・既存パターンと突き合わせて妥当と判断する。ただしTDR-CS-11側の`clear_shown_candidate_memory()`
  は未対応のまま残っており、この点の human/architect 確認は依然として推奨事項として残す。
- GENRE_ORDER_BY_COUNT・controlGroupingのL4カバレッジ不在（初回監査「孤児または不完全な契約要求」節）は
  今回のdiffで変更されておらず、未解決のまま残る。
- 全体として、初回監査の再監査条件のうち1・2は満たされたと判断する。3は「部分充填の直接注入」（判断2）
  について解消、「TDR-CS-11のクリア」（判断1）については未対応のまま残る。4は引き続き人間の確認を
  要する。
