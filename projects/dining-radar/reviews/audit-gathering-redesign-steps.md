# 独立監査: 会の画面群の再設計（第2段、TDR-GTH-49〜56・TDR-CS-20〜21ほか）

- **監査対象**: `git diff main...HEAD -- projects/dining-radar/tests/acceptance/`
  （`test/gathering-redesign-steps-2`のHEAD、commit `7e6e56f`。`test/gathering-redesign-steps`
  分と合わせて2回ぶん）。対象ファイル: `dsl/gathering_scheduling_browser.py`・
  `dsl/candidate_search_browser.py`・`steps/gathering_scheduling_steps.py`・
  `steps/candidate_search_steps.py`・`test_gathering_scheduling_acceptance.py`・
  `test_candidate_search_acceptance.py`。
- **起点の確認**: 指示どおり`git checkout -b review/gathering-redesign-steps
  test/gathering-redesign-steps-2`を実行し、4条件をすべて確認した——
  `git log --oneline -1` = `7e6e56f`／`gathering-scheduling.feature`の`TDR-GTH-56`出現数 = 2
  （シナリオ本文1＋ヘッダコメント1）／`gathering-scheduling-browser-interface.yaml`の
  `contractVersion: '0.18.0'`出現数 = 1／`test_gathering_scheduling_acceptance.py`の
  `def test_tdr_gth_56`出現数 = 1。すべて条件を満たしたため作業を継続した。
- **依拠した契約**: `gathering-scheduling.feature`（TDR-GTH-01〜56）・`candidate-search.feature`
  （TDR-CS-00〜21、07は廃止）・`gathering-scheduling-browser-interface.yaml`（0.18.0）・
  `candidate-search-browser-interface.yaml`（1.10.0）・`gathering-scheduling-api.yaml`
  （v0.14.0）・`test-support-api.yaml`（v1.5.8）・`adr/0054`・`0055`・`0056`（いずれも本worktree内に
  現存することを確認済み）。`adr/0037`決定1（Given状態は公開境界経由）も参照した。
- **独立性の担保**: 本worktree内でBashの相対パス（`cat -n`/`sed -n`/`grep`/`git diff`/`git show`）
  だけを使いコード本体を読み下した。シナリオ文（`.feature`）はコードを読み終えたあとに突き合わせた。
  docstring・コメントは「コードが実際に何をしているか」の記述として引用する場合に限り採用し、
  意図の弁明としては採用していない。`src/**`は読んでいない。

## 結論（先頭サマリ）

**Blocker: 0件。Major: 2件。Minor: 6件。**

この改訂（DSL 1本で800行超・テストで9本の新規シナリオ＋3本の改訂シナリオ）は、tester自身が
「見た目は緑でも実質検査していない」と報告していた箇所（確定確認の変わることの表＝TDR-GTH-53、
「あとで答える」の再掲＝TDR-GTH-42）を、契約0.18.0が新設した行/項目単位の観測面を使って正しく
強化している。`GATHERING_ALLOWED_PURPOSES`（33件）・`ALLOWED_CONTROL_PURPOSES`（18件）は
両契約の`allowedPurposes`列挙とそれぞれ1対1で一致することを、本監査で独自に契約側から
数え上げて確認した。TDR-GTH-49〜56・TDR-CS-20〜21のGivenはいずれも公開API境界（`adr/0037`決定1）
または既存の決定的test-support-apiモード（`GATHERING_OPEN_SHOP_WEEKDAY_MATCH`、曜日ごとの
既知件数）で組み立てられており、0票・同票・発行本数と有効本数の食い違いはすべて作為的に
構成されていて「偶然」に頼っていない。

その上で、**確定後の地図から経路線・輪が本当に消えていることの証明が弱い**（Major1）ことと、
**新設の確定確認ダイアログが横断的な禁止コントロール走査を一度も受けていない**（Major2）ことを
報告する。いずれもtesterの検査対象選定の問題というより、後者は既存の是正パターン（このコードベース
自身が繰り返し実践している「Reviewer audit Major#1」の慣行）の適用漏れであり、前者は契約側が
「経路線」概念に対応するtest idを一つも持たないという構造的な制約に起因する。

## 対訳表（本ラウンドで新規・改訂されたシナリオのみ）

| ID | シナリオ文の要旨 | 実際にコードが行うこと | 一致判定 |
|---|---|---|---|
| TDR-GTH-09（書き換え） | 参加者の回答画面には開いている店の件数も店の情報も示されない | `assert_schedule_question_has_no_open_shop_count`が`data-open-shop-count`属性そのものの`None`（不在）をリテラル文字列キーで検査。`schedule_question_shows_no_shop_details`と併用 | 一致。属性名を定数ではなくリテラルで確認する意図（契約が値を廃止したことの明示）も妥当 |
| TDR-GTH-20（書き換え） | 回答済みの参加者には取り消す操作が示されない | `assert_revoke_control_absent_at`が`assert_absent`で該当行のrevokeコントロール自体の不在を検査。API直叩き（`PARTICIPANT_LINK_ALREADY_ANSWERED`）はdefense-in-depthとして保持 | 一致。無効化ではなく不在への切替が正確 |
| TDR-GTH-34（さらに簡素化） | 確定後は決定内容のみ、自分の過去の回答も店ごとの一覧も示さない | `assert_participant_decision_has_no_own_response_attribute`が`data-your-schedule-response`の不在をリテラル確認、`participant_decision_has_no_shop_breakdown`が既存の不在確認を維持、`finalized_view_still_shows_shop_vote_tally`が「店の生きた集計は見えたまま」という契約の自己矛盾是正（ADR-0055決定8）の**正の**検査を追加し、`assert_shop_vote_option`の不在（投票操作自体は消える）も同時に検査 | 一致。前段の監査が指摘した自己矛盾（presenceRuleとreplacesQuestionSurfacesの不整合）を、より新しい記述（決定8）に沿って正しく解決している |
| TDR-GTH-38（書き換え） | 幹事の投票タリー画面に地図・店名・徒歩・店ページへのリンクが示される | `assert_shortlisted_shop_list_shows_map_and_shop_details`が`getGathering`のAPI応答と`data-shop-name`/`data-walking-time-minutes`/マーカーのshopId集合/`providerPageUrl`をクロスチェック。DOM自己整合だけでなくサーバー実値と突き合わせている | 一致。旧gatheringMode（廃止済み画面）ではなく新画面（shortlistedShopVotes）を正しく対象にしている |
| TDR-GTH-42（あとで答えるの再掲、ADR-0055決定3のstepを強化） | 「あとで答える」で、これまでの回答自体が再掲される | `assert_answer_later_confirmation_reproduces_schedule_answer`が専用test id（`...-confirmation-schedule-item`）を使い、「ちょうど1件・値が一致」を検査。旧来の「ライブ設問要素の使い回しを条件付きで検査」という抜け穴を閉じた | 一致。tester自身が報告した弱点（実装形状依存の条件分岐）を構造的に解消 |
| TDR-GTH-46（DSLのみ改訂、シナリオ文は前段のまま） | 候補日はカレンダーで複数選択でき、重複があれば全体拒否。カレンダーは月送り式の1か月表示 | `_advance_calendar_to_month_containing`/`_rewind_calendar_to_earliest_month`/`_selected_calendar_day_count`が、`removeSelected`の「月をまたいで存在する」カーディナリティを基準に選択状態を数え上げ、個々の日付は該当月へ月送りしてから直接セルを読む二段構え | 一致。ただし読み方の頑健性に留保あり（後述TDR-GTH-46固有の判断・Minor5） |
| TDR-GTH-49（新規） | 幹事は参加者ごとにどの候補日へ何と答えたかを見られる | `assert_response_table_matches`が`data-participant-link-id`でparticipantLinkList側と相関し、セル単位で`{候補日ID: ステータス}`の完全一致を検査。2つの異なるリンクに異なる候補日への回答を割り当て、行×列の交差点を実際に区別できることまで検証 | 一致。集計だけでなく個別セルの相関まで厚く検査 |
| TDR-GTH-50（新規） | 幹事は未確定の候補日を削除できる | `remove_candidate_date`がコントロール活性を確認しクリック、`assert_candidate_date_absent`で一覧から消えたことを検査 | 一致 |
| TDR-GTH-51（新規） | 確定済みの候補日は削除できない | UI側で`assert_remove_candidate_date_control_absent`（コントロール自体が不在）、API側で`GATHERING_NOT_IN_SCHEDULING_PHASE`（409）を検査。**契約自身が到達不能と認めて廃止した`CANDIDATE_DATE_CONFIRMED`ではなく、実際に到達するコードへ追随済み**（0.17.0追補14/commit 4c99644と整合） | 一致。是正の経緯も含めdocstringに明記されており追跡可能 |
| TDR-GTH-52（新規） | 確定後、参加者は決まった店の場所を地図で見られる。経路線・徒歩の輪は無い | 位置・徒歩の目安・店ページへのリンクは`getParticipantView`実値とクロスチェック（一致）。「経路線・輪が無い」は`candidate-walking-radius-ring`という**別契約の**test idの不在のみで検査 | **前半は一致・後半はMajor1（下記）** |
| TDR-GTH-53（新規） | 確定前に確認の一段で変わることの一覧（3行）を見る | `assert_finalize_confirm_dialog_shows_changes_summary`が行数=3・`data-change-subject`の3値の重複なし完全一致・各行の前後セルの非空をそれぞれ検査。開く→キャンセル→選択保持→再度開く→確定、の順で`finalizeCancel`の副作用不在も検査 | 一致。tester自身が報告した弱点（「なにか非空のテキストがある」としか検査できなかった）を行単位の観測面で解消。ただしダイアログ自体の横断検査が漏れている（Major2） |
| TDR-GTH-54（新規） | まだ誰も投票していない店には最有力の印がつかない | `assert_no_shortlisted_shop_is_current_leader`が「全店respondedCount=0」という前提を自己検査した上で、全店`currentLeader=False`を検査 | 一致 |
| TDR-GTH-55（新規） | 得票同数の店にはすべて最有力の印がつく | `assert_shortlisted_shop_current_leaders_are`が`currentLeader=True`の集合と期待集合の完全一致（=非対象の`False`も暗に保証）を検査。Given側で2人の参加者が同一パターンで投票し、combined tierを人為的に2/2/0へ揃えている | 一致。偶然の同点ではなく作為的な同点であることをdocstringで明言し、実際にそう構成されている |
| TDR-GTH-56（新規） | 参加者の投票画面の票の帯は会の総人数（発行され取り消されていない本数）を基準にする | `assert_shop_vote_tally_total_active_participant_count`が`data-total-active-participant-count`の値を検査。Givenで3本発行→1本（未回答）を取り消し、期待値をn=2とすることで「発行本数」と「有効本数」を意図的に食い違わせている | 一致。分母の取り違え（発行本数3を誤って使う実装）を検出できる構成 |
| TDR-CS-20（新規） | 会モードで店を会に入れると地図のピンにもその状態が示される | `toggle_a_not_yet_shortlisted_card_and_return_ref`が**クリックしたカード自身の**`data-candidate-ref`を返し、`assert_map_marker_gathering_shortlisted_is`で同じrefのマーカーの`data-gathering-shortlisted`を検査。トグルOFFの逆方向も検査 | 一致。「たまたま先頭のカードとマーカー」ではなく同一IDでの相関を保証している点が厚い |
| TDR-CS-21（新規） | 会モードで5件に達すると帯からその理由が分かる | `gathering_mode_band_shows(limit_reached=...)`が`data-shortlist-limit-reached`を検査。0件時`false`→5件到達後`true`の遷移を確認 | 一致 |

## 個別論点

### Major 1: TDR-GTH-52の「経路線・徒歩の輪は無い」が、別契約の要素名の不在だけに頼っている

`assert_participant_decision_map_shows_shop_and_origin_only`は、地図に店の位置マーカーと検索基点
マーカーの2点だけがあることを検査したあと、「経路線・輪が無い」ことについては
`candidate-walking-radius-ring`（candidate-search-browser-interface.yaml側で定義された、別画面の
同心リング要素）のtest idがこの地図の中に存在しないことだけを検査している。DSL自身のdocstringが
この限界を明言している：

> このcontractはファイル内のどこにも経路線用のtest idを定義しておらず、この画面自体のリング要素も
> 定義していないので、契約が定義していない属性をでっち上げずにこのsuiteが機械的に検査できる
> 「輪が無い」の唯一の形は、`candidate-walking-radius-ring`（このコードベースで唯一定義されている
> リング概念）がこの地図に漏れ出していないことだけである。

つまりこの検査は「candidate-search由来のリングを誤って流用していないか」は証明できるが、
シナリオが要求する「経路の線や徒歩の範囲を示す輪は**一切**示されない」という要求全体（例えば
実装が独自のtest idを持たないLeaflet Polylineや別のSVG要素を新たに描いた場合）までは証明できない。
これは`gathering-scheduling-browser-interface.yaml`の`decision.map.scope`が禁止する対象
（経路線・輪）に対応するtest idを一つも定義していないという契約側の構造的な穴に起因しており、
tester側の手落ちというより契約とtesterの共同責任である。**Blockerにはしない**——現時点で機械的に
検査できる最強の形をtesterは正しく選んでおり、意図的な握りつぶしではなく、限界を自己申告している。
ただし人間・architectへの申し送りとして次のいずれかを推奨する: (a) `decision.map`に「地図の
子要素はmarker/originMarker以外に存在しない」という数え上げ可能な不変条件を契約に追加する、
(b) この検査を「証明できていない」ことを明記したままとし、実装側のコードレビューで担保する。

### Major 2: TDR-GTH-53の確定確認ダイアログが、横断的な禁止コントロール走査を一度も受けていない

`assert_gathering_screen_has_no_forbidden_surfaces`（`allowedPurposes`/`forbiddenPurposes`/
開示禁止語の走査、このコードベース自身が"Reviewer audit Major#1"として繰り返し言及・是正して
きたパターン）は、`gathering-finalize-confirm-dialog`が画面に開いている状態では一度も呼ばれて
いない。確認したところ:

- `open_finalize_confirmation`/`assert_finalize_confirm_dialog_shows_changes_summary`/
  `confirm_finalize`/`cancel_finalize`を個別に呼ぶのはTDR-GTH-53だけである。
- TDR-GTH-33/34/35/36は`finalize_via_dashboard()`（open→confirmを続けて呼ぶだけのヘルパー）を
  使っており、両者の間で走査は実行されない。
- TDR-GTH-53自身も、ダイアログを開いた直後（`organizer_opens_finalize_confirmation()`の後）に
  走査を呼んでいない。

この確認ダイアログは`gathering-finalize-confirm-changes-row`/`-row-before`/`-row-after`という
このラウンドで新設された表示専用要素を持つ、既存のどのスキャン済み画面状態とも異なる新しいDOM形状
である。契約はこれらを`forbiddenFormControlCategories`のスキャン対象外・`allowedPurposes`登録
不要の表示専用要素と明記しているが、それは「実装が正しく表示専用にした場合」の話であり、
もし実装がここに宣言のない値入力欄や別の操作的コントロールを紛れ込ませても、本suiteはそれを
検出できない。TDR-GTH-33の`organizer_opens_the_dashboard()`直後の走査呼び出しに倣い、
`organizer_opens_finalize_confirmation()`の直後に1回追加することを推奨する。

### Minor 1: `_select_calendar_days`が入力isosの昇順を仮定しているが、防御的にソートしていない

`_select_calendar_days`（複数日をカレンダーで選択する共通ヘルパー）は、渡された`isos`リストの
順に月送りを進める（`_advance_calendar_to_month_containing`は前方へしか進まない）。現状の呼び出し
元（TDR-GTH-01: `[+3日, +10日]`、TDR-GTH-46: `[+3日, +20日]`）はいずれも昇順なので実害は無いが、
このメソッド自身は昇順を強制も検査もしていない。もし将来、降順・非整列のisosを渡す呼び出しが
追加されると、`_advance_calendar_to_month_containing`が「月送り13回以内にセルが現れない」という
`assertions.fail`で**大きな声で失敗する**（静かに誤ったパスをする心配は無い）が、原因の特定に
時間がかかる形で失敗する。姉妹メソッド`_assert_selected_calendar_days_equal`は`sorted(isos, ...)`
で明示的にソートしており、対称性を保つなら`_select_calendar_days`側にも同じソートを入れるべき。

### Minor 2: `steps/gathering_scheduling_steps.py`のモジュールdocstringが古い（TDR-GTH-55までの表記）

`"""Thin Gherkin-to-DSL mappings for TDR-GTH-01 through TDR-GTH-55."""`のままだが、このファイルは
TDR-GTH-56用のマッピング（`shop_vote_tally_total_active_participant_count_is`）を含む。
`test_gathering_scheduling_acceptance.py`側のモジュールdocstringは正しく56まで更新済みであり、
このファイルだけ更新漏れがある。

### Minor 3〜6（横断的な走査呼び出しの取捨・calendar読み取りの頑健性・contractの属性不足）は
下記「TDR-GTH-46固有の判断」「契約側の不足と判断したもの」の各節で扱う。

## レビューチェックリスト（5観点）

1. **過不足**: 検査が甘くなっている箇所はMajor1・2のとおり。TDR-GTH-49〜56・TDR-CS-20〜21の
   全シナリオに対応するテストメソッドが存在し（欠番なし、下記契約↔テスト対応監査参照）、
   逆に契約要求より過剰に厳格で誤検出リスクのある検査は見当たらない。
2. **Givenの正当性**: `adr/0037`決定1（公開API境界経由でGivenを組み立てる）を全シナリオが
   守っている。TDR-GTH-54（0票）は「参加者に一切回答させない」という消極的構成で偶然性が
   無く、TDR-GTH-55（同票）は2人の参加者に同一パターンで投票させることで人為的に同点を作って
   おり、TDR-GTH-56（発行本数と有効本数の食い違い）は3本発行して未回答の1本だけを明示的に
   取り消しており、いずれも決定的である。TDR-CS-20は5件到達に依存しないため曜日母集団を
   使わず（`NORMAL_WITH_WEIGHTED_SAMPLING`で十分）、TDR-CS-21は`GATHERING_OPEN_SHOP_WEEKDAY_
   MATCH`（木曜=6件、既知件数）を使っており、いずれも`adr/0052`が問題視した3つの偶発的破綻
   （曜日依存・表示上限・minItems:1）のパターンを踏襲していない。
3. **Thenの検証対象**: TDR-GTH-49（セル単位の相関）・TDR-GTH-38（サーバー実値とのクロス
   チェック）・TDR-CS-20（同一IDでのカード/マーカー相関）は最小要求以上に厚い。TDR-GTH-52の
   「経路線・輪が無い」はMajor1のとおり実質的に部分的検証にとどまる。
4. **失敗の握りつぶし**: 本ラウンドの差分に`try/except`によるエラー隠蔽・無条件`pass`の新規
   追加は無い（diffを機械的に走査して確認）。既存コード側に1件`except PlaywrightTimeoutError:
   pass`（会削除のナビゲーション待ち、TDR-GTH-48）があるが、これは本ラウンドの差分に含まれず
   （`main`から不変）、docstringが「ナビゲーションが起きなくても失敗として扱わない」という
   契約非固定の挙動を意図的に許容したものと明記しており、握りつぶしではない。
5. **暗黙の前提**: `_rewind_calendar_to_earliest_month`は「カレンダーに下限が無くても13回の
   月送りで往復できる」と自らのdocstringで推論しているが、この推論には隙がある——下限が
   本当に無い実装では、rewindが13回すべてを消費して過去へ進みうる分、その後の`_advance_
   calendar_to_month_containing`（同じ13回が上限）で現在＋対象月まで戻り切れない可能性が
   ある。契約は`monthNavigation`に下限を要求していないため、この前提は契約が保証しない
   実装依存の仮定である。実際に失敗するとすれば「大きな声で失敗する」（見えない月に空振り
   で通過するのではなく、`assertions.fail`が発火する）ため、危険な暗黙の前提ではあるが、
   誤って合格を出す種類の暗黙の前提ではない（詳細は次節）。

## TDR-GTH-46固有の判断（カレンダー選択の読み方・`removeSelected`の属性不足）

**`removeSelected`に日付識別属性が無いというtesterの指摘は契約を読んだ結果、妥当と判断する。**
`gathering-scheduling-browser-interface.yaml`の`calendar.removeSelected`定義を確認したところ、
`testId`/`purpose`/`description`/`cardinality`/`requirement`/`requiredOutcome`のみを持ち、
`dayCell`のような`attributes`（`data-date`等）を一切定義していない——「選択済みの日1件につき
1インスタンスが存在する」というカーディナリティの規約はあるが、そのインスタンスがどの日付に
対応するかを機械的に読み取る手段が契約上存在しない。これは`dayCell`自身が`data-date`/
`data-selected`という識別可能な属性を持つのと対照的である。

これに対するtesterの回避策（`_selected_calendar_day_count`で「現在選択中の日数」を
`removeSelected`要素数として数え、別途`_advance_calendar_to_month_containing`で各期待日付の
セルへ個別に月送りして直接`data-selected="true"`を確認する二段構え）は、**論理的には健全**
である——(a) 選択総数が期待集合の要素数と一致し、かつ(b) 期待集合の全要素が個別に選択済みと
確認できれば、(a)の総数制約により期待集合以外の要素が選択されている余地は無い。この組み合わせ
は「期待集合と実際の選択集合が完全に一致する」ことを正しく証明しており、`removeSelected`の
属性不足を実質的に補っている。

ただし2点、留保を付す:
1. **月送りの境界の頑健性**（上記チェックリスト5参照）: `_rewind_calendar_to_earliest_month`
   と`_advance_calendar_to_month_containing`はいずれも13回を上限とするが、契約が
   `monthNavigation`に下限を要求していないため、「下限の無い実装」に対してはこの往復が
   13回では足りない可能性が理論上ある。本ラウンドで実際に選択される日付はいずれも現在から
   数日〜3週間程度（TDR-GTH-01: 3日・10日後、TDR-GTH-46: 3日・20日後）であり、統合環境で
   典型的な実装（カレンダーが今日の月から開始する）であれば往復は数回で収まるはずだが、
   この仮定は契約に明記された保証ではない。**空振り（見えない月の選択を取りこぼす）は
   起きない**——数え上げが常に全月を対象にしているため。起こりうるのはむしろ逆に、
   「実際には正しく動いているのに13回の月送り上限に達して誤って失敗と報告される」という
   頑健性の問題であり、シナリオを偽って合格させる方向のリスクではない。
2. `removeSelected`が「選択済みの日1件につき1インスタンス」という契約上の規約から外れて
   実装された場合（例えば選択済みの日をまとめて1個のUIで表現する等）、`_selected_calendar_
   day_count`はカーディナリティ規約自体の違反として失敗するため安全側に倒れる。

総じて、tester自身の指摘（属性不足）は契約上の事実として妥当であり、その回避策は正しく機能する
設計だが「厳密には契約が保証しない下限仮定」に依存する頑健性上の留保が1点残る。**Blockerとは
判断しない**（誤検出方向ではなく、実装が正しくても稀に空振り気味に失敗しうる方向のリスクの
ため）。

## 契約↔テスト対応の監査

- **承認済みシナリオのうちstep未実装のもの**: 無し。`gathering-scheduling.feature`の
  TDR-GTH-01〜56（欠番なし、56シナリオ）・`candidate-search.feature`のTDR-CS-00〜21
  （07は契約上廃止済み、21シナリオ）のすべてに対応する`def test_tdr_*`メソッドが1本ずつ
  存在することを機械的に確認した（重複・欠落いずれも無し）。
- **シナリオに対応しない孤児step**: 無し。
- **同義stepの重複**: 見当たらない。
- **purposeの許可一覧と契約列挙の1:1対応**（本監査で契約側から独立に数え上げて確認）:
  `GATHERING_ALLOWED_PURPOSES`（33件）は`gathering-scheduling-browser-interface.yaml`
  0.18.0の`unavailableControls.allowedPurposes`（33件）と要素レベルで完全一致
  （差集合はどちらの向きも空集合）。`ALLOWED_CONTROL_PURPOSES`（18件）は
  `candidate-search-browser-interface.yaml`1.10.0の`allowedPurposes`（18件）と同様に
  完全一致。過去の監査で指摘された「一覧と実体のずれ」は本ラウンドには存在しない。
- **`profiles.localAcceptance.verifiesScenarios`との整合**: `gathering-scheduling-browser-
  interface.yaml`はTDR-GTH-01〜56（TDR-GTH-13を除く、これはAPIレベルで別途検証）を、
  `candidate-search-browser-interface.yaml`はTDR-CS-00〜21（07を除く）をそれぞれ列挙して
  おり、いずれもテストファイル側の実装と一致する。

## 統合後に欠陥注入すべきassertionの一覧

本ラウンドの欠陥注入は未実施（実装が並行して直され、ブラウザで壊せなかったとの申し送りを
受けている）。統合後、以下のassertionへの意図的な欠陥注入（フォールトインジェクション）を
優先的に推奨する:

1. **`assert_participant_decision_map_shows_shop_and_origin_only`**（TDR-GTH-52、Major1）:
   実装側に、契約が定義しないtest id（例えば`data-testid`無しの生のSVG/Polyline）で経路線を
   実際に描画する欠陥を注入する。**この検査は検知できないと予測する**——Major1の指摘どおり、
   `candidate-walking-radius-ring`という無関係なtest idの不在しか見ていないため。検知できない
   ことを実測で確認し、architectへ契約改訂（地図の子要素数の固定等）を申し送る根拠とする。
2. **`assert_gathering_screen_has_no_forbidden_surfaces`のfinalizeConfirmDialogでの不実行**
   （TDR-GTH-53、Major2）: 確認ダイアログ内に宣言のない`<input>`を1つ紛れ込ませる欠陥を注入し、
   現状のテストスイート全体がこれを検知できないことを確認したうえで、`organizer_opens_
   finalize_confirmation()`直後への走査呼び出し追加が有効であることを併せて検証する。
3. **`assert_no_shortlisted_shop_is_current_leader`/`assert_shortlisted_shop_current_leaders_
   are`**（TDR-GTH-54/55）: `data-current-leader`の算出を「先頭要素固定でtrue」という旧ルール
   （ADR-0050決定5、是正前）へ戻す欠陥を注入し、両assertionが確実に失敗することを確認する。
4. **`assert_shop_vote_tally_total_active_participant_count`**（TDR-GTH-56）: 分母を
   `totalIssuedParticipantLinks`（取り消し分を含む発行本数）へ差し替える欠陥を注入し、
   期待値n=2に対しn=3が返って失敗することを確認する。
5. **`assert_response_table_matches`**（TDR-GTH-49）: 行と列（参加者と候補日）の対応を
   入れ替える、または未回答の候補日に空文字列以外のステータスを持つセルを追加する欠陥を
   注入し、完全一致比較が確実に失敗することを確認する。
6. **`assert_answer_later_confirmation_reproduces_schedule_answer`**（TDR-GTH-42）: 未回答の
   候補日についても`scheduleItem`を描画してしまう欠陥（「ちょうど1件」規約への違反）を注入し、
   `to_have_count(1)`が失敗することを確認する。
7. **`_assert_selected_calendar_days_equal`/`_selected_calendar_day_count`**（TDR-GTH-46）:
   `removeSelected`を「現在表示中の月のみ」描画する退行（コミットメッセージが「直した」と
   述べている旧不具合そのもの）を意図的に再現し、複数月にまたがる選択のテストが確実に失敗する
   ことを確認する。
8. **`assert_revoke_control_absent_at`**（TDR-GTH-20）: revokeコントロールを「不在」ではなく
   「disabled」のまま描画する退行を注入し、`assert_absent`が確実に失敗することを確認する。
9. **`assert_finalize_confirm_dialog_shows_changes_summary`**（TDR-GTH-53）: 3行のうち1行を
   省略する、または2行が同じ`data-change-subject`を持つ欠陥を注入し、行数・値の完全一致検査が
   確実に失敗することを確認する。
10. **`assert_map_marker_gathering_shortlisted_is`**（TDR-CS-20）: カードのトグルとマーカーの
    `data-gathering-shortlisted`が非同期に更新される（マーカー側が古い値のまま残る）欠陥を
    注入し、確実に失敗することを確認する。

## 契約側の不足と判断したもの

1. **`decision.map`（TDR-GTH-52）が「経路線・輪が無い」ことを機械的に証明する手段を持たない**
   （Major1詳細参照）。地図の子要素を数え上げ可能にする不変条件、または「経路線」概念に
   対応する禁止test idの新設を推奨する。
2. **`calendar.removeSelected`が選択済みの日を識別する属性（`data-date`相当）を持たない**
   （TDR-GTH-46節参照）。testerの回避策は論理的に健全だが、直接の識別属性があれば実装・
   テスト双方が単純化できる。次回のカレンダー関連改訂の際に追加を検討されたい。
3. **`test-support-api.yaml`（v1.5.8）の`info.description`のシナリオ範囲表記が
   「TDR-GTH-01 through TDR-GTH-55」のままで、TDR-GTH-56を含んでいない**（TDR-GTH-56自体は
   新しいseamを要さないため実害は無いが、範囲表記としては古い）。次回のこのファイル改訂時に
   56まで揃えることを推奨する。
4. **`monthNavigation`が下限（これより過去には戻れない、等）を契約上固定していない**
   （TDR-GTH-46節参照）。実装依存のまま残すこと自体は設計判断として理解できるが、
   受け入れテスト側の月送り往復ロジックがこの未確定さの影響を受けることは明記に値する。

## 人間の承認判断のためのチェックリスト

- [ ] Major1（TDR-GTH-52の「経路線・輪が無い」検証が別契約要素の不在にしか頼っていない）を
      本PRのブロッカーとして扱うか、契約改訂を伴う次PRへ送るか
- [ ] Major2（確定確認ダイアログが横断的な禁止コントロール走査を一度も受けていない）を
      本PRで1行追加して埋めるか、次PRへ送るか
- [ ] Minor1（`_select_calendar_days`の昇順仮定）・Minor2（steps.pyのdocstring更新漏れ）は
      次回のこの画面群を触るラウンドへ送ってよいか
- [ ] 「統合後に欠陥注入すべきassertion」10件（上記）を、統合後の欠陥注入フェーズで
      実際に実行するかどうか
- [ ] 「契約側の不足と判断したもの」4件を、次回の契約改訂（architect）へ申し送るか
- [ ] `gathering-scheduling.feature`・`candidate-search.feature`・両`-api.yaml`・
      両`-browser-interface.yaml`はいずれも本ラウンドの記述時点で承認済み
      （2026-09-11付「会の画面群の仕様と実装を、この場の合意として承認する」）——本PRの
      マージが実装承認を兼ねる従来運用のままでよいか

以上。
