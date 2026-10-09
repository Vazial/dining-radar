---
id: 0073
scope: project/dining-radar
status: 承認済み
date: 2026-10-08
approved_by: "人間裁定 2026-10-08 KEN-24 コメント（チャットで選択肢から選択）"
supersedes: []
superseded_by: null
relates_to: [P-02, P-06, P-08, ADR-0063, ADR-0071, ADR-0072]
---

# ADR-0073: 店を選び中の日程タブを、決まった日の札1枚だけが見える形に畳む

> **承認者向けサマリ**: 監査 D3（KEN-24）。店を選び中の「日程」タブには、決まった日以外の候補日の札も並ぶ。
> **決定**: 日程タブを開いて見えるのは、決まった日（`data-confirmed="true"`）の `gathering-candidate-date` 1枚だけ。
> 他の日の札は DOM に残して属性も変えず、画面で見せないだけ（ADR-0071 の回答タブと同じ扱い）。
> 契約 `gathering-scheduling-browser-interface.yaml` は 0.29.0→0.30.0（追補29）。`.feature`・`allowedPurposes` は無変更。
> 人間が選択肢から選んで確定済み。店が0件のときの表示は変更なし。

## 文脈

- 検証の申告: `Read` したのは HANDOFF.md、architect 役定義、ADR-0013 決定8・ADR-0072、契約 0.29.0 の
  `shopSelectionPanel`・`candidateDateList`・追補27/28、監査 D3。板（`.orca/drops/dsg-out`）に日程タブを畳んだ形は
  無く、契約の文言が根拠。実行（撮影）はしていない。番号は全リモートブランチを見て 0072 が最大だったので 0073。
- 監査 D3: 日程タブの中身（決まった日のカード1枚）は板で決まっていない。人間は「日程が長すぎる」の延長で指摘した（指摘7）。
- 契約 0.29.0 は、日程タブを開くと `candidateDateList` が見える、としか書かない。SELECTING_SHOP では日は既に1つ決まっている。

## 決定

1. 日程タブ（`shopSelectionPanel.scheduleTab`）が選ばれている間、画面で見える `gathering-candidate-date` は
   `data-confirmed="true"` の1枚だけ。他の札は DOM に残し、`data-*` は一切変えず、見えなくするだけ。
   `candidateDateList` 要素自体は見えたまま。
2. 存在規則（3フェーズ無条件）・並び・属性・`removeCandidateDate` の規則は無変更。
3. 店が0件のときの表示は変更しない。

## 検討した代替案

- 他の日の札も出し、決まった日を目立たせる: 人間が「畳む」を選んだので不採用。
- 他の札を DOM から外す: 属性を見る検証（`data-confirmed` 以外の札）が壊れるので不採用。

## 帰結

- 契約 0.30.0（`scheduleTab.requiredOutcome`・`candidateDate.requirement` に追記、追補29）。
  `.feature`・`allowedPurposes`・`formControlExemptTestIds`・`verifiesScenarios` は無変更。
- 実装（別の起草・PR）: 日程タブの表示切替、L4 の DSL（見える札は1枚、他の札は DOM に属性つきで残る）。
