# KEN-70 画面×状態台帳

この台帳は、テンプレート、サーバー HTML、`gathering.js` / `candidate.js` の描画分岐、既存の撮影テストから洗い出した状態を記録する。`板あり・照合済み` は `geometry.json` と `test_wireframe_conformance.py` の対象、`板あり・照合なし` は geometry には追加済みだが実機キャプチャとの照合が未実施である。板がない行は実装を確定せず「要合意」とする。

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
|会・店を選び中・店0件|板なし・要合意|`proposed/ZeroState-A-*`, `ZeroState-B-*`|未確認|人間が案を選ぶまで実装を確定しない。店0件の修正だけは先行可|
|会・日程を聞き中・候補日0件|板なし・要合意|`proposed/ZeroState-A-*`, `ZeroState-B-*`|未確認|編集入口・次の行動の優先順位が未決定|
|会・日程を聞き中・回答0件|板なし・要合意|`proposed/ZeroState-A-*`, `ZeroState-B-*`|未確認|空の表を表示するか説明に寄せるか未決定|
|会・日程を聞き中・リンク0本|板なし・要合意|`proposed/ZeroState-A-*`, `ZeroState-B-*`|未確認|リンク発行の導線が未決定|
|会・決まった後・店情報不足|板なし・要合意|`proposed/ZeroState-A-*`, `ZeroState-B-*`|未確認|provider 再取得失敗時の表示が未決定|
|会・決まった後・日付情報不足|板なし・要合意|`proposed/ZeroState-A-*`, `ZeroState-B-*`|未確認|確定情報の欠損表示が未決定|
|会・店を選び中・店1件|板なし・要合意|`proposed/ZeroState-A-*`, `ZeroState-B-*`|未確認|単数カードと地図の関係が未決定|
|会・店を選び中・長い店名|板なし・要合意|`proposed/ZeroState-A-*`, `ZeroState-B-*`|未確認|折返し・ボタン幅を板で決めていない|
|会・店を選び中・多人数|板なし・要合意|`proposed/ZeroState-A-*`, `ZeroState-B-*`|未確認|投票集計の密度と省略が未決定|
|会・日程を聞き中・長い会名|板なし・要合意|`proposed/ZeroState-A-*`, `ZeroState-B-*`|未確認|見出しの省略規則が未決定|
|会・日程を聞き中・多人数|板なし・要合意|`proposed/ZeroState-A-*`, `ZeroState-B-*`|未確認|表の横幅とスクロール方針が未決定|
|会・店を選び中・スマホ店0件|板なし・要合意|`proposed/ZeroState-A-Sp.html`, `ZeroState-B-Sp.html`|未確認|PC案との情報密度差を決める必要あり|
|会・店を選び中・PC1305×900|板なし・要合意|`proposed/ZeroState-A-Pc.html`, `ZeroState-B-Pc.html`|未確認|実機幅の地図列と左列を決める必要あり|
|日程表・候補日編集|板あり・照合なし|S3-PcEditing.dc.html|`test_wireframe_geometry_includes_every_board_screen_in_the_ledger`|コンポーネント板。実装状態未撮影|
|日程表・選んでいる日|板あり・照合なし|SelA.dc.html|同上|コンポーネント板。実装状態未撮影|
|日程表・合計の行|板あり・照合なし|SumA.dc.html|同上|コンポーネント板。実装状態未撮影|
|日程表・色の決定|板あり・照合なし|ColorFinal.dc.html|同上|値の共有調査が必要|
|Dense-C・会1件ホーム|板あり・照合なし|Dense-C.dc.html|同上|長い状態列の実装照合未実施|
|会・店を選び中・地図列|板あり・照合なし|TabA-Sp.dc.html|同上|スマホのタブなし案。未撮影|
|会・店を選び中・スマホ|板あり・照合なし|GC-SpSelecting.dc.html|同上|店あり代表は板のみで未照合|
|会・日程を聞き中・スマホ|板あり・照合なし|GC-SpScheduling.dc.html|同上|回答表の実装照合未実施|

## 要合意の板案

`proposed/ZeroState-A-*` と `proposed/ZeroState-B-*` は採用前の静的 HTML である。各案は PC とスマホの2枚を持つ。

- 案A: PC は既存の左540px手順列＋右地図列を維持し、②の中に「開いている店から選ぶ」を左上に置く。スマホは②の中に同じ主ボタンを置き、地図は「候補なし」の空地図として残す。既存の板構造を最も保ちやすい代わりに、店0件では地図の情報量が少ない。
- 案B: PC は店0件時だけ地図列を畳み、左列を540pxで詰める。スマホは地図を出さず主ボタンと理由説明に寄せる。空白は減る代わりに、店あり/なしで地図の存在が変わり、レスポンシブ分岐が増える。

店0件は人間が先に選んだ案を前提に実装を進めてよい。その他の板なし行は合意前に実装を確定しない。

## ワイヤーフレーム値と実装トークンの調査

現状は、板の `<style>` と実装の `organizer.css` / `home.html` / JS が同じ値を個別のリテラルで持つ。代表値は背景 `#F2F4F0`、カード `#FFFFFF`、境界 `#DFE4DE` / `#C6CFC6`、文字 `#17201B`、主色 `#14614A`、44px操作面、10〜16px角丸、12〜24px余白である。板は Google Fonts を参照する一方、実装は system-ui を使うため、完全一致ではない。

案は「実装側に CSS custom properties を段階的に置き、板の `<style>` も同じ名前を参照する」方式。変更量は小〜中で差分を検出しやすいが、板の静的 HTML と複数画面の CSS を同時更新する必要があり、トークン名の削除・値の上書きには壊れやすさが残る。板→トークン生成は板ツール依存が強く、実装→板生成は板の意図を失うため今回は採用しない。

次段では、色・余白・角丸・文字サイズの代表値を抽出し、板と実装の不一致を検査で報告する。今回の段階では大規模な CSS 移行は行わない。
