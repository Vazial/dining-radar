# KEN-70 画面×状態台帳

この台帳は、テンプレート、サーバー HTML、`gathering.js` / `candidate.js` の描画分岐、既存の撮影テストから洗い出した状態を記録する。`板あり・照合済み` は `geometry.json` と `test_wireframe_conformance.py` の対象、`板あり・照合なし` は geometry には追加済みだが実機キャプチャとの照合が未実施である。板がない行は ADR-0084 の共通規則で機械検査し、個別の見た目は別スライスで板を起こす。

|画面×状態|板の有無|板ファイル名|照合テスト名|備考 / 未照合理由|
|---|---|---|---|---|
|ホーム・会複数|板あり・照合済み|HC-PcList.dc.html / HC-SpList.dc.html|`test_wireframe_geometry_has_all_adopted_board_screens`|geometry と既存の板契約を確認済み|
|会・店を選び中・店5件|板あり・照合済み|GC-PcSelecting.dc.html / GC-SpSelecting.dc.html|`test_wireframe_geometry_records_right_pane_and_steps`|通常の店あり状態|
|会・日程を聞き中・回答あり|板あり・照合済み|GC-PcScheduling.dc.html / GC-SpScheduling.dc.html|`test_wireframe_geometry_records_right_pane_and_steps`|回答あり表|
|会・日程を聞き中・回答なし|板あり・照合済み|S3-PcScheduling.dc.html / S3-SpScheduling.dc.html|`test_wireframe_geometry_records_right_pane_and_steps`|候補日編集前の代表状態|
|会・決まった後|板あり・照合済み|GC-PcFinal.dc.html / GC-SpFinal.dc.html|`test_wireframe_geometry_has_all_adopted_board_screens`|店情報ありの代表状態|
|ホーム・会0件|板あり・照合なし|Empty-Pc.dc.html / Empty-Sp.dc.html|`test_wireframe_geometry_includes_every_board_screen_in_the_ledger`|geometry に追加したが画像照合未実施|
|ナビ・PC右ペイン|板あり・照合なし|Nav-PcPane.dc.html|同上|geometry に追加したが実装の開閉状態未撮影|
|ナビ・スマホ下部バー/アカウント|板あり・照合なし|Nav-SpN1.dc.html|同上|同上|
|候補探索・会モード|板あり・照合なし|Cand-PcGathering.dc.html|同上|候補画面の会入口状態未撮影|
|候補探索・通常モード|板あり・照合なし|Cand-SpFree.dc.html|同上|同上|
|会・店を選び中・店0件|板あり・照合対象|ZeroState-A-Pc.dc.html / ZeroState-A-Sp.dc.html|`test_wireframe_geometry_includes_every_board_screen_in_the_ledger`|案Aを採用。実装画像との照合対象|
|会・日程を聞き中・候補日0件|板なし・共通規則で担保|—|共通状態検査（ADR-0084）|空状態の構造は共通規則で担保|
|会・日程を聞き中・回答0件|板なし・共通規則で担保|—|共通状態検査（ADR-0084）|空状態の構造は共通規則で担保|
|会・日程を聞き中・リンク0本|板なし・共通規則で担保|—|共通状態検査（ADR-0084）|空状態の構造は共通規則で担保|
|会・決まった後・店情報不足|板なし・共通規則で担保|—|共通状態検査（ADR-0084）|エラー理由1行＋やり直し1つ|
|会・決まった後・日付情報不足|板なし・共通規則で担保|—|共通状態検査（ADR-0084）|エラー理由1行＋やり直し1つ|
|会・店を選び中・店1件|板なし・共通規則で担保|—|共通状態検査（ADR-0084）|単数カードは共通規則で担保|
|会・店を選び中・長い店名|板なし・共通規則で担保|—|共通状態検査（ADR-0084）|2行省略と枠内を検査|
|会・店を選び中・多人数|板なし・共通規則で担保|—|共通状態検査（ADR-0084）|表内横スクロールとページ横スクロールなしを検査|
|会・日程を聞き中・長い会名|板なし・共通規則で担保|—|共通状態検査（ADR-0084）|2行省略と枠内を検査|
|会・日程を聞き中・多人数|板なし・共通規則で担保|—|共通状態検査（ADR-0084）|表内横スクロールとページ横スクロールなしを検査|
|会・店を選び中・スマホ店0件|板あり・照合対象|ZeroState-A-Sp.dc.html|`test_wireframe_geometry_includes_every_board_screen_in_the_ledger`|案Aを採用。4幅撮影で確認|
|会・店を選び中・PC1305×900|板あり・照合対象|ZeroState-A-Pc.dc.html|`test_wireframe_geometry_includes_every_board_screen_in_the_ledger`|案Aを採用。実機幅撮影で確認|
|日程表・候補日編集|板あり・照合なし|S3-PcEditing.dc.html|`test_wireframe_geometry_includes_every_board_screen_in_the_ledger`|コンポーネント板。実装状態未撮影|
|日程表・選んでいる日|板あり・照合なし|SelA.dc.html|同上|コンポーネント板。実装状態未撮影|
|日程表・合計の行|板あり・照合なし|SumA.dc.html|同上|コンポーネント板。実装状態未撮影|
|日程表・色の決定|板あり・照合なし|ColorFinal.dc.html|同上|値の共有調査が必要|
|Dense-C・会1件ホーム|板あり・照合なし|Dense-C.dc.html|同上|長い状態列の実装照合未実施|
|会・店を選び中・地図列|板あり・照合なし|TabA-Sp.dc.html|同上|スマホのタブなし案。未撮影|
|会・店を選び中・スマホ|板あり・照合なし|GC-SpSelecting.dc.html|同上|店あり代表は板のみで未照合|
|会・日程を聞き中・スマホ|板あり・照合なし|GC-SpScheduling.dc.html|同上|回答表の実装照合未実施|

## 実装テンプレート・描画分岐の棚卸し

上表の板契約に加え、実装に存在する全画面テンプレートと、各 JavaScript が状態によって描き分ける代表的な分岐を以下に記録する。板が無い行は ADR-0084 の共通規則で担保する。板がある行でも、`geometry.json` に矩形を登録しただけでは照合済みとは数えない。

|実装面|状態 / 分岐|板の有無|板ファイル名|照合テスト名|備考 / 未照合理由|
|---|---|---|---|---|---|
|会一覧 (`organizer_gathering_list.html`)|会0件|板なし・共通規則で担保|—|共通状態検査（ADR-0084）|空状態の案内1行＋主ボタン1つ。専用板は未作成|
|会一覧 (`organizer_gathering_list.html`)|会1件以上（SCHEDULING / SELECTING_SHOP / FINALIZED のカード）|板あり・照合なし|HC-PcList.dc.html / HC-SpList.dc.html / Dense-C.dc.html|`test_wireframe_geometry_includes_every_board_screen_in_the_ledger`|geometry 登録済み。長い会名・多人数を含む実装撮影は未実施|
|会作成 (`organizer_gathering_create.html`)|未入力 / 候補日未選択|板なし・共通規則で担保|—|共通状態検査（ADR-0084）|入力エラーは理由1行＋やり直し1つ。専用板は未作成|
|会作成 (`organizer_gathering_create.html`)|候補日選択済み・確認ダイアログ|板あり・照合なし|S3-PcEditing.dc.html / SelA.dc.html / SumA.dc.html / ColorFinal.dc.html|`test_wireframe_geometry_includes_every_board_screen_in_the_ledger`|コンポーネント板の実装照合未実施|
|幹事会画面 (`organizer_dashboard.html` / `gathering.js`)|SCHEDULING・候補日あり・回答あり|板あり・照合済み|GC-PcScheduling.dc.html / S3-PcScheduling.dc.html / S3-SpScheduling.dc.html|`test_wireframe_geometry_records_right_pane_and_steps`|代表状態。候補日0件・回答0件・リンク0本は別の要合意行|
|幹事会画面 (`gathering.js`)|SCHEDULING・候補日0件|板なし・共通規則で担保|—|共通状態検査（ADR-0084）|空状態の構造は共通規則で担保|
|幹事会画面 (`gathering.js`)|SCHEDULING・回答0件|板なし・共通規則で担保|—|共通状態検査（ADR-0084）|空状態の構造は共通規則で担保|
|幹事会画面 (`gathering.js`)|SCHEDULING・リンク0本|板なし・共通規則で担保|—|共通状態検査（ADR-0084）|空状態の構造は共通規則で担保|
|幹事会画面 (`gathering.js`)|SELECTING_SHOP・店0件|板あり・照合対象|ZeroState-A-Pc.dc.html / ZeroState-A-Sp.dc.html|共通状態検査（ADR-0084）|案Aを採用。実装画像との照合対象|
|幹事会画面 (`gathering.js`)|SELECTING_SHOP・店1件 / 店5件|板なし・共通規則で担保 / 板あり・照合済み|GC-PcSelecting.dc.html / GC-SpSelecting.dc.html|`test_wireframe_geometry_records_right_pane_and_steps`|店1件は共通規則、店5件は代表板あり|
|幹事会画面 (`gathering.js`)|FINALIZED・店/日付情報あり|板あり・照合済み|GC-PcFinal.dc.html / GC-SpFinal.dc.html|`test_wireframe_geometry_has_all_adopted_board_screens`|代表状態|
|幹事会画面 (`gathering.js`)|FINALIZED・店情報不足 / 日付情報不足|板なし・共通規則で担保|—|共通状態検査（ADR-0084）|エラー理由1行＋やり直し1つ。専用板は未作成|
|参加者回答 (`participant_answer.html` / `participant.js`)|読み込み中 / 無効リンク / 読み込み失敗|板なし・共通規則で担保|—|共通状態検査（ADR-0084）|エラー理由1行＋やり直し1つ。専用板は未作成|
|参加者回答 (`participant.js`)|SCHEDULING・回答0件 / 一部回答済み / 全回答済み|板なし・共通規則で担保|—|共通状態検査（ADR-0084）|空状態と長い表は共通規則で担保|
|参加者回答 (`participant.js`)|SELECTING_SHOP・店0件 / 店1件以上|板なし・共通規則で担保|—|共通状態検査（ADR-0084）|空状態と単数カードは共通規則で担保|
|参加者回答 (`participant.js`)|FINALIZED・店/日付情報あり|板なし・共通規則で担保|—|共通状態検査（ADR-0084）|専用板は未作成|
|参加者回答 (`participant.js`)|FINALIZED・店情報不足 / 日付情報不足|板なし・共通規則で担保|—|共通状態検査（ADR-0084）|エラー理由1行＋やり直し1つ|
|候補検索 (`home.html` / `candidate.js`)|読み込み中 / 通常モードで候補あり|板あり・照合なし|Cand-SpFree.dc.html / 既存候補画面板|未確認|geometry 登録済み。4幅の実装撮影と板照合が未実施|
|候補検索 (`candidate.js`)|候補0件・検索条件変更導線|板なし・共通規則で担保|—|共通状態検査（ADR-0084）|空状態の案内1行＋主ボタン1つ|
|候補検索 (`candidate.js`)|会モード・候補あり / 店0件|板あり・照合なし / 板あり・照合対象|Cand-PcGathering.dc.html / ZeroState-A-Pc.dc.html / ZeroState-A-Sp.dc.html|共通状態検査（ADR-0084）|会モードの代表板は未照合。店0件は案A|
|共通ナビ (`organizer_primary_nav.html` / `candidate.js`)|PC右ペイン閉 / 開|板あり・照合なし|Nav-PcPane.dc.html|`test_wireframe_geometry_includes_every_board_screen_in_the_ledger`|開閉の実装撮影未実施|
|共通ナビ (`organizer_primary_nav.html` / `candidate.js`)|スマホ下部バー / アカウントシート|板あり・照合なし|Nav-SpN1.dc.html|`test_wireframe_geometry_includes_every_board_screen_in_the_ledger`|シート開状態の実装撮影未実施|

認証の `login.html`、パスワード変更フォーム、完了画面は画面テンプレートとして存在するが、KEN-70 の会・候補・参加者ワイヤーフレーム契約の対象外である。これらは板なしとして実装を変更する対象ではなく、別スライスで板を起こす候補として扱う。

## 採用板と未採用案

`project/ZeroState-A-Pc.dc.html` と `project/ZeroState-A-Sp.dc.html` が合意済み案Aの正式な板である。`proposed/ZeroState-A-*` は原案の保存、`proposed/ZeroState-B-*` は不採用案の比較資料として残す。

- 案A: PC は既存の左540px手順列＋右地図列を維持し、②の中に「開いている店から選ぶ」を左上に置く。スマホは②の中に同じ主ボタンを置き、地図は「候補なし」の空地図として残す。既存の板構造を最も保ちやすい代わりに、店0件では地図の情報量が少ない。
- 案B: PC は店0件時だけ地図列を畳み、左列を540pxで詰める。スマホは地図を出さず主ボタンと理由説明に寄せる。空白は減る代わりに、店あり/なしで地図の存在が変わり、レスポンシブ分岐が増える。

店0件は案Aを正式板・geometry・実装・画像照合の対象にする。その他の板なし行は ADR-0084 の共通規則で機械検査し、個別の見た目を確定する板は別スライスで追加する。

## ワイヤーフレーム値と実装トークンの調査

現状は、板の `<style>` と実装の `organizer.css` / `home.html` / JS が同じ値を個別のリテラルで持つ。代表値は背景 `#F2F4F0`、カード `#FFFFFF`、境界 `#DFE4DE` / `#C6CFC6`、文字 `#17201B`、主色 `#14614A`、44px操作面、10〜16px角丸、12〜24px余白である。板は Google Fonts を参照する一方、実装は system-ui を使うため、完全一致ではない。

案は「実装側に CSS custom properties を段階的に置き、板の `<style>` も同じ名前を参照する」方式。変更量は小〜中で差分を検出しやすいが、板の静的 HTML と複数画面の CSS を同時更新する必要があり、トークン名の削除・値の上書きには壊れやすさが残る。板→トークン生成は板ツール依存が強く、実装→板生成は板の意図を失うため今回は採用しない。

次段では、色・余白・角丸・文字サイズの代表値を抽出し、板と実装の不一致を検査で報告する。今回の段階では大規模な CSS 移行は行わない。
