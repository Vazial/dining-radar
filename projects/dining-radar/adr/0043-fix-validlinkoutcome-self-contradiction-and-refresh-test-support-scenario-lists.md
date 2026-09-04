---
id: 0043
scope: project/dining-radar
status: 提案中
date: 2026-09-04
approved_by: null
supersedes: []
superseded_by: null
relates_to: [P-06, P-08, ADR-0013, ADR-0036, ADR-0037, ADR-0040, ADR-0041, ADR-0042]
---

# ADR-0043: `validLinkOutcome`の自己矛盾を修正し、test-support契約のシナリオ一覧を最新化する

> **承認者向けサマリ**: developerが`gathering-scheduling-browser-interface.yaml` v0.5の実装中に、
> 契約自身の自己矛盾を1件発見し、FR-028の流儀（解消せず報告）でそのまま報告した。
> `browserEntry.participantAnswer.validLinkOutcome`（2026-08-30起草、`gathering-schedule-
> question`を無条件に必須としていた）と、`scheduleQuestion.presenceRule`（2026-09-04追補、
> `ADR-0042`。`ParticipantView.decision`が非nullなら不在と規定）が、確定後の状態について
> 文字どおり矛盾していた——これはadr/0042起草時にarchitectが見落としていた、古い記述との整合
> 確認漏れである。本ADRはこれを修正する。あわせて、tester報告の軽微な文書陳腐化（test-support
> 契約のシナリオ一覧がTDR-GTH-26〜36を反映していなかった）も同時に直す。人間裁定を経ない、
> architect自身の技術的な整合性是正であるため、`meta/adr/0064`の作法に従い
> `status: 提案中`・`approved_by: null`とする。
>
> **修正方針**: developerの実装判断（より新しく具体的な`presenceRule`を正とし、確定後は設問を
> 出さない）を追認する——`Final.dc.html`B-3自体がこの読みを裏づけている。`validLinkOutcome`の
> 文面を、有効なリンクについて無条件に成り立つことだけ（ヘッダーの存在・エラー面の不在）に狭め、
> 局面・`decision`に依存する要素の生死は、それぞれの`presenceRule`だけに委ねる——同じ条件を
> 2箇所に書くと、今回のように片方だけ更新されて食い違う再発を招くための設計判断である。

## 文脈

### 1. 矛盾の内容

`gathering-scheduling-browser-interface.yaml`の`browserEntry.participantAnswer.
validLinkOutcome`は、2026-08-30の起草時点から一貫して次のとおりだった。

```yaml
validLinkOutcome:
  present: [gathering-participant-header, gathering-schedule-question]
  absent: [gathering-participant-link-error]
```

これは「有効なリンクを開けば、`gathering-schedule-question`が常に存在する」ことを無条件に
要求する記述である。一方、`ADR-0042`（2026-09-04）が`participantAnswer.scheduleQuestion`へ
追補した`presenceRule`は次のとおりだった。

> Absent once `ParticipantView.decision` is non-null.

確定後（`decision`が非null）の状態で、両者は文字どおり矛盾する——`validLinkOutcome`に従えば
`gathering-schedule-question`は存在しなければならないのに、`scheduleQuestion.presenceRule`に
従えば存在してはならない。

### 2. 発見の経緯

developerが`ADR-0042`の契約を実装する中でこの矛盾に気づき、FR-028の流儀（解消せず報告）で
そのまま報告した。developer自身は「より新しく・より具体的な`presenceRule`を正」として実装を
進めた（確定後は設問を出さない）——これは`Final.dc.html`B-3の描写（決定後は
per-candidate-date/per-shopの内訳を再掲しない）と整合する妥当な読みである。ただし契約の文面を
直すのはarchitectの領分であるため、本ADRで正式に修正する。

この矛盾は`ADR-0042`起草時のarchitect自身の見落としである——新しい`presenceRule`を追加した際、
`browserEntry`の古い記述との整合を確認していなかった。

## 決定

### 決定1. `validLinkOutcome`を無条件に成り立つことだけに狭める

`validLinkOutcome`を次のとおりに改める。

```yaml
validLinkOutcome:
  present: [gathering-participant-header]
  absent: [gathering-participant-link-error]
```

`gathering-schedule-question`（局面・`decision`に依存する要素）は`present`リストから除いた。
どの局面依存要素が代わりに存在するか（`decision`が null なら`gathering-schedule-question`、
非null なら`gathering-participant-decision`、投票開始後かつ`decision`が null なら
`gathering-shop-vote-question`も追加で存在する）は、それぞれの要素自身の`presenceRule`
（`scheduleQuestion.presenceRule`・`shopVoteQuestion.presenceRule`・
`finalizedView.presenceRule`）だけが定める——`validLinkOutcome`側では二度と重複して記述しない。

### 決定2. 条件を2箇所に書かない、という設計原則を明記する

今回の矛盾は、同じ条件（「`gathering-schedule-question`はいつ存在するか」）を`validLinkOutcome`
と`scheduleQuestion.presenceRule`の2箇所に書き、一方だけを更新したことで生まれた。契約本文へ、
`validLinkOutcome`は「有効なリンクについて無条件に成り立つ最小限のこと」だけを記述し、局面・
`decision`に依存する生死はその要素自身の`presenceRule`に一元化する、という設計原則を明記した
——将来同種の追補が入っても、同じ条件を2箇所で保守する必要が無いようにするためである。

### 決定3. test-support契約のシナリオ一覧を最新化する（tester報告、軽微）

`test-support-api.yaml`の`resetGatheringSchedulingAcceptanceState`・
`setCandidateProposalAcceptanceState`・`resetCandidateProposalAcceptanceState`の
`x-acceptance-scenarios`が、`ADR-0040`〜`ADR-0042`で追加したTDR-GTH-26〜36を反映していな
かった。これらのシナリオはいずれも新しいseamを要さず（`ADR-0037`決定1・`ADR-0040`決定1の
「公開境界経由で組み立てる」方針をそのまま踏襲している）、機能的な変更は無い——一覧を最新化し、
`info.description`のシナリオ範囲表記も揃えた。TDR-GTH-26/27（5件選定・その日に開いている店
だけが選べること）は`GATHERING_OPEN_SHOP_WEEKDAY_MATCH`が定めるのと同じ母集団・同じ
`previewOpenShopsForCandidateDate`配線を経由するため、`setCandidateProposalAcceptanceState`/
`resetCandidateProposalAcceptanceState`の一覧にも追加した。

## 検討した代替案

- **`scheduleQuestion.presenceRule`を古い`validLinkOutcome`に合わせて撤回する（確定後も設問を
  出す）**: 却下。`Final.dc.html`B-3自体が、決定後は per-candidate-date の内訳を再掲しない
  設計を明示しており、developerの実装判断（新しい`presenceRule`を正とする）と一致する。撤回は
  承認済みの画面設計と矛盾する。
- **`validLinkOutcome`に条件分岐を書き込み、局面ごとの完全な一覧を維持する**: 却下（決定2）。
  `scheduleQuestion`・`shopVoteQuestion`・`finalizedView.decision`のいずれも既に自分自身の
  `presenceRule`を持っており、同じ情報を`validLinkOutcome`側にも書くと、今回とまったく同じ
  「片方だけ更新されて食い違う」再発の芽を残すことになる。

## 帰結

- `contracts/gathering-scheduling-browser-interface.yaml`（更新、`contractVersion`
  0.5→0.5.1、ステータス: 承認待ち）: `validLinkOutcome`を無条件に成り立つ要素だけに狭め、
  `scheduleQuestion.presenceRule`へ「ここが唯一の典拠である」旨を明記した。
- `contracts/test-support-api.yaml`（更新、`version` 1.5.0→1.5.1、ステータス: 承認待ち）:
  `x-acceptance-scenarios`の3箇所を最新化し、`info.description`のシナリオ範囲表記を
  「TDR-GTH-01 through TDR-GTH-36」へ揃えた。機能的な変更は無い。
- `gathering-scheduling-api.yaml`・`gathering-scheduling.feature`・`product-brief.md`は
  本ADRでは変更しない——本ADRは既存契約の文面の自己矛盾是正と文書最新化にとどまる。
- `ARCHITECTURE.md`・`design.md`は変更しない。

## 未決事項（次工程・人間への申し送り）

1. **本ADRは人間のチャット裁定を経ていない**（`meta/adr/0064`書式に従い`status: 提案中`・
   `approved_by: null`とした）。修正方針そのものに異論があれば、人間のレビューを経て
   `承認済み`へ改める。
2. `ADR-0042`が残した未決事項（「店を絞りなおす」「5件を差し替える」の区別、母集団が多い日の
   5件選定）は本ADRの範囲外であり、引き続き未決のままである。
