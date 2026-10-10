# KEN-50 監査: 日程を聞いている幹事画面を板 Q5-a に戻した実装（未コミット差分）

- 対象: 作業ツリーの未コミット差分（`contracts/gathering-scheduling-browser-interface.yaml` 0.32.0、`gathering.js`、`organizer.css`、`tests/acceptance/dsl/gathering_scheduling_browser.py`、新規 `tests/ui_invariants/test_scheduling_board_q5a.py`、新規 `adr/0076`）。コードは直していない。
- 突き合わせ先: 板 Q5-a（`board-q5a-pc.png`、`board-q5a-sp.png`）、`adr/0076`、契約 0.32.0 追補31（CH-1〜5、RT-1〜4、PH-1〜4、LK-1〜3）。
- 結論: **Critical 1件・Major 2件**。Minor 3件・Info 5件。指揮役の修正が要る（下の C-1、M-1、M-2）。

## どう確かめたか

- 撮影: `test_zz_capture_states.py -k dashboard_scheduling` を `DINING_RADAR_CAPTURE_DIR` 付きで自分で流し直し、1440×900、1024×768、768×1024、390×844、360×740 の画像を見た（変更前は指揮役の `before` と並べた）。20日分の画面は使い捨てテストで 1920、1440、1024、768、360 も測った。
- 退行比較: `git worktree`（HEAD、確認後に削除済み）から SELECTING_SHOP と FINALIZED の全撮影（145枚）を取り、実装後と並べた。画像の差は地図の点と店の並びだけで、枠・表・回答リンクの節の形は同じだった。
- 実行して緑だったもの: `test_scheduling_board_q5a.py` 17 passed。`tests/ui_invariants` 全体 108 passed・9 xfailed。`tests`（ui_invariants 以外）937 passed。`client-js-tests` の vitest 140 passed（node_modules あり）。
- 欠陥注入: 下の「検査の落ち方」に一覧。注入は `gathering.js`・`organizer.css` を一時的に書き換え、注入ごとに退避したコピーへ戻した。最後に SHA-256 が開始時と一致することを確認した（`581e26be…`、`8360fe78…`）。`git status` の差分は開始時と同じ。
- 使い捨てテストはすべてスクラッチパッドに置き、リポジトリには残していない。

## 板との一致（観点1）

| 項目 | 結果 |
|---|---|
| 候補日の見出し帯（薄緑の帯、左「候補日 N日」、右に枠つきの「＋候補日を足す」、下に白い面に札） | 1440・1024・768・390・360 すべてで板どおり。点線の札は消えた。 |
| 回答リンクの見出し帯（左「回答リンク N本」、右に枠つきボタン） | 同上。文言は板が「＋ 回答リンクを発行」、実装が「リンクを発行」（契約は文言を固定していない。I-1）。 |
| 表の全幅 | 1920・1440・1024・768・390・360 で T.left=0、T.right=画面幅。カードの外。PC は日付列 44px、月・日・曜日を縦に積み、文字が隣と接しない。スマホは名前の列と先頭の日付が入り、右は横に滑る。 |
| 回答リンクの行（PC） | 1024 以上で「名前｜答えた/まだ｜コピー｜取り消す」の1行。1023 以下は名前の下に積む。板の PC と並びは同じ。位置のずれは m-3。 |
| ページの外枠 | 板の PC 画像は枠つきのカードの中。実装は SCHEDULING で外側のカードも外し、1440 でも画面の左右の端まで広がる（変更前は 960px の中央のカード）。I-2。 |

## 契約・テストの対応（観点2）

| 契約 | 実装 | test_scheduling_board_q5a.py | 判定 |
|---|---|---|---|
| CH-1〜CH-5 | `renderCandidateDateHeading`、`.gth-band`、`.gth-banded`（`gathering.js:1620`、`organizer.css`） | `_check_heading`（prefix CH）。ライブ 1440・390、較正 CH-1〜5 | 対応あり。CH-4 の高さ 44px も測る。 |
| RT-1〜RT-4 | `.gth-response-section`、`.gth-response-scroll`、積み見出し | `_check_table`。較正 RT-1、RT-2、RT-3（2種）、RT-4 | 対応あり。RT-2 の祖先走査は dashboard 根でなく body まで（契約より厳しい側）。 |
| PH-1〜PH-4 | `renderParticipantLinkPane`（SCHEDULING 枝） | `_check_heading`（prefix PH）。較正は PH-2 のみ | PH-1・3・4 は CH と同じ関数を通る。独立の較正は無い（I-3）。背景の検査が「PH-5」と報告される（m-1）。 |
| LK-1〜LK-3 | `.gth-banded .gth-link-row` 等、SCHEDULING のみ取り消すを後ろへ | `_check_rows`。較正 LK-1〜3 | 対応あり。LK-3 の「ページを溢れない」が幅 390 の定数で測られる（m-2）。 |
| `schedulingLayout.order`（追補31の改め） | `gathering.js:3390` 付近 | DSL `assert_scheduling_layout_follows_the_board`（DOM 順と画面上の順） | 対応あり。ただし順序だけで、**中身が切れていないか**は誰も測っていない（M-1）。 |

- 契約の `requiredTestIds` に `gathering-candidate-date-heading`・`gathering-participant-link-heading` が入っている。実装の2要素は表示専用で、`data-gathering-control-purpose` を持たない。
- `.feature`・`allowedPurposes`・`formControlExemptTestIds`・`verifiesScenarios` は無変更（ADR の宣言どおり）。`contractVersion` は 0.32.0 で、YAML として読める。
- 孤児 step・同義 step の重複: なし（新設の DSL 定数は `CANDIDATE_DATE_HEADING`、`PARTICIPANT_LINK_HEADING` の2つだけで、どちらも使われている）。

## 検査の落ち方（観点3、欠陥注入）

`test_scheduling_board_q5a.py` のライブ2本、または acceptance の `test_gth_scheduling_screen_follows_the_board_and_confirms_the_sole_leader` を落とせたか。

| # | 壊した内容 | 落ちた条項 |
|---|---|---|
| I1 | 候補日を足すを点線のリンクボタンに戻す | CH-4（1440・390） |
| I2 | 表を `gth-pane`（カード）に戻す | RT-1、RT-2（1440・390） |
| I3 | 取り消すを再びコピーの前に入れる | LK-2（1440） |
| I4 | 日付見出しの積みを無効化 | RT-3（セルの文字がセルの外へ） |
| I5 | 帯の背景を白にする | CH-5、PH-5(=PH-4)（1440・390） |
| I6 | PC の行を縦積みに戻す | LK-1、LK-2（1440） |
| I7 | 発行ボタンを帯の外へ出す | PH-2、PH-3（1440） |
| I8 | スマホで名前の列を広げ先頭の日付を外へ押し出す | RT-4（390 のみ。PC は緑でよい） |
| I9 | 表の入れ物の横滑りを無効化 | RT-2、RT-4（1440・390） |
| I10 | スマホで行のボタンを行の外へはみ出させる | LK-3（390） |
| I11 | 帯のボタンを点線にする | CH-4、PH-4（1440・390） |
| I12 | 表の左に 20px の余白を足す | RT-1（1440・390） |
| I13 | 帯と一覧の順を入れ替える（acceptance） | DOM 順 |
| I14 | 回答リンクの帯と一覧の順を入れ替える（acceptance と ライブ） | DOM 順、PH-1 |

**14件とも落ちた。変えた検査は壊すと赤くなる。** ただし、**測っていない種類の壊れ方**が1つあり、これが本物の欠陥だった（C-1）。

## 所見

### Critical

**C-1 `.gth-banded` の `overflow: hidden` が画面より高い中身を切り、ページも滑らないため、候補日の札・追加フォーム・回答リンクの行に届かなくなる。**

- 場所: `organizer.css` の `.gth-dash--scheduling > .gth-banded { padding: 0; gap: 0; overflow: hidden; }`。
- 仕組み: `body → .app-shell → .app-card → main → .gth-dash` が縦の flex で、高さが画面にそろっている（390×844 で body 844、dash 722）。`.gth-banded` は縦 flex の子で `overflow: hidden` になったため、最小の高さが中身でなく 0 になり、画面に収まるよう縮む。`html` の `scrollHeight` は 844 のままで、ページは滑らない。
- 測った値（20日分、`.gth-banded` の高さ／中身の高さ）:

  | 幅×高さ | 候補日の節 | 回答リンクの節 | ページが滑るか |
  |---|---|---|---|
  | 390×844 | 130／608 | 36／156 | 滑らない（docH=844） |
  | 1024×768 | 68／284 | 39／156 | 滑らない（docH=768） |
  | 1440×900 | 141／230 | 99／156 | 滑らない（docH=900） |

- 実害（画像でも確認）:
  - 1024×768 では札の1段目の下で切れ、回答リンクの行が1行も見えない。
  - 390 では回答リンクの節が帯の途中まで（36px）しかなく、行も発行ボタンも半分以上切れる。
  - 「＋候補日を足す」を押すと、フォームは節の中（`candidateDateList` の中）に開くが、1440 で節の底が 804px、フォームが 839〜1274px にあり、**フォームが見えない**。390 も同じ（フォーム 1195px〜、節の底 732px）。
  - 14日分の 1440×900 でもたまたま収まっているだけ。20日分の 1440×900 では札の3段目が切れる。
- 診断（直してはいない）: `overflow: hidden` を一時的に外すと、390 で docH=1386、1440 で 1030 になりページが滑り、節の高さは中身と一致した（615／613、165／163）。
- なぜ検査が見逃したか:
  - `test_scheduling_board_q5a.py` は矩形を測るだけで、祖先の `overflow` による切れを見ない。Playwright の `to_be_visible` も切れは見ない。acceptance もその意味で緑。
  - 既存の `test_layout_sanity.py::test_gathering_dashboard_scheduling_phase` は xfail（項目4・5・6・13）のため、赤が隠れている。`--runxfail` で流すと、360×740 で `gathering-candidate-date rect=(27.0,581.4)-(187.2,627.4) は div.gth-pane (10.0,516.4)-(350.0,608.7) の外に出ている` が出る（check4）。xfail の理由に書かれた原因（小窓のはみ出し、h1 の押し出し、グレー文字）とは別物。HEAD での同じ画面の結果は取っていない。
- 直し方の候補（実装は指揮役）: 角丸のための `overflow: hidden` をやめる（子に角丸を持たせる）、`overflow: clip` に替える、または `.gth-banded` に `flex-shrink: 0` を足す。直したら、上の表の3幅で節の高さ＝中身の高さ、ページが滑ること、追加フォームが見えることを確かめる。

### Major

**M-1 検査が C-1 の種類の壊れ方を測っていない。** `test_scheduling_board_q5a.py` に「帯・一覧・行・追加フォームが祖先の枠で切れていない」条項が無い。契約の幾何条件にも無い（CH・PH・RT・LK は位置と形だけ）。C-1 の修正と同時に、機械で落ちる検査を足す必要がある。案: 各節で `scrollHeight <= clientHeight + 1`、最後の札と最後の回答リンクの行の矩形が `.gth-banded` の矩形に入っている、追加フォームを開いたときフォームの矩形が節の中に入る、ページ末尾まで滑れる（`scrollHeight` が窓より大きいとき `scrollY` が増える）。検査を足したら、C-1 を再現する欠陥注入（`overflow: hidden` を戻す）で赤になることを確かめる。`test_layout_sanity` の xfail の説明も、この新しい赤を含めるか、原因を直して外す判断が要る。

**M-2 キャッシュの版番号（`?v=`）が上がっていない。** `organizer_dashboard.html` の `organizer.css?v=20261009-adr0075-top-bar2` と `gathering.js?v=20261009-adr0075-top-bar` が変更前のまま。テンプレートのコメント（FR-025）が「`gathering.js` を変えるたびに上げる」と定め、ADR-0076 の申し送り4も「`?v=` を上げる」と書いている。このままだと、すでにこの画面を開いたブラウザは古い CSS・JS のまま（または片方だけ新しい組み合わせ）で動く。`organizer_gathering_list.html` の CSS 側も同じ共有ファイルを指すので、版番号を揃える必要がある。

### Minor

1. **m-1 テストの報告名が契約と違う。** `_check_heading` が背景の検査を `{prefix}-5` で報告するため、回答リンクの帯では「PH-5」と出る。契約の PH は 1〜4 で、背景は PH-4 の中。落ちたときの追跡先が合わない。
2. **m-2 LK-3 のページ溢れが幅 390 の定数で測られる。** `_check_rows` の `i_["right"] > PHONE_VIEWPORT["width"]` は、幅が違うと誤検出（1023×768 と 768×1024 で赤）し、360 のときは 30px の溢れを見逃す。probe の `V` を使うべき。今のライブテストは 390 だけなので現状では緑。
3. **m-3 PC の回答リンクで、取り消すのある行だけコピーが約6px左へずれる。** 1920 で、答えた行のコピーが x=1631、まだ行（取り消すあり）が 1625。`.gth-banded .gth-link-actions` は `flex: 0 0 15rem`（240px）で、ボタン2つ（`min-width: 7.5rem` ×2＋隙間 6px＝246px）が列からはみ出し、行全体を押し戻している。板はコピーの列がそろっている。LK-1〜2 の条項には触れないので検査は緑。

### Info

- **I-1** 回答リンクの発行ボタンの文言は「リンクを発行」（リンクのアイコンつき）で、板は「＋ 回答リンクを発行」。契約は文言を固定していない（ADR-0066 決定2）。
- **I-2** SCHEDULING では外側のカード（`.app-card`、`.app-shell`）を全幅・枠なしにするため、1920 では説明の2行や札も画面の端いっぱいに広がる（上限なし）。板の PC 画像は枠つきのカード。ADR-0076 確認事項3（PC でも画面の端まで）に書かれており、RT-1・RT-2 の帰結なので指摘に留める。
- **I-3** PH-1・3・4 は CH と同じ関数を通るため、独立の較正テストは無い（PH-2 のみ）。実害は無いが、ADR-0065 を厳密に読むなら足すと安心。
- **I-4** 板のスマホ画像にある「選んだ日の列の濃い見出し」「表の縦罫線」「右端の薄れ」は実装に無い。契約は固定しておらず（ADR-0076 確認事項2）、矛盾はない。
- **I-5** 札（日付の丸い枠）の文字は板より大きい（15px 前後・太字、板は 12px の通常）。既存の ADR-0072 の札で、今回の差分の対象外。

## SELECTING_SHOP・FINALIZED の退行（観点4）

退行は見られない。HEAD と並べた全撮影（SELECTING_SHOP の店・日程・回答・リンクの4タブ、確定の小窓、FINALIZED の初期・回答・リンク）で、画像差は地図の点と店の並びだけだった。回答リンクの行（取り消すを先頭に入れる従来の枝）、`.gth-pane` の表、`ADR-0071` の見出しセルは差分上も SCHEDULING のときだけ別の枝へ入る。新しいクラス（`.gth-banded`、`.gth-band`、`.gth-response-section`、`.gth-dash--scheduling`、`--stacked`）は SCHEDULING の描画からしか付かない。SELECTING_SHOP・FINALIZED にリンクがある場合の行そのものは撮影していない（撮影の Given はリンク0本）。`ui_invariants` 全体と acceptance は緑。

## organizer.css の既存規則への副作用（観点5）

- 新しい規則はすべて `body:has(#gathering-app .gth-dash--scheduling)`、`.gth-dash--scheduling`、`.gth-banded`、`.gth-band`、`.gth-response-section`、`.gth-response-header-cell--stacked` で始まる。既存の `.gth-pane`、`.gth-link-row` は書き換えていない。FINALIZED の同種の規則（`gth-dash--finalized`）と同じ方式。
- 副作用が出ているのは C-1 だけ。`.gth-dash` が縦 flex で高さが窓にそろう既存の構造と、新しい `overflow: hidden` の相互作用。
- `.gth-response-section` の中の `.gth-response-scroll`（`overflow-x: auto`）も flex の子として縮み得る。今回の撮影は人が1人の表だけで、9行のような縦に長い表では測っていない。C-1 を直した後に、表の縦も切れていないことを同じ方法で確かめる必要がある。
- 描画の初回（データ到着前）は従来のカード、到着後に全幅へ変わるので、ちらつきが出る可能性がある。測っていない。

## 判定

**Critical 1件（C-1）・Major 2件（M-1、M-2）。** 板との一致（候補日の帯・表の全幅・回答リンクの帯と行）は、PC・スマホとも 1440・1024・768・390・360 の画像で確認できた。契約 CH・RT・PH・LK と実装・テストの対応も取れており、変えた検査は注入した14件の欠陥すべてで落ちた。しかし `.gth-banded` の `overflow: hidden` が窓より高い中身を切り、ページも滑らないため、追加フォームと回答リンクの行が実際には使えない。この種の壊れ方を測る検査が無かったので、M-1 の検査を足してから C-1 を直し、注入で赤→緑を確かめる順を勧める。vitest（140 passed）と Python の全テストは緑。

---

# 再監査（2026-10-10）

- 対象: C-1・M-1・M-2 を直した作業ツリー（`organizer.css` の `.gth-dash--scheduling > .gth-banded` が `overflow: clip`、`?v=20261010-ken50-q5a-clip`、`test_scheduling_board_q5a.py` に切れ検査と較正を追加）。コードは直していない。
- 判定: **Critical 0・Major 0。** C-1・M-1・M-2 は直っている。Minor 3件（m-1〜m-3）は未対応のまま残る。

## 確かめたこと

| 項目 | 結果 |
|---|---|
| C-1（切れ） | 20日・参加者9人で、390×844・1024×768・1440×900・360×740 の全ページ撮影を見た。候補日の節は中身と同じ高さ（`h`＝`scrollHeight`＋枠2px。390で615／613、1024で291／289、1440で237／235）、ページは末尾まで滑り（docH 2037／1735／1681）、回答リンクの9行すべてに届く。 |
| 追加フォームを開いた状態 | 390・1024・1440・360 で撮影。フォーム（カレンダー、足す／やめる）は節の中に全部入り、下の回答リンクの節を押し下げている。 |
| M-1（検査） | `test_scheduling_board_q5a.py` 26 passed（前回17）。切れ検査は 3日・14日・20日×9人、4つの大きさ、フォーム閉／開を測る。**注入**: `overflow: clip` を `hidden` に戻すと 390・1024 で CLIP 赤（例: 候補日の節 scrollHeight 446 > clientHeight 119）。元に戻すと緑。SHA-256 は開始時（`148da73b…`）と一致。 |
| M-2（版番号） | 2つのテンプレートとも `organizer.css?v=` と `gathering.js?v=` が `20261010-ken50-q5a-clip` に揃った。 |
| 撮影（`test_zz_capture_states.py -k dashboard_scheduling`、`DINING_RADAR_CAPTURE_DIR` 付き） | 1 passed。14日・3日・小窓の各サイズ（390・1024・1440・360・768・430）を見た。上端に出る帯・札・表に切れ無し。 |
| 角丸・影・枠 | `.gth-banded` の計算値は全幅で 角丸12px、影 none、枠 1px #dfe4de。これは既存の `.gth-pane` と同じ。`overflow: clip` で帯の角が丸く切れ、はみ出しも無い。 |
| `overflow: clip` の副作用 | 子の焦点枠は帯のボタンの周りで切れない（帯に余白 0.375rem）。テキスト選択、横滑り（表の `overflow-x: auto` は別の入れ物）に変化なし。最小高さは中身になるので縮まない。 |
| SELECTING_SHOP・FINALIZED | 新規則は `.gth-dash--scheduling` 限定の1か所なので、他の局面の CSS は変わっていない（`gathering.js` は SHA-256 が初回監査と同じ `581e26be…`）。`tests/ui_invariants` 117 passed・9 skipped・9 xfailed、`tests`（ui_invariants 以外）967 passed。再撮影は SCHEDULING のみ（他局面は前回の 145 枚比較から変化する差分が無いため再取得せず）。 |

## 残る Minor・Info（前回から変化なし）

- **m-1** `_check_heading` が背景検査を `{prefix}-5` で報告する（PH-5 と出る）。
- **m-2** `_check_rows` の LK-3 溢れが `PHONE_VIEWPORT["width"]`（390 固定）で測られる（`test_scheduling_board_q5a.py:358`）。
- **m-3** PC の回答リンクで、取り消すのある行だけコピーが数 px 左へずれる（1024 の全ページ撮影で、答えた行のコピー x≈735 に対し まだ行 x≈729）。`.gth-banded .gth-link-actions` が `flex: 0 0 15rem`（`organizer.css:3210`）。
- I-1〜I-5 は前回のとおり。
- 新たに見つけたもの: **I-6** 20日分では候補日の札が 14日と同じ幅の枠に並ぶだけで、表（全幅）の右端まで日付列が伸びる。板に20日の例は無く、矛盾はない。

## 未測定

- 描画の初回（データ到着前）の従来カードから全幅への切り替えのちらつき。
- Q5-a の他の局面（SELECTING_SHOP・FINALIZED）でリンクがある場合の行の撮影。
