# 監査レポート: KEN-57 候補画面PC・絞り込みパネルのジャンル行修正

- 作成: reviewer
- 対象: 未コミット差分（home.html、test_zz_capture_states.py、新規 tests/ui_invariants/test_genre_row_pc.py）
- 見たもの: 差分、人間の症状画像、修正前(before)と修正後(after-v2)の画像、GenreRow板の決定。
- 実装・テストは書き換えていない。

## 結論

**Critical なし。Major あり（1件）。このままの承認は不可。M-1 を直してから通す。**

## Major

### M-1 PCでアカウントメニューが絞り込みバーの下に潜る（重なり順の後退）

- 原因: `#candidate-filter-bar` を `z-index: 8` から `1000`＋`isolation: isolate` にした。
  - PC上部の `.app-card > .primary-nav-desktop` は `z-index: 10`。メニュー本体はこの文脈の中にある。
  - 絞り込みバーがナビより前面に出るようになった。
- 画像で確認（1440x900、`candidates__menu_open`）:
  - before: メニューが全項目表示される（先頭「ランチ候補をさがす」が見える）。
  - after-v2: 絞り込みバーの高さ（約y=141まで）のメニュー上部が隠れる。
  - 先頭項目「ランチ候補をさがす」が消える。バー右端の「別の候補を出す」がメニューの前に出る。
- 影響: PCでアカウントメニューの項目が1つ押せなくなる。
- 対応案: パネルが地図より前に出れば足りる。バー全体を 1000 にしない。ナビ(10)・メニュー(20)より低く、地図(0)・Leaflet の文脈より高い値にする。
- 注意: 新テストにも `menu_open` の撮影にも、この重なりを検知する検査がない。直したら menu_open の after を撮り直して確認する。

## Minor

- m-1 **回帰テストは panel CSS の赤確認ができない（tester 報告は妥当）。**
  - 検査(c)は `elementFromPoint` で「パネルの上に他の要素が来ないか」だけを見る。
  - 背景の透け(98%→不透明)は検出できない。症状画像の「背面が透けて重なる」は元々 hit-test を通る。
  - 背景が不透明であることは、computed `background-color` の alpha が 1 であることで観測すべき。
  - z-index 側も、地図が z=0 の文脈に閉じているため、旧値(8)でも通る可能性が高い。
  - つまりテストが実際に守るのは「ジャンル行が1段・非折返し・トグル固定」(a)(b)だけ。(c)は名ばかり。
  - 今の1件はジャンル行について緑。パネル不透明の保証にはならない。
- m-2 PCでチップ列の右端がハードカット（after-v2 の「エス」）。
  - スマホ側にある右端のフェード（`.candidate-filter-row::after`）がPCにない。
  - 横スクロールできる合図が弱い。
  - GenreRow板は「右側だけスクロール」を決めているだけで、フェードは要求していない。ずれはないので Minor。
- m-3 `candidate-genre-scrollable` の `overflow-x:auto` / `nowrap` はスマホ幅の `.candidate-filter-row-chips` と重複する（同じ値）。
  - 害はない。PC側の明示という意味では妥当。
- m-4 テストは `open_candidate_screen_at_two_column_viewport` 後に `candidate-filter-open` を直接クリックしている。
  - 理由はコメントに書かれていて筋は通る。ただし共有ヘルパーを避けるため、将来の画面変更に追随しにくい。

## 観点別の判定

| 観点 | 判定 |
|---|---|
| 症状（トグルが2段の中央に浮く・重なる） | 直っている。after-v2 では「ほか 1件…」が同じ行の左端、チップが1行 |
| GenreRow板の決定（トグル左固定・チップ側のみ横スクロール、折返しなし、行高不変） | 沿っている（DOM順そのまま、スクロールしてもトグル位置不変をテストが確認） |
| チップが重ならない | 重ならない（`flex: 0 0 auto`、テストで相互の重なりも検査） |
| パネルの見た目（角丸・影・背景） | 角丸・影は維持。背景は 98% → 不透明で、板に近づく方向。後退なし。ただしPC用のパネルの板は無い |
| スマホ幅 | 変更は PC の `@media (min-width: 64rem)` ブロック内と `.candidate-genre-scrollable` / `.candidate-chip` のみ。スマホは元々 nowrap なので変化なし。スマホ画像(360/390)に崩れは見られない |
| 地図・トースト・メニューの重なり | **メニューが後退(M-1)**。地図はパネルの下になっており問題なし。トースト(fixed, z=32)は下部で、パネルが下端まで来ない限り干渉しない |
| 回帰テストが症状を捉えるか | ジャンル行は捉える。パネルCSSは捉えない(m-1) |
| ADR・契約の変更 | 不要。見た目と配置のみで、genreOptionOrder・presentation・controlGrouping に触れない。GenreRow板も「契約は追補なしで実装可」としている。ただし「トグル左固定」は機械観測されない旨が板にあり、本テストが事実上その観測を担う |

## 実行した確認

- `tests/ui_invariants/test_genre_row_pc.py`: 1 passed（現状の差分で緑）。
- パネルCSSを戻した赤確認は、コードを書かない制約により実施していない。m-1 は静的な読解による判断。
- 自分で新しく撮影はしていない。既存の before / after-v2 の画像で判断した。

---

## 再監査（2回目・M-1 修正後の作業ツリー）

### 結論

**Critical なし。Major なし。M-1 は解消。承認可（Minor のみ残る）。**

### 確認したこと

- 差分: `#candidate-filter-bar` は `z-index: 8`（元の値）に戻り、`isolation: isolate` を追加。パネルは `z-index: 1`・`background: #fff`・角丸 0.75rem。チップは `flex: 0 0 auto`。
- M-1: after-v3 `menu_open__1440x900` で、メニュー全項目（先頭「ランチ候補をさがす」含む）が絞り込みバーの前に出ている。before と同じ見え方。
- パネルの前後: `filter_open__1440x900` でパネルが候補カードと地図の両方の前にある。背面の透けなし。バーの z=8 が地図(z=0)・カード・会モード帯(sticky z=6)より高い。
- 重なり順の後退なし: ナビ z=10・メニュー z=20 > バー z=8。トースト fixed z=32、下部ナビ z=30/31。地図内の高い値は地図の文脈内（home.html 532〜561 のコメント通り）。`gathering_mode_added_toast__1440x900` でトーストは前面、会モード帯もバーの下。
- スマホ幅: PC 向け変更は `@media (min-width: 64rem)` ブロック内。共通の変更は `.candidate-genre-scrollable`（nowrap、元々同じ）と `.candidate-chip` の `flex: 0 0 auto`（チップは `white-space: nowrap` で、行は既に横スクロール）。`filter_open__390x844` に崩れなし。
- `tests/ui_invariants/test_genre_row_pc.py`: 1 passed（再実行）。

### Minor（残り）

- m-1 は継続: 検査(c)は不透明背景も z-index も検出できない。
  - 今の回帰テストが守るのはジャンル行の一段・非折返し・トグル固定。症状の「ジャンル行」は捉えている。
  - 余裕があれば computed `background-color` の alpha=1 を検査に足すとよい。必須ではない。
- m-5 回帰テストは「メニューがバーの下に潜る」(M-1) を検出しない。`menu_open` の画像確認でしか防げない。`elementFromPoint` でメニュー先頭項目が最前面か見る検査を足せる。
- m-6（今回の差分外・既存）: スマホ幅 `filter_open__390x844` でパネル背面の地図要素がうっすら透けて見える。PC 側だけ #fff にしたため。スマホ不変の指示どおり。
- m-2 / m-3 / m-4 は前回のまま（実害なし）。

### 実行した確認（2回目）

- 差分の読解、after-v3 の画像（menu_open / filter_open 1440、gathering_mode_added_toast 1440、filter_open 390）、症状画像。
- 回帰テスト再実行（緑）。自分での新規撮影はしていない（after-v3 で足りた）。
- コード・テストは書き換えていない。
