# 独立監査: TDR-GTH-26〜41 step定義・DSL（三段階投票・地図・基点マーカー）

- 監査対象コミット: `a3c213a`（`origin/test/gathering-three-tier-steps`。このworktreeは別ブランチ
  （`worktree-agent-ab8ea48b11fa58eff`）を使用中で、かつ`test/gathering-three-tier-steps`という
  ブランチ名は既に別worktree（`agent-ac873dc1ae6ce697c`）が使用中だったため、ローカルに新しいブランチは
  作らず、`git show <ref>:<path>`でファイル内容を直接取得して読んだ（ワーキングツリーはチェックアウトを
  変更していない）。
- 監査対象範囲: `git diff origin/contracts/gathering-three-tier-vote...origin/test/
  gathering-three-tier-steps -- projects/dining-radar/tests/acceptance/`
  - `tests/acceptance/dsl/gathering_scheduling_browser.py`（+269/-41行）
  - `tests/acceptance/steps/gathering_scheduling_steps.py`（+55/-16行）
  - `tests/acceptance/test_gathering_scheduling_acceptance.py`（+198/-47行、TDR-GTH-37〜41の新規
    5テスト＋TDR-GTH-26/28/29/30/31/32/33/34の三段階モデルへの書き直し）
- 依拠した契約: `contracts/gathering-scheduling.feature`（TDR-GTH-26〜41、28・30・34・37・40が改訂、
  38・39・41が新設——依頼どおり）、`gathering-scheduling-api.yaml` v0.8.0、
  `gathering-scheduling-browser-interface.yaml` v0.7.0、`test-support-api.yaml` v1.5.3、
  `adr/0044`・`adr/0045`・`adr/0046`。いずれも`git show origin/contracts/gathering-three-tier-vote:
  <path>`で取得し、バージョン番号を実ファイルのフィールド（`contractVersion`/`info.version`）で
  確認した——依頼文の版と一致。
- 独立性の担保: 対訳表はDSL・steps・テスト本体のコードを先に読み下し、その後に`.feature`の
  シナリオ文・ADR-0044/0045/0046と突き合わせる順で作成した。testerのdocstring・インラインコメント
  （例:「Reviewer audit Major#1」等の前回監査への参照）は「コードが実際に何をしているか」の記述として
  引用する場合のみ採用し、意図の弁明としては採用していない。`src/**`は読んでいない。
- 実行した機械検証: 3ファイルを`ast.parse`で構文検証（OK）。`GATHERING_ALLOWED_PURPOSES`
  （DSL、23件）と契約`allowedPurposes`（23件）を機械的に集合比較し完全一致を確認。同様に
  `GATHERING_FORBIDDEN_TEST_IDS`（DSL）と契約`forbiddenTestIds`も完全一致を確認。新設の10個の
  step/DSLメソッドがテスト本体から最低1回は呼ばれていること、旧・二択承認投票モデルの識別子
  （`vote_for_shops`・`toggle_shop_vote`・`YOUR_APPROVAL_ATTR`・`APPROVAL_COUNT_ATTR`・
  `approvedShopIds`等）が対象ブランチのライブコード中に1つも残っていない（docstring中の
  「置き換えた」という説明文のみ）ことを`grep`で確認した。**L4の実行（ブラウザ+バックエンド相手の
  実走）はこの監査では行っていない**——orchestratorの合流検証が既にL4全65件緑（1回目6件失敗、
  developerが5回再現を試みるも再現せず、環境要因と判断済み）と報告しており、本監査はその事実を
  判断材料として受領するに留め、独自の再実行はしていない。

## 結論（先頭サマリ）

**Blocker: 0件。Major: 1件。Minor: 3件。**

依頼された核心的な約束のうち5点——(a)参加者の並びが近い順で投票しても変わらない、(b)幹事の並びが
「行きたい＋行ってもいい」の合算降順、(c)三段階の値と未回答(null)の区別、(d)確定後に未回答の店が
`UNANSWERED`として並ぶこと、(f)参加者の地図に基点マーカーが出ること——は、いずれも緩められることなく
検査されている。特に(a)は「投票前後でDOM順が不変であること」を実際に投票を1回はさんで直接検証しており
模範的、(d)は`assertEqual(decision["shopVotes"], shop_votes)`という**完全一致**（部分一致ではない）の
辞書比較で、確定後の記録に「答えなかった店」が過不足なく1件だけ`UNANSWERED`として含まれることを証明
している。横断検査`screen_has_no_forbidden_controls_or_disclosures`は、本ラウンドが新設した2つの
新しい画面状態（TDR-GTH-38の地図付き選定画面、TDR-GTH-39の地図付き投票画面）の両方に対し、明示的な
呼び出しとインラインコメント（前回監査Major#1への参照）付きで実行されている——**FR-030が「3回目が
起きるなら押し込みを実施すべき」と警告していた再発は、今回は起きていない**。

一方、(e)「地図と店の情報が幹事の選定・参加者の投票それぞれに出ること」の検証には1件のMajorがある——
地図マーカーと一覧項目の対応検査が、同一リポジトリの姉妹契約（candidate-search）が同種の検査に既に
確立している検査様式より構造的に弱い（後述Major 1）。

## 対訳表（コードから読み取った記述 → シナリオとの突き合わせ）

| ID | 実際にコードが行うこと | シナリオ文との一致 |
|---|---|---|
| TDR-GTH-26 | （本文無変更、ペイロード形式のみ更新）5件選定・投票開始のGiven/When/Thenに加え、`SHOP_VOTING_NOT_STARTED`（finalize・vote両方）と`INVALID_SHOP_SELECTION`の0件/6件境界を検査。投票開始後の`screen_has_no_forbidden_controls_or_disclosures`呼び出しはshortlistSelection画面に対し継続。 | 一致。三段階化に伴うペイロード（`{shopId: "WANT_TO_GO"}`辞書形式）への追随のみで、検査の厚みは前回監査時から不変。 |
| TDR-GTH-27 | （本文・実装とも無変更）定休日の店は選べないことをUI不可視・API拒否の両方で検査。 | 一致。 |
| TDR-GTH-28 | 参加者が投票開始済みの会を開き、shop_aへの回答前が`"UNANSWERED"`であることを明示的に確認してから`WANT_TO_GO`で回答→`data-your-vote`が`WANT_TO_GO`に変わることを検査。`screen_has_no_forbidden_controls_or_disclosures`を新モデルの画面に対し実行。shop_bには`NOT_GOING`（三段階のうち「未回答とは別の、明示的な第3の回答」）で回答し区別を検査。 | 一致し、旧版（複数選択・0件可）が要求していた「回答前は未回答」の明示チェックを新規に追加しており厚くなっている。三段階の値とUNANSWEREDの区別（本監査の確認事項(c)）が単一シナリオ内で両方証明されている。 |
| TDR-GTH-29 | 他参加者が未投票の間は`shop_a`/`shop_b`双方のタリーが不在、自分がshop_aに投票した後はshop_aのタリーのみ出現（`want_to_go=1, ok_to_go=1`）しshop_bは引き続き不在であることを検査（店ごとのゲーティングであることを明示）。 | 一致。「店ごと」であることを追加で明示検査しており、前回（会全体で1つのゲートと誤解しうる書き方）より厳密。 |
| TDR-GTH-30 | shop_aにWANT_TO_GOで回答→NOT_GOINGへ変更→変更が反映されることを検査。差し替え投票トリガーの`INVALID_SHOP_SELECTION`（未shortlistの店への投票）も同一テスト内で検査。 | 一致。「いつでも変更できる」という業務規則は三段階の語彙でも同型のまま検査されている。 |
| TDR-GTH-31 | 1参加者が3店に三段階で異なる回答（WANT_TO_GO/OK_TO_GO/NOT_GOING）をし、それぞれ異なる内訳（1/0/0, 0/1/0, 0/0/1、いずれもresponded=1）になることを確認してから、無関係の2店を差し替え、残した3店の内訳が不変であることを再検査。 | 一致。前回（2参加者・approvalCount）から1参加者・三段階の内訳へ書き換わったが、「差し替えで残した票は変わらない」という被検査対象自体は同型のまま維持されている。 |
| TDR-GTH-32 | 参加者がshop_0にWANT_TO_GOで投票済みの状態で差し替え、新しく加わったshop_5が参加者側`"UNANSWERED"`・タリー不在、幹事側`want_to_go=0, ok_to_go=0, not_going=0, responded=0`であることを検査。 | 一致。D7の店ごと分母（addedAt基準）が三段階の内訳全項目に対して0であることまで検査しており厚い。 |
| TDR-GTH-33 | 2店shortlist・shortlistedShopVotes画面（`screen_has_no_forbidden...`実行）→foreign_shopでのfinalize拒否(`INVALID_SHOP_SELECTION`)→shop_a確定→FINALIZED画面（`screen_has_no_forbidden...`再実行）→確定後の日程回答・投票がいずれも`{shopId: status}`形式のペイロードで409拒否→再確定も409。 | 一致。三段階化はペイロード形状のみに影響し、確定・拒否の検査自体は前回から不変の厚さ。 |
| TDR-GTH-34 | 参加者が確定前に日程GOING、shop_aにWANT_TO_GO投票。別参加者がshop_bにOK_TO_GO投票（=`link`は一度もshop_bに答えない、シナリオの新Given「一度も答えなかった店が1件ある」を満たす）。幹事がshop_aを確定。`link`が開き直すと`decision.shopVotes`が`{shop_a: "WANT_TO_GO", shop_b: "UNANSWERED"}`と**完全一致**（辞書の完全等価比較、他の店・他の値の混入も検出できる）。確定後の名前操作コントロール不在（前回Major#2の修正）も継続して検査。 | 一致し、ADR-0046決定4/未決事項3の決着（未回答店も`UNANSWERED`として列挙する）を過不足なく検証しており模範的。 |
| TDR-GTH-35/36 | （無変更）確定後は新規リンク発行不可／既存リンクは再コピー可。 | 一致（本ラウンドの変更なし、リグレッションの兆候なし）。 |
| TDR-GTH-37 | 参加者が投票画面を開き、DOM順が`ParticipantView.shopVoteQuestions`のAPI順と一致することを確認（近い順、TDR-GTH-08と同じ自己整合性による検証——実座標を読めないことによる構造的な限界、既存の記録どおり）。開いた直後のDOM順を記録し、店の1つに投票した後、DOM順が記録した並びと**完全に不変**であることを検査。 | 一致。「近い順」と「投票しても変わらない」の両方を、それぞれ異なる検査手段（前者は自己整合性、後者は実測前後比較）で個別に証明しており、後者について本番不具合の再発防止として直接的。 |
| TDR-GTH-38 | 幹事が5件選定画面を開き、`gathering-open-shop-map`が存在し、`gathering-open-shop-map-marker`の`data-shop-id`集合が一覧項目の`shopId`集合と一致すること、各一覧項目に徒歩・席数・禁煙・予算感の4フィールドが存在すること、店ページリンクのhrefが`previewOpenShopsForCandidateDate`の`providerPageUrl`と一致することを検査。直後に`screen_has_no_forbidden_controls_or_disclosures`を実行（前回Major#1への言及コメント付き）。 | 一致するが、マーカー対応検査の様式に弱点がある（下記Major 1）。 |
| TDR-GTH-39 | 3店shortlist後、参加者が投票画面を開き、`gathering-shop-vote-map`の存在、マーカーの`shopId`集合が投票質問要素の`shopId`集合と一致すること、各質問要素に4フィールド＋店ページリンク（href一致）が存在することを検査。直後に`screen_has_no_forbidden_controls_or_disclosures`を実行。 | 一致するが、同じ弱点がある（下記Major 1）。**この呼び出しの時点で`Gathering.votingStartedAt`は既に非nullであるため、`gathering-search-origin-marker`（ADR-0045）も画面上に存在する状態でこの検査を通過している**——TDR-GTH-41自身はこの検査を呼んでいないが、契約のpresenceRule（`shopVoteMap`と同じゲーティング）に照らすと、検索基点マーカーが存在する画面状態はこの時点で実質的に検査を受けている（下記Minor 3参照）。 |
| TDR-GTH-40 | 3店shortlist、2参加者がそれぞれ異なる組み合わせで投票（shop_high: 2/0/0, shop_mid: 0/1/1, shop_low: 0/0/2、いずれもresponded=2）し、幹事ダッシュボードでこの3店の内訳を検査した後、`shortlisted_shop_list_is_ordered_by_combined_tier_descending`でDOM順の`wantToGoCount+okToGoCount`が降順（sorted比較）であることを検査。 | 一致。組み合わせ数を意図的に相異なる値(2/1/0)にすることで、タイブレークの実装依存性に検査結果が依存しないよう設計されており良い。 |
| TDR-GTH-41 | 1店shortlist後、参加者が投票画面を開き、`gathering-shop-vote-map`と`gathering-search-origin-marker`の両方が存在することを検査。 | 一致。契約自身が「座標値そのものの一致は要求しない、存在のみがMust」と明記しており（`test-support-api.yaml`のF1教訓を踏まえた意図的なスコープ限定）、それに過不足なく対応している。ただしこのテスト自身は`screen_has_no_forbidden_controls_or_disclosures`を呼んでいない（下記Minor 3）。 |

## 個別論点

### Major 1: 地図マーカーと一覧項目の対応検査が、姉妹契約（candidate-search）の同種検査より構造的に弱い

`assert_open_shop_list_shows_map_and_shop_details`（TDR-GTH-38）と
`assert_shop_vote_question_list_shows_map_and_shop_details`（TDR-GTH-39）はいずれも、マーカーと
一覧項目（質問要素）の対応を次の1行だけで検査している。

```python
marker_ids = {marker_nodes.nth(index).get_attribute(SHOP_ID_ATTR) for index in range(marker_nodes.count())}
self.assertions.assertEqual(marker_ids, {item["shopId"] for item in items})
```

これは**集合の等価性**しか証明しない。もし実装が同じ店のマーカーを誤って2つ描画し、代わりに別の店の
マーカーを1つも描かない（あるいは逆）という欠陥があっても、両方の店IDが集合として結果に含まれている限り
この検査は緑になる——`marker_nodes.count()`と`len(items)`が一致することも、マーカーIDに重複が無いことも
どちらも検査していない。

これは新規に導入された弱さであり、既存の推測ではなく**同一リポジトリの姉妹契約に、同種の検査に対する
既に確立された、より厳密な様式が存在する**ことで裏付けられる。`candidate_search_browser.py`の
`assert_cards_and_map_show_current_proposal`（マップマーカーとカードの対応検査、同じ「地図要素と
一覧項目をdata属性で相関付ける」という種類のMust）は次の3行で構成される。

```python
cards = self._card_candidate_refs()
markers = [ref for ref in self._marker_candidate_refs() if ref]
self.assertions.assertEqual(cards, expected_refs)
self.assertions.assertEqual(sorted(markers), sorted(expected_refs))
self.assertions.assertEqual(len(markers), len(set(markers)))
```

`sorted(markers) == sorted(expected_refs)`（件数一致・値一致をリスト比較で担保）と
`len(markers) == len(set(markers))`（重複マーカーの明示的な禁止）という、集合比較にはない2つの追加保証を
既に持っている。今回追加された2つのgathering側マーカー検査（TDR-GTH-38・39）はこの先例に倣わず、より
弱い集合比較のみを採用しており、「地図と店の情報が幹事の選定・参加者の投票それぞれに出ること」という
本ラウンドの核心的な約束（依頼の確認事項(e)）の証明強度が、既存の同種実装より後退している。

**該当箇所**: `gathering_scheduling_browser.py`の`assert_open_shop_list_shows_map_and_shop_details`
（TDR-GTH-38用）・`assert_shop_vote_question_list_shows_map_and_shop_details`（TDR-GTH-39用）の
いずれも同じパターン。

### Minor 1: `assert_shop_vote_tally`が、双子である`assert_shortlisted_shop_tally`と異なり三段階の自己整合性（`want_to_go+ok_to_go+not_going==responded`）を検査しない

`assert_shortlisted_shop_tally`（幹事向け）は3値の合計が`responded`と一致することを明示的に
`assertEqual`で検査するとdocstringも明記している（"checked here too, not only trusted"）。一方、
参加者向けの双子`assert_shop_vote_tally`（`gathering-shop-vote-tally`要素、同じ`ShopVoteStatus`
契約不変量を持つはずの`ParticipantShopVoteOption.tally`）にはこの自己整合性チェックが無い——各値を
呼び出し元が渡した期待値とだけ比較する。呼び出し元（TDR-GTH-29）が渡す期待値自体が整合的な組み合わせ
（`want_to_go=1, ok_to_go=1, not_going=0, responded=2`）であるため、この非対称自体が現時点で実害の
あるテストの穴を生んではいないが、双子メソッド間の検査の厚みが揃っていない。

### Minor 2: TDR-GTH-37は「投票しても変わらない」を自分の投票でのみ検査し、他の参加者の投票による影響は検査していない

契約の`orderingInvariant`は「この順序は、この参加者によるものであれ他の参加者によるものであれ、投票が
行われた・変更された・未回答のままであることに起因するいかなる理由によっても変化してはならない」と、
自分以外の参加者の投票による影響も明示的に述べている。TDR-GTH-37は自分（`link`ただ1本）の投票前後の
順序不変性のみを検査しており、別の参加者が投票した場合に順序が動かないことは（別リンクでの投票→
このリンクを開き直す、という手順が必要になり）検査されていない。距離基準の並びは投票結果と無関係な
値から決まる設計（ADR-0044決定2）であるため実害の可能性は低いが、契約文言が明示する対象の一部が
未検査のまま残っている。

### Minor 3: TDR-GTH-41は`screen_has_no_forbidden_controls_or_disclosures`を自分では呼ばない——ただし実質的な検査は別シナリオ経由で行われている

TDR-GTH-38・39は、それぞれが新設する画面状態に対して明示的にこの横断検査を呼んでいる（前回監査
Major#1・FR-030への言及コメント付き）。TDR-GTH-41は`gathering-search-origin-marker`という新設の
表示要素を検査する専用シナリオだが、このテスト自身はこの横断検査を呼んでいない。

もっとも、契約の`presenceRule`により`gathering-search-origin-marker`は`gathering-shop-vote-map`と
全く同じゲーティング（`Gathering.votingStartedAt`が非null）で出現するため、TDR-GTH-39が
`organizer_shortlists_shops_via_api`実行後に参加者画面を開いて横断検査を呼ぶ時点で、この検索基点
マーカーは**既に画面上に存在した状態**でその検査を通過している——契約の意味論上、これは偶然ではなく
必然の副次的カバレッジである。したがって「検査対象の画面状態が一度も横断検査を受けていない」という
FR-030・前回Major#1と同種の欠落には該当しないと判断するが、**この副次的カバレッジはTDR-GTH-39の
コード自体からは意図が読み取れず**（`assert_shop_vote_question_list_shows_map_and_shop_details`の
docstringも検索基点マーカーの存在を前提とした説明をしていない）、次にこの画面のGiven手順が変わった
場合（例: 検索基点マーカーが出る前の状態で先に横断検査を呼ぶよう改変された場合）に気づかれずに
カバレッジが失われるおそれがある。依頼文が「今回は最初から条件に入れて依頼した」と明記している以上、
TDR-GTH-41自身が明示的に呼ぶ形にしておくのが望ましい（防御的な明示性の問題であり、実際のカバレッジの
欠落ではないため、Blocker/Majorではなく記録に留める）。

## レビューチェックリスト（5観点）

1. **過不足**: 過剰な検査は見当たらない。不足はMajor 1（マーカー対応検査の強度）とMinor 1〜3のとおり。
   TDR-GTH-26〜41の16シナリオすべてに対応するテストメソッドが存在し、シナリオ→テストの1対1対応の
   欠落は無い。新設10メソッド（DSL・steps両層）はすべてテスト本体から最低1回呼ばれており、旧・
   二択承認投票モデルの識別子はライブコードから完全に一掃されている（docstring中の説明文のみ残存）。
2. **Givenの正当性**: ADR-0037決定1に全面準拠。本ラウンドで新規追加されたGiven/Then用の値取得ヘルパー
   （`fetch_confirmed_date_open_shop_preview`・`fetch_participant_view_via_api`）はいずれも
   `previewOpenShopsForCandidateDate`・`getParticipantView`という既存の公開API境界を叩くのみで、
   新しいtest-supportシームは一切追加されていない（test-support-api.yaml側の変更も「新しいseamは
   要らない」と明記された`x-acceptance-scenarios`登録のみ）。
3. **Thenの検証対象**: 依頼された核心的な約束(a)〜(d)・(f)はいずれも緩められておらず、TDR-GTH-34・37の
   検査はむしろ最小要求より厚い（辞書の完全一致比較、投票前後の実測比較）。(e)についてはMajor 1の
   とおり構造的な弱さがある。契約が明記する新設Must（三段階の語彙・並び順・地図・詳細情報・検索基点）
   はいずれも対応するシナリオが存在し、未検査のまま放置された契約Mustは（Major 1の対応検査強度を
   除き）見当たらない。
4. **失敗の握りつぶし**: `try/except`によるエラー隠蔽、無条件`pass`、意味のない`assertTrue(True)`の
   類は見当たらない。`assert_participant_decision`の`shopVotes`比較が部分一致（`assertIn`等）ではなく
   完全な辞書等価（`assertEqual`）になっている点は、他の参加者の情報混入や店の取りこぼしを両方検出
   できる形であり、握りつぶしの反対（厳格化）の好例。
5. **暗黙の前提**: TDR-GTH-40が「行きたい/行ってもいい」の合算値をあえて3店で相異なる値(2/1/0)に
   することでタイブレーク実装への依存を避けている点は明示的に良い設計。TDR-GTH-37の近い順検査が
   API自身の主張との自己整合性に留まり実座標を独立に検算していない点は、TDR-GTH-08から続く既知の
   構造的限界であり新規の暗黙の前提ではない（既存の記録どおり）。Minor 3で述べた「TDR-GTH-39実行時に
   検索基点マーカーが既に存在する」という事実に依存した副次的カバレッジは、暗黙のままでは次の改変で
   気づかれずに失われうる暗黙の前提である。

## 契約↔テスト対応の監査

- **承認済みシナリオのうちstep未実装のもの**: 無し（TDR-GTH-26〜41すべてに対応するテストメソッドが
  存在する。`test_tdr_gth_*`の連番に欠番は無い）。
- **シナリオに対応しない孤児step**: 無し。`fetch_confirmed_date_open_shop_preview`・
  `fetch_participant_view_via_api`はstepsから直接呼ばれない内部DSLヘルパーだが、いずれも同ファイル内の
  公開DSLメソッド（`assert_open_shop_list_shows_map_and_shop_details`・
  `assert_shop_vote_question_list_shows_map_and_shop_details`・
  `assert_shop_vote_question_order_matches_participant_view`）から呼ばれており死蔵コードではない。
- **同義stepの重複**: 見当たらない。`participant_answers_shop_vote`（単発）と
  `participant_answers_shop_votes`（複数、内部で単発をループ）は旧`toggle_shop_vote`/`vote_for_shops`
  と同じ「単発+複数形」の対の様式を踏襲しており、重複ではなく意図的な設計。
- **契約が定めるがどのシナリオ番号にも紐付かないMust**: `allowedPurposes`（23件）・`forbiddenTestIds`
  （3件）はDSL側の定数と完全一致することを機械的に確認済み。`voteOptions`の
  `cardinality: exactly-three-per-gathering-shop-vote-question`（店ごとに三択の要素が正確に3個
  存在すること）は、本ラウンドのどのテストからも独立には検査されていないが、これは既存の
  `scheduleQuestion.responseOptions`（同型の三択、TDR-GTH-01〜25のいずれからも同様に未検査）と
  同じ、このテストスイート全体で一貫した既存の慣行であり、本ラウンドで新規に生じた欠落ではないと
  判断した。

## 前回までの監査指摘の再発チェック

- **Major#1（横断検査の呼び忘れ、FR-030、2回連続再発）**: **今回は再発していない**。TDR-GTH-38・39が
  それぞれ新設する画面状態（地図付き選定画面・地図付き投票画面）の両方に対し、明示的な呼び出しと
  「前回監査Major#1」への参照コメントが付いている。依頼文が「今回は最初から条件に入れて依頼した」と
  述べたとおり履行されている。ただし前回・前々回と異なり、本ラウンドが新設する画面状態の数自体が
  少ない（2面）ため、次に同種の抜けが起きるとすればより微妙なケース（Minor 3のような副次的カバレッジに
  依存する画面）で起きる可能性がある——FR-030が挙げた押し込み案(b)（L2で「各画面状態が最低1回横断検査を
  受けていること」を機械検査する）は、本ラウンドの結果を見ても依然として有効な提案だと判断する。
- **前回Major#2（確定後の名前操作コントロール不在の未検査）**: TDR-GTH-34で`participant_name_controls_
  are_absent()`が引き続き呼ばれており、後退していない（本ラウンドの差分では無変更）。
- **前回Major#3（409/400エラー分岐の一部未検査）**: `GATHERING_NOT_IN_SELECTING_SHOP_PHASE`・
  `SHOP_VOTING_NOT_STARTED`・`INVALID_SHOP_SELECTION`の残りトリガー・`finalizeGathering`再試行の
  いずれも、TDR-GTH-26・27・30・33のコメント付きで引き続き検査されており後退していない。
- **FR-031（全文再構成でTDR-GTH-38〜41が消えた事故）**: この事故は契約ブランチ側
  （`contracts/gathering-three-tier-vote`）の出来事であり、本監査対象（テストブランチ）とは別の
  作業だが、念のため契約側の現在の状態を確認した——`gathering-scheduling-browser-interface.yaml`の
  `profiles.localAcceptance.verifiesScenarios`・`test-support-api.yaml`の
  `x-acceptance-scenarios`のいずれにもTDR-GTH-38〜41が登録されており、消失は解消済みで本監査対象の
  テストコードにも影響していない。

## 人間の承認判断のためのチェックリスト

- [ ] Blocker: 0件（本監査の判定）
- [ ] Major 1（地図マーカー対応検査が姉妹契約の同種検査より弱い、TDR-GTH-38・39の両方）を、本PRの
      ブロッカーとしてtesterへ差し戻すか、次PRへ送るか——`candidate_search_browser.py`の
      `assert_cards_and_map_show_current_proposal`と同じ3行パターン（sorted比較＋重複無し検査）への
      置き換えは軽微な修正で済むと見積もる
- [ ] Minor 1（`assert_shop_vote_tally`の自己整合性チェック欠如）・Minor 2（TDR-GTH-37が他参加者の
      投票による影響を検査しない）・Minor 3（TDR-GTH-41が横断検査を自分で呼ばない）を、本PRで
      対応するか次回送りにするか
- [ ] FR-030の押し込み案(b)（L2で画面状態ごとの横断検査カバレッジを機械検査する）を、今回2回連続の
      非再発を踏まえてもなお着手するか、もう少し証拠を積むか
- [ ] TDR-GTH-26〜41が依拠する4契約（`.feature`・`api.yaml` v0.8.0・`browser-interface.yaml` v0.7.0・
      `test-support-api.yaml` v1.5.3）はいずれも`status: 承認待ち`——本PRのマージが骨格承認・実装承認を
      兼ねる従来運用のままで良いか
- [ ] `adr/0046`は`status: 提案中`（人間裁定を経ていない技術的判断の記録）——本ラウンドのテストは
      この提案中のADRが記録した設計判断（店ページリンクのpurpose宣言対象外、地図要素識別子、定休日を
      出さない）にすべて追随しているが、ADR自体の承認は別途必要

以上。
