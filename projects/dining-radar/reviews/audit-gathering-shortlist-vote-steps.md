# 独立監査: TDR-GTH-26〜36 step定義・DSL（店の絞り込み連携・承認投票・確定）

- 監査対象コミット: `0966059`（`origin/test/gathering-shortlist-vote-steps`。ローカルでは
  検証のため `review/gathering-shortlist-vote-steps` を同一コミットに作成して checkout した
  ——`test/gathering-shortlist-vote-steps` ブランチ名は別worktreeが既に使用中だったため）。
- 監査対象範囲: `git diff origin/contracts/gathering-shortlist-vote-finalize...origin/test/
  gathering-shortlist-vote-steps -- projects/dining-radar/tests/acceptance/`
  - `tests/acceptance/dsl/gathering_scheduling_browser.py`（追加分、TDR-GTH-26〜36）
  - `tests/acceptance/steps/gathering_scheduling_steps.py`（追加分）
  - `tests/acceptance/test_gathering_scheduling_acceptance.py`（TDR-GTH-26〜36の11テスト）
  - TDR-GTH-01〜25は本文無変更（docstringのシナリオ範囲表記のみ更新）であることを確認済み。
- 依拠した契約: `contracts/gathering-scheduling.feature`（TDR-GTH-26〜36）、
  `contracts/gathering-scheduling-api.yaml` v0.5.1、
  `contracts/gathering-scheduling-browser-interface.yaml` v0.5、
  `contracts/test-support-api.yaml` v1.5.0、`adr/0037`・`adr/0040`・`adr/0041`・`adr/0042`。
- 独立性の担保: 対訳表はコード（DSL・steps・テスト本体）を先に読み下し、その後に
  `gathering-scheduling.feature`のシナリオ文と突き合わせる順で作成した。tester のdocstring・
  コメントは「コードが実際に何をしているか」の記述として引用する場合に限り採用し、意図の
  弁明・自己申告としては採用していない。`src/**` は読んでいない（この半分のスライスには
  そもそも実装が存在しない——`0966059`のコミットメッセージ自体がそう明記している）。
- 実行した機械検証: `python -c "ast.parse(...)"` で3ファイルの構文検証（OK）、
  `python -m pytest tests/acceptance/test_gathering_scheduling_acceptance.py --collect-only -q`
  でTDR-GTH-01〜36の36テストが例外無く収集できることを確認した（インポート・デコレータ・
  fixtureの配線に破綻が無いことの確認）。**L4の実行（ブラウザ+バックエンド相手の実走）は
  行っていない**——このコミットには対応する実装が存在せず（`0966059`のコミットメッセージが
  明示）、実行しても「実装が無いことによる失敗」以外の情報は得られないため。本監査はコード
  読解と契約突き合わせのみに基づく。govlint等のL0検証はcontracts側の変更を伴わないため対象外。

## 結論（先頭サマリ）

**Blocker: 0件。Major: 3件。Minor: 1件。**

5つの核心的な約束（(a)自分が投票した後にだけ他者の票が見える、(b)D7差し替えでの店ごとの
分母、(c)確定の不可逆性、(d)FINALIZED局面で消える操作コントロールの一覧、(e)確定後の
参加者画面が他者の情報を含まない）は、いずれも**緩められることなく**、そして最小要求より
厚い形で検査されている。特に(d)は`assert_finalized_controls_are_absent`が
`adr/0042`決定3が列挙する8項目（7つのtest-id + 1つのpurpose属性）と過不足なく1:1で
対応しており模範的。(e)はTDR-GTH-34が2人の参加者に異なる店を承認させ、確定後の
`decision.yourApprovedShops`が**自分が承認した店だけ**（他方の参加者が承認した店を含まない）
ことを実データで検証しており、これも模範的である。「保留→送信」（`assert_no_shortlist_
recorded_yet`）も、送信前にサーバー側状態が空のままであることをGETで独立に確認しており、
妥当な証明になっている。Given状態の構築はADR-0037決定1（公開API境界経由）に全面的に
従っており、新しいtest-supportシームは導入されていない。

一方で、契約が明記する複数のMustが**未検査のまま**残っている。最も重いのは、この契約改訂で
新設された6つのpurpose（`gathering-open-shop-select`等）を含む6つの新しい画面状態
（5件選定・投票中差し替え・確定操作・FINALIZED後の幹事画面・参加者投票画面・参加者確定後
画面）のいずれに対しても、横断検査`screen_has_no_forbidden_controls_or_disclosures`が
**一度も呼ばれていない**ことである——これは本プロジェクトの前回監査
（`audit-gathering-scheduling-steps.md`論点5、および同ファイルにtester自身が残した
「Major#3」の再発防止コメント）が既に一度指摘・是正した同じ種類の欠落が、新しい画面群
全体（6面すべて）に対して未対応のまま再発したものである。

## 対訳表（コードから読み取った記述 → シナリオとの突き合わせ）

| ID | 実際にコードが行うこと | シナリオ文との一致 |
|---|---|---|
| TDR-GTH-26 | API Givenで「開催日確定済み・店を選び中」の会を作り、幹事ダッシュボードを開いて`gathering-open-shop-list`の先頭5件をUIクリックで選択（`data-shortlisted`のtrue化を確認）。選択直後、`GET /gatherings/{id}`で`shortlistedShops`が依然`[]`であること（サーバー未送信）を確認してから、送信ボタンをクリック（`setShortlistedShops`を呼ぶ）。DOM上の`gathering-shortlisted-shop-list`のshopId集合が選んだ5件と一致し、局面が`SELECTING_SHOP`のまま変わらないことを検査。 | 一致。かつ「チェックだけでは送信しない」ことをサーバー状態の直接確認で証明しており、最小要求より厚い。 |
| TDR-GTH-27 | まだSCHEDULINGの会で、全店開店の木曜と1店定休の月曜を仮選択して`previewOpenShopsForCandidateDate`のshopId集合を比較差分し、月曜だけ閉まっている1店を特定（テスト構築技法、SCHEDULING中でなければ実行不能）。月曜を確定してSELECTING_SHOPへ進め、UI上の`gathering-open-shop-list`にその店が出現しないことを検査。さらにAPI直叩きでその店をshortlistしようとし`400 INVALID_SHOP_SELECTION`を検査。 | 一致。UIでの不可視性とAPIでの拒否の両方を検査しており厚い。 |
| TDR-GTH-28 | API Givenで2店をshortlistし、リンク発行・参加者が開き、UIでshop_aにチェック（`setShopVotes`即時送信）→`your-approval`がa=true/b=falseを検査→shop_aのチェックを外す（0件に戻す）→a=false/b=falseを検査→参加者ビュー全体が正常状態であることを検査。 | 一致。「1つも選ばないことも選べる」を明示的に検査（0件へ戻す操作が拒否されないこと）。 |
| TDR-GTH-29 | 別リンクの参加者Aがshop_aに投票済みの状態で、参加者Bがリンクを開く。**投票前**: shop_a・shop_bともタリー要素が不在であることを検査。参加者Bがshop_aに投票した**後**: shop_aのタリーが`approval=2, responded=2`、shop_b（Bが承認しなかった店）も`approval=0, responded=2`として出現することを検査。 | 一致。投票前の不在・投票後の出現の両方を検査し、かつ自分が承認しなかった店の集計まで見えることまで実証しており厚い。 |
| TDR-GTH-30 | 1参加者がshop_aに投票→a=true/b=falseを検査→shop_bも追加投票→shop_aを外す→最終的にa=false/b=trueであることを検査。 | 一致。 |
| TDR-GTH-31 | 5店shortlist、2参加者がそれぞれ異なる組み合わせで投票（shop_0=2票, shop_1=1票, shop_2=0票、分母はいずれもresponded=2）。UIでshop_4→shop_5へ差し替え（`replace_shortlisted_shop`は、差し替えパネルを開いた直後に**残す店（old_shop_id）がdata-shortlisted="true"で事前チェックされていること自体も検査**してから、旧店を外し新店を追加して送信）。差し替え後、shop_0/1/2の3店のタリーがそれぞれ異なる値のまま不変であることを再検査。 | 一致。異なる票数を持つ3店で「残した票が変わらない」ことを実測しており厚い。 |
| TDR-GTH-32 | 5店shortlist、1参加者がshop_0に投票済みの状態でshop_4→shop_5へ差し替え。参加者が再度リンクを開くと、shop_5の`your-approval`が`"UNANSWERED"`でタリー不在であることを検査。幹事側では同じshop_5のタリーが`approval=0, responded=0`（他の店のresponded=2とは異なる、addedAt基準の分母）であることを検査。 | 一致。D7の店ごと分母（addedAt基準）を組織者側・参加者側の両方の観測面から実測しており模範的。 |
| TDR-GTH-33 | 2店shortlist、リンク発行後、幹事がUIでshop_aを確定選択して送信（`finalizeGathering`）。局面が`FINALIZED`になることと、ADR-0042決定3が列挙する操作コントロール一覧（後述）が過不足なく不在になることを検査。その後、同じ参加者リンクでAPI直叩きの日程回答・店投票をそれぞれ試み、両方`409 GATHERING_FINALIZED`であることを検査。 | 一致。「日程の回答と店の投票はそれ以上受け付けられなくなる」を両方個別に検査。 |
| TDR-GTH-34 | 参加者が確定前にGOINGで回答済み、幹事が2店shortlistし、その参加者はshop_a、**別の参加者**はshop_bにそれぞれ投票。幹事がshop_aを確定。元の参加者がリンクを開き直すと、`decision`が`confirmedCandidateDate`・`shopId=shop_a`・`yourScheduleResponse="GOING"`・`approvedShopIds=[shop_a]`（**shop_bを含まない**）ちょうどそれだけであることを検査。加えて`gathering-schedule-question`/`gathering-shop-vote-question`/`gathering-participant-progress`がすべて不在（完全な置き換え）であることを検査。最後にAPI直叩きの日程回答・投票を試み両方`409`を検査。 | 一致。「他の参加者の回答や投票は示されない」を、実際に別の参加者が異なる店を承認した状況で`approvedShopIds`から除外されることを検証しており、最小要求より厳密。ただし`gathering-participant-name-open`/`-submit`の不在（下記Major2）はここでも未検査。 |
| TDR-GTH-35 | 1店shortlist、幹事が確定。API直叩きで新規リンク発行を試み`409 GATHERING_FINALIZED`を検査。確定後コントロール一覧の不在も再検査。 | 一致。 |
| TDR-GTH-36 | 幹事が確定**前**にUIでリンクを1本発行、1店shortlistして確定。確定**後**、同じリンクをUIの再コピーボタンでクリックし（ボタンが実際に到達可能・有効であることを実演）、返るURLが元のURLと一致することを検査。 | 一致。API許可の確認に留まらずUI操作として再コピー可能性を実演しており厚い。 |

## 個別論点

### Major 1: 横断検査（`screen_has_no_forbidden_controls_or_disclosures`）が新しい6画面のいずれにも一度も効いていない

`GATHERING_ALLOWED_PURPOSES`には今回の6つの新purpose
（`gathering-open-shop-select`・`gathering-shortlist-submit`・`gathering-shortlist-open`・
`gathering-finalize-shop-select`・`gathering-finalize-submit`・`gathering-shop-vote-select`）
が正しく追加されている（`gathering-scheduling-browser-interface.yaml`の
`allowedPurposesNote2026_09_04`と1件も過不足なく一致）。しかし、この登録を実際に検証する
`assert_gathering_screen_has_no_forbidden_surfaces`（`steps.screen_has_no_forbidden_controls_
or_disclosures`）は、TDR-GTH-26〜36の11テストのいずれからも**一度も呼ばれていない**。
既存のTDR-GTH-01〜25では8箇所で呼ばれているのと対照的である（`grep`で確認済み、行113・
149・207・221・324・417・425・440はすべてTDR-GTH-26より前）。

この結果、次の6つの新しい画面状態は、`unavailableControls.forbiddenTestIds`／
`allowedPurposes`／`forbiddenPurposes`、および`disclosureObservations`の canary文字列検査の
**どれも一度も適用されないまま**マージされうる。

- `organizerDashboard.shortlistSelection`（5件選定、初回）
- `organizerDashboard.shortlistedShopVotes`（投票中、D7差し替えパネルを開いた状態を含む）
- `organizerDashboard`の確定操作面（`gathering-finalize-shop-select`/`-submit`が存在する状態）
- `organizerDashboard.finalizedSummary`（FINALIZED後の幹事画面）
- `participantAnswer.shopVoteQuestion`（参加者の投票画面）
- `participantAnswer.finalizedView`（参加者の確定後画面）

このファイル自身の`assert_gathering_screen_has_no_forbidden_surfaces`のdocstringは
「reviewer audit Minor#4」という前回監査の再発防止コメントを残しており、この種の欠落が
一度指摘・修正された実績がある（`audit-gathering-scheduling-steps.md`論点5、および
TDR-GTH-02のコード中コメント「Reviewer audit Major#3: the cross-cutting forbidden-surfaces
check ... had never run while gathering-add-candidate-date-form/-input ... actually existed
in the DOM」）。今回はその同じ失敗パターンが、新設された画面6面**全て**に対して再発している
——registrationは正しく更新されているが、それを実際に発火させる呼び出しが1つも追加されて
いない。未登録の操作コントロールがこれらの画面のどこかに紛れ込んでも、どのテストも検知
できない。

### Major 2: 参加者の確定後画面で「名前を変える操作も置かない」（adr/0042決定4）が未検査

`gathering-scheduling-browser-interface.yaml`の`nameControl.open`/`submit`はいずれも
「Absent once `ParticipantView.decision` is non-null」と明記し、`adr/0042`決定4も
「Final.dc.html B-3: "名前を変える操作も置かない"」と名指ししている。しかし
`assert_participant_question_surfaces_are_replaced`（TDR-GTH-34で使用される唯一の
「確定後は操作面が全て置き換わる」検査）は`[SCHEDULE_QUESTION, SHOP_VOTE_QUESTION,
PARTICIPANT_PROGRESS]`の3要素の不在だけを検査し、`gathering-participant-name-open`/
`gathering-participant-name-submit`は含まれていない。`grep`で確認した限り、この2つの
test-idの不在は、TDR-GTH-26〜36のどのテストからも、また既存のTDR-GTH-01〜25のどの
テストからも一度も検査されていない——確定後の参加者画面に「操作はありません」という
契約の主張のうち、名前変更操作の消失分だけが未実証のまま残っている。

### Major 3: 新設された409/400エラー分岐のうち、複数が一度も踏まれていない

今回の契約改訂で新設・拡張された4つのエラーコード
（`GATHERING_NOT_IN_SELECTING_SHOP_PHASE`・`SHOP_VOTING_NOT_STARTED`・
`INVALID_SHOP_SELECTION`・再利用の`GATHERING_FINALIZED`）のうち、後者2つは手厚く検査されて
いる一方（`GATHERING_FINALIZED`はsetScheduleResponse・setShopVotes・issueParticipantLinksの
3操作すべてで検査済み）、前者2つは`grep`で確認した限りテストコード中に**一度も出現しない**。

- `GATHERING_NOT_IN_SELECTING_SHOP_PHASE`（`setShortlistedShops`/`finalizeGathering`が、
  まだSCHEDULING局面のまま呼ばれた場合の409）: 未検査。
- `SHOP_VOTING_NOT_STARTED`（`finalizeGathering`/`setShopVotes`が、`shortlistedShops`が
  空のまま呼ばれた場合の409）: 未検査。
- `INVALID_SHOP_SELECTION`は`setShortlistedShops`の「開いていない店」ケース（TDR-GTH-27）
  でのみ検査されており、契約の`InvalidShopSelection`が明記する残り2つのトリガー——
  `setShopVotes`/`finalizeGathering`が現在のshortlistに存在しない`shopId`を指定した場合、
  および`SetShortlistedShopsRequest.shopIds`の件数境界（0件、または6件以上——P2で人間裁定
  済みの境界）——はいずれも未検査。
- `finalizeGathering`自身の409の3つ目の分岐（既にFINALIZED後に再度`finalizeGathering`を
  呼んだ場合）も未検査（TDR-GTH-33/35/36はいずれも確定後に他の操作の拒否は検査するが、
  確定操作自体の再試行は検査していない）。

これらはいずれも`.feature`の特定のシナリオ番号には紐付かない（`INVALID_SHOP_SELECTION`の
「開いていない店」トリガーだけがTDR-GTH-27として明文化されている）契約レベルのMustだが、
契約自身が明示的にコード・exampleペイロードまで書いている分岐である。過不足の「不足」側
として記録する。

### Minor 1: `gathering-list-item`の名前属性（`adr/0042`決定6）はこの回のスコープ外

`adr/0042`決定6は`gathering-list-item`へ`data-gathering-title`を追加したとしているが、
`grep`で確認した限りTDR-GTH-26〜36のどのテストもこの属性を検査していない。もっとも、この
属性は会一覧画面（TDR-GTH-21/22/25が扱う画面）に属し、TDR-GTH-26〜36のどのシナリオにも
直接紐付かない——本ラウンドの監査対象診断（店の絞り込み・投票・確定）の範囲外である可能性が
高い。次に会一覧まわりのstepを改訂する回で拾われるべき事項として記録するに留め、本ラウンドの
Blocker/Majorには含めない。

## レビューチェックリスト（5観点）

1. **過不足**: 過剰な検査（契約より厳しすぎる誤検出リスク）は見当たらない。不足はMajor
   1〜3のとおり複数ある。TDR-GTH-26〜36の11シナリオ全てに対応するテストメソッドは存在し、
   シナリオ→テストの1対1対応の欠落自体は無い（`pytest --collect-only`で36件全て収集確認）。
2. **Givenの正当性**: ADR-0037決定1に全面準拠。新設されたGiven-state builder
   （`create_selecting_shop_gathering`・`fetch_confirmed_date_open_shop_ids`・
   `set_shortlisted_shops_via_api`・`identify_a_shop_closed_on_the_confirmed_date`）は
   すべて公開API（`gathering-scheduling-api.yaml`）経由であり、新しいtest-supportシームは
   一切追加されていない（`grep`で`test-support`参照が既存の期限切れ・レート制限・母集団
   モード設定に限られることを確認済み）。
3. **Thenの検証対象**: (a)〜(e)の核心的な約束はいずれも緩められておらず、最小要求より厚い
   検査が複数箇所にある（TDR-GTH-29・31・32・34、特に(d)の`assert_finalized_controls_are_
   absent`は`adr/0042`決定3の列挙8項目と過不足なく一致）。一方でMajor2・3のとおり、契約が
   明記する一部のThen/Mustが未検査のまま残る。
4. **失敗の握りつぶし**: `try/except`によるエラー隠蔽、無条件`pass`、意味のない
   true assertionは見当たらない。全アサーションヘルパーは既存の共有インフラ
   （`assert_all_absent`/`assert_present`等）をそのまま再利用しており、新規に緩められた
   挙動は無い。`assert_no_shortlist_recorded_yet`は「送信していないこと」を、送信前の
   サーバー側`shortlistedShops`が空のままであることのGET確認という形で証明しており、
   ネットワーク傍受は使っていないが、`setShortlistedShops`がこの配列を変更する唯一の
   操作であることを踏まえると妥当な間接証明になっている。
5. **暗黙の前提**: `identify_a_shop_closed_on_the_confirmed_date`は「候補日の開店店舗集合の
   差分が必ずちょうど1件になる」という、この契約のテストデータ（`OPEN_SHOP_COUNT_BY_
   WEEKDAY`）に固有の前提を`assertEqual(len(closed_ids), 1, ...)`で明示的に検査しており、
   崩れれば即座に失敗する（握りつぶしではない）。もう一点、`select_first_n_open_shops_for_
   shortlist`は開いている店の一覧の**DOM順**が5件以上存在することを暗黙に前提とするが、
   これは既存の`previewOpenShopsForCandidateDate`のキャップ（現状10件）の範囲内であり、
   `GATHERING_OPEN_SHOP_WEEKDAY_MATCH`モードの木曜=6件という既知値と整合するため、
   本ラウンドで新たに導入された脆さではない。

## 契約↔テスト対応の監査

- **承認済みシナリオのうちstep未実装のもの**: 無し（TDR-GTH-26〜36すべてに対応する
  テストメソッドが存在する）。
- **シナリオに対応しない孤児step**: 無し。DSL層の非公開ヘルパー
  （`current_preview_shop_ids`・`_read_open_shop_list_items`・`_open_shop_list_item_locator`・
  `toggle_open_shop_selection`・`_read_shortlisted_shop_items`・`open_shortlist_replace`・
  `_shop_vote_question_locator`・`_read_participant_decision`）はstepsから直接呼ばれないが、
  いずれも同ファイル内の公開DSLメソッドから内部的に呼ばれており、死蔵コードではない
  （grep + 手動確認済み）。
- **同義stepの重複**: 見当たらない。
- **契約が定めるがどのシナリオ番号にも紐付かないMust**の未検査は、上記Major1〜3および
  Minor1として記録した。

## 人間の承認判断のためのチェックリスト

- [ ] Blocker: 0件（本監査の判定）
- [ ] Major1（横断検査が新6画面に一度も効いていない）を、本PRのブロッカーとして
      testerへ差し戻すか、次PRへ送るか——前回監査で同種の欠落が「Major」として是正された
      先例があることに留意
- [ ] Major2（参加者確定後画面の名前操作コントロール不在が未検査）を、本PRのブロッカーと
      するか次PRへ送るか
- [ ] Major3（`GATHERING_NOT_IN_SELECTING_SHOP_PHASE`・`SHOP_VOTING_NOT_STARTED`・
      `INVALID_SHOP_SELECTION`の残り2トリガー・`finalizeGathering`の再試行、いずれも未検査）
      をどこまで本PRで埋めるか、どこまで契約Mustとして許容範囲内と判断するか
- [ ] Minor1（`data-gathering-title`）は本ラウンドのスコープ外として次回送りにするか
- [ ] TDR-GTH-26〜36が依拠する`gathering-scheduling-api.yaml`・`-browser-interface.yaml`・
      `.feature`はいずれも`status: 承認待ち`——本PR（一連の契約PR）のマージが骨格承認・
      実装承認を兼ねる運用（`adr/0042`が明記）のままで良いか

以上。
