---
id: 0077
scope: project/dining-radar
status: 承認済み
date: 2026-10-10
approved_by: "人間裁定 2026-10-08 監査 B-1（選択肢 (1) 線画 SVG）。KEN-55 の指示で ADR の起草・承認済み化は担当に委任"
supersedes: []
superseded_by: null
relates_to: [ADR-0059, ADR-0066, ADR-0075]
---

# ADR-0077: ナビの絵を絵文字から線画 SVG にする

> **承認者向けサマリ**: 監査 B-1（KEN-55）。ナビ（PC の≡メニュー、スマホの下部バー）の絵が絵文字（🔍🍽👤☰）で、
> 端末ごとに形・色が違い、この機械では四角になる。板は線画（虫眼鏡・カレンダー・人・三本線）。
> **決定**: 線画の inline SVG にする。候補画面の契約を 1.16.0→1.17.0 に上げ、`navIcons` を足す。

## 文脈

- 検証の申告: `Read` したのは HANDOFF.md、`orchestration.md`、監査 B-1、板（`party2/d6` S2-a、`a-nav-r4-full` S2）の SVG、
  `organizer_primary_nav.html`・`home.html` のナビ部分、契約の `primaryNavigationGeometry`。実行は後段の PR に記す。
- 契約は ADR-0066 で「アイコンは固定しない見た目の選択」としていたため、絵文字が板と食い違っても検査に掛からなかった。

## 決定

1. ナビの絵（≡、メニューの「さがす」「ランチ会」、下部バーの3項目）は `aria-hidden` の線画 inline SVG にする。
   `stroke="currentColor"`、塗りなし。色は文字色に従い、現在地は緑 `#14614a`、それ以外は `#4b564e`、≡ は `#17201b`。
2. 契約 `candidate-search-browser-interface.yaml` に `primaryNavigationGeometry.navIcons` を足す（1.16.0→1.17.0）。
   絵文字・絵記号（U+2600–27BF、U+1F300–1FAFF）をナビの絵に使わない。大きさ・線の太さ・色は固定しない。
3. testId・文言・並び・`candidate-search.feature` は無変更。
4. 同じ ADR で「ランチ会 N」の数の丸は扱わない（板にあるが本チケットの範囲外。必要なら別チケット）。

## 検討した代替案

- 絵文字のまま板を描き直す: OS 依存を受け入れることになる。人間が (1) を選んだ。

## 帰結

- 実装: 2 つのテンプレート（`home.html`、`organizer_primary_nav.html`）と CSS。`tests/` に絵文字不在・SVG 存在の検査を足す。
